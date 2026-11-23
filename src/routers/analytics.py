"""
SecureDoc AI — Analytics & Observability Router
Endpoints for system health, telemetry tracing, cache metrics, and available models.
"""
import os
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.auth import AuthUser, get_current_user, require_admin
from src.database import check_db_health, db_upsert_user, db_get_user_by_email
from src.email_validator import validate_email_address
from src.legal_kb import get_rag_engine
from src.llm import check_ollama_status
from src.cache import get_semantic_cache
from src.telemetry import get_telemetry
from src.config import MODELS
from src.routers.audit import get_guest_remaining_uses, GUEST_FREE_LIMIT

router = APIRouter(tags=["Analytics & Observability"])


class EmailValidateRequest(BaseModel):
    email: str


@router.post("/api/auth/validate-email")
def api_validate_email(req: EmailValidateRequest):
    """Kiểm tra chuẩn tài khoản Google / Email doanh nghiệp thật trước khi gửi mã xác nhận"""
    return validate_email_address(req.email, check_dns=True)


@router.get("/api/auth/config")
def api_auth_config():
    """Trả về cấu hình công khai Supabase (nếu có SUPABASE_ANON_KEY để gửi email xác thực thật)"""
    return {
        "supabase_url": os.getenv("SUPABASE_URL", "https://iodflivbxuklkupfphsu.supabase.co").strip(),
        "supabase_anon_key": os.getenv("SUPABASE_ANON_KEY", "").strip(),
        "real_email_verification_enabled": bool(os.getenv("SUPABASE_ANON_KEY", "").strip()),
    }


class ProfileSyncRequest(BaseModel):
    email: str
    name: str


@router.post("/api/auth/sync-profile")
async def api_sync_profile(req: ProfileSyncRequest):
    """Lưu tên hiển thị thật của người dùng vào Database để đồng bộ xuyên trình duyệt / InPrivate"""
    email = (req.email or "").strip().lower()
    name = (req.name or "").strip()
    if email and name:
        await db_upsert_user(email=email, username=name, overwrite_name=True)
    return {"status": "ok"}


@router.get("/api/auth/me")
async def get_auth_me(request: Request, user: AuthUser = Depends(get_current_user)):
    """Xác thực & đồng bộ hồ sơ người dùng hiện tại từ Supabase JWT / Database"""
    resolved_name = user.name
    if user.is_authenticated:
        db_user = await db_get_user_by_email(user.email)
        if db_user and db_user.get("username"):
            # Ưu tiên tên thật đã đăng ký trong Database nếu client chỉ suy diễn từ tiền tố email
            email_prefix = user.email.split("@")[0].lower()
            if user.name.lower().replace(" ", "") == email_prefix:
                resolved_name = db_user["username"]
        await db_upsert_user(email=user.email, username=resolved_name, role=user.role)
    return {
        "id": user.id,
        "email": user.email,
        "name": resolved_name,
        "role": user.role,
        "is_authenticated": user.is_authenticated,
        "guest_remaining_uses": None if user.is_authenticated else get_guest_remaining_uses(request),
        "guest_limit": GUEST_FREE_LIMIT,
    }


@router.get("/api/health")
async def health_check():
    """Kiểm tra tình trạng vận hành hệ thống (System Health Check)"""
    db_health = await check_db_health()
    rag_engine = get_rag_engine()
    ollama_ok = check_ollama_status()
    cache_stats = get_semantic_cache().get_stats()
    telemetry_summary = get_telemetry().get_summary()

    return {
        "status": "online",
        "service": "SecureDoc AI Enterprise",
        "database": db_health,
        "ollama_local": "available" if ollama_ok else "offline",
        "vector_rag_laws_count": len(rag_engine.documents),
        "semantic_cache": cache_stats,
        "telemetry": telemetry_summary,
    }


@router.get("/api/telemetry")
def api_get_telemetry():
    """Xem số liệu AI Observability: Token usage, Cost ($), p95 Latency"""
    return get_telemetry().get_summary()


@router.get("/api/cache/stats")
def api_get_cache_stats():
    """Xem thống kê tỷ lệ trúng Semantic Cache"""
    return get_semantic_cache().get_stats()


@router.post("/api/cache/clear")
def api_clear_cache(_admin: AuthUser = Depends(require_admin)):
    """Xóa bộ nhớ đệm ngữ nghĩa (Chỉ dành cho Admin)"""
    get_semantic_cache().clear()
    return {"status": "cleared"}


@router.get("/api/models")
def list_models():
    """Danh sách các model khả dụng (Cloud Gemini + Qwen 3.5)"""
    ollama_ready = check_ollama_status()
    result = []
    for m in MODELS:
        item = dict(m)
        item["available"] = ollama_ready if "ollama" in item["id"] else True
        result.append(item)
    return result
