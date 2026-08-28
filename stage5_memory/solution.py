"""第 5 关参考实现：会话记忆与上下文管理。

- 短期：对话过长时自动压缩旧历史为摘要
- 长期：memory.md 跨会话保留用户身份/偏好，remember 工具主动写入
运行：
    uv run python stage5_memory/solution.py            # 交互
    uv run python stage5_memory/solution.py --selftest # 自检长期记忆
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "stage3_harness"))
import gateway

MEM_FILE = os.path.join(os.path.dirname(__file__), "memory.md")
MAX_CHARS = 8000


def load_memory() -> str:
    if os.path.exists(MEM_FILE):
        with open(MEM_FILE, encoding="utf-8") as f:
            return f.read().strip()
    return ""


def remember(fact: str) -> str:
    """把一条关于用户的重要事实长期记住。fact:要记住的事实"""
    with open(MEM_FILE, "a", encoding="utf-8") as f:
        f.write(f"- {fact}\n")
    return "已记住"


REMEMBER_SCHEMA = {
    "type": "function",
    "function": {
        "name": "remember",
        "description": "当用户告诉你其身份、所属单位、常用采购品类等重要信息时，调用本工具长期记住",
        "parameters": {"type": "object",
                       "properties": {"fact": {"type": "string", "description": "要记住的事实"}},
                       "required": ["fact"]},
    },
}


def _total_chars(messages) -> int:
    return sum(len(str(m.get("content") or "")) for m in messages)


def compress(messages: list) -> list:
    """把最早的 60% 历史压缩成一条摘要，保留 system 和最近对话。"""
    system = messages[0]
    body = messages[1:]
    cut = int(len(body) * 0.6)
    if cut < 2:
        return messages
    old, recent = body[:cut], body[cut:]
    convo = "\n".join(f'{m["role"]}: {m.get("content","")}' for m in old)
    summary = gateway.call_model("analyze", messages=[
        {"role": "user", "content": "把以下采购对话压缩成要点，保留关键事实、金额、结论和未完成事项：\n" + convo}
    ])
    return [system, {"role": "user", "content": "【早前对话摘要】" + (summary.content or "")}] + recent


def chat_once(messages: list) -> str:
    if _total_chars(messages) > MAX_CHARS:
        print("  （上下文超阈值，触发压缩）")
        messages[:] = compress(messages)

    msg = gateway.call_model("chat", messages=messages, tools=[REMEMBER_SCHEMA])
    if msg.tool_calls:
        messages.append(msg.model_dump())
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            # 只取 fact 字段，容忍小模型偶尔产出的多余/错误参数
            fact = args.get("fact") or next(iter(args.values()), "")
            if tc.function.name == "remember" and fact:
                result = remember(str(fact))
            else:
                result = f"工具调用参数无效: {args}"
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
        msg = gateway.call_model("chat", messages=messages)
    messages.append({"role": "assistant", "content": msg.content or ""})
    return (msg.content or "").strip()


def build_system() -> str:
    mem = load_memory()
    base = "你是西高院采购助手。回答用中文。/no_think"
    if mem:
        base += f"\n\n【已知的用户长期信息】\n{mem}"
    return base


def main() -> None:
    if "--selftest" in sys.argv:
        # 第一次会话：告知身份并写入长期记忆
        m1 = [{"role": "system", "content": build_system()},
              {"role": "user", "content": "我是设备部采购员老王，主要负责高压开关类采购，请记住"}]
        print("第一次会话 →", chat_once(m1))
        # 模拟重启：重新构建 system（会加载 memory.md）
        m2 = [{"role": "system", "content": build_system()},
              {"role": "user", "content": "我是谁？我平时负责什么采购？"}]
        print("重启后提问 →", chat_once(m2))
        return

    messages = [{"role": "system", "content": build_system()}]
    print("采购助手（带记忆，输入 /quit 退出）\n")
    while True:
        q = input("你: ").strip()
        if q == "/quit":
            break
        if q:
            messages.append({"role": "user", "content": q})
            print("助手: " + chat_once(messages) + "\n")


if __name__ == "__main__":
    main()
