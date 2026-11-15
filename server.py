# server.py — Backend FastAPI cho giao diện web HTML/CSS của SecureDoc AI
# Chạy:  .venv\Scripts\python.exe -m uvicorn server:app --port 8000 --reload
import io
import json
import threading
import time
import uuid
import hashlib
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from src.analyzer import audit_document, chat_followup_stream, check_ollama_status
from src.exporter import generate_audit_docx
from src.ingestion import extract_text
from src.privacy import redact_pii_report, redact_pii_vault, restore_pii
from src.legal_kb import get_rag_engine
from src.legal_sync import sync_law_from_url
from src.guardrails import check_input_guardrails
from src.cache import get_semantic_cache
from src.telemetry import get_telemetry, estimate_tokens
from src.database import init_db, db_save_session, db_save_feedback, check_db_health

BASE_DIR = Path(__file__).parent
WEB_DIR = BASE_DIR / "web"
STORE_PATH = BASE_DIR / "data" / "web_sessions.json"
MAX_UPLOAD_BYTES = 15 * 1024 * 1024

# Danh sách model hiển thị trong menu chọn model (Cloud Gemini + On-Premise Ollama)
MODELS = [
    {"id": "gemini-3.5-flash", "label": "Gemini 3.5 Flash"},
    {"id": "gemini-3.8-flash", "label": "Gemini 3.8 Flash"},
    {"id": "gemini-3.5-flash-lite", "label": "Gemini 3.5 Flash Lite"},
    {"id": "ollama:qwen2.5", "label": "Qwen 2.5 (Local On-Prem)"},
]
MODEL_IDS = {m["id"] for m in MODELS}

# Rate Limiter: DoS Throttling & Bot Abuse Prevention
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo bảng cơ sở dữ liệu Async khi server khởi động
    await init_db()
    yield


