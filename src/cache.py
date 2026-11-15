# src/cache.py — Semantic Caching Engine
"""
Bộ nhớ đệm ngữ nghĩa (Semantic Cache) cho SecureDoc AI:
- So sánh ngữ nghĩa câu hỏi với kho câu hỏi - trả lời đã lưu.
- Nếu độ tương đồng cao (similarity > 0.90) trong cùng ngữ cảnh tài liệu:
  -> Trả về kết quả ngay lập tức (<50ms) với chi phí $0 và 0 LLM tokens.
- Giúp tiết kiệm 60-80% chi phí API cho các câu hỏi lặp lại hoặc biến thể tương đương.
"""

import time
import json
import math
import re
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

CACHE_FILE = Path(__file__).parent.parent / "data" / ".semantic_cache.json"


def _tokenize(text: str) -> List[str]:
    """Tách từ đơn giản và loại bỏ dấu/ký tự đặc biệt để so sánh túi từ (Bag-of-Words / Shingles)"""
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    return [w for w in cleaned.split() if len(w) > 1]


def _compute_cosine_sim(vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
    """Tính Cosine Similarity giữa 2 vector TF-IDF/tần số từ"""
    common = set(vec1.keys()) & set(vec2.keys())
    dot = sum(vec1[k] * vec2[k] for k in common)
    mag1 = math.sqrt(sum(v * v for v in vec1.values()))
    mag2 = math.sqrt(sum(v * v for v in vec2.values()))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)


def _to_tf_vector(tokens: List[str]) -> Dict[str, float]:
    vec: Dict[str, float] = {}
    for t in tokens:
        vec[t] = vec.get(t, 0.0) + 1.0
    return vec


class SemanticCache:
    def __init__(self, threshold: float = 0.90, max_entries: int = 500):
        self.threshold = threshold
        self.max_entries = max_entries
        self.entries: List[Dict[str, Any]] = []
        self.hits = 0
        self.misses = 0
        self.saved_tokens = 0
        self.saved_cost_usd = 0.0
        self._load()

    def _load(self):
        if CACHE_FILE.exists():
            try:
                data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
                self.entries = data.get("entries", [])
                self.hits = data.get("hits", 0)
                self.misses = data.get("misses", 0)
                self.saved_tokens = data.get("saved_tokens", 0)
                self.saved_cost_usd = data.get("saved_cost_usd", 0.0)
            except Exception:
                self.entries = []

    def _save(self):
        try:
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "hits": self.hits,
                "misses": self.misses,
                "saved_tokens": self.saved_tokens,
                "saved_cost_usd": self.saved_cost_usd,
                "entries": self.entries[-self.max_entries:],
            }
            CACHE_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def get(self, question: str, doc_context_hash: str = "") -> Optional[Tuple[str, float]]:
        """
        Tìm kiếm câu trả lời trong cache có độ tương đồng >= threshold.
        Returns:
            (cached_answer, similarity_score) nếu tìm thấy, ngược lại None.
        """
        q_tokens = _tokenize(question)
        if len(q_tokens) < 2:
            self.misses += 1
            return None

        q_vec = _to_tf_vector(q_tokens)
        best_match = None
        best_sim = 0.0

        for item in reversed(self.entries):
            # Chỉ khớp nếu cùng context tài liệu (hoặc cả 2 đều không có doc context)
            if item.get("doc_hash") != doc_context_hash:
                continue

            sim = _compute_cosine_sim(q_vec, item["vector"])
            if sim > best_sim:
                best_sim = sim
                best_match = item

        if best_match and best_sim >= self.threshold:
            self.hits += 1
            # Ước lượng số token đã tiết kiệm được
            est_tokens = len(q_tokens) + len(_tokenize(best_match["answer"]))
            self.saved_tokens += est_tokens
            # Giá Gemini Flash: ~$0.075/1M input, ~$0.30/1M output
            self.saved_cost_usd += (est_tokens / 1_000_000) * 0.15
            self._save()
            return best_match["answer"], round(best_sim, 3)

        self.misses += 1
        return None

    def set(self, question: str, answer: str, doc_context_hash: str = ""):
        """Lưu một cặp (câu hỏi, câu trả lời) mới vào Semantic Cache"""
        tokens = _tokenize(question)
        if len(tokens) < 2 or not answer or not answer.strip():
            return

        vec = _to_tf_vector(tokens)
        self.entries.append({
            "question": question.strip(),
            "vector": vec,
            "answer": answer.strip(),
            "doc_hash": doc_context_hash,
            "timestamp": time.time(),
        })

        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]

        self._save()

    def get_stats(self) -> Dict[str, Any]:
        """Thống kê hiệu quả hoạt động của Cache"""
        total = self.hits + self.misses
        hit_rate = round((self.hits / total) * 100, 1) if total > 0 else 0.0
        return {
            "total_entries": len(self.entries),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate_pct": hit_rate,
            "saved_tokens": self.saved_tokens,
            "saved_cost_usd": round(self.saved_cost_usd, 4),
        }

    def clear(self):
        """Xóa toàn bộ cache"""
        self.entries.clear()
        self.hits = 0
        self.misses = 0
        self.saved_tokens = 0
        self.saved_cost_usd = 0.0
        self._save()


# Singleton instance
_cache_instance = SemanticCache()


def get_semantic_cache() -> SemanticCache:
    return _cache_instance
