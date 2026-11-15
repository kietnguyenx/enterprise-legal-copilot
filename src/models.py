# src/models.py — SQLAlchemy 2.0 Database Models
"""
Định nghĩa cấu trúc bảng (Schema Models) cho SecureDoc AI:
1. User: Phân quyền truy cập doanh nghiệp (RBAC).
2. Document: Quản lý siêu dữ liệu tệp tải lên và mã băm SHA-256.
3. AuditSession: Lưu trữ kết quả thẩm định phức hợp (JSONB / JSON Tree).
4. HITLFeedback: Lưu trữ đánh giá và hiệu đính của chuyên viên (Human-in-the-Loop).
"""

import time
from sqlalchemy import Column, Integer, String, Float, Text, Boolean, JSON, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(128), unique=True, nullable=False)
    role = Column(String(32), default="lawyer")  # "admin", "lawyer", "auditor", "viewer"
    is_active = Column(Boolean, default=True)
    created_at = Column(Float, default=time.time)

    documents = relationship("Document", back_populates="owner", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    file_name = Column(String(256), nullable=False)
    file_size_bytes = Column(Integer, default=0)
    sha256_hash = Column(String(64), index=True)
    content_snippet = Column(Text, nullable=True)
    pii_summary = Column(JSON, nullable=True)
    uploaded_at = Column(Float, default=time.time)

    owner = relationship("User", back_populates="documents")


class AuditSession(Base):
    __tablename__ = "audit_sessions"

    id = Column(String(32), primary_key=True, index=True)  # session id (e.g. 12-char hex)
    title = Column(String(256), nullable=False)
    file_name = Column(String(256), nullable=True)
    file_size = Column(String(32), nullable=True)
    risk_score = Column(Integer, default=0)
    risk_level = Column(String(32), default="LOW RISK")
    
    # Lưu trữ toàn bộ kết quả phân tích AI phân cấp dưới dạng JSON / JSONB
    audit_data = Column(JSON, nullable=True)
    pii_vault = Column(JSON, nullable=True)
    messages = Column(JSON, nullable=True)  # Toàn bộ lịch sử tin nhắn
    
    updated_at = Column(Float, default=time.time, index=True)
    created_at = Column(Float, default=time.time)

    feedbacks = relationship("HITLFeedback", back_populates="session", cascade="all, delete-orphan")


class HITLFeedback(Base):
    """Bảng lưu trữ phản hồi Human-in-the-Loop để xây dựng tập dữ liệu DPO / Fine-tuning"""
    __tablename__ = "hitl_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(32), ForeignKey("audit_sessions.id"), nullable=False, index=True)
    message_index = Column(Integer, default=-1)
    rating = Column(String(16), nullable=False)  # "like", "dislike"
    user_correction = Column(Text, nullable=True)  # Nội dung hiệu đính của chuyên viên
    ai_original_text = Column(Text, nullable=True)  # Nội dung câu trả lời gốc của AI
    created_at = Column(Float, default=time.time)

    session = relationship("AuditSession", back_populates="feedbacks")
