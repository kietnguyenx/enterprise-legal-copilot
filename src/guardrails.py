# src/guardrails.py — Input Guardrails & Prompt Injection Defense
"""
Module bảo vệ an ninh prompt (Input Guardrails) cho SecureDoc AI:
1. Phát hiện & chặn đứng các cuộc tấn công Prompt Injection / Jailbreak.
2. Ngăn ngừa rò rỉ System Prompt, System Instructions, hoặc API keys.
3. Chặn các nỗ lực vượt rào đạo đức, phá vỡ vai trò trợ lý pháp lý doanh nghiệp.
"""

import re
import logging
from typing import Tuple

logger = logging.getLogger("securedoc.guardrails")

# Danh sách các mẫu Prompt Injection nguy hiểm (cả tiếng Anh và tiếng Việt)
_INJECTION_PATTERNS = [
    # 1. Chỉ thị ép quên hướng dẫn trước (Instruction Override)
    (r"(?i)\b(ignore|forget|disregard|override|bỏ\s*qua|quên\s*hết|hủy\s*bỏ)\b.*\b(previous|all|system|chỉ\s*thị|hướng\s*dẫn|câu\s*lệnh|quy\s*tắc)\b", "instruction_override"),
    (r"(?i)\bquên\s+(hết|tất\s*cả|mọi)\s+(quy\s*định|lời\s*dặn|chỉ\s*thị|prompt)\b", "instruction_override_vi"),
    
    # 2. Ép in System Prompt / Bí mật hệ thống (System Prompt Extraction / Leakage)
    (r"(?i)\b(print|show|output|reveal|display|in\s*ra|hiển\s*thị|tiết\s*lộ|nói\s*cho\s*tôi)\b.*\b(system\s*prompt|system\s*instructions|initial\s*instructions|prompt\s*gốc|mã\s*nguồn|api\s*key)\b", "system_prompt_leak"),
    (r"(?i)\b(lặp\s*lại|in\s*lại|repeat)\b.*\b(toàn\s*bộ\s*nội\s*dung\s*bên\s*trên|everything\s*above)\b", "system_prompt_leak_repeat"),
    
    # 3. Kỹ thuật đóng vai bẻ khóa (Role-play Jailbreak / DAN mode)
    (r"(?i)\b(DAN\s*mode|do\s*anything\s*now|developer\s*mode|chế\s*độ\s*nhà\s*phát\s*triển|jailbreak|bẻ\s*khóa)\b", "roleplay_jailbreak"),
    (r"(?i)\btừ\s*giờ\s*bạn\s*hãy\s*đóng\s*vai\s+(hacker|kẻ\s*tấn\s*công|nhân\s*vật\s*không\s*giới\s*hạn)\b", "malicious_roleplay"),
    
    # 4. Kỹ thuật đảo ngược logic an toàn (Adversarial Inversion)
    (r"(?i)\b(simulate|giả\s*lập)\b.*\b(illegal|tội\s*phạm|lừa\s*đảo|vi\s*phạm\s*pháp\s*luật)\b", "adversarial_simulation"),
]

# Từ khóa nhạy cảm không thuộc phạm vi xử lý của trợ lý pháp lý
_MALICIOUS_INTENTS = [
    (r"(?i)\b(tấn\s*công\s*ddos|viết\s*malware|tạo\s*virus|hack\s*pass|ăn\s*cắp\s*dữ\s*liệu)\b", "cyber_threat"),
    (r"(?i)\b(rửa\s*tiền|trốn\s*thuế\s*bất\s*hợp\s*pháp|hối\s*lộ\s*quan\s*chức)\b", "illegal_compliance"),
]

# Từ khóa nhận diện ngữ cảnh pháp lý / hợp đồng (tránh chặn nhầm câu hỏi hợp lệ như "hợp đồng gia công phần mềm")
_LEGAL_CONTEXT_HINT = re.compile(
    r"(?i)\b("
    r"hợp\s*đồng|điều\s*khoản|điều\s+\d+|khoản\s+\d+|luật|bộ\s*luật|nghị\s*định|thông\s*tư|"
    r"pháp\s*lý|pháp\s*luật|phạt\s*vi\s*phạm|bồi\s*thường|tranh\s*chấp|khiếu\s*nại|khởi\s*kiện|"
    r"bên\s*a|bên\s*b|chấm\s*dứt|bảo\s*mật|nda|phụ\s*lục|thẩm\s*định|rà\s*soát|đàm\s*phán|"
    r"sở\s*hữu\s*trí\s*tuệ|bản\s*quyền|lao\s*động|sa\s*thải|bảo\s*hiểm|thuế|doanh\s*nghiệp|"
    r"quyền\s*lợi|nghĩa\s*vụ|thanh\s*toán|nghiệm\s*thu|đặt\s*cọc|lãi\s*suất|tài\s*liệu|văn\s*bản|"
    r"rủi\s*ro|redline|công\s*văn|biên\s*bản|contract|clause|legal|agreement|compliance|liability"
    r")\b"
)

