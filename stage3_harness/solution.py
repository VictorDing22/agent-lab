"""第 3 关参考实现：把供应商工具接入 harness + 模型网关。

运行：
    uv run python stage3_harness/solution.py --selftest
    uv run python stage3_harness/solution.py            # 交互模式
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.dirname(__file__))

import datastore
from harness import run_agent, tool

SUPPLIERS = datastore.load_suppliers()

SYSTEM = "你是西高院采购助手，可调用工具查询供应商库。需要数据就调工具，不要编造。回答用中文。"


@tool
def search_suppliers(category: str = "", keyword: str = "") -> str:
    """按品类或关键词搜索供应商，返回匹配到的供应商名称与ID列表。category:采购品类如高压开关；keyword:名称关键词"""
    hits = [f'{s["id"]} {s["name"]}（{"/".join(s["category"])}）'
            for s in SUPPLIERS
            if (not category or category in "".join(s["category"]))
            and (not keyword or keyword in s["name"])]
    return "\n".join(hits) if hits else "没有匹配的供应商"


@tool
def get_supplier_detail(supplier_id: str) -> str:
    """按供应商ID返回详细信息：资质、注册资金、历史项目、风险状态等。supplier_id:供应商编号如S001"""
    for s in SUPPLIERS:
        if s["id"] == supplier_id:
            return json.dumps(s, ensure_ascii=False, indent=2)
    return f"未找到供应商 {supplier_id}"


def confirm_cli(name: str, args: dict) -> bool:
    ans = input(f"  ⚠ 确认执行 {name}({args})? [y/N] ").strip().lower()
    return ans == "y"


def main() -> None:
    if "--selftest" in sys.argv:
        q = "S005 这家供应商靠谱吗？帮我看看它的风险状态和历史评价"
        print(f"问题：{q}\n")
        print("回答：\n" + run_agent(q, system=SYSTEM))
        return
    print("采购助手 v2（harness + 模型网关，输入 /quit 退出）\n")
    while True:
        q = input("你: ").strip()
        if q == "/quit":
            break
        if q:
            print("助手: " + run_agent(q, system=SYSTEM) + "\n")


if __name__ == "__main__":
    main()
