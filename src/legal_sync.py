# src/legal_sync.py — Online Legal Web Scraper & Vector Ingestion
import re
import json
import socket
import logging
import ipaddress
from pathlib import Path
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup

from src.legal_kb import get_rag_engine

BASE_DIR = Path(__file__).resolve().parent.parent
LAWS_DIR = BASE_DIR / "data" / "laws"
SYNCED_FILE = LAWS_DIR / "synced_web_laws.json"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 SecureDocAI/1.0"
)


def extract_articles_from_text(raw_text: str, default_law_name: str) -> list[dict]:
    """Tách văn bản pháp luật thành từng Điều khoản có cấu trúc."""
    # Pattern nhận diện: "Điều 1.", "Điều 1:", "Điều 1 -"
    article_pattern = re.compile(
        r'(?:^|\n)\s*(Điều\s+\d+[a-z]?[\.\:\-]?\s*[^\n]*)',
        re.IGNORECASE
    )

    matches = list(article_pattern.finditer(raw_text))
    articles = []

    if matches:
        for i, match in enumerate(matches):
            header = match.group(1).strip()
            start_idx = match.end()
            end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)
            body = raw_text[start_idx:end_idx].strip()

            # Tách số điều và tiêu đề điều
            parts = re.split(r'[\.\:\-]\s*', header, maxsplit=1)
            art_num = parts[0].strip()
            art_title = parts[1].strip() if len(parts) > 1 else header

            if len(body) >= 20:
                articles.append({
                    "law_id": f"web_{re.sub(r'[^a-zA-Z0-9]', '_', art_num).lower()}",
                    "law_name": default_law_name,
                    "article": art_num,
                    "title": art_title,
                    "content": body[:4000],
                    "category": "online_synced"
                })

    # Nếu văn bản không chia theo 'Điều ...', chia theo các đoạn văn có ý nghĩa
    if not articles:
        paragraphs = [p.strip() for p in raw_text.split("\n\n") if len(p.strip()) > 80]
        for idx, p in enumerate(paragraphs[:20]):
            lines = p.split("\n")
            p_title = lines[0][:80]
            articles.append({
                "law_id": f"web_sec_{idx+1}",
                "law_name": default_law_name,
                "article": f"Mục {idx+1}",
                "title": p_title,
                "content": p[:3000],
                "category": "online_synced"
            })

    return articles


def _validate_safe_public_url(url: str):
    """Chống lỗ hổng SSRF: Chỉ cho phép http/https tới địa chỉ công khai, chặn IP nội bộ/localhost."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or not parsed.hostname:
        raise ValueError(f"Đường dẫn URL không hợp lệ (chỉ hỗ trợ http/https công khai): '{url}'")

    hostname = parsed.hostname.lower().strip(".")
    blocked_hosts = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal"}
    if hostname in blocked_hosts or hostname.endswith(".local") or hostname.endswith(".internal"):
        raise ValueError("Chặn truy cập địa chỉ nội bộ (SSRF Protection).")

    try:
        ip_obj = ipaddress.ip_address(hostname)
        ips_to_check = [ip_obj]
    except ValueError:
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            ips_to_check = [ipaddress.ip_address(item[4][0]) for item in addr_info]
        except Exception:
            ips_to_check = []

    for ip in ips_to_check:
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError(f"Chặn truy cập dải IP nội bộ/không công khai ({ip}) (SSRF Protection).")
    return parsed


def sync_law_from_url(url: str, custom_name: str | None = None) -> dict:
    """Tải nội dung từ link web pháp luật, bóc tách và tự động nạp vào Vector DB."""
    parsed = _validate_safe_public_url(url)

    headers = {"User-Agent": USER_AGENT}
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            html_content = resp.text
    except Exception as e:
        raise RuntimeError(f"Không thể kết nối đến đường link: {e}")

    soup = BeautifulSoup(html_content, "html.parser")

    # Loại bỏ các thành phần rác trên trang web
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "iframe", "noscript"]):
        tag.decompose()

    # Trích xuất tiêu đề bài viết / văn bản luật
    page_title = ""
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        page_title = h1.get_text(strip=True)
    elif soup.title and soup.title.get_text(strip=True):
        page_title = soup.title.get_text(strip=True)
    else:
        page_title = f"Văn bản từ {parsed.netloc}"

    law_name = custom_name or page_title

    # Lấy nội dung chữ sạch
    raw_text = soup.get_text(separator="\n", strip=True)

    extracted_articles = extract_articles_from_text(raw_text, default_law_name=law_name)
    if not extracted_articles:
        raise ValueError("Không trích xuất được điều khoản hoặc nội dung văn bản nào từ trang này.")

    # Đọc danh sách đã lưu trước đó nếu có
    existing_laws = []
    if SYNCED_FILE.exists():
        try:
            existing_laws = json.loads(SYNCED_FILE.read_text(encoding="utf-8"))
        except Exception:
            existing_laws = []

    # Khử trùng lặp theo (law_name, article)
    existing_keys = {
        f"{item.get('law_name', '').strip()}_{item.get('article', '').strip()}".lower()
        for item in existing_laws
    }

    new_added = 0
    for art in extracted_articles:
        key = f"{art.get('law_name', '').strip()}_{art.get('article', '').strip()}".lower()
        if key not in existing_keys:
            existing_laws.append(art)
            existing_keys.add(key)
            new_added += 1

    # Lưu lại file
    SYNCED_FILE.write_text(json.dumps(existing_laws, ensure_ascii=False, indent=2), encoding="utf-8")

    # Kích hoạt làm mới chỉ mục Vector DB ngay lập tức
    engine = get_rag_engine()
    engine.refresh()

    return {
        "status": "success",
        "url": url,
        "law_name": law_name,
        "total_extracted": len(extracted_articles),
        "newly_added": new_added,
        "total_synced_in_db": len(existing_laws),
        "sample_articles": extracted_articles[:3]
    }
