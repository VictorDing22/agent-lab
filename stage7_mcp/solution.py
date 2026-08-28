"""第 7 关参考实现：供应商风险智能审核。

本文件用"本地直接注册"方式接入征信工具（credit_tools），便于快速跑通与自检；
真正的 MCP 接入见 server.py + README 的 client 部分。两种方式对模型完全透明。
运行：
    uv run python stage7_mcp/solution.py --selftest
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "stage3_harness"))
sys.path.insert(0, os.path.dirname(__file__))

import datastore
from credit_tools import check_litigation_blacklist, query_credit
from harness import run_agent, tool

SUPPLIERS = datastore.load_suppliers()


@tool
def find_supplier(name: str) -> str:
    """按名称查供应商，返回其ID和统一社会信用代码。name:供应商名称或关键词"""
    hits = [f'{s["id"]} {s["name"]} 信用代码={s["credit_code"]} 风险状态={s["risk_status"]}'
            for s in SUPPLIERS if name in s["name"]]
    return "\n".join(hits) if hits else "未找到"


tool(query_credit)
tool(check_litigation_blacklist)

SYSTEM = (
    "你是西高院供应商风险审核助手。审核流程：先用 find_supplier 拿到信用代码，"
    "再用 query_credit 查征信、check_litigation_blacklist 查涉诉名单，最后给出风险分级(低/中/高)和处置建议。"
    "输出必须严格区分两部分：\n"
    "【外部数据事实】逐条列出命中的客观事实（注明来源）\n"
    "【AI综合分析建议】你的分级判断和处置建议\n"
    "不得把AI推断当作权威事实。回答用中文。"
)


def main() -> None:
    if "--selftest" in sys.argv:
        for q in ["帮我审一下远东电力工程有限公司的风险", "帮我审一下中原电气集团有限公司的风险"]:
            print(f"\n{'='*50}\n问题：{q}\n")
            print(run_agent(q, system=SYSTEM, task_type="analyze", verbose=True))
        return
    print("供应商风险审核助手（输入 /quit 退出）\n")
    while True:
        q = input("你: ").strip()
        if q == "/quit":
            break
        if q:
            print(run_agent(q, system=SYSTEM, task_type="analyze") + "\n")


if __name__ == "__main__":
    main()
