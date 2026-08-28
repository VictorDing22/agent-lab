"""第 8 关参考实现：评测集批量跑分。

把 evals.jsonl 的问题喂给一个"综合助手"（RAG制度 + 征信风控），
自动判断 expect_contains 是否命中，输出得分表。
运行（需 Ollama + 已 ingest）：
    uv run python stage8_capstone/run_evals.py
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "stage3_harness"))
sys.path.insert(0, os.path.join(ROOT, "stage6_rag"))
sys.path.insert(0, os.path.join(ROOT, "stage7_mcp"))

import datastore
from harness import run_agent, tool
from rag import search_policy as _sp
from credit_tools import check_litigation_blacklist, query_credit

_suppliers = datastore.load_suppliers()


@tool
def find_supplier(name: str) -> str:
    """按名称查供应商，返回ID和统一社会信用代码。name:供应商名称"""
    hits = [f'{s["id"]} {s["name"]} 信用代码={s["credit_code"]}' for s in _suppliers if name in s["name"]]
    return "\n".join(hits) if hits else "未找到"


tool(_sp)
tool(query_credit)
tool(check_litigation_blacklist)

SYSTEM = (
    "你是西高院采购综合助手。制度问题用 search_policy 检索并注明条款出处；"
    "供应商风险问题用 find_supplier + query_credit + check_litigation_blacklist 判断。"
    "查不到的如实说没有，不要编造。回答用中文，尽量简洁。"
)


def main() -> None:
    path = os.path.join(os.path.dirname(__file__), "evals.jsonl")
    cases = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
    passed = 0
    print(f"共 {len(cases)} 个用例\n" + "=" * 60)
    for i, c in enumerate(cases, 1):
        ans = run_agent(c["q"], system=SYSTEM, task_type="analyze", verbose=False)
        # expect_contains 每一项可以是字符串（必须命中），
        # 也可以是列表（同义词组，命中其中任意一个即可）——更贴近真实语义评测。
        def _ok(item):
            if isinstance(item, list):
                return any(alt in ans for alt in item)
            return item in ans
        hit = all(_ok(kw) for kw in c["expect_contains"])
        passed += hit
        print(f"[{i}] {'✅' if hit else '❌'} ({c.get('scenario','')}) {c['q']}")
        if not hit:
            print(f"     期望包含 {c['expect_contains']}")
            print(f"     实际: {ans[:120].strip()}")
    print("=" * 60)
    print(f"通过 {passed}/{len(cases)} = {passed/len(cases)*100:.0f}%")


if __name__ == "__main__":
    main()