# Topical Guardrail (Layer 1 — Zero-Token): Chặn các yêu cầu rõ ràng nằm ngoài phạm vi Pháp luật & Hợp đồng
_OUT_OF_SCOPE_PATTERNS = [
    # Nấu ăn / ẩm thực
    r"(?i)(cách\s*nấu|hướng\s*dẫn\s*nấu|nấu\s*phở|nấu\s*ăn|công\s*thức\s*(nấu|làm\s*bánh|pha\s*chế)|hôm\s*nay\s*ăn\s*gì|món\s*ngon\s*mỗi\s*ngày|how\s+to\s+cook|recipe\s+for)",
    # Lập trình / viết code / làm game
    r"(?i)(viết\s*code|lập\s*trình\s*(game|web|app|python|java|c\+\+)|tạo\s*game|rắn\s*săn\s*mồi|code\s*(python|java|c\+\+|javascript|html|css|sql)|debug\s*code|sửa\s*lỗi\s*code|giải\s*leetcode|thuật\s*toán\s*(sắp\s*xếp|tìm\s*kiếm)|write\s+(python|java|js|html)\s+code|build\s+a\s+game)",
    # Bài tập toán / lý / hóa phổ thông
    r"(?i)(giải\s*phương\s*trình|tính\s*tích\s*phân|tính\s*đạo\s*hàm|bài\s*tập\s*(toán|vật\s*lý|hóa\s*học|tiếng\s*anh)|cân\s*bằng\s*phương\s*trình\s*hóa|solve\s+this\s+(math|equation))",
    # Giải trí / tử vi / tình cảm / thể thao / xổ số
    r"(?i)(xem\s*bói|tử\s*vi|cung\s*hoàng\s*đạo|kể\s*chuyện\s*cười|làm\s*thơ\s*tình|viết\s*thơ\s*(tình|tặng)|cách\s*(tán\s*gái|tán\s*trai|cưa\s*đổ)|soi\s*cầu|kết\s*quả\s*xổ\s*số|tỷ\s*số\s*bóng\s*đá|lịch\s*thi\s*đấu\s*bóng\s*đá|build\s*đồ\s*tướng|tell\s+me\s+a\s+joke)",
    # Y tế kê đơn / du lịch / thời tiết
    r"(?i)(uống\s*thuốc\s*gì|kê\s*đơn\s*thuốc|cách\s*chữa\s*bệnh|thời\s*tiết\s*hôm\s*nay|lịch\s*trình\s*du\s*lịch|địa\s*điểm\s*du\s*lịch)",
]

OUT_OF_SCOPE_REPLY = (
    "⚖️ **Ngoài phạm vi chuyên môn:** SecureDoc AI là trợ lý pháp lý chuyên biệt về "
    "**thẩm định hợp đồng, phát hiện rủi ro điều khoản và đối chiếu Pháp luật Việt Nam** "
    "(không hỗ trợ các chủ đề ngoài lề như nấu ăn, lập trình, giải bài tập hay giải trí).\n\n"
    "Bạn có thể **tải hợp đồng lên** (`.pdf`, `.docx`, ảnh chụp) hoặc đặt câu hỏi về điều khoản, "
    "mức phạt vi phạm, chấm dứt hợp đồng, bảo mật hay đàm phán đối tác để tôi hỗ trợ ngay!"
)


def check_input_guardrails(user_prompt: str) -> Tuple[bool, str, str]:
    """
    Kiểm tra an toàn dữ liệu đầu vào trước khi chuyển tiếp cho mô hình AI.
    
    Returns:
        (is_safe, category, message_or_sanitized_prompt)
        - is_safe: True nếu prompt an toàn; False nếu phát hiện tấn công/vi phạm.
        - category: Phân loại ("clean", "injection", "jailbreak", "harmful").
        - message_or_sanitized_prompt: Lời giải thích từ chối nếu không an toàn, hoặc prompt sạch đã chuẩn hóa.
    """
    if not user_prompt or not user_prompt.strip():
        return True, "clean", ""

    # 0. Chuẩn hóa & loại bỏ ký tự tàng hình (zero-width chars) TRƯỚC khi quét regex chống bypass
    text = re.sub(r"[\u200B-\u200D\uFEFF]", "", user_prompt.strip())

    # 1. Quét phát hiện Prompt Injection & System Leakage (bật re.DOTALL chống bypass bằng \n)
    for pattern, rule_id in _INJECTION_PATTERNS:
        match = re.search(pattern, text, flags=re.DOTALL)
        if match:
            matched_segment = match.group(0)[:60]
            logger.warning(f"🚨 Phát hiện Prompt Injection [{rule_id}]: '{matched_segment}'")
            return (
                False,
                rule_id,
                "⚠️ Yêu cầu của bạn chứa cấu trúc câu lệnh can thiệp vào quy chuẩn bảo mật hoặc hướng dẫn hệ thống (Prompt Injection Guardrail). SecureDoc AI từ chối thực hiện yêu cầu này để bảo vệ tính toàn vẹn dữ liệu doanh nghiệp."
            )

    # 2. Quét phát hiện ý đồ độc hại
    for pattern, rule_id in _MALICIOUS_INTENTS:
        match = re.search(pattern, text, flags=re.DOTALL)
        if match:
            logger.warning(f"🚨 Phát hiện yêu cầu phi pháp/độc hại [{rule_id}]")
            return (
                False,
                rule_id,
                "⚠️ Yêu cầu của bạn vi phạm chính sách sử dụng và chuẩn mực tuân thủ pháp lý doanh nghiệp. SecureDoc AI chỉ hỗ trợ thẩm định, rà soát rủi ro hợp đồng và phân tích văn bản pháp luật."
            )

    # 3. Topical Guardrail (Zero-Token): Chặn câu hỏi ngoài phạm vi Pháp luật / Hợp đồng để tránh tốn token LLM
    if not _LEGAL_CONTEXT_HINT.search(text):
        for pattern in _OUT_OF_SCOPE_PATTERNS:
            if re.search(pattern, text, flags=re.DOTALL):
                logger.info(f"🛡️ Topical Guardrail chặn yêu cầu ngoài phạm vi: '{text[:60]}'")
                return False, "out_of_scope", OUT_OF_SCOPE_REPLY

    return True, "clean", text
