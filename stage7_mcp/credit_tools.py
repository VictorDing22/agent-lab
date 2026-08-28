"""第 7 关：征信/涉诉查询的底层函数。

这些函数既被 server.py（MCP 方式）复用，也可被 solution.py 直接注册（本地方式），
方便你对比"本地工具"和"MCP 工具"两种接入。
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import datastore

_CREDIT = datastore.load_credit()
_BLACKLIST = datastore.load_blacklist()


def query_credit(credit_code: str) -> str:
    """按统一社会信用代码查询企业征信：工商状态、法律纠纷、行政处罚、经营异常、失信信息、股权冻结、舆情。credit_code:统一社会信用代码"""
    data = _CREDIT.get(credit_code)
    if not data:
        return f"征信库中未找到 {credit_code}（外部数据暂不可用，不应据此判定为低风险）"
    return json.dumps(data, ensure_ascii=False, indent=2)


def check_litigation_blacklist(name_or_code: str) -> str:
    """查询企业是否命中中国西电涉诉风险客户名单。name_or_code:企业名称或统一社会信用代码"""
    hit = any(name_or_code == item or item in name_or_code or name_or_code in item
              for item in _BLACKLIST)
    return "命中涉诉风险客户名单" if hit else "未命中涉诉风险客户名单"
