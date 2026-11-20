# src/database.py — SQLAlchemy 2.0 Async Database Connection
"""
Quản lý kết nối cơ sở dữ liệu bất đồng bộ (Async Database Engine):
- Hỗ trợ cả PostgreSQL (chế độ Production / Cloud) và SQLite Async (chế độ Local / Test).
- Tự động fallback mượt mà nếu môi trường chưa cài PostgreSQL.
"""

import os
import logging
from pathlib import Path
from typing import AsyncGenerator, Optional, Dict, Any, List
from dotenv import load_dotenv

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, update, delete, text

from src.models import Base, User, Document, AuditSession, HITLFeedback

load_dotenv()
logger = logging.getLogger("securedoc.database")

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Lấy DATABASE_URL từ .env, nếu không có thì dùng SQLite Async mặc định
DEFAULT_SQLITE_URL = f"sqlite+aiosqlite:///{DATA_DIR / 'securedoc.db'}"
RAW_DB_URL = os.getenv("DATABASE_URL", "").strip()

if RAW_DB_URL:
    # Chuẩn hóa postgres:// hoặc postgresql:// thành postgresql+asyncpg://
    if RAW_DB_URL.startswith("postgres://"):
        DB_URL = RAW_DB_URL.replace("postgres://", "postgresql+asyncpg://", 1)
    elif RAW_DB_URL.startswith("postgresql://") and "+asyncpg" not in RAW_DB_URL:
        DB_URL = RAW_DB_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    else:
        DB_URL = RAW_DB_URL
else:
    DB_URL = DEFAULT_SQLITE_URL

