"""采购数据读取（各关共用）。

数据加载不是本练手营的学习重点，所以抽出来共用，让每关的 solution 专注于
当关要学的 agent 概念。学习时你可以只看每关 solution.py 里"新概念"的部分。
"""

import json
import os

BASE = os.path.join(os.path.dirname(__file__), "采购数据")


def load_suppliers() -> list[dict]:
    with open(os.path.join(BASE, "供应商.json"), encoding="utf-8") as f:
        return json.load(f)


def load_credit() -> dict:
    with open(os.path.join(BASE, "外部数据", "征信.json"), encoding="utf-8") as f:
        return json.load(f)


def load_blacklist() -> list[str]:
    path = os.path.join(BASE, "外部数据", "涉诉风险客户名单.txt")
    items = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                items.append(line)
    return items


def policy_files() -> list[str]:
    d = os.path.join(BASE, "制度")
    return [os.path.join(d, n) for n in os.listdir(d) if n.endswith(".md")]
