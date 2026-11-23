# src/legal_verifier.py — Deterministic Clause Extractor, Multi-Query RAG & Citation Verifier Agent
"""
Hệ thống 3 lớp chống sót điều khoản & chống ảo giác trích dẫn (0-token Verification Engine):
1. Clause Extractor: Tự động bóc tách danh sách chính xác các Điều/Khoản có trong hợp đồng gốc.
2. Clause-Level Multi-Query RAG: Truy xuất điều luật Việt Nam khớp theo từng nhóm điều khoản (tránh sót luật).
3. Citation & Coverage Verifier (Critic):
   - Xác minh câu trích dẫn (source_quote) có thực sự tồn tại trong hợp đồng gốc không; tự neo lại câu gốc chuẩn xác nếu LLM viết lệch nhẹ.
   - Kiểm tra độ phủ điều khoản (clause coverage) so với hợp đồng gốc, tránh bịa số Điều không tồn tại.
   - Tự đồng bộ số đếm risk_counts (high/medium/low) và clauses_reviewed khớp 100% với bảng điều khoản.
   - Đối chiếu các số Điều luật được nhắc trong báo cáo với kho Ground-Truth RAG.
"""

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any


# Nhận diện tiêu đề Điều khoản trong hợp đồng tiếng Việt & tiếng Anh (Điều 1., ĐIỀU 2:, Article 3., Section 4.)
_CLAUSE_HEADER_RE = re.compile(
    r"(?im)^[ \t]*(?:#+\s*)?(?:\*{1,2})?"
    r"((?:Điều|ĐIỀU|Article|ARTICLE|Section|SECTION)\s+\d+(?:\.\d+)?)"
    r"\s*(?:[:.\-–—]\s*([^\n]{0,120}))?"
)

# Nhận diện tham chiếu số Điều trong output của LLM (VD: "Điều 5.2", "Điều 8", "Khoản 2 Điều 5")
_CLAUSE_NUM_RE = re.compile(r"(?i)(?:điều|article|section)\s*(\d+)(?:\.(\d+))?")

# Nhận diện số Điều luật trích dẫn trong giải thích / khuyến nghị
_LAW_ARTICLE_RE = re.compile(r"(?i)(?:điều)\s+(\d+)")


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", str(text or "")).strip()


