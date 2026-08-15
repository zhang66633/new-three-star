# -*- coding: utf-8 -*-
"""rag.py —— 记忆向量检索（补回版）

依据 docs/引擎设计规范.md §4：TF-IDF + RRF 融合的记忆检索。
实现纯 Python 的字符 n-gram TF-IDF 向量化 + 余弦相似度排序，并用 RRF
（Reciprocal Rank Fusion）融合「向量相似度排名」与「关键词+时效排名」取 top-k。

注：设计原文的「DeepSeek Embedding」因 DeepSeek 仅提供 chat 模型、无 embedding
接口，此处以「字符 n-gram TF-IDF 向量」作为无需外部依赖的嵌入替代——对中文短文本
（LTM 120-150 字）而言，n-gram TF-IDF 已能稳定表达语义重叠。
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable


def _clean(text: str) -> str:
    """去标点/空白，保留中英文与数字（\\w 含 CJK）。"""
    return re.sub(r"[^\w]", "", text or "")


def _ngrams(text: str, min_n: int = 1, max_n: int = 3) -> Counter:
    """字符 n-gram（1~3 字滑窗）词频统计。"""
    text = _clean(text)
    grams: Counter = Counter()
    for n in range(min_n, max_n + 1):
        for i in range(len(text) - n + 1):
            grams[text[i:i + n]] += 1
    return grams


def _normalize(vec: dict[str, float]) -> dict[str, float]:
    """L2 归一化。"""
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {k: v / norm for k, v in vec.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    """余弦相似度（已归一化时等价于点积）。"""
    if not a or not b:
        return 0.0
    small, big = (a, b) if len(a) <= len(b) else (b, a)
    return sum(v * big.get(k, 0.0) for k, v in small.items())


def tfidf_rank(items: list[dict], query: str, top_k: int = 5) -> list[dict]:
    """TF-IDF 向量化 + 余弦相似度排序，返回相似度降序的 items。"""
    if not items:
        return []
    docs = [(it, _ngrams(str(it.get("text", "")))) for it in items]
    query_grams = _ngrams(query)
    df: Counter = Counter()
    for _, dg in docs:
        for g in dg:
            df[g] += 1
    n = max(1, len(docs))
    idf = {g: math.log((n + 1.0) / (c + 1.0)) + 1.0 for g, c in df.items()}

    def _vec(grams: Counter) -> dict[str, float]:
        total = max(1, sum(grams.values()))
        raw = {g: (c / total) * idf.get(g, 0.0) for g, c in grams.items()}
        return _normalize(raw)

    qv = _vec(query_grams)
    scored = [(it, _cosine(qv, _vec(dg))) for it, dg in docs]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [it for it, _ in scored[:top_k]]


def rrf_fuse(rankings: Iterable[list[dict]], k: int = 60) -> list[dict]:
    """RRF 融合多路排名（按 item id 聚合，得分降序）。"""
    scores: dict[str, float] = {}
    order: dict[str, dict] = {}
    for ranking in rankings:
        for rank, it in enumerate(ranking):
            key = str(it.get("id") or rank)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            order[key] = it
    return [order[key] for key, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)]


def _keyword_recency_rank(items: list[dict], query: str, top_k: int = 5) -> list[dict]:
    """关键词重叠（2-4 字滑窗）×1.5 + 时效衰减 ×0.5 的排名。"""
    q = re.sub(r"[\s，。、；：！？]+", "", query or "")
    keywords: set[str] = set()
    for wlen in (2, 3, 4):
        for i in range(len(q) - wlen + 1):
            w = q[i:i + wlen]
            if w.strip():
                keywords.add(w)
    if not keywords:
        return sorted(items, key=lambda m: m.get("ts", 0), reverse=True)[:top_k]
    max_ts = max((m.get("ts", 0) for m in items), default=1)

    def score(m: dict) -> float:
        text = str(m.get("text", ""))
        hits = sum(1 for kw in keywords if kw in text)
        recency = (m.get("ts", 0) or 0) / max(max_ts, 1)
        return hits * 1.5 + recency * 0.5

    scored = sorted(items, key=score, reverse=True)
    relevant = [m for m in scored if score(m) > 0]
    return (relevant or scored)[:top_k]


def retrieve_ltm(items: list[dict], query: str, top_k: int = 5) -> list[dict]:
    """LTM 检索：TF-IDF 向量排名 与 关键词+时效排名 经 RRF 融合取 top-k。"""
    if not items:
        return []
    vector_rank = tfidf_rank(items, query, top_k=top_k)
    keyword_rank = _keyword_recency_rank(items, query, top_k=top_k)
    fused = rrf_fuse([vector_rank, keyword_rank])
    return fused[:top_k] or items[:top_k]
