# src/analyzer.py
import os
import json
import logging
import urllib.request
from dotenv import load_dotenv
from google import genai
from google.genai import types

from src.legal_kb import get_rag_engine

load_dotenv()

FALLBACK_MODELS = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.8-flash"]
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def check_ollama_status() -> bool:
    """Kiểm tra máy chủ Ollama on-premise có đang chạy hay không"""
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags", headers={"User-Agent": "SecureDoc-AI"})
        with urllib.request.urlopen(req, timeout=1.2) as resp:
            return resp.status == 200
    except Exception:
        return False


def _call_ollama(prompt: str, model: str = "qwen2.5:latest", json_mode: bool = False) -> str:
    """Gọi mô hình nội bộ Ollama on-premise"""
    clean_model = model.replace("ollama:", "")
    payload = {
        "model": clean_model,
        "prompt": prompt,
        "stream": False,
    }
    if json_mode:
        payload["format"] = "json"
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res.get("response", "")


def _stream_ollama(prompt: str, model: str = "qwen2.5:latest"):
    """Stream token từ mô hình nội bộ Ollama on-premise"""
    clean_model = model.replace("ollama:", "")
    payload = {
        "model": clean_model,
        "prompt": prompt,
        "stream": True,
    }
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        for line in resp:
            if line:
                chunk = json.loads(line.decode("utf-8"))
                text = chunk.get("response", "")
                if text:
                    yield text


def _call_gemini_with_fallback(prompt: str, primary_model: str = "gemini-3.5-flash", json_mode: bool = False):
    """Hybrid Router: Tự động chuyển model dự phòng nếu model chính bị bận hoặc lỗi (Cloud Gemini + Local Ollama)"""
    # Nếu chọn mô hình On-Premise Ollama
    if primary_model.startswith("ollama") or "qwen" in primary_model.lower():
        try:
            return _call_ollama(prompt, model=primary_model, json_mode=json_mode)
        except Exception as e:
            logging.warning(f"Ollama local model ({primary_model}) không phản hồi ({e}), tự động chuyển sang Cloud Gemini...")
            primary_model = "gemini-3.5-flash"

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    models_to_try = [primary_model] + [m for m in FALLBACK_MODELS if m != primary_model]
    config = types.GenerateContentConfig(response_mime_type="application/json") if json_mode else None

    last_err = None
    for model_candidate in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_candidate,
                contents=prompt,
                config=config,
            )
            return response.text
        except Exception as e:
            last_err = e
            logging.warning(f"Model {model_candidate} gặp lỗi ({e}), đang chuyển sang model dự phòng...")
            continue

    raise RuntimeError(f"Tất cả mô hình đều bận, vui lòng thử lại sau giây lát: {last_err}")


