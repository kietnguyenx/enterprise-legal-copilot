# src/privacy.py — Smart PII Token Vault for SecureDoc AI
import re

_PII_PATTERNS = [
    ("phone", "PHONE", re.compile(r'(?<!\d)(?:0|\+84)[35789]\d(?:[\s\.-]?\d){7}(?!\d)')),
    ("email", "EMAIL", re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')),
    ("id", "ID", re.compile(r'(?i)(?<!\d)(?:\d{9}|\d{12})(?!\d)(?!\s*(?:vnđ|vnd|đồng|usd|eur|đ\b))')),
    ("bank", "BANK", re.compile(r'(?i)(?<!\d)\d{10,16}(?!\d)(?!\s*(?:vnđ|vnd|đồng|usd|eur|đ\b))')),
]


def redact_pii_vault(text: str) -> tuple[str, dict[str, int], dict[str, str]]:
    """
    Smart PII Token Vault:
    Gán token định danh duy nhất (VD: [PHONE_01], [PHONE_02], [ID_01]) cho từng thực thể nhạy cảm.
    Trả về: (văn_bản_đã_che, thống_kê_số_lượng, kho_token_giải_mã)
    """
    counts = {}
    vault = {}
    counters = {}

    for cat_key, prefix, pattern in _PII_PATTERNS:
        matches = pattern.findall(text)
        # Note: nếu pattern có capture group, findall trả về group, nên ta dùng finditer
        iter_matches = list(pattern.finditer(text))
        counts[cat_key] = len(iter_matches)

        if not iter_matches:
            continue

        # Duyệt qua các match để gán token theo thứ tự xuất hiện
        # Duy trì ánh xạ: nếu cùng 1 số điện thoại lặp lại nhiều lần, dùng chung 1 token
        seen_values = {}
        for match in iter_matches:
            val = match.group(0)
            if val not in seen_values:
                counters[prefix] = counters.get(prefix, 0) + 1
                token = f"[{prefix}_{counters[prefix]:02d}]"
                seen_values[val] = token
                vault[token] = val

        # Thay thế bằng token
        # Để tránh thay thế chồng lấn, thay thế các giá trị dài trước
        for val, token in sorted(seen_values.items(), key=lambda x: len(x[0]), reverse=True):
            text = text.replace(val, token)

    return text, counts, vault


def restore_pii(text: str, vault: dict[str, str]) -> str:
    """Khôi phục lại thông tin thực tế từ Token Vault (khi xuất hợp đồng chính thức)."""
    if not vault:
        return text
    for token, original_value in vault.items():
        text = text.replace(token, original_value)
    return text


def redact_pii_report(text: str) -> tuple[str, dict[str, int]]:
    """Tương thích ngược: Che giấu thông tin và trả về (văn_bản, thống_kê)."""
    cleaned, counts, _ = redact_pii_vault(text)
    return cleaned, counts


def redact_pii(text: str) -> str:
    """Tương thích ngược đơn giản: Chỉ trả về văn bản đã che giấu."""
    return redact_pii_vault(text)[0]
