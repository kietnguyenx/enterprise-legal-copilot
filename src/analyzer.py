# src/analyzer.py
"""
SecureDoc AI — Legal Document Auditor & Conversational Orchestrator
Coordinates Document Ingestion, Legal RAG, Prompts, and Hybrid LLM Router.
"""
import re
import json
import logging
from dotenv import load_dotenv

from src.legal_kb import get_rag_engine
from src.legal_verifier import (
    extract_document_clauses,
    format_clause_checklist_for_prompt,
    retrieve_laws_multi_query,
    verify_and_reconcile_audit,
)
from src.prompts import build_chat_prompt, build_audit_prompt
from src.llm import check_ollama_status, call_with_fallback, stream_with_fallback

load_dotenv()


def _build_chat_prompt(context: str, question: str, chat_history: list | None = None) -> str:
    """Helper bọc lại build_chat_prompt kèm bước tìm kiếm Vector RAG nếu phát hiện từ khóa pháp lý"""
    rag_section = ""
    legal_keywords = ["luật", "quy định", "phạt", "bồi thường", "chấm dứt", "hủy bỏ", "đặt cọc", "lãi suất", "nda", "bảo mật", "khoản", "điều"]
    if any(k in question.lower() for k in legal_keywords):
        try:
            rag_engine = get_rag_engine()
            matched_laws = rag_engine.retrieve_relevant_laws(question, top_k=2)
            if matched_laws:
                rag_section = f"\nCĂN CỨ PHÁP LÝ LIÊN QUAN ĐƯỢC TRÍCH XUẤT TỪ VECTOR RAG:\n{rag_engine.format_laws_for_prompt(matched_laws)}\n"
        except Exception:
            pass

    return build_chat_prompt(context, question, chat_history, rag_section=rag_section)


def _build_rag_query_from_document(cleaned_text: str) -> str:
    """Lấy mẫu đại diện từ cả đầu, giữa và cuối hợp đồng dài để RAG không bỏ sót điều khoản phạt/tranh chấp."""
    if len(cleaned_text) <= 5500:
        return cleaned_text
    mid = len(cleaned_text) // 2
    return (
        cleaned_text[:2000]
        + "\n"
        + cleaned_text[mid - 750 : mid + 750]
        + "\n"
        + cleaned_text[-2000:]
    )


def _safe_parse_audit_json(response_text: str) -> dict:
    """Parse JSON an toàn từ LLM: tự sửa dấu phẩy thừa và có cấu trúc dự phòng tránh crash 500."""
    raw = (response_text or "").strip()
    start, end = raw.find("{"), raw.rfind("}")
    candidate = raw[start : end + 1] if (start != -1 and end > start) else raw

    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        # Thử sửa lỗi phổ biến nhất của LLM: dấu phẩy thừa trước } hoặc ]
        repaired = re.sub(r",\s*([}\]])", r"\1", candidate)
        try:
            parsed = json.loads(repaired)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    logging.warning("⚠️ LLM trả về JSON không hợp lệ, kích hoạt cấu trúc fallback an toàn.")
    return {
        "risk_score": 50,
        "risk_level": "MEDIUM RISK",
        "risk_counts": {"high": 0, "medium": 1, "low": 0},
        "summary": raw[:600] if raw else "Không thể phân tích cấu trúc JSON từ mô hình AI. Vui lòng thử lại.",
        "recommendation": "Vui lòng kiểm tra thủ công hoặc chạy thẩm định lại bằng model dự phòng.",
        "clauses": [],
        "scenarios": {
            "aggressive": "Yêu cầu rà soát lại toàn bộ điều khoản bất lợi.",
            "balanced": "Thương lượng điều chỉnh theo quy định Luật Thương mại 2005 và Bộ luật Dân sự 2015.",
            "conservative": "Bổ sung điều khoản giới hạn trách nhiệm bồi thường.",
        },
    }


