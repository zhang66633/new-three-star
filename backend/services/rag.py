"""
知识库检索 v2：TF-IDF + DeepSeek Embedding 混合检索
====================================================
用于叙事引擎，根据当前场景检索相关素材注入prompt。

v2 升级：
- 混合检索：TF-IDF（关键词匹配）+ DeepSeek Embedding（语义相似度）
- Reciprocal Rank Fusion 融合排序
- 返回完整文本块（不再截断）
- 降级策略：embedding 不可用时自动退回纯 TF-IDF
"""
import os
import re
import json
import jieba
import pickle
import hashlib
import logging
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge")
MATERIALS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "materials")
INDEX_PATH = os.path.join(os.path.dirname(__file__), "..", "knowledge", "rag_index.pkl")
EMBEDDING_CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "knowledge", "embedding_cache.json")

# 停用词（简化版）
STOP_WORDS = set("的了是在我你他她它们这那有和就不人都一一个上也很到说要去你会着没看好自己什么")

# DeepSeek API 配置（从 config 导入，这里做安全兜底）
try:
    from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL
except ImportError:
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")


def tokenize(text: str) -> str:
    """jieba分词，去停用词"""
    words = jieba.cut(text)
    return " ".join(w for w in words if w.strip() and w not in STOP_WORDS and len(w) > 1)


def chunk_text(text: str, chunk_size: int = 300, overlap: int = 50) -> list[str]:
    """将长文本切成重叠片段"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - overlap
    return chunks


def load_all_materials() -> list[dict]:
    """加载所有素材并切片"""
    documents = []

    # 1. 世界观文档
    wv_dir = os.path.join(KNOWLEDGE_DIR, "worldviews")
    if os.path.exists(wv_dir):
        for fname in os.listdir(wv_dir):
            if fname.endswith(".md"):
                with open(os.path.join(wv_dir, fname), "r", encoding="utf-8") as f:
                    text = f.read()
                world_id = fname.replace("_full.md", "")
                for chunk in chunk_text(text, 400, 80):
                    documents.append({"text": chunk, "source": f"worldview/{world_id}", "type": "worldview"})

    # 2. 素材库
    for fname in ["新三国世界观素材库.md", "新三国天意理论与梗文化.md", "新三国台词合集.md"]:
        fpath = os.path.join(MATERIALS_DIR, fname)
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                text = f.read()
            for chunk in chunk_text(text, 350, 70):
                documents.append({"text": chunk, "source": f"materials/{fname}", "type": "reference"})

    # 3. OCR剧本（如果存在）
    script_path = os.path.join(MATERIALS_DIR, "script_ocr", "full_script.txt")
    if os.path.exists(script_path):
        with open(script_path, "r", encoding="utf-8") as f:
            text = f.read()
        # 按页分割
        pages = re.split(r"=== 第\d+页 ===", text)
        for i, page in enumerate(pages):
            if page.strip():
                for chunk in chunk_text(page.strip(), 300, 50):
                    documents.append({"text": chunk, "source": f"script/p{i+1}", "type": "script"})

    return documents


def build_index():
    """构建TF-IDF索引并保存"""
    print("Loading materials...")
    documents = load_all_materials()
    print(f"Loaded {len(documents)} chunks")

    # 分词
    print("Tokenizing...")
    tokenized = [tokenize(doc["text"]) for doc in documents]

    # TF-IDF
    print("Building TF-IDF...")
    vectorizer = TfidfVectorizer(max_features=10000)
    tfidf_matrix = vectorizer.fit_transform(tokenized)

    # 保存
    index_data = {
        "vectorizer": vectorizer,
        "tfidf_matrix": tfidf_matrix,
        "documents": documents,
    }
    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
    with open(INDEX_PATH, "wb") as f:
        pickle.dump(index_data, f)
    print(f"Index saved: {len(documents)} chunks, matrix shape {tfidf_matrix.shape}")
    return index_data


# ---------------------------------------------------------------------------
# TF-IDF 检索（v2：原 search 函数，保留为混合检索的组件）
# ---------------------------------------------------------------------------

def search_tfidf(query: str, top_k: int = 8, filter_type: str = None) -> list[dict]:
    """TF-IDF 关键词检索——擅长精确关键词匹配。"""
    if not os.path.exists(INDEX_PATH):
        # 索引缺失时惰性构建一次（自愈：新克隆无需手动跑 build_index）
        print("RAG index not found — building now...")
        build_index()
        if not os.path.exists(INDEX_PATH):
            return []

    with open(INDEX_PATH, "rb") as f:
        index_data = pickle.load(f)

    vectorizer = index_data["vectorizer"]
    tfidf_matrix = index_data["tfidf_matrix"]
    documents = index_data["documents"]

    query_tokenized = tokenize(query)
    query_vec = vectorizer.transform([query_tokenized])
    similarities = cosine_similarity(query_vec, tfidf_matrix).flatten()

    if filter_type:
        mask = np.array([doc["type"] == filter_type for doc in documents])
        similarities = similarities * mask

    top_indices = similarities.argsort()[-top_k:][::-1]
    results = []
    for idx in top_indices:
        if similarities[idx] > 0.03:
            results.append({
                "text": documents[idx]["text"],
                "source": documents[idx]["source"],
                "score": float(similarities[idx]),
                "doc_index": int(idx),
            })
    return results


# ---------------------------------------------------------------------------
# DeepSeek Embedding 语义检索（v2 新增）
# ---------------------------------------------------------------------------

# 内存缓存：避免重复调用 embedding API
_embedding_cache: dict[str, list[float]] = {}


def _load_embedding_cache():
    """从磁盘加载 embedding 缓存。"""
    global _embedding_cache
    if _embedding_cache:
        return
    if os.path.exists(EMBEDDING_CACHE_PATH):
        try:
            with open(EMBEDDING_CACHE_PATH, "r", encoding="utf-8") as f:
                _embedding_cache = json.load(f)
            logger.info(f"Loaded {len(_embedding_cache)} embedding cache entries")
        except Exception:
            _embedding_cache = {}


def _save_embedding_cache():
    """保存 embedding 缓存到磁盘。"""
    try:
        with open(EMBEDDING_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(_embedding_cache, f, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Failed to save embedding cache: {e}")


def _cache_key(text: str) -> str:
    """生成缓存键（文本哈希）。"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


