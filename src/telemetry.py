# src/telemetry.py — AI Observability, Token & Latency Tracing
"""
Hệ thống giám sát chỉ số AI (AI Observability) cho SecureDoc AI:
- Đo lường Input Tokens, Output Tokens, ước tính chi phí USD ($).
- Theo dõi độ trễ chi tiết (p50, p95 Latency Tracing) cho từng bước trong pipeline.
- Cung cấp số liệu thời gian thực cho Dashboard / API telemetry.
"""

import time
import json
from pathlib import Path
from typing import Dict, Any, List

TELEMETRY_FILE = Path(__file__).parent.parent / "data" / ".telemetry_stats.json"

# Bảng giá chuẩn Google Gemini Cloud API (per 1,000,000 tokens)
GEMINI_PRICING = {
    "gemini-3.5-flash": {"input_per_m": 0.075, "output_per_m": 0.30},
    "gemini-3.8-flash": {"input_per_m": 0.10, "output_per_m": 0.40},
    "gemini-3.5-flash-lite": {"input_per_m": 0.0375, "output_per_m": 0.15},
    "ollama:qwen3.5": {"input_per_m": 0.0, "output_per_m": 0.0},  # Local Ollama = $0
    "qwen3.5:local": {"input_per_m": 0.0, "output_per_m": 0.0},
}


def estimate_tokens(text: str) -> int:
    """Ước lượng số token: Tiếng Việt ~2.2 ký tự/token, Tiếng Anh ~4 ký tự/token"""
    if not text:
        return 0
    # Ước tính bình quân ~2.8 ký tự / token cho văn bản song ngữ / pháp lý
    return max(1, int(len(text) / 2.8))


def calculate_cost(input_tokens: int, output_tokens: int, model_name: str = "gemini-3.5-flash") -> float:
    """Tính chi phí ước tính theo USD"""
    pricing = GEMINI_PRICING.get(model_name, GEMINI_PRICING["gemini-3.5-flash"])
    input_cost = (input_tokens / 1_000_000) * pricing["input_per_m"]
    output_cost = (output_tokens / 1_000_000) * pricing["output_per_m"]
    return round(input_cost + output_cost, 6)


class TelemetryTracker:
    def __init__(self, max_records: int = 1000):
        self.max_records = max_records
        self.records: List[Dict[str, Any]] = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost_usd = 0.0
        self.total_requests = 0
        self._load()

    def _load(self):
        if TELEMETRY_FILE.exists():
            try:
                data = json.loads(TELEMETRY_FILE.read_text(encoding="utf-8"))
                self.records = data.get("records", [])
                self.total_input_tokens = data.get("total_input_tokens", 0)
                self.total_output_tokens = data.get("total_output_tokens", 0)
                self.total_cost_usd = data.get("total_cost_usd", 0.0)
                self.total_requests = data.get("total_requests", 0)
            except Exception:
                pass

    def _save(self):
        try:
            TELEMETRY_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "total_input_tokens": self.total_input_tokens,
                "total_output_tokens": self.total_output_tokens,
                "total_cost_usd": round(self.total_cost_usd, 5),
                "total_requests": self.total_requests,
                "records": self.records[-self.max_records:],
            }
            TELEMETRY_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def record_request(
        self,
        endpoint: str,
        model_name: str,
        input_text: str,
        output_text: str,
        latency_breakdown: Dict[str, float],
        is_cache_hit: bool = False,
    ):
        """Ghi nhận một lượt gọi AI kèm chi phí và thời gian trễ"""
        in_tokens = estimate_tokens(input_text)
        out_tokens = estimate_tokens(output_text)
        cost = 0.0 if is_cache_hit else calculate_cost(in_tokens, out_tokens, model_name)

        total_latency_ms = sum(latency_breakdown.values())

        entry = {
            "endpoint": endpoint,
            "model": model_name,
            "input_tokens": in_tokens,
            "output_tokens": out_tokens,
            "total_tokens": in_tokens + out_tokens,
            "cost_usd": cost,
            "is_cache_hit": is_cache_hit,
            "latency_ms": round(total_latency_ms, 2),
            "breakdown_ms": {k: round(v, 2) for k, v in latency_breakdown.items()},
            "timestamp": time.time(),
        }

        self.records.append(entry)
        self.total_input_tokens += in_tokens
        self.total_output_tokens += out_tokens
        self.total_cost_usd += cost
        self.total_requests += 1

        if len(self.records) > self.max_records:
            self.records = self.records[-self.max_records:]

        self._save()
        return entry

    def get_summary(self) -> Dict[str, Any]:
        """Tổng hợp các chỉ số p50, p95 latency và chi phí"""
        latencies = sorted([r["latency_ms"] for r in self.records]) if self.records else [0.0]
        n = len(latencies)
        p50 = latencies[int(n * 0.50)] if n else 0.0
        p95 = latencies[min(int(n * 0.95), n - 1)] if n else 0.0

        return {
            "total_requests": self.total_requests,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "latency_p50_ms": round(p50, 1),
            "latency_p95_ms": round(p95, 1),
            "recent_requests_count": len(self.records),
        }


# Singleton instance
_telemetry_instance = TelemetryTracker()


def get_telemetry() -> TelemetryTracker:
    return _telemetry_instance
