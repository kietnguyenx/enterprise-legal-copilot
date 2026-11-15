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

    text = user_prompt.strip()

    # 1. Quét phát hiện Prompt Injection & System Leakage
    for pattern, rule_id in _INJECTION_PATTERNS:
        match = re.search(pattern, text)
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
        match = re.search(pattern, text)
        if match:
            logger.warning(f"🚨 Phát hiện yêu cầu phi pháp/độc hại [{rule_id}]")
            return (
                False,
                rule_id,
                "⚠️ Yêu cầu của bạn vi phạm chính sách sử dụng và chuẩn mực tuân thủ pháp lý doanh nghiệp. SecureDoc AI chỉ hỗ trợ thẩm định, rà soát rủi ro hợp đồng và phân tích văn bản pháp luật."
            )

    # 3. Chuẩn hóa nhẹ nhàng loại bỏ các ký tự điều khiển ẩn (zero-width chars)
    sanitized = re.sub(r"[\u200B-\u200D\uFEFF]", "", text)

    return True, "clean", sanitized
