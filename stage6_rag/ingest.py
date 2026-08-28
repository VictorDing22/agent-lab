"""第 6 关参考实现：制度文档 → 切分 → 向量化 → 入库（SQLite）。

按"第X条"切分，保留制度名/版本/生效日期/条号元数据。
运行：
    uv run python stage6_rag/ingest.py
"""

import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "stage3_harness"))

import datastore
import gateway

DB = os.path.join(os.path.dirname(__file__), "policy.db")


def parse_frontmatter(text: str) -> tuple[dict, str]:
    meta = {}
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return meta, text
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, m.group(2)


def split_by_article(body: str) -> list[tuple[str, str]]:
    """按"第X条"切分，返回 [(条号, 正文), ...]。"""
    parts = re.split(r"(第[一二三四五六七八九十百]+条)", body)
    chunks = []
    i = 1
    while i < len(parts):
        art = parts[i].strip()
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        chunks.append((art, f"{art} {content}"))
        i += 2
    return chunks


def main() -> None:
    conn = sqlite3.connect(DB)
    conn.execute("DROP TABLE IF EXISTS chunks")
    conn.execute("""CREATE TABLE chunks(
        id INTEGER PRIMARY KEY, policy TEXT, version TEXT, effective TEXT,
        article TEXT, text TEXT, embedding TEXT)""")

    rows = []
    for path in datastore.policy_files():
        with open(path, encoding="utf-8") as f:
            meta, body = parse_frontmatter(f.read())
        policy = meta.get("标题", os.path.basename(path))
        for art, text in split_by_article(body):
            rows.append((policy, meta.get("制度版本", ""), meta.get("生效日期", ""), art, text))

    print(f"共切出 {len(rows)} 个条款块，正在向量化...")
    texts = [r[4] for r in rows]
    embeddings = gateway.call_model("embed", texts=texts)

    import json
    for (policy, ver, eff, art, text), emb in zip(rows, embeddings):
        conn.execute("INSERT INTO chunks(policy,version,effective,article,text,embedding) VALUES(?,?,?,?,?,?)",
                     (policy, ver, eff, art, text, json.dumps(emb)))
    conn.commit()
    conn.close()
    print(f"入库完成 → {DB}")
    print("抽样检查前 3 块：")
    for policy, ver, eff, art, text in rows[:3]:
        print(f"  [{policy} {art}] {text[:50]}...")


if __name__ == "__main__":
    main()