def _audit_missed_clauses_patch(
    missed_clause_objs: list[dict],
    legal_grounding_text: str,
    model_name: str,
) -> list[dict]:
    """
    Self-Healing Pass (chỉ kích hoạt khi phát hiện bỏ sót Điều khoản ở lượt 1):
    Gửi riêng đúng nội dung các Điều khoản bị sót để bổ sung vào bảng kết quả, đảm bảo độ phủ 100%.
    """
    if not missed_clause_objs:
        return []

    snippets = "\n\n".join(
        f"[{c['ref']}{(': ' + c['title']) if c.get('title') else ''}]\n{c.get('body', '')[:1500]}"
        for c in missed_clause_objs[:8]
    )
    patch_prompt = f"""
    Bạn là Chuyên gia Kiểm định Pháp lý (Self-Correction Critic Agent).
    Lượt thẩm định trước đã bỏ sót các điều khoản dưới đây trong hợp đồng. Hãy đánh giá bổ sung ĐÚNG các điều khoản này và đối chiếu với kho luật RAG bên dưới:

    CÁC ĐIỀU KHOẢN BỊ SÓT:
    --------------------------------------------------
    {snippets}
    --------------------------------------------------

    GROUND TRUTH LAW (RAG):
    {legal_grounding_text}

    BẮT BUỘC TRẢ VỀ DUY NHẤT 1 ĐỐI TƯỢNG JSON HỢP LỆ:
    {{
      "clauses": [
        {{
          "ref": "<Đúng tên Điều X gốc>",
          "topic": "<Chủ đề ngắn gọn của điều khoản>",
          "status": "<Cao / Trung bình / Thấp>",
          "action": "<Đề xuất sửa / Cần xem xét / Chấp nhận>",
          "note": "<Giải thích rủi ro ngắn gọn, trích đúng Điều luật RAG nếu có>"
        }}
      ]
    }}
    """
    try:
        patch_raw = call_with_fallback(patch_prompt, primary_model=model_name, json_mode=True)
        parsed = _safe_parse_audit_json(patch_raw)
        extra = parsed.get("clauses")
        return extra if isinstance(extra, list) else []
    except Exception as e:
        logging.warning(f"⚠️ Self-Healing Pass bỏ qua do lỗi nhẹ: {e}")
        return []


def audit_document(cleaned_text: str, model_name: str = "gemini-3.5-flash") -> dict:
    """
    Pipeline 3 giai đoạn chuẩn hóa & chống ảo giác:
    1. Clause Extractor Agent (0-token): Bóc tách chính xác danh sách Điều khoản gốc.
    2. Clause-Level Multi-Query RAG (0-token): Truy xuất top 6 điều luật Việt Nam khớp từng Điều khoản.
    3. Legal Auditor LLM + Verification Critic Agent (tự đồng bộ số liệu, xác minh nguyên văn, tự vá điều khoản bị sót).
    """
    rag_engine = get_rag_engine()

    # Giai đoạn 1: Bóc tách cấu trúc Điều khoản gốc
    extracted_clauses = extract_document_clauses(cleaned_text)
    clause_checklist = format_clause_checklist_for_prompt(extracted_clauses)

    # Giai đoạn 2: Clause-Level Multi-Query Legal RAG (khắc phục sót luật ở hợp đồng dài)
    relevant_laws = retrieve_laws_multi_query(rag_engine, cleaned_text, extracted_clauses, max_laws=6)
    legal_grounding_text = rag_engine.format_laws_for_prompt(relevant_laws)

    # Giai đoạn 3: Thẩm định chính kèm Checklist bắt buộc
    prompt = build_audit_prompt(cleaned_text, legal_grounding_text, clause_checklist=clause_checklist)
    response_text = call_with_fallback(prompt, primary_model=model_name, json_mode=True)
    data = _safe_parse_audit_json(response_text)

    data["retrieved_laws"] = [
        {
            "law_name": item.get("law_name"),
            "article": item.get("article"),
            "title": item.get("title"),
            "relevance_score": item.get("relevance_score"),
        }
        for item in relevant_laws
    ]

    # Giai đoạn 4: Critic Verification Agent (0-token kiểm định trích dẫn & độ phủ điều khoản)
    data = verify_and_reconcile_audit(data, cleaned_text, extracted_clauses, relevant_laws)

    # Giai đoạn 5 (Conditional Self-Healing): Chỉ gọi bổ sung nếu phát hiện sót Điều khoản thật sự
    verif = data.get("verification") or {}
    missed_labels = verif.get("missed_clauses") or []
    if len(extracted_clauses) >= 2 and missed_labels:
        missed_set = {lbl.split(":")[0].strip().lower() for lbl in missed_labels}
        missed_objs = [c for c in extracted_clauses if c["ref"].lower() in missed_set]
        if missed_objs:
            logging.info(f"🔄 Self-Healing Agent phát hiện sót {len(missed_objs)} điều khoản, đang rà bổ sung...")
            patched_clauses = _audit_missed_clauses_patch(missed_objs, legal_grounding_text, model_name=model_name)
            if patched_clauses:
                data.setdefault("clauses", []).extend(patched_clauses)
                data = verify_and_reconcile_audit(data, cleaned_text, extracted_clauses, relevant_laws)
                data["verification"]["self_healed_clauses"] = len(patched_clauses)

    return data


def chat_followup(
    context: str,
    question: str,
    chat_history: list | None = None,
    model_name: str = "gemini-3.5-flash",
) -> str:
    """Trả lời hội thoại toàn bộ một lần (fallback)"""
    prompt = _build_chat_prompt(context, question, chat_history)
    return call_with_fallback(prompt, primary_model=model_name)


def chat_followup_stream(
    context: str,
    question: str,
    chat_history: list | None = None,
    model_name: str = "gemini-3.5-flash",
):
    """Generator trả về từng mảnh chữ (Token Streaming) theo thời gian thực (Hỗ trợ cả Gemini Cloud & Ollama On-Prem)"""
    prompt = _build_chat_prompt(context, question, chat_history)
    yield from stream_with_fallback(prompt, primary_model=model_name)
