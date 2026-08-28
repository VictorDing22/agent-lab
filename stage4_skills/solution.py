"""第 4 关参考实现：技能包机制（渐进式披露）。

启动时只把技能的 name+description 注入 system prompt；
模型判断需要时才调 load_skill 加载全文。
运行：
    uv run python stage4_skills/solution.py --selftest
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "stage3_harness"))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)) + "/stage6_rag")

import datastore
from harness import run_agent, tool

SKILLS_DIR = os.path.join(os.path.dirname(__file__), "skills")
SUPPLIERS = datastore.load_suppliers()


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, m.group(2)


def discover_skills() -> dict[str, dict]:
    skills = {}
    for name in os.listdir(SKILLS_DIR):
        path = os.path.join(SKILLS_DIR, name, "SKILL.md")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                meta, body = _parse_frontmatter(f.read())
            skills[meta.get("name", name)] = {"desc": meta.get("description", ""), "body": body}
    return skills


SKILLS = discover_skills()


@tool
def load_skill(name: str) -> str:
    """加载指定技能的完整操作说明。name:技能名，见system prompt里列出的可用技能"""
    if name in SKILLS:
        return SKILLS[name]["body"]
    return f"没有名为 {name} 的技能。可用：{', '.join(SKILLS)}"


@tool
def get_supplier_detail(supplier_id: str) -> str:
    """按供应商ID返回详细信息。supplier_id:供应商编号如S001"""
    import json
    for s in SUPPLIERS:
        if s["id"] == supplier_id:
            return json.dumps(s, ensure_ascii=False, indent=2)
    return f"未找到供应商 {supplier_id}"


_skill_list = "\n".join(f"- {n}: {v['desc']}" for n, v in SKILLS.items())
SYSTEM = (
    "你是西高院采购助手。你有以下技能可用，判断与当前问题相关时，"
    f"先调用 load_skill 加载该技能的完整步骤再作答：\n{_skill_list}\n回答用中文。"
)


def main() -> None:
    if "--selftest" in sys.argv:
        for q in ["帮我写一份120万元采购某专利检测设备的单一来源申请理由",
                  "帮我看看 S008 的背调够不够入库标准"]:
            print(f"\n{'='*50}\n问题：{q}\n")
            print("回答：" + run_agent(q, system=SYSTEM, verbose=True))
        return
    print("采购助手（带技能，输入 /quit 退出）\n")
    while True:
        q = input("你: ").strip()
        if q == "/quit":
            break
        if q:
            print("助手: " + run_agent(q, system=SYSTEM) + "\n")


if __name__ == "__main__":
    main()