engine = create_async_engine(
    DB_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db():
    """Khởi tạo bảng cơ sở dữ liệu khi khởi động máy chủ (có Failover thực sự sang SQLite khi Cloud DB lỗi)"""
    global engine, AsyncSessionLocal, DB_URL
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            try:
                await conn.execute(text("ALTER TABLE audit_sessions ADD COLUMN owner_id VARCHAR(128)"))
            except Exception:
                pass
        logger.info(f"✅ Cơ sở dữ liệu khởi tạo thành công: {DB_URL.split('@')[-1] if '@' in DB_URL else DB_URL}")
    except Exception as e:
        logger.error(f"❌ Lỗi khi khởi tạo cơ sở dữ liệu ({e}), thực hiện chuyển mạch dự phòng sang SQLite...")
        if DB_URL != DEFAULT_SQLITE_URL:
            DB_URL = DEFAULT_SQLITE_URL
            engine = create_async_engine(DB_URL, echo=False, future=True, pool_pre_ping=True)
            AsyncSessionLocal = async_sessionmaker(
                bind=engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                try:
                    await conn.execute(text("ALTER TABLE audit_sessions ADD COLUMN owner_id VARCHAR(128)"))
                except Exception:
                    pass
            logger.info("✅ Đã chuyển mạch dự phòng sang SQLite Async thành công!")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency cung cấp AsyncSession cho FastAPI routes"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ================= CÁC HÀM TIỆN ÍCH LƯU TRỮ VÀ TRUY VẤN NHANH =================

async def db_get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Lấy hồ sơ người dùng theo email từ bảng users"""
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.email == email.strip().lower()))
            u = result.scalar_one_or_none()
            if u:
                return {"id": u.id, "username": u.username, "email": u.email, "role": u.role}
            return None
    except Exception as e:
        logger.warning(f"Không thể truy vấn user từ DB ({e})")
        return None


async def db_upsert_user(email: str, username: str, role: str = "lawyer", overwrite_name: bool = False) -> bool:
    """Đồng bộ thông tin người dùng đã xác thực vào bảng users"""
    try:
        norm_email = email.strip().lower()[:128]
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.email == norm_email))
            existing = result.scalar_one_or_none()
            if existing:
                existing.role = role or existing.role
                if overwrite_name and username and username.strip():
                    existing.username = username.strip()[:64]
            else:
                db.add(User(username=(username or norm_email.split("@")[0]).strip()[:64], email=norm_email, role=role or "lawyer"))
            await db.commit()
            return True
    except Exception as e:
        logger.warning(f"Không thể đồng bộ user vào DB ({e})")
        return False


async def db_save_session(session_data: Dict[str, Any]) -> bool:
    """Lưu hoặc cập nhật thông tin phiên làm việc vào Database"""
    try:
        sid = session_data["id"]
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(AuditSession).where(AuditSession.id == sid))
            existing = result.scalar_one_or_none()

            if existing:
                existing.owner_id = session_data.get("owner_id", existing.owner_id)
                existing.title = session_data.get("title", existing.title)
                existing.file_name = session_data.get("file_name", existing.file_name)
                existing.file_size = session_data.get("file_size", existing.file_size)
                audit = session_data.get("audit") or {}
                existing.risk_score = audit.get("risk_score", existing.risk_score)
                existing.risk_level = audit.get("risk_level", existing.risk_level)
                existing.audit_data = audit
                existing.pii_vault = session_data.get("pii_vault", existing.pii_vault)
                existing.messages = session_data.get("messages", existing.messages)
                existing.updated_at = session_data.get("updated", existing.updated_at)
            else:
                audit = session_data.get("audit") or {}
                new_session = AuditSession(
                    id=sid,
                    owner_id=session_data.get("owner_id"),
                    title=session_data.get("title", "Phiên thẩm định"),
                    file_name=session_data.get("file_name"),
                    file_size=session_data.get("file_size"),
                    risk_score=audit.get("risk_score", 0),
                    risk_level=audit.get("risk_level", "LOW RISK"),
                    audit_data=audit,
                    pii_vault=session_data.get("pii_vault"),
                    messages=session_data.get("messages", []),
                    updated_at=session_data.get("updated", 0.0),
                )
                db.add(new_session)

            await db.commit()
            return True
    except Exception as e:
        logger.warning(f"Không thể lưu session vào DB ({e})")
        return False


async def db_save_feedback(session_id: str, rating: str, message_index: int = -1, user_correction: str = "", original_text: str = "") -> bool:
    """Lưu phản hồi Human-in-the-Loop (HITL) vào Database (kiểm tra session tồn tại tránh lỗi Foreign Key mồ côi)"""
    try:
        async with AsyncSessionLocal() as db:
            exists = await db.execute(select(AuditSession.id).where(AuditSession.id == session_id))
            if exists.scalar_one_or_none() is None:
                logger.info(f"Bỏ qua lưu HITL feedback vào DB vì session '{session_id}' chưa tồn tại trong bảng cha.")
                return False
            fb = HITLFeedback(
                session_id=session_id,
                message_index=message_index,
                rating=rating,
                user_correction=user_correction,
                ai_original_text=original_text,
            )
            db.add(fb)
            await db.commit()
            return True
    except Exception as e:
        logger.warning(f"Không thể lưu HITL feedback vào DB ({e})")
        return False


async def db_delete_sessions(session_ids: Optional[List[str]] = None) -> bool:
    """Xóa đồng bộ các phiên làm việc trong Database"""
    try:
        async with AsyncSessionLocal() as db:
            if session_ids is None:
                await db.execute(delete(HITLFeedback))
                await db.execute(delete(AuditSession))
            elif session_ids:
                await db.execute(delete(HITLFeedback).where(HITLFeedback.session_id.in_(session_ids)))
                await db.execute(delete(AuditSession).where(AuditSession.id.in_(session_ids)))
            await db.commit()
            return True
    except Exception as e:
        logger.warning(f"Không thể xóa session trong DB ({e})")
        return False


async def check_db_health() -> Dict[str, Any]:
    """Kiểm tra tình trạng sức khỏe kết nối cơ sở dữ liệu"""
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(select(1))
            return {"status": "healthy", "engine": DB_URL.split("://")[0]}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