app = FastAPI(title="SecureDoc AI - Enterprise Legal Copilot", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

_lock = threading.Lock()


def _load_store() -> dict:
    if STORE_PATH.exists():
        try:
            return json.loads(STORE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {}


SESSIONS: dict = _load_store()


def _save_store():
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(SESSIONS, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STORE_PATH)


def _subtitle(s: dict) -> str:
    audit = s.get("audit")
    if audit:
        n_high = (audit.get("risk_counts") or {}).get("high", 0)
        return f"Audit Risk · {n_high} rủi ro cao, điểm {audit.get('risk_score', 0)}/100"
    for m in reversed(s.get("messages", [])):
        if m.get("role") == "assistant" and m.get("content"):
            return m["content"].replace("\n", " ")[:80]
    return "Cuộc trò chuyện mới"


def _public(s: dict, full: bool = False) -> dict:
    data = {
        "id": s["id"],
        "title": s["title"],
        "subtitle": _subtitle(s),
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


def _get(sid: str) -> dict:
    s = SESSIONS.get(sid)
    if not s:
        raise HTTPException(404, "Không tìm thấy phiên làm việc")
    return s


def _model(model: str | None) -> str:
    return model if model in MODEL_IDS else MODELS[0]["id"]


def _human_size(n: int) -> str:
    return f"{n / 1024 / 1024:.1f} MB" if n > 1024 * 1024 else f"{max(1, n // 1024)} KB"


# ================= RESTful API ENDPOINTS =================

@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/health")
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


@app.get("/api/telemetry")
def api_get_telemetry():
    """Xem số liệu AI Observability: Token usage, Cost ($), p95 Latency"""
    return get_telemetry().get_summary()


@app.get("/api/cache/stats")
def api_get_cache_stats():
    """Xem thống kê tỷ lệ trúng Semantic Cache"""
    return get_semantic_cache().get_stats()


@app.post("/api/cache/clear")
def api_clear_cache():
    """Xóa bộ nhớ đệm ngữ nghĩa"""
    get_semantic_cache().clear()
    return {"status": "cleared"}


@app.get("/api/models")
def list_models():
    # Kiểm tra xem Ollama có sẵn không để đánh dấu nhãn cho người dùng
    ollama_ready = check_ollama_status()
    result = []
    for m in MODELS:
        item = dict(m)
        if "ollama" in item["id"]:
            item["available"] = ollama_ready
            item["label"] = item["label"] + (" (Sẵn sàng)" if ollama_ready else " (Offline)")
        else:
            item["available"] = True
        result.append(item)
    return result


@app.get("/api/sessions")
def list_sessions():
    with _lock:
        items = sorted(SESSIONS.values(), key=lambda s: s.get("updated", 0), reverse=True)
        return [_public(s) for s in items]


@app.get("/api/sessions/{sid}")
def get_session(sid: str):
    with _lock:
        return _public(_get(sid), full=True)


class DeleteRequest(BaseModel):
    ids: list[str] | None = None


@app.post("/api/sessions/delete")
def delete_sessions(req: DeleteRequest):
    with _lock:
        targets = list(SESSIONS) if req.ids is None else req.ids
        for sid in targets:
            SESSIONS.pop(sid, None)
        _save_store()
    return {"deleted": len(targets)}


class FeedbackRequest(BaseModel):
    session_id: str
    rating: str  # "like" | "dislike"
    message_index: int = -1
    user_correction: str = ""
    original_text: str = ""


@app.post("/api/feedback")
async def api_submit_feedback(req: FeedbackRequest):
    """Lưu phản hồi Human-in-the-Loop (HITL) phục vụ đánh giá và Fine-tuning DPO"""
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
            _save_store()

    # Lưu bất đồng bộ vào Database
    await db_save_feedback(
        session_id=req.session_id,
        rating=req.rating,
        message_index=req.message_index,
        user_correction=req.user_correction,
        original_text=req.original_text,
    )
    return {"status": "success", "message": "Cảm ơn bạn đã phản hồi để hoàn thiện mô hình!"}


@app.post("/api/upload")
@limiter.limit("10/minute")
async def upload(request: Request, file: UploadFile = File(...), model: str = Form(None), pii_guard: bool = Form(True)):
    t0 = time.time()
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
    selected_model = _model(model)
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
        "title": f"Thẩm định {buf.name.rsplit('.', 1)[0]}"[:60],
        "file_name": buf.name,
        "file_size": _human_size(len(data)),
        "doc_context": cleaned,
        "audit": audit,
        "pii": pii,
        "pii_vault": vault,
        "messages": [{"role": "user", "type": "file", "file_name": buf.name}],
        "updated": time.time(),
    }
    with _lock:
        SESSIONS[sid] = session
        _save_store()

    # Lưu vào Database
    await db_save_session(session)

    return _public(session, full=True)


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str
    model: str | None = None
    pii_guard: bool = True


@app.post("/api/chat")
@limiter.limit("40/minute")
async def chat(request: Request, req: ChatRequest):
    text = req.message.strip()
    if not text:
        raise HTTPException(400, "Tin nhắn trống")

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

    selected_model = _model(req.model)

    with _lock:
        if req.session_id and req.session_id in SESSIONS:
            session = SESSIONS[req.session_id]
        else:
            sid = uuid.uuid4().hex[:12]
            session = {
                "id": sid,
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
        _save_store()

        context = session.get("doc_context", "")
        if not context and session.get("audit"):
            context = json.dumps(session["audit"], ensure_ascii=False)

    doc_hash = hashlib.md5(context[:1000].encode("utf-8")).hexdigest() if context else "no_doc"

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
            _save_store()

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

    def generate():
        parts = []
        try:
            for chunk in chat_followup_stream(context, text, chat_history=history, model_name=selected_model):
                parts.append(chunk)
                yield chunk
        finally:
            full_reply = "".join(parts)
            duration_ms = (time.time() - t_start) * 1000
            
            # Ghi vào Semantic Cache để tái sử dụng
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
                session["messages"].append({"role": "assistant", "type": "text", "content": full_reply})
                session["updated"] = time.time()
                _save_store()

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


@app.get("/api/sessions/{sid}/export")
def export_docx(sid: str):
    with _lock:
        s = _get(sid)
        if not s.get("audit"):
            raise HTTPException(400, "Phiên này chưa có kết quả thẩm định")
        content = generate_audit_docx(s.get("file_name") or "Tai_lieu", s["audit"])
        stem = (s.get("file_name") or "Tai_lieu").rsplit(".", 1)[0]
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''Bao_Cao_Tham_Dinh_{_quote(stem)}.docx"},
    )


def _quote(s: str) -> str:
    from urllib.parse import quote
    return quote(s)


# ================= CƠ SỞ DỮ LIỆU PHÁP LUẬT & VECTOR RAG =================

class SyncLawUrlRequest(BaseModel):
    url: str
    custom_name: str | None = None


@app.post("/api/laws/sync-url")
def api_sync_law_url(req: SyncLawUrlRequest):
    """Cào nội dung điều luật từ link trực tuyến và nạp tự động vào Vector DB."""
    url = req.url.strip()
    if not url:
        raise HTTPException(400, "Vui lòng nhập đường link URL")
    try:
        result = sync_law_from_url(url, custom_name=req.custom_name)
        return result
    except Exception as e:
        raise HTTPException(502, f"Không thể cào link luật: {e}")


@app.post("/api/laws/upload")
def api_upload_law_file(file: UploadFile = File(...), category: str = Form("custom")):
    """Nạp file văn bản luật mới (.json, .txt, .md, .docx, .pdf) trực tiếp từ máy tính."""
    data = file.file.read()
    if len(data) < 20:
        raise HTTPException(400, "File rỗng hoặc quá nhỏ")

    filename = file.filename or "custom_law.txt"
    dest_path = BASE_DIR / "data" / "laws" / filename
    dest_path.write_bytes(data)

    try:
        engine = get_rag_engine()
        engine.refresh()
        return {
            "status": "success",
            "file_name": filename,
            "total_laws_in_db": len(engine.documents)
        }
    except Exception as e:
        raise HTTPException(500, f"Đã lưu file nhưng lỗi khi lập chỉ mục vector: {e}")


@app.get("/api/laws/list")
def api_list_laws():
    """Xem danh sách toàn bộ các điều luật đang có trong hệ sinh thái RAG."""
    engine = get_rag_engine()
    docs = [
        {
            "law_name": d.get("law_name"),
            "article": d.get("article"),
            "title": d.get("title"),
            "category": d.get("category"),
            "source_file": d.get("source_file"),
            "snippet": d.get("content", "")[:120] + "..."
        }
        for d in engine.documents
    ]
    return {
        "total": len(docs),
        "laws": docs
    }


@app.get("/api/laws/search")
def api_search_laws(q: str, top_k: int = 4):
    """Tìm kiếm điều luật tương đồng bằng Vector Embedding & Cosine Similarity."""
    query = q.strip()
    if not query:
        raise HTTPException(400, "Từ khóa tìm kiếm không được để trống")
    engine = get_rag_engine()
    results = engine.retrieve_relevant_laws(query, top_k=top_k)
    return {
        "query": query,
        "count": len(results),
        "results": results
    }