def _build_chat_prompt(context: str, question: str, chat_history: list | None = None) -> str:
    """Xây dựng prompt chuẩn cho cả chế độ thường và chế độ Streaming (như AI Web ChatGPT/Gemini)"""
    history_str = ""
    if chat_history:
        recent_turns = []
        for msg in chat_history[-10:]:
            role_label = "Người dùng" if msg.get("role") == "user" else "SecureDoc AI"
            if msg.get("type") == "text":
                recent_turns.append(f"{role_label}: {msg.get('content', '')}")
            elif msg.get("type") == "file":
                recent_turns.append(f"{role_label}: [Đã đính kèm tài liệu: {msg.get('file_name', '')}]")
        if recent_turns:
            history_str = "\n".join(recent_turns)

    doc_section = (
        f"TÀI LIỆU ĐANG ĐƯỢC ĐÍNH KÈM TRONG PHIÊN:\n--------------------------------------------------\n{context[:18000]}\n--------------------------------------------------"
        if context and context.strip()
        else "Hiện chưa có tài liệu đính kèm (Chế độ trò chuyện AI Web tự do)."
    )

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

    return f"""
    Bạn là **SecureDoc AI** — Trợ lý AI thông minh đa năng (tương tự ChatGPT / Gemini Web) kết hợp chuyên gia phân tích tài liệu & pháp lý doanh nghiệp.

    {doc_section}
    {rag_section}
    LỊCH SỬ TRÒ CHUYỆN GẦN ĐÂY:
    {history_str if history_str else "(Bắt đầu cuộc trò chuyện)"}

    TIN NHẮN MỚI NHẤT CỦA NGƯỜI DÙNG:
    {question}

    NGUYÊN TẮC PHẢN HỒI:
    1. **Trò chuyện tự nhiên & Đa năng như AI Web (ChatGPT / Gemini):**
       - Nếu người dùng chào hỏi, trò chuyện phiếm, hỏi kiến thức tổng hợp, lập trình, dịch thuật, viết email, soạn văn bản, giải toán, hay bất kỳ chủ đề nào ngoài tài liệu: hãy trả lời trực tiếp, thông minh, tự nhiên và đầy đủ (TUYỆT ĐỐI KHÔNG mở đầu máy móc rằng "Trong tài liệu không đề cập...").
    2. **Khi người dùng hỏi về hợp đồng/tài liệu đang đính kèm:**
       - Phân tích chính xác dựa trên nội dung tài liệu, trích dẫn rõ điều khoản/trang (ví dụ: *Theo Điều 8.2*, *Trang 1*) hoặc trích nguyên văn trong ngoặc kép để đối chiếu.
       - Nếu có căn cứ pháp lý liên quan ở trên, đối chiếu trực tiếp quy định của pháp luật Việt Nam.
    3. **Hiểu mạch hội thoại nhiều lượt (Multi-turn Memory):**
       - Kết nối mượt mà với LỊCH SỬ TRÒ CHUYỆN GẦN ĐÂY khi người dùng hỏi nối tiếp ("giải thích kỹ hơn", "viết lại ngắn hơn", "còn bên B thì sao?").
    4. **Trình bày đẹp mắt:**
       - Sử dụng Markdown rõ ràng (in đậm **...**, danh sách gạch đầu dòng, bảng biểu hoặc khối code nếu cần) để hiển thị trực quan trên giao diện web.
    """


