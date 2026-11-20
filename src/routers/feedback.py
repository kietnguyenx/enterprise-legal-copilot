"""
SecureDoc AI — Feedback & Document Export Router
Endpoints for Human-in-the-Loop (HITL) feedback and Word (.docx) report export.
"""
import time
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from src.auth import AuthUser, get_current_user, can_access_session
from src.database import db_save_feedback
from src.exporter import generate_audit_docx
from src.privacy import restore_pii
from src.services.session_service import SESSIONS, _lock, save_store, get_session_by_id

router = APIRouter(tags=["Feedback & Export"])


def _restore_pii_recursive(obj, vault: dict):
    """Đệ quy khôi phục token PII gốc trong toàn bộ cây kết quả thẩm định JSON."""
    if not vault:
        return obj
    if isinstance(obj, str):
        return restore_pii(obj, vault)
    if isinstance(obj, list):
        return [_restore_pii_recursive(item, vault) for item in obj]
    if isinstance(obj, dict):
        return {k: _restore_pii_recursive(v, vault) for k, v in obj.items()}
    return obj


class FeedbackRequest(BaseModel):
    session_id: str
    rating: str  # "like" | "dislike"
    message_index: int = -1
    user_correction: str = ""
    original_text: str = ""


@router.post("/api/feedback")
async def api_submit_feedback(req: FeedbackRequest):
    """Lưu phản hồi Human-in-the-Loop (HITL) phục vụ đánh giá và Fine-tuning DPO"""
    if not req.session_id or not req.session_id.strip():
        raise HTTPException(400, "session_id không được để trống")
    if req.rating not in ("like", "dislike"):
        raise HTTPException(400, "Rating phải là 'like' hoặc 'dislike'")

    with _lock:
        if req.session_id in SESSIONS:
            sess = SESSIONS[req.session_id]
            if "feedbacks" not in sess:
                sess["feedbacks"] = []
            sess["feedbacks"].append({
                "rating": req.rating,
                "message_index": req.message_index,
                "user_correction": req.user_correction,
                "timestamp": time.time(),
            })
            save_store()

    # Lưu bất đồng bộ vào Database
    await db_save_feedback(
        session_id=req.session_id,
        rating=req.rating,
        message_index=req.message_index,
        user_correction=req.user_correction,
        original_text=req.original_text,
    )
    return {"status": "success", "message": "Cảm ơn bạn đã phản hồi để hoàn thiện mô hình!"}


@router.get("/api/sessions/{sid}/export")
def export_docx(sid: str, restore_original_pii: bool = False, user: AuthUser = Depends(get_current_user)):
    """Xuất báo cáo thẩm định hợp đồng ra tệp Microsoft Word (.docx), hỗ trợ giải mã PII gốc có kiểm soát"""
    with _lock:
        s = get_session_by_id(sid)
        if not can_access_session(s, user):
            raise HTTPException(403, "Bạn không có quyền xuất báo cáo của phiên thẩm định này")
        if not s.get("audit"):
            raise HTTPException(400, "Phiên này chưa có kết quả thẩm định")
        audit_payload = s["audit"]
        if restore_original_pii and s.get("pii_vault"):
            audit_payload = _restore_pii_recursive(audit_payload, s["pii_vault"])
        content = generate_audit_docx(s.get("file_name") or "Tai_lieu", audit_payload)
        stem = (s.get("file_name") or "Tai_lieu").rsplit(".", 1)[0]

    suffix = "_GiaiMa_PII" if restore_original_pii else ""
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''Bao_Cao_Tham_Dinh_{quote(stem)}{suffix}.docx"},
    )
