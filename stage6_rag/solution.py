"""第 6 关参考实现：制度问答 agent（RAG + 可追溯出处）。

先运行 ingest.py 建库，再运行本文件。
    uv run python stage6_rag/ingest.py
    uv run python stage6_rag/solution.py --selftest
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "stage3_harness"))
sys.path.insert(0, os.path.dirname(__file__))

from harness import run_agent, tool
from rag import search_policy as _search_policy

tool(_search_policy)  # 把检索函数注册为工具

SYSTEM = (
    "你是西高院采购制度助手。回答必须基于 search_policy 检索到的条款，"
    "并注明依据《制度名》第X条。若检索不到相关规定，如实说明没有查到，禁止编造条款。回答用中文。"
)

TESTS = [
    "单一来源采购超过多少钱需要专家论证？",
    "失信被执行人能不能准入？",
    "预算300万的设备应该用什么采购方式？",
    "采购能不能拆成小单避免招标？",
    "出差报销流程是什么？",
]


def main() -> None:
    if "--selftest" in sys.argv:
        for q in TESTS:
            print(f"\n{'='*50}\n问题：{q}\n")
            print("回答：" + run_agent(q, system=SYSTEM, verbose=False))
        return
    print("采购制度助手（RAG，输入 /quit 退出）\n")
    while True:
        q = input("你: ").strip()
        if q == "/quit":
            break
        if q:
            print("助手: " + run_agent(q, system=SYSTEM) + "\n")


if __name__ == "__main__":
    main()
