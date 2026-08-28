"""第 8 关参考实现：供应商智能推荐（可解释评分）。

推荐主要靠结构化字段 + 规则，不是纯 LLM——这正是真项目的正确做法。
包含：按信用代码去重、高风险剔除、可解释加分/扣分。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import datastore


def dedup_suppliers(suppliers: list[dict]) -> list[dict]:
    """按统一社会信用代码去重（S001/S006 是同一家）。保留字段更全的一条。"""
    by_code: dict[str, dict] = {}
    for s in suppliers:
        code = s["credit_code"]
        if code not in by_code or len(str(s)) > len(str(by_code[code])):
            by_code[code] = s
    return list(by_code.values())


def score_supplier(s: dict, category: str) -> dict:
    """对单个供应商打分，返回分数和可解释的加分/扣分项。"""
    reasons = []
    score = 0

    if category and category in "".join(s["category"]):
        score += 30; reasons.append(f"+30 品类匹配（{category}）")
    else:
        reasons.append("+0 品类不完全匹配")

    projects = s.get("history_projects", [])
    if projects:
        good = sum(1 for p in projects if p.get("evaluation") in ("优", "良"))
        score += 10 * good; reasons.append(f"+{10*good} 历史合作{len(projects)}次，其中优良{good}次")
    else:
        reasons.append("+0 无历史合作记录")

    if s.get("background_check") == "完整":
        score += 15; reasons.append("+15 背调完整")
    else:
        score -= 10; reasons.append("-10 背调不完整")

    if s.get("qualification_expire", "") >= "2026-07-20":
        score += 10; reasons.append("+10 资质在有效期内")
    else:
        score -= 15; reasons.append("-15 资质已过期/临期")

    rs = s.get("risk_status")
    if rs == "正常":
        score += 10; reasons.append("+10 风险状态正常")
    elif rs == "关注":
        score -= 10; reasons.append("-10 风险状态：关注")

    return {"id": s["id"], "name": s["name"], "score": score, "reasons": reasons, "risk_status": rs}


def recommend(category: str, top_k: int = 3) -> list[dict]:
    suppliers = dedup_suppliers(datastore.load_suppliers())
    # 高风险直接剔除（依据《采购管理办法》第七条）
    candidates = [s for s in suppliers if s.get("risk_status") != "高风险"]
    scored = [score_supplier(s, category) for s in candidates]
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


if __name__ == "__main__":
    print("需求品类：高压开关\n")
    for i, r in enumerate(recommend("高压开关"), 1):
        print(f"{i}. {r['name']}（{r['id']}）  综合分 {r['score']}")
        for reason in r["reasons"]:
            print(f"     {reason}")
        print()
