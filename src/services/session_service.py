"""
SecureDoc AI — Session Management Service
Handles in-memory caching and persistent JSON serialization of audit sessions.
"""
import json
import threading
from pathlib import Path
from fastapi import HTTPException
from src.config import STORE_PATH

_lock = threading.Lock()


def _load_store() -> dict:
    if STORE_PATH.exists():
        try:
            return json.loads(STORE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {}


SESSIONS: dict = _load_store()


def save_store():
    """Lưu an toàn các phiên làm việc ra tệp JSON"""
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(SESSIONS, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STORE_PATH)


def get_subtitle(s: dict) -> str:
    """Tạo dòng phụ đề hiển thị tóm tắt cho phiên"""
    audit = s.get("audit")
    if audit:
        n_high = (audit.get("risk_counts") or {}).get("high", 0)
        return f"Audit Risk · {n_high} rủi ro cao, điểm {audit.get('risk_score', 0)}/100"
    for m in reversed(s.get("messages", [])):
        if m.get("role") == "assistant" and m.get("content"):
            return m["content"].replace("\n", " ")[:80]
    return "Cuộc trò chuyện mới"


def format_public_session(s: dict, full: bool = False) -> dict:
    """Định dạng dữ liệu phiên trả về cho giao diện web"""
    data = {
        "id": s["id"],
        "title": s["title"],
        "subtitle": get_subtitle(s),
        "file_name": s.get("file_name"),
        "updated": s.get("updated", 0),
    }
    if full:
        data.update({
            "file_size": s.get("file_size"),
            "audit": s.get("audit"),
            "pii": s.get("pii"),
            "messages": s.get("messages", []),
        })
    return data


def get_session_by_id(sid: str) -> dict:
    """Lấy phiên làm việc theo ID hoặc báo lỗi 404"""
    s = SESSIONS.get(sid)
    if not s:
        raise HTTPException(404, "Không tìm thấy phiên làm việc")
    return s
