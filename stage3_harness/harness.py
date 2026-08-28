"""第 3 关参考实现：mini harness（工具注册器 + 护栏 + tracing）。

配合 gateway.py 使用。业务里注册工具只需 @tool 装饰一个带 docstring 的函数。
"""

import inspect
import json
import os
import time

import gateway

# 全局工具注册表：name -> {"fn":..., "schema":...}
TOOLS: dict[str, dict] = {}

_PY2JSON = {str: "string", int: "integer", float: "number", bool: "boolean"}


def tool(fn):
    """装饰器：读函数签名与类型注解，自动生成 JSON Schema 并注册。"""
    sig = inspect.signature(fn)
    props, required = {}, []
    for name, p in sig.parameters.items():
        jtype = _PY2JSON.get(p.annotation, "string")
        props[name] = {"type": jtype}
        if p.default is inspect.Parameter.empty:
            required.append(name)
    schema = {
        "type": "function",
        "function": {
            "name": fn.__name__,
            "description": (fn.__doc__ or "").strip(),
            "parameters": {"type": "object", "properties": props, "required": required},
        },
    }
    TOOLS[fn.__name__] = {"fn": fn, "schema": schema}
    return fn


def _trace_path() -> str:
    d = os.path.join(os.path.dirname(__file__), "traces")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, time.strftime("%Y%m%d_%H%M%S") + ".jsonl")


def run_agent(question: str, system: str, task_type: str = "chat",
              max_steps: int = 15, confirm=None, verbose: bool = True) -> str:
    """带护栏和 tracing 的 agent 循环。
    confirm(name, args)->bool 可选：危险工具执行前的人工确认回调。
    """
    messages = [{"role": "system", "content": system + " /no_think"},
                {"role": "user", "content": question}]
    schemas = [t["schema"] for t in TOOLS.values()]
    trace = _trace_path()

    def rec(obj):
        with open(trace, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    for step in range(1, max_steps + 1):
        msg = gateway.call_model(task_type, messages=messages, tools=schemas)
        if not msg.tool_calls:
            rec({"step": step, "type": "final", "content": (msg.content or "")[:500]})
            return (msg.content or "").strip()

        messages.append(msg.model_dump())
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            t0 = time.time()
            if verbose:
                print(f"  [第{step}步] {name}({args})")

            if name not in TOOLS:
                result = f"未注册的工具: {name}"
            elif confirm and not confirm(name, args):
                result = "用户拒绝了该操作"
            else:
                try:
                    result = TOOLS[name]["fn"](**args)
                except Exception as e:  # noqa: BLE001  异常自愈：回填错误让模型自我修正
                    result = f"工具执行出错: {e}"
            rec({"step": step, "type": "tool", "tool": name, "args": args,
                 "ms": int((time.time() - t0) * 1000), "preview": str(result)[:200]})
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(result)})

    return "（达到最大步数，未得出最终答案）"
