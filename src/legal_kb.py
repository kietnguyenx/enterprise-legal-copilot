# src/legal_kb.py — Legal Vector RAG Engine for SecureDoc AI
import os
import json
import pickle
import hashlib
import logging
from pathlib import Path
import numpy as np
from dotenv import load_dotenv
from google import genai

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
LAWS_DIR = BASE_DIR / "data" / "laws"
CACHE_PATH = LAWS_DIR / ".vector_cache.pkl"
EMBEDDING_MODEL = "gemini-embedding-001"


def _compute_laws_hash(files: list[Path]) -> str:
    """Tính mã băm MD5 của toàn bộ tệp luật để phát hiện thay đổi nội dung."""
    hasher = hashlib.md5()
    for f in sorted(files, key=lambda x: str(x)):
        if f.name.startswith("."):
            continue
        try:
            hasher.update(f.read_bytes())
        except OSError:
            pass
    return hasher.hexdigest()


def _cosine_similarity(vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Tính Cosine Similarity giữa 1 vector truy vấn và ma trận các vector tài liệu."""
    vec_norm = np.linalg.norm(vec)
    mat_norms = np.linalg.norm(matrix, axis=1)
    # Tránh chia cho 0
    mat_norms[mat_norms == 0] = 1e-10
    if vec_norm == 0:
        return np.zeros(len(matrix))
    return np.dot(matrix, vec) / (mat_norms * vec_norm)


class LegalRAGEngine:
    def __init__(self, laws_dir: Path = LAWS_DIR):
        self.laws_dir = Path(laws_dir)
        self.laws_dir.mkdir(parents=True, exist_ok=True)
        self.documents: list[dict] = []
        self.embeddings: np.ndarray | None = None
        self._client: genai.Client | None = None
        self._ensure_loaded()

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        return self._client

    def _read_all_law_files(self) -> tuple[list[dict], list[Path]]:
        """Đọc và chuẩn hóa toàn bộ tài liệu luật từ thư mục data/laws/, tự động khử trùng lặp."""
        docs = []
        valid_files = []
        seen_keys = set()

        for file_path in self.laws_dir.glob("*"):
            if file_path.name.startswith(".") or file_path.is_dir():
                continue
            valid_files.append(file_path)
            try:
                if file_path.suffix.lower() == ".json":
                    data = json.loads(file_path.read_text(encoding="utf-8"))
                    if isinstance(data, list):
                        for item in data:
                            dedup_key = f"{item.get('law_name', '').strip()}_{item.get('article', '').strip()}".lower()
                            if dedup_key in seen_keys and dedup_key != "_":
                                continue
                            seen_keys.add(dedup_key)
                            doc_repr = (
                                f"[{item.get('law_name', 'Văn bản pháp luật')} - {item.get('article', 'Điều khoản')}: "
                                f"{item.get('title', '')}]\n{item.get('content', '')}"
                            )
                            docs.append({
                                "law_id": item.get("law_id", file_path.stem),
                                "law_name": item.get("law_name", "Văn bản pháp lý"),
                                "article": item.get("article", ""),
                                "title": item.get("title", ""),
                                "content": item.get("content", ""),
                                "category": item.get("category", "general"),
                                "full_text": doc_repr,
                                "source_file": file_path.name
                            })
                elif file_path.suffix.lower() in [".txt", ".md"]:
                    raw_text = file_path.read_text(encoding="utf-8")
                    paragraphs = [p.strip() for p in raw_text.split("\n\n") if len(p.strip()) > 30]
                    for idx, para in enumerate(paragraphs):
                        dedup_key = hashlib.md5(para.encode("utf-8")).hexdigest()
                        if dedup_key in seen_keys:
                            continue
                        seen_keys.add(dedup_key)
                        docs.append({
                            "law_id": f"{file_path.stem}_{idx+1}",
                            "law_name": file_path.stem.replace("_", " ").title(),
                            "article": f"Mục {idx+1}",
                            "title": para.split("\n")[0][:80],
                            "content": para,
                            "category": "general",
                            "full_text": para,
                            "source_file": file_path.name
                        })
            except Exception as e:
                logging.error(f"Lỗi khi nạp file luật {file_path.name}: {e}")

        return docs, valid_files

    def _build_embeddings(self, docs: list[dict]) -> np.ndarray:
        """Tạo vector embeddings theo lô (batch) từ mô hình Gemini."""
        if not docs:
            return np.empty((0, 3072))

        texts = [d["full_text"] for d in docs]
        all_vecs = []
        batch_size = 10

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            res = self.client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=batch
            )
            if hasattr(res, "embeddings") and res.embeddings:
                for emb in res.embeddings:
                    all_vecs.append(emb.values)
            elif hasattr(res, "embedding") and res.embedding:
                all_vecs.append(res.embedding.values)

        return np.array(all_vecs, dtype=np.float32)

    def _ensure_loaded(self):
        """Tải từ cache hoặc tạo mới index nếu có thay đổi trong thư mục luật."""
        docs, files = self._read_all_law_files()
        current_hash = _compute_laws_hash(files)

        if CACHE_PATH.exists():
            try:
                with open(CACHE_PATH, "rb") as f:
                    cache_data = pickle.load(f)
                if cache_data.get("hash") == current_hash and len(cache_data.get("docs", [])) == len(docs):
                    self.documents = cache_data["docs"]
                    self.embeddings = cache_data["embeddings"]
                    return
            except Exception as e:
                logging.warning(f"Cache vector không đọc được ({e}), tiến hành tái tạo...")

        # Tái tạo và lưu cache
        self.documents = docs
        if docs:
            self.embeddings = self._build_embeddings(docs)
        else:
            self.embeddings = np.empty((0, 3072))

        try:
            with open(CACHE_PATH, "wb") as f:
                pickle.dump({
                    "hash": current_hash,
                    "docs": self.documents,
                    "embeddings": self.embeddings
                }, f)
        except OSError as e:
            logging.warning(f"Không thể ghi vector cache: {e}")

    def refresh(self):
        """Buộc làm mới chỉ mục vector khi có tài liệu hoặc URL mới nạp vào."""
        if CACHE_PATH.exists():
            try:
                CACHE_PATH.unlink()
            except OSError:
                pass
        self._ensure_loaded()

    def _lexical_fallback_search(self, query: str, top_k: int = 3) -> list[dict]:
        """Fallback tìm kiếm từ khóa (BM25-lite) khi Embedding API ngoại tuyến, hết quota hoặc chạy trên CI."""
        import re
        q_tokens = {w for w in re.findall(r"\w+", query.lower()) if len(w) > 1}
        if not q_tokens:
            return []
        scored = []
        for doc in self.documents:
            corpus = f"{doc.get('law_name', '')} {doc.get('article', '')} {doc.get('title', '')} {doc.get('content', '')}".lower()
            doc_tokens = set(re.findall(r"\w+", corpus))
            overlap = len(q_tokens & doc_tokens)
            if overlap > 0:
                score = round(min(0.95, 0.45 + overlap / max(len(q_tokens), 4)), 3)
                d_copy = dict(doc)
                d_copy["relevance_score"] = score
                scored.append(d_copy)
        scored.sort(key=lambda x: x["relevance_score"], reverse=True)
        return scored[:top_k]

    def retrieve_relevant_laws(self, query: str, top_k: int = 3, min_score: float = 0.45) -> list[dict]:
        """Truy xuất các điều luật tương quan nhất dựa trên Cosine Similarity (kèm Lexical Fallback khi offline/CI)."""
        if not self.documents:
            return []

        clean_query = query.strip()
        if not clean_query:
            return []

        if self.embeddings is None or len(self.embeddings) == 0:
            return self._lexical_fallback_search(clean_query, top_k=top_k)

        # Rút gọn truy vấn nếu quá dài
        query_snippet = clean_query[:1000]
        try:
            res = self.client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=query_snippet
            )
            if hasattr(res, "embeddings") and res.embeddings:
                query_vec = np.array(res.embeddings[0].values, dtype=np.float32)
            elif hasattr(res, "embedding") and res.embedding:
                query_vec = np.array(res.embedding.values, dtype=np.float32)
            else:
                return self._lexical_fallback_search(clean_query, top_k=top_k)
        except Exception as e:
            logging.warning(f"Embedding API không khả dụng ({e}), chuyển sang Lexical Fallback Search...")
            return self._lexical_fallback_search(clean_query, top_k=top_k)

        scores = _cosine_similarity(query_vec, self.embeddings)
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            score = float(scores[idx])
            if score >= min_score:
                doc_copy = dict(self.documents[idx])
                doc_copy["relevance_score"] = round(score, 3)
                results.append(doc_copy)

        return results

    def format_laws_for_prompt(self, laws: list[dict]) -> str:
        """Định dạng các điều luật đã truy xuất thành chuỗi ngữ cảnh chuẩn cho Prompt."""
        if not laws:
            return "Không tìm thấy điều luật tương đồng trực tiếp trong cơ sở dữ liệu."

        parts = []
        for i, law in enumerate(laws, 1):
            parts.append(
                f"[CƠ SỞ PHÁP LÝ #{i}] {law.get('law_name')} - {law.get('article')}: {law.get('title')}\n"
                f"Độ tương đồng ngữ nghĩa: {law.get('relevance_score', 0)}\n"
                f"Nội dung quy định: \"{law.get('content')}\""
            )
        return "\n\n".join(parts)


# Singleton instance để các module dùng chung
_rag_engine: LegalRAGEngine | None = None


def get_rag_engine() -> LegalRAGEngine:
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = LegalRAGEngine()
    return _rag_engine