def _normalize_for_match(text: str) -> str:
    """Chuẩn hóa khoảng trắng, dấu câu và chữ thường để so khớp trích dẫn nguyên văn."""
    s = _strip_html(text)
    s = unicodedata.normalize("NFC", s).lower()
    s = re.sub(r"[“”\"'‘’`]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_document_clauses(text: str) -> list[dict[str, Any]]:
    """
    Agent 1 (Clause Extractor): Bóc tách chính xác danh sách Điều khoản & nội dung từng Điều từ hợp đồng gốc.
    Giúp LLM không bao giờ bỏ sót Điều khoản và có căn cứ kiểm chứng chống bịa số Điều.
    """
    if not text or not text.strip():
        return []

    matches = list(_CLAUSE_HEADER_RE.finditer(text))
    if not matches:
        return []

    clauses: list[dict[str, Any]] = []
    seen_refs: set[str] = set()

    for idx, m in enumerate(matches):
        raw_ref = re.sub(r"\s+", " ", m.group(1)).strip()
        # Chuẩn hóa viết hoa chữ đầu: "ĐIỀU 5" -> "Điều 5"
        num_m = _CLAUSE_NUM_RE.search(raw_ref)
        canonical_num = num_m.group(1) if num_m else raw_ref
        canonical_ref = f"Điều {canonical_num}" if raw_ref.lower().startswith("điều") else raw_ref.title()

        raw_title = (m.group(2) or "").strip(" *:-–—\t\r")
        start_pos = m.start()
        end_pos = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[start_pos:end_pos].strip()

        # Tránh trùng lặp nếu trong mục lục nhắc lại cùng 1 Điều (ưu tiên bản có nội dung dài hơn)
        key = canonical_ref.lower()
        if key in seen_refs:
            for existing in clauses:
                if existing["ref"].lower() == key and len(body) > len(existing["body"]):
                    existing["title"] = raw_title or existing["title"]
                    existing["body"] = body
            continue

        seen_refs.add(key)
        clauses.append({
            "ref": canonical_ref,
            "number": canonical_num,
            "title": raw_title,
            "body": body,
        })

    return clauses


def format_clause_checklist_for_prompt(extracted_clauses: list[dict[str, Any]]) -> str:
    """Tạo danh sách Checklist bắt buộc đưa vào Prompt để LLM rà soát đủ từng Điều."""
    if not extracted_clauses:
        return ""
    lines = [
        f"DANH SÁCH {len(extracted_clauses)} ĐIỀU KHOẢN ĐƯỢC BÓC TÁCH TỪ HỢP ĐỒNG GỐC (BẮT BUỘC RÀ SOÁT ĐỦ, KHÔNG BỎ SÓT & KHÔNG BỊA SỐ ĐIỀU):"
    ]
    for c in extracted_clauses:
        title_part = f": {c['title']}" if c.get("title") else ""
        lines.append(f"- {c['ref']}{title_part}")
    return "\n".join(lines)


def retrieve_laws_multi_query(rag_engine, cleaned_text: str, extracted_clauses: list[dict[str, Any]], max_laws: int = 6) -> list[dict]:
    """
    Agent 2 (Clause-Level Multi-Query RAG):
    Truy xuất pháp luật Việt Nam theo từng điều khoản + tổng thể văn bản, khử trùng lặp và giữ top điều luật liên quan nhất.
    Giúp hợp đồng nhiều chủ đề (Phạt vi phạm + Chấm dứt + Bảo mật + SHTT) không bị sót căn cứ luật.
    """
    best_by_id: dict[str, dict] = {}

    def _merge(items: list[dict]):
        for item in items:
            key = str(item.get("id") or f"{item.get('law_name')}_{item.get('article')}")
            prev = best_by_id.get(key)
            if not prev or float(item.get("relevance_score", 0)) > float(prev.get("relevance_score", 0)):
                best_by_id[key] = dict(item)

    # 1. Truy vấn tổng thể (đầu + giữa + cuối hợp đồng)
    if len(cleaned_text) <= 5500:
        overview_query = cleaned_text
    else:
        mid = len(cleaned_text) // 2
        overview_query = cleaned_text[:2000] + "\n" + cleaned_text[mid - 750 : mid + 750] + "\n" + cleaned_text[-2000:]
    _merge(rag_engine.retrieve_relevant_laws(overview_query, top_k=4))

    # 2. Truy vấn chuyên sâu theo từng Điều khoản bóc tách được (tối đa 12 điều đầu/quan trọng)
    for cl in extracted_clauses[:12]:
        clause_query = f"{cl.get('title', '')} {cl.get('body', '')[:600]}".strip()
        if len(clause_query) >= 20:
            _merge(rag_engine.retrieve_relevant_laws(clause_query, top_k=2))

    ranked = sorted(best_by_id.values(), key=lambda x: float(x.get("relevance_score", 0)), reverse=True)
    return ranked[:max_laws]


def _find_best_matching_sentence(quote: str, source_text: str) -> tuple[bool, float, str]:
    """
    Kiểm tra xem câu trích dẫn `quote` có khớp NGUYÊN VĂN trong `source_text` không.
    Trả về: (is_exact_verbatim, similarity_score, matched_original_sentence).
    """
    clean_quote = _strip_html(quote)
    if not clean_quote or not source_text:
        return False, 0.0, ""

    norm_quote = _normalize_for_match(clean_quote)
    norm_source = _normalize_for_match(source_text)

    # 1. Khớp chính xác nguyên văn substring 100%
    if len(norm_quote) >= 12 and norm_quote in norm_source:
        return True, 1.0, clean_quote

    # 2. Tách câu từ tài liệu gốc để tìm câu gốc gần nhất (chống LLM tự ý diễn đạt lại câu gốc)
    raw_sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?;])\s+|\n+", source_text)
        if len(s.strip()) >= 15
    ]
    best_score = 0.0
    best_sentence = ""
    for sent in raw_sentences:
        norm_sent = _normalize_for_match(sent)
        if norm_quote in norm_sent or norm_sent in norm_quote:
            score = min(len(norm_quote), len(norm_sent)) / max(len(norm_quote), len(norm_sent), 1)
            score = max(score, 0.88)
        else:
            score = SequenceMatcher(None, norm_quote, norm_sent).ratio()
        if score > best_score:
            best_score = score
            best_sentence = sent

    return False, round(best_score, 3), best_sentence


def _normalize_severity(status: str) -> str:
    s = (status or "").strip().lower()
    if any(k in s for k in ("cao", "high", "nghiêm trọng", "critical")):
        return "high"
    if any(k in s for k in ("trung", "medium", "vừa", "moderate")):
        return "medium"
    return "low"


