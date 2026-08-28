"""第 1 关：采购智能助手雏形（含三个改造练习）。

运行（交互）：
    uv run python stage1_chat/chat.py

运行（自检三个改造，非交互）：
    uv run python stage1_chat/chat.py --selftest

命令：
    /quit                  退出
    /system <新提示词>     热替换 system prompt
    /save [文件名]         保存对话历史为 JSON（默认 chat_history.json）
    /load [文件名]         从 JSON 恢复对话历史
"""

from __future__ import annotations

import json
import os
import sys
from openai import OpenAI

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
MODEL = os.environ.get("CHAT_MODEL", "qwen3:8b")

DEFAULT_SYSTEM = (
    "你是西高院的采购智能助手，服务采购人员的日常问答。"
    "回答简洁、专业，用中文。涉及制度或金额时，如果不确定就明确说明需要核实，不要编造条款。"
)

# 默认历史文件放在本关目录下
DEFAULT_HISTORY = os.path.join(os.path.dirname(__file__), "chat_history.json")


def estimate_tokens(messages: list[dict]) -> tuple[int, int]:
    """粗略估算：字符数，以及 字符数÷1.5 ≈ token 数。"""
    chars = sum(len(str(m.get("content") or "")) for m in messages)
    tokens = max(1, int(chars / 1.5))
    return chars, tokens


def set_system(messages: list[dict], new_prompt: str) -> None:
    """热替换 system：改第一条 system，没有则插到最前。"""
    if messages and messages[0].get("role") == "system":
        messages[0]["content"] = new_prompt
    else:
        messages.insert(0, {"role": "system", "content": new_prompt})


def save_history(messages: list[dict], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)


def load_history(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list) or not data:
        raise ValueError("历史文件格式不对，应为非空 messages 数组")
    return data


def ask(messages: list[dict], user_text: str, *, stream: bool = True) -> str:
    """发一轮用户消息，返回助手完整回答，并写回 messages。"""
    messages.append({"role": "user", "content": user_text})
    if stream:
        resp = client.chat.completions.create(
            model=MODEL, messages=messages, stream=True,
        )
        print("助手: ", end="", flush=True)
        parts: list[str] = []
        for chunk in resp:
            delta = chunk.choices[0].delta.content or ""
            print(delta, end="", flush=True)
            parts.append(delta)
        print("\n")
        reply = "".join(parts)
    else:
        resp = client.chat.completions.create(
            model=MODEL, messages=messages, stream=False,
        )
        reply = resp.choices[0].message.content or ""
        print(f"助手: {reply}\n")

    messages.append({"role": "assistant", "content": reply})
    chars, tokens = estimate_tokens(messages)
    print(f"  [用量估算] 当前历史约 {chars} 字符 / ~{tokens} tokens（字符÷1.5）\n")
    return reply


def main() -> None:
    messages: list[dict] = [{"role": "system", "content": DEFAULT_SYSTEM}]
    print(
        f"采购助手已连接 {MODEL}\n"
        "命令: /quit  /system <提示词>  /save [文件]  /load [文件]\n"
    )

    while True:
        user_input = input("你: ").strip()
        if not user_input:
            continue

        if user_input == "/quit":
            break

        if user_input.startswith("/system"):
            new_prompt = user_input[len("/system"):].strip()
            if not new_prompt:
                print("用法: /system 你的新提示词\n")
                continue
            set_system(messages, new_prompt)
            print(f"已切换 system prompt：{new_prompt[:80]}{'…' if len(new_prompt) > 80 else ''}\n")
            continue

        if user_input.startswith("/save"):
            parts = user_input.split(maxsplit=1)
            path = parts[1].strip() if len(parts) > 1 else DEFAULT_HISTORY
            if not os.path.isabs(path):
                path = os.path.join(os.path.dirname(__file__), path)
            save_history(messages, path)
            print(f"已保存 {len(messages)} 条消息 → {path}\n")
            continue

        if user_input.startswith("/load"):
            parts = user_input.split(maxsplit=1)
            path = parts[1].strip() if len(parts) > 1 else DEFAULT_HISTORY
            if not os.path.isabs(path):
                path = os.path.join(os.path.dirname(__file__), path)
            try:
                messages = load_history(path)
            except Exception as e:  # noqa: BLE001
                print(f"加载失败: {e}\n")
                continue
            print(f"已加载 {len(messages)} 条消息 ← {path}\n")
            chars, tokens = estimate_tokens(messages)
            print(f"  [用量估算] 当前历史约 {chars} 字符 / ~{tokens} tokens\n")
            continue

        ask(messages, user_input, stream=True)


def selftest() -> None:
    """非交互验证三个改造。"""
    print("=" * 50)
    print("自检：三个改造练习")
    print("=" * 50)

    # —— 改造2：token 估算会随轮数增长 ——
    print("\n[改造2] token 估算随轮数增长")
    messages: list[dict] = [{"role": "system", "content": DEFAULT_SYSTEM + " /no_think"}]
    c1, t1 = estimate_tokens(messages)
    ask(messages, "用一句话介绍单一来源采购是什么。", stream=False)
    c2, t2 = estimate_tokens(messages)
    ask(messages, "再补充一句它和公开招标的区别。", stream=False)
    c3, t3 = estimate_tokens(messages)
    print(f"轮次增长: tokens {t1} → {t2} → {t3}")
    assert t3 > t2 > t1, "token 应随轮数增长"
    print("✅ 改造2 通过")

    # —— 改造1：/system 热替换 ——
    print("\n[改造1] /system 热替换人设")
    set_system(messages, "你是严格的采购合规审核员。回答必须简短、语气严厉，并提醒合规风险。/no_think")
    assert messages[0]["role"] == "system"
    assert "合规审核员" in messages[0]["content"]
    reply = ask(messages, "供应商报价低就可以指定他吗？", stream=False)
    print(f"（人设切换后回答预览）{reply[:120].replace(chr(10), ' ')}")
    print("✅ 改造1 通过（system 已替换；语气是否变严厉可人工看上面预览）")

    # —— 改造3：/save 与 /load ——
    print("\n[改造3] /save 与 /load")
    path = os.path.join(os.path.dirname(__file__), "_selftest_history.json")
    save_history(messages, path)
    assert os.path.exists(path), "保存文件应存在"
    restored = load_history(path)
    assert len(restored) == len(messages), "加载条数应一致"
    assert restored[0]["content"] == messages[0]["content"], "system 应一致"
    assert restored[-1]["role"] == "assistant", "最后一条应是助手回答"
    # 模拟“重启”：丢弃内存中的 messages，从文件恢复后再问一句指代上文的问题
    messages = restored
    reply2 = ask(messages, "刚才我问的指定供应商问题，你的结论一句话再说一遍。", stream=False)
    print(f"（恢复后仍能承接上文）{reply2[:120].replace(chr(10), ' ')}")
    os.remove(path)
    print("✅ 改造3 通过")

    print("\n" + "=" * 50)
    print("全部三个改造自检通过")
    print("=" * 50)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        main()
