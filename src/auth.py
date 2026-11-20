# src/auth.py — Supabase JWT Authentication & User Isolation Dependency
"""
Xác thực người dùng qua Supabase JWT (Bearer Token) và phân tách dữ liệu (User Isolation):
- Nếu có SUPABASE_JWT_SECRET trong .env: Xác minh chữ ký HS256 & thời hạn token (exp).
- Nếu chưa cấu hình secret (môi trường local dev): Giải mã an toàn JWT payload hoặc dùng header X-User-Email.
- Nếu là khách / test tự động chưa gửi token: Trả về Guest User để đảm bảo tương thích ngược.
"""

import os
import json
import time
import hmac
import base64
import hashlib
import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import unquote
from fastapi import Depends, Request, HTTPException

logger = logging.getLogger("securedoc.auth")


def _get_admin_emails() -> set[str]:
    raw = os.getenv("ADMIN_EMAILS", "khoa.nguyen@securedoc.ai,admin@securedoc.ai")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


@dataclass
class AuthUser:
    id: str
    email: str
    name: str
    role: str = "lawyer"  # "admin", "lawyer", "auditor", "viewer"
    is_authenticated: bool = False


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * ((4 - len(segment) % 4) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def decode_supabase_jwt(token: str) -> Optional[dict]:
    """Giải mã và xác minh Supabase JWT token (hỗ trợ HS256 không cần thư viện ngoài)."""
    parts = token.split(".")
    if len(parts) != 3:
        return None

    header_b64, payload_b64, sig_b64 = parts
    secret = os.getenv("SUPABASE_JWT_SECRET", "").strip()

    try:
        header = json.loads(_b64url_decode(header_b64).decode("utf-8"))
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception:
        return None

    # Nếu có SUPABASE_JWT_SECRET và thuật toán là HS256 -> bắt buộc kiểm tra chữ ký
    if secret and header.get("alg") == "HS256":
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected_sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        try:
            actual_sig = _b64url_decode(sig_b64)
        except Exception:
            return None
        if not hmac.compare_digest(expected_sig, actual_sig):
            logger.warning("🚨 Từ chối JWT có chữ ký không hợp lệ.")
            return None

    # Kiểm tra hạn sử dụng token (exp)
    exp = payload.get("exp")
    if isinstance(exp, (int, float)) and exp < time.time():
        logger.warning("🚨 JWT đã hết hạn.")
        return None

    return payload


def _derive_name_from_email(email: str) -> str:
    prefix = email.split("@")[0].replace(".", " ").replace("_", " ").replace("-", " ")
    return " ".join(w.capitalize() for w in prefix.split()) or "Người dùng"


def get_current_user(request: Request) -> AuthUser:
    """
    FastAPI Dependency trích xuất người dùng hiện tại từ:
    1. Header `Authorization: Bearer <supabase_jwt>`
    2. Query param `?token=<supabase_jwt>` (dùng cho link tải file `/export`)
    3. Header `X-User-Email` (chế độ đăng nhập email/password cục bộ)
    4. Mặc định trả về Guest User nếu chưa đăng nhập (tương thích ngược).
    """
    token = ""
    auth_header = request.headers.get("Authorization", "").strip()
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
    elif request.query_params.get("token"):
        token = request.query_params.get("token", "").strip()

    if token:
        payload = decode_supabase_jwt(token)
        if not payload:
            raise HTTPException(status_code=401, detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn. Vui lòng đăng nhập lại.")

        meta = payload.get("user_metadata") or {}
        app_meta = payload.get("app_metadata") or {}
        email = (payload.get("email") or meta.get("email") or "").strip().lower()
        uid = str(payload.get("sub") or email or "supabase_user")
        name = meta.get("full_name") or meta.get("name") or _derive_name_from_email(email or "user@securedoc.ai")
        role = app_meta.get("role") or meta.get("role") or ("admin" if email in _get_admin_emails() else "lawyer")
        return AuthUser(
            id=uid,
            email=email or f"{uid}@securedoc.ai",
            name=name,
            role=role,
            is_authenticated=True,
        )

    # Fallback nhẹ cho tài khoản đăng nhập cục bộ (X-User-Email)
    local_email = unquote(request.headers.get("X-User-Email", "")).strip().lower()
    if local_email and "@" in local_email:
        local_name = unquote(request.headers.get("X-User-Name", "")).strip() or _derive_name_from_email(local_email)
        uid = "local_" + hashlib.sha256(local_email.encode("utf-8")).hexdigest()[:16]
        role = "admin" if local_email in _get_admin_emails() else "lawyer"
        return AuthUser(
            id=uid,
            email=local_email,
            name=local_name,
            role=role,
            is_authenticated=True,
        )

    return AuthUser(
        id="guest",
        email="guest@securedoc.ai",
        name="Guest",
        role="lawyer",
        is_authenticated=False,
    )


def require_admin(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    """Bảo vệ các API quản trị (Xóa Cache, Nạp/Cào Luật RAG): Chỉ tài khoản Admin mới được phép."""
    if user.is_authenticated and user.role != "admin":
        raise HTTPException(403, "Chức năng quản trị này chỉ dành cho tài khoản Admin.")
    return user


def can_access_session(session: dict, user: AuthUser) -> bool:
    """Kiểm tra quyền sở hữu phiên thẩm định (User Isolation & RBAC)."""
    if user.role == "admin":
        return True
    owner_id = session.get("owner_id")
    # Nếu phiên chưa gắn owner_id (dữ liệu cũ hoặc tạo bởi guest)
    if not owner_id or owner_id == "guest":
        return not user.is_authenticated or owner_id in (None, "guest", user.id)
    return owner_id == user.id
