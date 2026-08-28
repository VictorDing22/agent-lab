"""第 2 关参考实现：徒手 agent 循环 + 查供应商库。

这是"标准答案"，建议你先自己照 README 写，卡住了再对照本文件。
运行：
    uv run python stage2_tools/solution.py
或非交互自检（跑一个内置问题）：
    uv run python stage2_tools/solution.py --selftest
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import datastore
from openai import OpenAI

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
MODEL = os.environ.get("CHAT_MODEL", "qwen3:8b")

SUPPLIERS = datastore.load_suppliers()


# ---------- 三个工具函数（先能独立跑通，再接模型）----------

def search_suppliers(category: str = "", keyword: str = "") -> str:
    """按品类或关键词搜索供应商，返回匹配到的供应商名称与ID列表。"""
    hits = []
    for s in SUPPLIERS:
        if category and category not in "".join(s["category"]):
            continue
        if keyword and keyword not in s["name"]:
            continue
        hits.append(f'{s["id"]} {s["name"]}（品类：{"/".join(s["category"])}）')
    return "\n".join(hits) if hits else "没有匹配的供应商"


def list_suppliers() -> str:
    """列出供应商库里所有供应商的ID和名称。"""
    return "\n".join(f'{s["id"]} {s["name"]}' for s in SUPPLIERS)


def get_supplier_detail(supplier_id: str) -> str:
    """按供应商ID返回其详细信息：资质、注册资金、历史项目、风险状态等。"""
    for s in SUPPLIERS:
        if s["id"] == supplier_id:
            return json.dumps(s, ensure_ascii=False, indent=2)
    return f"未找到供应商 {supplier_id}"


# 工具注册表：名字 -> (函数, 给模型看的 JSON Schema)
TOOLS = {
    "search_suppliers": (search_suppliers, {
        "type": "function",
        "function": {
            "name": "search_suppliers",
            "description": "按品类或关键词搜索供应商，返回匹配到的供应商名称与ID列表",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "采购品类，如 高压开关、电线电缆"},
                    "keyword": {"type": "string", "description": "供应商名称关键词"},
                },
            },
        },
    }),
    "list_suppliers": (list_suppliers, {
        "type": "function",
        "function": {
            "name": "list_suppliers",
            "description": "列出供应商库里所有供应商的ID和名称",
            "parameters": {"type": "object", "properties": {}},
        },
    }),
    "get_supplier_detail": (get_supplier_detail, {
        "type": "function",
        "function": {
            "name": "get_supplier_detail",
            "description": "按供应商ID返回其详细信息：资质、注册资金、历史项目、风险状态等",
            "parameters": {
                "type": "object",
                "properties": {"supplier_id": {"type": "string", "description": "供应商编号，如 S001"}},
                "required": ["supplier_id"],
            },
        },
    }),
}

SYSTEM = (
    "你是西高院采购助手，可以调用工具查询供应商库。"
    "需要数据时调用工具，不要凭空编造供应商信息。回答用中文。/no_think"
)


def run_agent(question: str, max_steps: int = 8, verbose: bool = True) -> str:
    """agent 循环：模型想→调工具→看结果→再想，直到给出最终答案。"""
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": question}]
    tool_schemas = [schema for _, schema in TOOLS.values()]

    for step in range(1, max_steps + 1):
        resp = client.chat.completions.create(
            model=MODEL, messages=messages, tools=tool_schemas, temperature=0.2,
        )
        msg = resp.choices[0].message

        # 模型没有再请求工具 —— 说明它给出了最终答案
        if not msg.tool_calls:
            return (msg.content or "").strip()

        # 把模型这轮的 assistant 消息（含 tool_calls）放回历史
        messages.append(msg.model_dump())

        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            if verbose:
                print(f"  [第{step}步] 调用 {name}({args})")
            # 执行工具，异常也回填给模型让它自愈
            try:
                fn = TOOLS[name][0]
                result = fn(**args)
            except Exception as e:  # noqa: BLE001
                result = f"工具执行出错: {e}"
            if verbose:
                print(f"          结果: {result[:200].strip()}")
            messages.append({
                "role": "tool", "tool_call_id": tc.id, "content": result,
            })

    return "（达到最大步数，未得出最终答案）"


def main() -> None:
    if "--selftest" in sys.argv:
        q = "帮我找能供高压开关的供应商，并告诉我哪家历史合作评价最好"
        print(f"问题：{q}\n")
        print("回答：\n" + run_agent(q))
        return
    print("采购助手（可查供应商库，输入 /quit 退出）\n")
    while True:
        q = input("你: ").strip()
        if q == "/quit":
            break
        if not q:
            continue
        print("助手: " + run_agent(q) + "\n")


if __name__ == "__main__":
    main()