def audit_document(cleaned_text: str, model_name: str = "gemini-3.5-flash") -> dict:
    """Gọi Gemini thẩm định tài liệu: Tự động phân tích động 100% theo từng tình huống cụ thể, đối chiếu cơ sở pháp lý RAG."""
    rag_engine = get_rag_engine()
    relevant_laws = rag_engine.retrieve_relevant_laws(cleaned_text[:4000], top_k=3)
    legal_grounding_text = rag_engine.format_laws_for_prompt(relevant_laws)
    
    prompt = f"""
    Bạn là Giám đốc Pháp chế và Chuyên gia Đàm phán Hợp đồng Doanh nghiệp cao cấp.
    Nhiệm vụ của bạn là đọc và phân tích văn bản thực tế dưới đây:
    --------------------------------------------------
    {cleaned_text[:20000]}
    --------------------------------------------------

    CƠ SỞ DỮ LIỆU PHÁP LUẬT ĐỂ ĐỐI CHIẾU (GROUND TRUTH LAW TỪ HỆ THỐNG RAG):
    --------------------------------------------------
    {legal_grounding_text}
    --------------------------------------------------

    QUY TẮC THẨM ĐỊNH TỰ ĐỘNG THEO TÌNH HUỐNG:
    1. ĐỌC KỸ VĂN BẢN TRÊN: Toàn bộ phân tích, trích dẫn, điều khoản và câu hỏi PHẢI xuất phát từ chính văn bản được cung cấp, tuyệt đối KHÔNG bịa đặt hay dùng văn mẫu có sẵn.
    2. NGUYÊN TẮC BLUF (Bottom Line Up Front): Trả lời thẳng vào trọng tâm, ngắn gọn, súc tích, không chào hỏi lan man.
    3. ĐỐI CHIẾU CƠ SỞ PHÁP LÝ: Khi thẩm định các điều khoản phạt, bồi thường, bảo mật hay quyền chấm dứt hợp đồng, BẮT BUỘC đối chiếu với các quy định pháp luật được cung cấp ở trên (ví dụ: trần 8% theo Điều 301 Luật Thương mại, Điều 418/428 Bộ luật Dân sự...).
    4. TỰ XÂY DỰNG 3 KỊCH BẢN ĐÀM PHÁN RIÊNG BIỆT: Tự tìm điều khoản bất lợi nhất của tài liệu này để đưa ra 3 phương án hành động cụ thể cho riêng trường hợp này.
    BẮT BUỘC TRẢ VỀ DUY NHẤT 1 ĐỐI TƯỢNG JSON HỢP LỆ VỚI CẤU TRÚC SAU:
    {{
        "risk_score": <Tính toán điểm rủi ro từ 0 đến 100 dựa trên mức độ bất lợi thực tế của tài liệu>,
        "risk_level": "<Tự xếp loại: HIGH RISK nếu điểm > 70, MEDIUM RISK nếu 40-70, LOW RISK nếu < 40>",
        
        "executive_summary": "<Tự viết 2-3 câu tóm tắt chính xác: Tên tài liệu này là gì? Giữa các bên nào? Điều khoản nào mang tính rủi ro nghiêm trọng nhất trong văn bản này?>",
        
        "recommendation": "<Tự đưa ra 1-2 câu khuyến nghị hành động dứt khoát nhất dành riêng cho tài liệu này, trích dẫn căn cứ luật nếu có>",
        
        "risk_counts": {{
            "high": <Số lượng điều khoản rủi ro cao tìm thấy trong tài liệu>,
            "medium": <Số lượng điều khoản rủi ro trung bình tìm thấy trong tài liệu>,
            "low": <Số lượng điều khoản an toàn/rủi ro thấp tìm thấy trong tài liệu>
        }},
        "clauses_reviewed": <Tổng số điều khoản bạn đã đọc và rà soát được trong tài liệu>,
        "negotiation_scenarios": {{
            "aggressive": {{
                "title": "Kịch bản Cứng rắn (Thế Áp Đảo)",
                "strategy": "<Dựa vào điều khoản bất lợi nhất của tài liệu này, hãy đề xuất phương án đàm phán tối đa có lợi, đòi xóa bỏ hoặc siết phạt ngược lại đối tác>"
            }},
            "balanced": {{
                "title": "Kịch bản Cân bằng (Win - Win)",
                "strategy": "<Dựa vào điều khoản bất lợi nhất, hãy đề xuất phương án hòa giải hợp lý, đưa về trần quy định pháp luật và bổ sung thời gian khắc phục lỗi>"
            }},
            "conservative": {{
                "title": "Kịch bản Dự phòng (Thế Yếu)",
                "strategy": "<Nếu buộc phải chấp nhận điều khoản này của đối tác, hãy đề xuất giải pháp giảm thiểu thiệt hại bằng cách đặt trần bồi thường hoặc mua bảo hiểm rủi ro>"
            }}
        }},
        "notebooklm_studio": {{
            "executive_briefing": [
                "<Gạch đầu dòng 1: Tên các bên và tư cách pháp lý được nêu trong tài liệu>",
                "<Gạch đầu dòng 2: Phạm vi công việc hoặc đối tượng giao dịch cốt lõi>",
                "<Gạch đầu dòng 3: Giá trị thanh toán và phương thức giao dịch thực tế>",
                "<Gạch đầu dòng 4: Rủi ro pháp lý lớn nhất được phát hiện trong tài liệu>",
                "<Gạch đầu dòng 5: Thời hạn hiệu lực và điều kiện chấm dứt của tài liệu này>"
            ],
            "timeline_milestones": [
                {{"event": "<Tên mốc sự kiện 1 tìm thấy trong văn bản>", "deadline": "<Thời hạn cụ thể của mốc 1>"}},
                {{"event": "<Tên mốc sự kiện 2 tìm thấy trong văn bản>", "deadline": "<Thời hạn cụ thể của mốc 2>"}},
                {{"event": "<Tên mốc sự kiện 3 tìm thấy trong văn bản>", "deadline": "<Thời hạn cụ thể của mốc 3>"}}
            ],
            "suggested_faq": [
                {{
                    "question": "<Tự đặt câu hỏi quan trọng số 1 mà người ký hợp đồng này nhất định phải lưu ý>",
                    "answer": "<Câu trả lời ngắn gọn được đối chiếu trực tiếp từ điều khoản trong tài liệu>"
                }},
                {{
                    "question": "<Tự đặt câu hỏi quan trọng số 2 về quyền lợi hoặc trách nhiệm bồi thường>",
                    "answer": "<Câu trả lời ngắn gọn được đối chiếu trực tiếp từ điều khoản trong tài liệu>"
                }}
            ],
            "missing_clauses": [
                "<Tự phát hiện điều khoản quan trọng số 1 mà tài liệu này bị thiếu hoặc bỏ quên>",
                "<Tự phát hiện điều khoản quan trọng số 2 mà tài liệu này bị thiếu hoặc bỏ quên>"
            ]
        }},
        "clauses": [
            {{
                "ref": "<Tên điều khoản thực tế, ví dụ: Điều 3 hoặc Khoản 2.1>",
                "topic": "<Tên chủ đề thực tế của điều khoản đó>",
                "status": "<Cao / Trung bình / Thấp>",
                "action": "<Đề xuất sửa / Cần xem xét / Chấp nhận>",
                "note": "<Giải thích ngắn gọn lý do tại sao xếp mức độ này, đối chiếu với luật nếu có>"
            }}
        ],
        "quote_ref": "<Tên điều khoản rủi ro cao nhất>",
        "source_quote": "<Trích dẫn NGUYÊN VĂN 1 câu từ tài liệu gốc chứa rủi ro cao nhất và bao quanh cụm từ nguy hiểm bằng cặp thẻ <mark>...</mark>>",
        
        "redline_diff": {{
            "clause_title": "Legal Redline Diff",
            "original": "<Trích nguyên văn câu gốc bất lợi từ tài liệu>",
            "revised": "<Soạn lại câu chữ mới hợp lý, công bằng hơn để thay thế câu gốc>"
        }}
    }}
    """
    response_text = _call_gemini_with_fallback(prompt, primary_model=model_name, json_mode=True)
    start, end = response_text.find("{"), response_text.rfind("}")
    if start != -1 and end > start:
        response_text = response_text[start:end + 1]
    data = json.loads(response_text)
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
    """Trả lời toàn bộ một lần (fallback)"""
    prompt = _build_chat_prompt(context, question, chat_history)
    return _call_gemini_with_fallback(prompt, primary_model=model_name)


