"""第 6 关参考实现：混合检索（向量 + 关键词）。"""

import json
import math
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "stage3_harness"))
import gateway

DB = os.path.join(os.path.dirname(__file__), "policy.db")


def _cosine(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb + 1e-9)


def hybrid_search(query: str, top_k: int = 3, alpha: float = 0.7) -> list[dict]:
    """混合检索：alpha*向量相似度 + (1-alpha)*关键词命中。"""
    conn = sqlite3.connect(DB)
    rows = conn.execute("SELECT policy,version,effective,article,text,embedding FROM chunks").fetchall()
    conn.close()

    qvec = gateway.call_model("embed", texts=[query])[0]

    scored = []
    for policy, ver, eff, art, text, emb in rows:
        vec_score = _cosine(qvec, json.loads(emb))
        # 关键词命中：query 中的字/词在 text 里出现的比例（简易实现）
        kw = [t for t in set(query) if not t.isspace()]
        kw_score = sum(1 for c in kw if c in text) / (len(kw) + 1e-9)
        score = alpha * vec_score + (1 - alpha) * kw_score
        scored.append({"policy": policy, "version": ver, "effective": eff,
                       "article": art, "text": text, "score": score})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def search_policy(query: str) -> str:
    """检索采购制度知识库，返回最相关的条款（含制度名与条号），供回答时引用出处。query:要查询的制度问题"""
    hits = hybrid_search(query)
    return "\n\n".join(f'【《{h["policy"]}》{h["article"]}（{h["effective"]}生效）】\n{h["text"]}'
                       for h in hits)


if __name__ == "__main__":
    for q in ["单一来源超过多少钱要专家论证", "失信被执行人能不能准入", "预算300万用什么采购方式"]:
        print(f"\n=== {q} ===")
        print(search_policy(q))
