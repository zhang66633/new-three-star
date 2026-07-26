"""
轻量级知识库检索：jieba分词 + TF-IDF + 余弦相似度
用于叙事引擎，根据当前场景检索相关素材注入prompt
"""
import os
import re
import jieba
import pickle
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

KNOWLEDGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge")
MATERIALS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "materials")
INDEX_PATH = os.path.join(os.path.dirname(__file__), "..", "knowledge", "rag_index.pkl")

# 停用词（简化版）
STOP_WORDS = set("的了是在我你他她它们这那有和就不人都一一个上也很到说要去你会着没看好自己什么")


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


def search(query: str, top_k: int = 5, filter_type: str = None) -> list[dict]:
    """检索最相关的文本片段"""
    if not os.path.exists(INDEX_PATH):
        return []

    with open(INDEX_PATH, "rb") as f:
        index_data = pickle.load(f)

    vectorizer = index_data["vectorizer"]
    tfidf_matrix = index_data["tfidf_matrix"]
    documents = index_data["documents"]

    # 查询向量化
    query_tokenized = tokenize(query)
    query_vec = vectorizer.transform([query_tokenized])

    # 余弦相似度
    similarities = cosine_similarity(query_vec, tfidf_matrix).flatten()

    # 过滤
    if filter_type:
        mask = np.array([doc["type"] == filter_type for doc in documents])
        similarities = similarities * mask

    # Top-K
    top_indices = similarities.argsort()[-top_k:][::-1]
    results = []
    for idx in top_indices:
        if similarities[idx] > 0.05:  # 最低相关度阈值
            results.append({
                "text": documents[idx]["text"],
                "source": documents[idx]["source"],
                "score": float(similarities[idx]),
            })
    return results


if __name__ == "__main__":
    build_index()