def verify_and_reconcile_audit(
    audit_data: dict,
    cleaned_text: str,
    extracted_clauses: list[dict[str, Any]],
    retrieved_laws: list[dict],
) -> dict:
    """
    Agent 3 (Legal Citation & Coverage Verifier — 0 token):
    1. Kiểm chứng từng điều khoản trong output có khớp với số Điều tồn tại trong hợp đồng gốc không.
    2. Tìm danh sách điều khoản bị bỏ sót (missed_clauses).
    3. Xác minh trích dẫn nguyên văn (source_quote); nếu LLM viết lệch nhẹ so với bản gốc -> tự động cảnh báo hoặc neo lại.
    4. Đồng bộ số đếm risk_counts (high/medium/low) và clauses_reviewed chuẩn xác 100%.
    5. Xác minh các số Điều luật được trích dẫn có khớp với kho Ground-Truth RAG không.
    """
    if not isinstance(audit_data, dict):
        return audit_data

    extracted_nums = {c["number"] for c in extracted_clauses}
    clauses = audit_data.get("clauses")
    if not isinstance(clauses, list):
        clauses = []
        audit_data["clauses"] = clauses

    # 1. Xác minh số Điều trong bảng kết quả & tính độ phủ (Coverage)
    covered_nums: set[str] = set()
    verified_clause_count = 0
    unverified_refs: list[str] = []

    for cl in clauses:
        if not isinstance(cl, dict):
            continue
        ref_str = str(cl.get("ref") or cl.get("clause") or cl.get("name") or "")
        m = _CLAUSE_NUM_RE.search(ref_str)
        if extracted_nums:
            if m and m.group(1) in extracted_nums:
                cl["verified_in_doc"] = True
                covered_nums.add(m.group(1))
                verified_clause_count += 1
            else:
                cl["verified_in_doc"] = False
                if ref_str:
                    unverified_refs.append(ref_str)
        else:
            # Hợp đồng dạng văn bản tự do không đánh số "Điều 1, 2..."
            cl["verified_in_doc"] = True
            verified_clause_count += 1

    missed_clauses = [
        f"{c['ref']}{(': ' + c['title']) if c.get('title') else ''}"
        for c in extracted_clauses
        if c["number"] not in covered_nums
    ]

    # 2. Tự đồng bộ số đếm rủi ro (tránh tình trạng số tóm tắt mâu thuẫn với bảng chi tiết)
    if clauses:
        counts = {"high": 0, "medium": 0, "low": 0}
        for cl in clauses:
            if isinstance(cl, dict):
                sev = _normalize_severity(cl.get("status") or cl.get("severity") or cl.get("level") or "")
                counts[sev] += 1
        audit_data["risk_counts"] = counts
        audit_data["clauses_reviewed"] = max(len(clauses), len(covered_nums))

    # 3. Xác minh trích dẫn nguyên văn (source_quote)
    raw_quote = str(audit_data.get("source_quote") or "")
    is_exact_quote, quote_score, best_match = _find_best_matching_sentence(raw_quote, cleaned_text)
    quote_verified = is_exact_quote
    quote_auto_corrected = False
    if raw_quote and not is_exact_quote and quote_score >= 0.55 and best_match:
        # LLM diễn đạt lệch so với bản gốc -> tự động neo lại NGUYÊN VĂN 100% câu khớp nhất từ hợp đồng gốc
        audit_data["source_quote"] = best_match
        quote_verified = True
        quote_auto_corrected = True

    # 4. Xác minh số Điều luật trích dẫn so với kho Ground-Truth RAG
    rag_article_nums: set[str] = set()
    for law in (retrieved_laws or []):
        for num in re.findall(r"\d+", str(law.get("article") or "")):
            rag_article_nums.add(num)

    # Gom toàn bộ text phân tích để kiểm tra các điều luật được trích dẫn
    citation_corpus = " ".join([
        str(audit_data.get("executive_summary") or ""),
        str(audit_data.get("recommendation") or ""),
        " ".join(str(c.get("note") or "") for c in clauses if isinstance(c, dict)),
    ])
    cited_nums = set(_LAW_ARTICLE_RE.findall(citation_corpus))
    # Loại trừ các số Điều của chính hợp đồng (tránh nhầm "Điều 5" của hợp đồng với "Điều 5" của luật)
    cited_law_nums = {n for n in cited_nums if n in rag_article_nums or (int(n) >= 50 and n not in extracted_nums)}
    verified_law_nums = sorted(cited_law_nums & rag_article_nums, key=lambda x: int(x))
    ungrounded_law_nums = sorted(cited_law_nums - rag_article_nums, key=lambda x: int(x))

    # 5. Gắn báo cáo Verification Report vào output để Frontend & Exporter hiển thị minh bạch
    total_extracted = len(extracted_clauses)
    coverage_pct = round((len(covered_nums) / total_extracted) * 100, 1) if total_extracted > 0 else 100.0

    warnings: list[str] = []
    if missed_clauses:
        warnings.append(f"Còn {len(missed_clauses)} điều khoản chưa được liệt kê chi tiết trong bảng.")
    if unverified_refs:
        warnings.append(f"Tham chiếu không khớp số Điều gốc: {', '.join(unverified_refs[:3])}.")
    if raw_quote and not quote_verified:
        warnings.append("Câu trích dẫn nguyên văn có độ khớp thấp, cần đối chiếu bản gốc.")
    if ungrounded_law_nums:
        warnings.append(f"Điều luật trích ngoài kho RAG hiện tại: Điều {', '.join(ungrounded_law_nums)}.")

    audit_data["verification"] = {
        "status": "verified" if not warnings else "needs_review",
        "extracted_clauses_count": total_extracted,
        "covered_clauses_count": len(covered_nums) if total_extracted > 0 else len(clauses),
        "coverage_pct": coverage_pct,
        "missed_clauses": missed_clauses,
        "unverified_clause_refs": unverified_refs,
        "quote_verified": quote_verified,
        "quote_match_score": quote_score,
        "quote_auto_corrected": quote_auto_corrected,
        "rag_laws_checked": len(retrieved_laws or []),
        "verified_law_articles": [f"Điều {n}" for n in verified_law_nums],
        "ungrounded_law_articles": [f"Điều {n}" for n in ungrounded_law_nums],
        "warnings": warnings,
    }
    return audit_data
