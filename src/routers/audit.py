"""
SecureDoc AI — Core Document Ingestion & Conversational Audit Router
Endpoints for uploading/auditing documents and streaming AI audit responses with SSE.
"""
import io
import json
import time
import uuid
import asyncio
import hashlib
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.auth import AuthUser, get_current_user, can_access_session
from src.config import MAX_UPLOAD_BYTES, resolve_model, format_human_size
from src.limiter import limiter
from src.ingestion import extract_text
from src.privacy import redact_pii_vault, redact_pii_report
from src.guardrails import check_input_guardrails
from src.cache import get_semantic_cache
from src.telemetry import get_telemetry
from src.database import db_save_session, db_upsert_user
from src.analyzer import audit_document, chat_followup_stream
from src.services.session_service import SESSIONS, _lock, save_store, format_public_session

router = APIRouter(tags=["Document Ingestion & Chat Audit"])


@router.post("/api/upload")
@limiter.limit("10/minute")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    model: str = Form(None),
    pii_guard: bool = Form(True),
    user: AuthUser = Depends(get_current_user),
):
    """Tiếp nhận, bóc tách và tự động thẩm định tài liệu hợp đồng (hỗ trợ PDF, DOCX, TXT, CSV, MD & Ảnh OCR)"""
    if user.is_authenticated:
        await db_upsert_user(email=user.email, username=user.name, role=user.role)
    data = file.file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File vượt quá 15 MB")

    buf = io.BytesIO(data)
    buf.name = file.filename or "tai_lieu"

    # 1. Bóc tách nội dung tài liệu
    t_ingest_start = time.time()
    try:
        raw_text = extract_text(buf)
    except ValueError as e:
        raise HTTPException(400, str(e))
    ingest_ms = (time.time() - t_ingest_start) * 1000

    # 2. Lớp khiên bảo mật Smart PII Token Vault
    t_pii_start = time.time()
    vault = {}
    if pii_guard:
        cleaned, pii, vault = redact_pii_vault(raw_text)
    else:
        cleaned, pii = raw_text, {}
    pii_ms = (time.time() - t_pii_start) * 1000

    # 3. Phân tích & Thẩm định rủi ro qua Hybrid LLM
    selected_model = resolve_model(model)
    t_llm_start = time.time()
    try:
        audit = audit_document(cleaned, model_name=selected_model)
    except Exception as e:
        raise HTTPException(502, f"AI không thẩm định được tài liệu: {e}")
    llm_ms = (time.time() - t_llm_start) * 1000

    # Ghi nhận Telemetry Observability
    get_telemetry().record_request(
        endpoint="/api/upload",
        model_name=selected_model,
        input_text=cleaned[:20000],
        output_text=json.dumps(audit, ensure_ascii=False),
        latency_breakdown={"ingest_ms": ingest_ms, "pii_ms": pii_ms, "llm_ms": llm_ms},
    )

    sid = uuid.uuid4().hex[:12]
    session = {
        "id": sid,
        "owner_id": user.id,
        "owner_email": user.email,
        "title": f"Thẩm định {buf.name.rsplit('.', 1)[0]}"[:60],
        "file_name": buf.name,
        "file_size": format_human_size(len(data)),
        "doc_context": cleaned,
        "audit": audit,
        "pii": pii,
        "pii_vault": vault,
        "messages": [{"role": "user", "type": "file", "file_name": buf.name}],
        "updated": time.time(),
    }
    with _lock:
        SESSIONS[sid] = session
        save_store()

    # Lưu vào Database
    await db_save_session(session)

    return format_public_session(session, full=True)


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str
    model: str | None = None
    pii_guard: bool = True