def chat_followup_stream(
    context: str,
    question: str,
    chat_history: list | None = None,
    model_name: str = "gemini-3.5-flash",
):
    """Generator trả về từng mảnh chữ (Token Streaming) theo thời gian thực (Hỗ trợ cả Gemini Cloud & Ollama On-Prem)"""
    prompt = _build_chat_prompt(context, question, chat_history)

    # Nếu yêu cầu mô hình On-Premise Ollama
    if model_name.startswith("ollama") or "qwen" in model_name.lower():
        try:
            for chunk in _stream_ollama(prompt, model=model_name):
                yield chunk
            return
        except Exception as e:
            logging.warning(f"Ollama stream ({model_name}) gặp lỗi ({e}), tự động chuyển về Cloud Gemini...")
            model_name = "gemini-3.5-flash"

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    models_to_try = [model_name] + [m for m in FALLBACK_MODELS if m != model_name]

    last_err = None
    for model_candidate in models_to_try:
        try:
            stream = client.models.generate_content_stream(
                model=model_candidate,
                contents=prompt,
            )
            for chunk in stream:
                if getattr(chunk, "text", None):
                    yield chunk.text
            return
        except Exception as e:
            last_err = e
            logging.warning(f"Stream model {model_candidate} gặp lỗi ({e}), đang chuyển sang model dự phòng...")
            continue

    yield f"Hệ thống đang bận, vui lòng thử lại sau giây lát: {last_err}"