async def get_embedding(text: str) -> list[float] | None:
    """
    调用 DeepSeek Embedding API 获取文本向量。
    带内存缓存 + 磁盘缓存，避免重复调用。
    """
    key = _cache_key(text)

    # 1. 内存缓存
    _load_embedding_cache()
    if key in _embedding_cache:
        return _embedding_cache[key]

    # 2. API 调用
    if not DEEPSEEK_API_KEY:
        return None

    try:
        import httpx
        url = f"{DEEPSEEK_BASE_URL}/embeddings"
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "deepseek-embedding",
            "input": text[:8000],  # DeepSeek embedding 最大输入长度
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                embedding = data["data"][0]["embedding"]
                # 缓存
                _embedding_cache[key] = embedding
                if len(_embedding_cache) % 50 == 0:
                    _save_embedding_cache()
                return embedding
            else:
                logger.warning(f"Embedding API error: {resp.status_code} {resp.text[:200]}")
                return None
    except Exception as e:
        logger.warning(f"Embedding API exception: {e}")
        return None


async def search_semantic(query: str, top_k: int = 8) -> list[dict]:
    """
    语义检索：用 DeepSeek Embedding 做余弦相似度匹配。
    擅长语义相近但关键词不同的内容。
    降级：API 不可用时返回空列表。
    """
    query_embedding = await get_embedding(query)
    if query_embedding is None:
        return []

    if not os.path.exists(INDEX_PATH):
        return []

    with open(INDEX_PATH, "rb") as f:
        index_data = pickle.load(f)

    documents = index_data["documents"]

    # 为所有文档块获取 embedding（带缓存）
    doc_embeddings = []
    valid_indices = []
    for i, doc in enumerate(documents):
        emb = await get_embedding(doc["text"][:200])  # 前200字足够语义匹配
        if emb is not None:
            doc_embeddings.append(emb)
            valid_indices.append(i)
        # 每20个块保存一次缓存
        if len(doc_embeddings) % 20 == 0:
            _save_embedding_cache()

    _save_embedding_cache()

    if not doc_embeddings:
        return []

    # 批量计算余弦相似度
    doc_matrix = np.array(doc_embeddings)
    query_vec = np.array(query_embedding).reshape(1, -1)
    similarities = cosine_similarity(query_vec, doc_matrix).flatten()

    top_k = min(top_k, len(similarities))
    top_local = similarities.argsort()[-top_k:][::-1]

    results = []
    for local_idx in top_local:
        global_idx = valid_indices[local_idx]
        if similarities[local_idx] > 0.5:  # embedding 相似度阈值较高
            results.append({
                "text": documents[global_idx]["text"],
                "source": documents[global_idx]["source"],
                "score": float(similarities[local_idx]),
                "doc_index": int(global_idx),
            })
    return results


