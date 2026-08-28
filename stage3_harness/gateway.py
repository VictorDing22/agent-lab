"""第 3 关参考实现：MaaS 模型网关。

所有模型调用的唯一入口。业务代码只准调 call_model，不准直接 new OpenAI。
这就是西高院方案里反复强调的"业务不直连模型，一律走网关"的微缩版。
"""

import json
import os
import time
from collections import deque

from openai import OpenAI

_client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

# 模型路由表：task_type -> (模型, 默认参数)
# 真项目里这里就是 chat 路由千问、analyze 路由 DeepSeek、embed 路由 Embedding 模型
# 模型名可用环境变量覆盖，方便用小模型快速验证：
#   CHAT_MODEL=qwen3:0.6b EMBED_MODEL=nomic-embed-text uv run ...
_CHAT = os.environ.get("CHAT_MODEL", "qwen3:8b")
_EMBED = os.environ.get("EMBED_MODEL", "bge-m3")
ROUTES = {
    "chat":    (_CHAT, {"temperature": 0.3}),
    "analyze": (_CHAT, {"temperature": 0.1}),   # 复杂分析：更低温度更稳
    "embed":   (_EMBED, {}),
}

_LOG = os.path.join(os.path.dirname(__file__), "gateway_log.jsonl")
_recent_calls: dict[str, deque] = {}   # 限流用：每个 task_type 最近调用时间
_RATE_LIMIT_PER_SEC = 5


def _rate_limit(task_type: str) -> None:
    now = time.time()
    dq = _recent_calls.setdefault(task_type, deque())
    while dq and now - dq[0] > 1.0:
        dq.popleft()
    if len(dq) >= _RATE_LIMIT_PER_SEC:
        sleep = 1.0 - (now - dq[0])
        time.sleep(max(sleep, 0))
    dq.append(time.time())


def _log(rec: dict) -> None:
    with open(_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def call_model(task_type: str, messages=None, texts=None, tools=None, retries: int = 2, **opts):
    """统一模型入口。
    task_type='chat'/'analyze' 走对话；task_type='embed' 传 texts=[...] 做向量化。
    统一处理路由、限流、重试、日志、用量统计。
    """
    if task_type not in ROUTES:
        raise ValueError(f"未知 task_type: {task_type}")
    model, defaults = ROUTES[task_type]
    params = {**defaults, **opts}
    _rate_limit(task_type)

    start = time.time()
    last_err = None
    for attempt in range(retries + 1):
        try:
            if task_type == "embed":
                resp = _client.embeddings.create(model=model, input=texts)
                out = [d.embedding for d in resp.data]
                usage = getattr(resp, "usage", None)
                tokens = getattr(usage, "total_tokens", 0) if usage else 0
                _log({"time": time.strftime("%H:%M:%S"), "task": task_type, "model": model,
                      "ms": int((time.time() - start) * 1000), "n": len(texts or []), "tokens": tokens})
                return out
            else:
                kwargs = {"model": model, "messages": messages, **params}
                if tools:
                    kwargs["tools"] = tools
                resp = _client.chat.completions.create(**kwargs)
                usage = resp.usage
                _log({"time": time.strftime("%H:%M:%S"), "task": task_type, "model": model,
                      "ms": int((time.time() - start) * 1000),
                      "tokens": getattr(usage, "total_tokens", 0) if usage else 0})
                return resp.choices[0].message
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(0.5 * (attempt + 1))
    _log({"time": time.strftime("%H:%M:%S"), "task": task_type, "model": model, "error": str(last_err)})
    raise RuntimeError(f"模型调用失败（已重试{retries}次）: {last_err}")
