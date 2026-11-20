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


def audit_document(cleaned_text: str, model_name: str = "gemini-3.5-flash") -> dict:
    """Gọi LLM thẩm định tài liệu: Tự động phân tích động theo từng tình huống cụ thể, đối chiếu cơ sở pháp lý RAG."""
    rag_engine = get_rag_engine()
    rag_query = _build_rag_query_from_document(cleaned_text)
    relevant_laws = rag_engine.retrieve_relevant_laws(rag_query, top_k=3)
    legal_grounding_text = rag_engine.format_laws_for_prompt(relevant_laws)
    
    prompt = build_audit_prompt(cleaned_text, legal_grounding_text)
    response_text = call_with_fallback(prompt, primary_model=model_name, json_mode=True)
    
    data = _safe_parse_audit_json(response_text)
    data["retrieved_laws"] = [
        {
            "law_name": item.get("law_name"),
            "article": item.get("article"),
            "title": item.get("title"),
            "relevance_score": item.get("relevance_score")
        }
        for item in relevant_laws
    ]
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
