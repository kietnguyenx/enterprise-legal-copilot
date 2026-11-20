"""
SecureDoc AI — Enterprise Prompt Engineering Module
Contains system prompts, schema templates, and prompt builders for audit and chat.
"""

def build_chat_prompt(context: str, question: str, chat_history: list | None = None, rag_section: str = "") -> str:
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


def build_audit_prompt(cleaned_text: str, legal_grounding_text: str) -> str:
    """Xây dựng prompt thẩm định hợp đồng với nguyên tắc BLUF, 3 kịch bản đàm phán và schema JSON"""
    return f"""
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