# ---------------------------------------------------------------------------
# 混合检索（v2 新增）
# ---------------------------------------------------------------------------

def _reciprocal_rank_fusion(
    tfidf_results: list[dict],
    semantic_results: list[dict],
    k: int = 60,
    tfidf_weight: float = 0.6,
    semantic_weight: float = 0.4,
) -> list[dict]:
    """
    Reciprocal Rank Fusion：融合 TF-IDF 和语义检索的结果。
    TF-IDF 权重更高（0.6 vs 0.4），因为它更擅长精确关键词匹配，
    避免语义检索把不相关的文本"飘"进来。
    """
    scores = {}
    docs = {}

    # TF-IDF 排名贡献
    for rank, r in enumerate(tfidf_results, 1):
        key = r["doc_index"]
        scores[key] = scores.get(key, 0) + tfidf_weight / (k + rank)
        docs[key] = r

    # 语义检索排名贡献
    for rank, r in enumerate(semantic_results, 1):
        key = r["doc_index"]
        scores[key] = scores.get(key, 0) + semantic_weight / (k + rank)
        if key not in docs:
            docs[key] = r

    # 按融合分数排序
    sorted_keys = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
    fused = []
    for key in sorted_keys:
        r = docs[key].copy()
        r["score"] = scores[key]
        fused.append(r)

    return fused


async def search_hybrid(
    query: str,
    top_k: int = 5,
    filter_type: str = None,
    tfidf_weight: float = 0.6,
) -> list[dict]:
    """
    混合检索：TF-IDF + DeepSeek Embedding → RRF 融合。
    - TF-IDF 保证关键词精确命中
    - Embedding 补充语义相关内容
    - 降级：embedding 不可用时自动退回纯 TF-IDF
    """
    # 1. TF-IDF 检索（同步，永远可用）
    tfidf_results = search_tfidf(query, top_k=top_k * 2, filter_type=filter_type)

    # 2. 语义检索（异步，可能降级）
    semantic_results = await search_semantic(query, top_k=top_k * 2)

    # 3. 融合
    if semantic_results:
        fused = _reciprocal_rank_fusion(
            tfidf_results, semantic_results,
            tfidf_weight=tfidf_weight,
            semantic_weight=1.0 - tfidf_weight,
        )
        results = fused[:top_k]
        logger.debug(
            f"Hybrid search: TF-IDF={len(tfidf_results)}, "
            f"Semantic={len(semantic_results)}, Fused={len(results)}"
        )
    else:
        # 降级：纯 TF-IDF
        results = tfidf_results[:top_k]
        logger.debug(f"TF-IDF only (embedding unavailable): {len(results)} results")

    # 过滤太低分的
    results = [r for r in results if r["score"] > 0.01]
    return results


# ---------------------------------------------------------------------------
# 同步兼容接口（供 Director 的 distill_rag 使用）
# ---------------------------------------------------------------------------

def search(query: str, top_k: int = 5, filter_type: str = None) -> list[dict]:
    """
    同步检索接口（兼容旧代码）。
    内部调用 search_tfidf（同步可用），Director 如需语义检索请用 search_hybrid。
    """
    return search_tfidf(query, top_k, filter_type)


if __name__ == "__main__":
    build_index()

