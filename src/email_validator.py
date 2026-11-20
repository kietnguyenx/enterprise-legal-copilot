# src/email_validator.py — Industry-Standard Email & Google Account Format Validator
"""
Kiểm tra chuẩn địa chỉ Email trước khi cho phép gửi mã xác nhận / đăng ký:
1. Kiểm tra cú pháp RFC chuẩn.
2. Phát hiện lỗi gõ nhầm phổ biến (gmial.com, gmal.com, gmail.con...).
3. Chặn danh sách email rác / email dùng 1 lần (Disposable Email Blocklist).
4. Áp dụng quy tắc chuẩn tài khoản Google thật cho @gmail.com / @googlemail.com
   (6–30 ký tự, chỉ gồm a-z, 0-9, dấu chấm; không bắt đầu/kết thúc bằng dấu chấm; không có '..').
5. Xác minh tên miền tồn tại thật trên Internet qua DNS lookup.
"""

import re
import socket
from typing import Dict, Any

_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
_GMAIL_LOCAL_REGEX = re.compile(r"^[a-z0-9.]{6,30}$")

_DISPOSABLE_DOMAINS = {
    "tempmail.com", "temp-mail.org", "10minutemail.com", "guerrillamail.com",
    "mailinator.com", "yopmail.com", "sharklasers.com", "trashmail.com",
    "fakeinbox.com", "getnada.com", "dispostable.com", "maildrop.cc",
    "throwawaymail.com", "mohmal.com", "emailondeck.com",
}

_COMMON_TYPOS = {
    "gmial.com": "gmail.com",
    "gmal.com": "gmail.com",
    "gamil.com": "gmail.com",
    "gnail.com": "gmail.com",
    "gmail.con": "gmail.com",
    "gmail.co": "gmail.com",
    "gmaill.com": "gmail.com",
    "hotmial.com": "hotmail.com",
    "outlok.com": "outlook.com",
    "yaho.com": "yahoo.com",
}

_TRUSTED_FAST_DOMAINS = {
    "gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com",
    "icloud.com", "yahoo.com", "securedoc.ai",
}


def validate_email_address(raw_email: str, check_dns: bool = True) -> Dict[str, Any]:
    """
    Trả về dict:
      - valid (bool)
      - normalized (str)
      - reason (str)
      - suggestion (str | None)
      - provider_type ("google" | "corporate_or_other")
    """
    email = (raw_email or "").strip().lower()
    if not email or not _EMAIL_REGEX.match(email):
        return {
            "valid": False,
            "normalized": email,
            "reason": "Định dạng email không hợp lệ. Vui lòng nhập đúng dạng ten@domain.com.",
            "suggestion": None,
            "provider_type": "unknown",
        }

    local_part, domain = email.rsplit("@", 1)

    # 1. Phát hiện lỗi gõ nhầm phổ biến (VD: @gmial.com -> @gmail.com)
    if domain in _COMMON_TYPOS:
        suggested_domain = _COMMON_TYPOS[domain]
        return {
            "valid": False,
            "normalized": email,
            "reason": f"Tên miền '@{domain}' có vẻ bị gõ nhầm. Có phải ý bạn là '{local_part}@{suggested_domain}'?",
            "suggestion": f"{local_part}@{suggested_domain}",
            "provider_type": "unknown",
        }

    # 2. Chặn email rác / email 10 phút
    if domain in _DISPOSABLE_DOMAINS:
        return {
            "valid": False,
            "normalized": email,
            "reason": f"Hệ thống không chấp nhận email tạm thời/rác (@{domain}). Vui lòng dùng Gmail hoặc email doanh nghiệp thật.",
            "suggestion": None,
            "provider_type": "disposable",
        }

    # 3. Kiểm tra quy tắc chặt chẽ của tài khoản Google (@gmail.com / @googlemail.com)
    if domain in ("gmail.com", "googlemail.com"):
        if not _GMAIL_LOCAL_REGEX.match(local_part) or local_part.startswith(".") or local_part.endswith(".") or ".." in local_part:
            return {
                "valid": False,
                "normalized": email,
                "reason": "Tài khoản Gmail không hợp lệ (tên Gmail phải từ 6–30 ký tự, chỉ gồm chữ thường, số và dấu chấm, không chứa ký tự đặc biệt hay '..').",
                "suggestion": None,
                "provider_type": "google",
            }
        return {
            "valid": True,
            "normalized": email,
            "reason": "Địa chỉ Gmail hợp lệ theo chuẩn Google.",
            "suggestion": None,
            "provider_type": "google",
        }

    # 4. Xác minh tên miền doanh nghiệp tồn tại thật qua DNS
    if check_dns and domain not in _TRUSTED_FAST_DOMAINS:
        try:
            socket.getaddrinfo(domain, None)
        except OSError:
            return {
                "valid": False,
                "normalized": email,
                "reason": f"Tên miền '@{domain}' không tồn tại trên Internet. Vui lòng kiểm tra lại địa chỉ email.",
                "suggestion": None,
                "provider_type": "unknown",
            }

    return {
        "valid": True,
        "normalized": email,
        "reason": "Địa chỉ email hợp lệ.",
        "suggestion": None,
        "provider_type": "corporate_or_other",
    }
