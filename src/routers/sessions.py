"""
SecureDoc AI — Sessions Management Router
Endpoints for listing, retrieving, and deleting audit sessions.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from src.auth import AuthUser, get_current_user, can_access_session
from src.database import db_delete_sessions
from src.services.session_service import SESSIONS, _lock, save_store, format_public_session, get_session_by_id

router = APIRouter(tags=["Sessions Management"])


class DeleteRequest(BaseModel):
    ids: list[str] | None = None


@router.get("/api/sessions")
def list_sessions(user: AuthUser = Depends(get_current_user)):
    """Lấy danh sách tóm tắt các phiên làm việc thuộc quyền sở hữu của người dùng hiện tại"""
    with _lock:
        visible = [s for s in SESSIONS.values() if can_access_session(s, user)]
        items = sorted(visible, key=lambda s: s.get("updated", 0), reverse=True)
        return [format_public_session(s) for s in items]


@router.get("/api/sessions/{sid}")
def get_session(sid: str, user: AuthUser = Depends(get_current_user)):
    """Lấy chi tiết một phiên làm việc bao gồm audit, pii và tin nhắn (kiểm tra quyền truy cập)"""
    with _lock:
        session = get_session_by_id(sid)
        if not can_access_session(session, user):
            raise HTTPException(403, "Bạn không có quyền truy cập phiên thẩm định này")
        return format_public_session(session, full=True)


@router.post("/api/sessions/delete")
async def delete_sessions(req: DeleteRequest, user: AuthUser = Depends(get_current_user)):
    """Xóa danh sách các phiên làm việc thuộc quyền sở hữu của user (đồng bộ bộ nhớ đệm & Database)"""
    with _lock:
        if req.ids is None:
            targets = [sid for sid, s in SESSIONS.items() if can_access_session(s, user)]
        else:
            targets = [sid for sid in req.ids if sid in SESSIONS and can_access_session(SESSIONS[sid], user)]
        for sid in targets:
            SESSIONS.pop(sid, None)
        save_store()
    await db_delete_sessions(targets)
    return {"deleted": len(targets)}
