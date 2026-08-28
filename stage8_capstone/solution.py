"""第 8 关参考实现：三大采购场景毕业项目。

组装前面所有零件，提供三个场景 + 权限过滤演示。
运行：
    uv run python stage8_capstone/solution.py 推荐 高压开关
    uv run python stage8_capstone/solution.py 单一来源 "某专利检测设备" 120
    uv run python stage8_capstone/solution.py 风险 远东电力工程有限公司
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "stage3_harness"))
sys.path.insert(0, os.path.join(ROOT, "stage6_rag"))
sys.path.insert(0, os.path.join(ROOT, "stage7_mcp"))
sys.path.insert(0, os.path.dirname(__file__))

from harness import run_agent, tool
from recommend import recommend


# ---------- 场景 B：供应商推荐（结构化评分，确定性，不依赖模型）----------
def scenario_recommend(category: str) -> str:
    out = [f"需求品类：{category}  推荐结果（已去重、已剔除高风险）：\n"]
    for i, r in enumerate(recommend(category), 1):
        out.append(f"{i}. {r['name']}（{r['id']}）综合分 {r['score']}")
        out += [f"     {reason}" for reason in r["reasons"]]
        out.append("")
    out.append("注：以上为可解释评分，供人工决策参考，不替代评审。")
    return "\n".join(out)


# ---------- 场景 A：单一来源审核（RAG + skill + 模型）----------
def scenario_single_source(target: str, amount_wan: float) -> str:
    from rag import search_policy as _sp
    tool(_sp)
    system = (
        "你是单一来源采购审核助手。请：1) 用 search_policy 查《单一来源采购管理办法》确认"
        f"金额({amount_wan}万元)对应的审批/论证要求；2) 按四要素(采购标的/唯一性论证/价格合理性/不可替代性)"
        "起草申请理由；3) 做合规提示（是否触发专家论证、是否含被禁止理由）；"
        "4) 注明制度出处。结尾提示需人工确认，不自动提交。回答用中文。"
    )
    q = f"采购标的：{target}，预算金额：{amount_wan}万元。请起草单一来源申请理由并做合规审核。"
    return run_agent(q, system=system, task_type="analyze")


# ---------- 场景 C：风险审核（复用第7关的征信工具）----------
def scenario_risk(name: str) -> str:
    import datastore
    from credit_tools import check_litigation_blacklist, query_credit

    suppliers = datastore.load_suppliers()

    @tool
    def find_supplier(name: str) -> str:
        """按名称查供应商，返回其ID和统一社会信用代码。name:供应商名称或关键词"""
        hits = [f'{s["id"]} {s["name"]} 信用代码={s["credit_code"]} 风险状态={s["risk_status"]}'
                for s in suppliers if name in s["name"]]
        return "\n".join(hits) if hits else "未找到"

    tool(query_credit)
    tool(check_litigation_blacklist)
    system = (
        "你是供应商风险审核助手。流程：find_supplier 拿信用代码 → query_credit 查征信 → "
        "check_litigation_blacklist 查涉诉名单 → 给风险分级(低/中/高)和处置建议。"
        "输出严格区分【外部数据事实】和【AI综合分析建议】，不得把AI推断当权威事实。回答用中文。"
    )
    return run_agent(f"帮我审一下{name}的风险", system=system, task_type="analyze")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    kind = args[0]
    if kind == "推荐":
        print(scenario_recommend(args[1]))
    elif kind == "单一来源":
        print(scenario_single_source(args[1], float(args[2])))
    elif kind == "风险":
        print(scenario_risk(args[1]))
    else:
        print("未知场景，可选：推荐 / 单一来源 / 风险")


if __name__ == "__main__":
    main()