@router.post("/api/chat")
@limiter.limit("40/minute")
async def chat(request: Request, req: ChatRequest, user: AuthUser = Depends(get_current_user)):
    """Luồng hội thoại đối thoại pháp lý thời gian thực qua Server-Sent Events (SSE)"""
    text = req.message.strip()
    if not text:
        raise HTTPException(400, "Tin nhắn trống")
    if len(text) > 10000:
        raise HTTPException(400, "Tin nhắn vượt quá giới hạn tối đa 10.000 ký tự.")

    # 1. Input Guardrails: Chống Prompt Injection & Jailbreak Defense
    is_safe, guard_cat, guard_msg = check_input_guardrails(text)
    if not is_safe:
        def stream_guardrail():
            yield guard_msg
        return StreamingResponse(
            stream_guardrail(),
            media_type="text/plain; charset=utf-8",
            headers={"X-Guardrail-Blocked": "true", "X-Category": guard_cat},
        )

    text = guard_msg  # Prompt đã được chuẩn hóa

    # 2. Smart PII Guard
    pii_count = 0
    if req.pii_guard:
        text, counts = redact_pii_report(text)
        pii_count = sum(counts.values())

    selected_model = resolve_model(req.model)

    with _lock:
        if req.session_id and req.session_id in SESSIONS:
            session = SESSIONS[req.session_id]
            if not can_access_session(session, user):
                raise HTTPException(403, "Bạn không có quyền trò chuyện trong phiên thẩm định này")
        else:
            sid = uuid.uuid4().hex[:12]
            session = {
                "id": sid,
                "owner_id": user.id,
                "owner_email": user.email,
                "title": text[:48] + ("…" if len(text) > 48 else ""),
                "file_name": None,
                "doc_context": "",
                "audit": None,
                "pii": None,
                "messages": [],
                "updated": time.time(),
            }
            SESSIONS[sid] = session

        history = list(session["messages"])
        session["messages"].append({"role": "user", "type": "text", "content": text})
        session["updated"] = time.time()
        save_store()

        context = session.get("doc_context", "")
        if not context and session.get("audit"):
            context = json.dumps(session["audit"], ensure_ascii=False)

    # Băm toàn bộ nội dung tài liệu (SHA-256) tránh va chạm Cache giữa 2 hợp đồng cùng mẫu bìa
    doc_hash = hashlib.sha256(context.encode("utf-8")).hexdigest() if context else "no_doc"

    # 3. Semantic Caching Engine (Zero-Cost Sub-50ms Response)
    cached_result = get_semantic_cache().get(text, doc_context_hash=doc_hash)
    if cached_result:
        cached_answer, similarity = cached_result
        get_telemetry().record_request(
            endpoint="/api/chat",
            model_name=selected_model,
            input_text=text,
            output_text=cached_answer,
            latency_breakdown={"cache_lookup_ms": 15.0},
            is_cache_hit=True,
        )

        with _lock:
            session["messages"].append({"role": "assistant", "type": "text", "content": cached_answer})
            session["updated"] = time.time()
            save_store()

        def stream_cached():
            yield cached_answer

        return StreamingResponse(
            stream_cached(),
            media_type="text/plain; charset=utf-8",
            headers={
                "X-Session-Id": session["id"],
                "X-Cache-Hit": "true",
                "X-Cache-Similarity": str(similarity),
                "X-PII-Count": str(pii_count),
                "Cache-Control": "no-cache",
            },
        )

    # 4. LLM Streaming Response & Telemetry Tracking
    t_start = time.time()

    async def generate():
        parts = []
        stream_failed = False
        try:
            for chunk in chat_followup_stream(context, text, chat_history=history, model_name=selected_model):
                parts.append(chunk)
                yield chunk
        except Exception as exc:
            stream_failed = True
            yield f"\n⚠️ Đã xảy ra lỗi khi kết nối mô hình AI: {exc}"
        finally:
            full_reply = "".join(parts).strip()
            duration_ms = (time.time() - t_start) * 1000

            # Chống Cache Poisoning: Chỉ lưu cache khi stream thành công và có nội dung thực tế
            if not stream_failed and len(full_reply) >= 10:
                get_semantic_cache().set(text, full_reply, doc_context_hash=doc_hash)

            # Ghi nhận Telemetry Observability
            get_telemetry().record_request(
                endpoint="/api/chat",
                model_name=selected_model,
                input_text=text + " " + context[:2000],
                output_text=full_reply,
                latency_breakdown={"llm_stream_ms": duration_ms},
            )

            with _lock:
                if full_reply:
                    session["messages"].append({"role": "assistant", "type": "text", "content": full_reply})
                    session["updated"] = time.time()
                    save_store()
                session_snapshot = dict(session)

            # Đồng bộ lịch sử chat mới nhất lên Database (PostgreSQL / SQLite)
            await db_save_session(session_snapshot)

    return StreamingResponse(
        generate(),
        media_type="text/plain; charset=utf-8",
        headers={
            "X-Session-Id": session["id"],
            "X-Cache-Hit": "false",
            "X-PII-Count": str(pii_count),
            "Cache-Control": "no-cache"
        },
    )
