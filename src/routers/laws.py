"""
SecureDoc AI — Legal Knowledge Base & Vector RAG Router
Endpoints for uploading, syncing, listing, and searching Vietnamese laws.
"""
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

from src.auth import AuthUser, require_admin
from src.config import LAWS_DIR, MAX_UPLOAD_BYTES
from src.legal_kb import get_rag_engine
from src.legal_sync import sync_law_from_url

router = APIRouter(tags=["Legal Knowledge Base & RAG"])
ALLOWED_LAW_EXTS = {".json", ".txt", ".md", ".pdf", ".docx"}


class SyncLawUrlRequest(BaseModel):
    url: str
    custom_name: str | None = None


@router.post("/api/laws/sync-url")
def api_sync_law_url(req: SyncLawUrlRequest, _admin: AuthUser = Depends(require_admin)):
    """Cào nội dung điều luật từ link trực tuyến và nạp tự động vào Vector DB (Chỉ Admin)."""
    url = req.url.strip()
    if not url:
        raise HTTPException(400, "Vui lòng nhập đường link URL")
    try:
        result = sync_law_from_url(url, custom_name=req.custom_name)
        return result
    except Exception as e:
        raise HTTPException(502, f"Không thể cào link luật: {e}")


@router.post("/api/laws/upload")
def api_upload_law_file(
    file: UploadFile = File(...),
    category: str = Form("custom"),
    _admin: AuthUser = Depends(require_admin),
):
    """Nạp file văn bản luật mới (.json, .txt, .md, .docx, .pdf) trực tiếp từ máy tính (Chỉ Admin)."""
    data = file.file.read()
    if len(data) < 20:
        raise HTTPException(400, "File rỗng hoặc quá nhỏ")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File luật vượt quá giới hạn 15 MB")

    # Bảo vệ chống Path Traversal (Defense-in-Depth 2 lớp) & kiểm tra đuôi file
    raw_name = (file.filename or "custom_law.txt").strip()
    if not raw_name or ".." in raw_name or "/" in raw_name or "\\" in raw_name:
        raise HTTPException(400, "Tên file không hợp lệ (phát hiện ký tự điều hướng đường dẫn).")

    filename = Path(raw_name).name
    if Path(filename).suffix.lower() not in ALLOWED_LAW_EXTS:
        raise HTTPException(400, f"Định dạng file không được phép. Chỉ hỗ trợ: {', '.join(sorted(ALLOWED_LAW_EXTS))}")

    LAWS_DIR.mkdir(parents=True, exist_ok=True)
    dest_path = (LAWS_DIR / filename).resolve()
    if dest_path.parent != LAWS_DIR.resolve():
        raise HTTPException(400, "Đường dẫn lưu file không hợp lệ.")
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


@router.get("/api/laws/list")
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


@router.get("/api/laws/search")
def api_search_laws(q: str, top_k: int = Query(4, ge=1, le=20)):
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
