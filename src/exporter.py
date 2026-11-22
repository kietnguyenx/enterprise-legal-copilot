# src/exporter.py — Corporate Legal Audit Multi-Format Generator (.docx, .pdf A4, .csv, .md, .json)
import csv
import html
import io
import json
import re
from datetime import datetime
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH


def _clean_text(text: str) -> str:
    """Loại bỏ các thẻ HTML đơn giản nếu có"""
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", str(text)).strip()


def generate_audit_docx(file_name: str, audit_data: dict) -> bytes:
    """Tạo file Word (.docx) Báo cáo Thẩm định Hợp đồng chuẩn Enterprise"""
    doc = Document()

    # Thiết lập lề 2cm tiêu chuẩn văn phòng
    sections = doc.sections
    for s in sections:
        s.top_margin = Inches(0.8)
        s.bottom_margin = Inches(0.8)
        s.left_margin = Inches(0.8)
        s.right_margin = Inches(0.8)

    # 1. TIÊU ĐỀ BÁO CÁO
    title = doc.add_heading("BÁO CÁO THẨM ĐỊNH RỦI RO PHÁP LÝ & KỊCH BẢN ĐÀM PHÁN", level=1)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_meta = meta.add_run(
        f"Tài liệu thẩm định: {file_name}  |  Ngày xuất: {datetime.now().strftime('%d/%m/%Y %H:%M')}  |  SecureDoc AI Enterprise"
    )
    run_meta.font.size = Pt(9.5)
    run_meta.font.color.rgb = RGBColor(100, 116, 139)

    doc.add_paragraph("—" * 60).alignment = WD_ALIGN_PARAGRAPH.CENTER

    # 2. ĐIỂM RỦI RO TỔNG THỂ & KHUYẾN NGHỊ HÀNH ĐỘNG
    risk_score = audit_data.get("risk_score", 0)
    risk_level = audit_data.get("risk_level", "CHƯA XẾP LOẠI")
    
    doc.add_heading(f"1. ĐIỂM SỐ RỦI RO PHÁP LÝ: {risk_score}/100 ({risk_level})", level=2)
    
    counts = audit_data.get("risk_counts") or {}
    p_stat = doc.add_paragraph()
    p_stat.add_run(f"• Số điều khoản rà soát: {audit_data.get('clauses_reviewed', len(audit_data.get('clauses', [])))}\n")
    p_stat.add_run(f"• Rủi ro Cao: {counts.get('high', 0)}  |  Trung bình: {counts.get('medium', 0)}  |  Thấp: {counts.get('low', 0)}\n")

    exec_summary = audit_data.get("executive_summary", "")
    if exec_summary:
        doc.add_heading("2. TÓM TẮT ĐIỀU HÀNH (EXECUTIVE SUMMARY)", level=2)
        doc.add_paragraph(_clean_text(exec_summary))

    rec = audit_data.get("recommendation", "")
    if rec:
        p_rec = doc.add_paragraph()
        run_rec_title = p_rec.add_run("Khuyến nghị cốt tử của Giám đốc Pháp chế: ")
        run_rec_title.bold = True
        run_rec_title.font.color.rgb = RGBColor(180, 40, 20)
        p_rec.add_run(_clean_text(rec))

    # 3. NOTEBOOKLM STUDIO: TỔNG QUAN, TIẾN ĐỘ & ĐIỀU KHOẢN BỊ BỎ QUÊN
    studio = audit_data.get("notebooklm_studio") or {}
    briefing = studio.get("executive_briefing") or []
    milestones = studio.get("timeline_milestones") or []
    missing = studio.get("missing_clauses") or []
    faqs = studio.get("suggested_faq") or []

    if briefing or milestones or missing:
        doc.add_heading("3. HỒ SƠ ĐIỀU HÀNH CHUYÊN SÂU (NOTEBOOKLM STUDIO)", level=2)
        
        if briefing:
            doc.add_heading("3.1. Các điểm then chốt hợp đồng (Key Briefing Points):", level=3)
            for item in briefing:
                doc.add_paragraph(_clean_text(item), style="List Bullet")

        if milestones:
            doc.add_heading("3.2. Dòng thời gian & Các mốc nghiệm thu (Timeline Milestones):", level=3)
            t_ms = doc.add_table(rows=1, cols=2)
            t_ms.style = "Table Grid"
            t_ms.rows[0].cells[0].text = "Sự kiện / Mốc hợp đồng"
            t_ms.rows[0].cells[1].text = "Thời hạn cụ thể"
            for m in milestones:
                row = t_ms.add_row().cells
                row[0].text = _clean_text(m.get("event", ""))
                row[1].text = _clean_text(m.get("deadline", ""))

        if missing:
            doc.add_heading("3.3. Các điều khoản thiết yếu bị bỏ quên (Missing Clauses):", level=3)
            for item in missing:
                p_miss = doc.add_paragraph(style="List Bullet")
                p_miss.add_run("⚠️ ").font.color.rgb = RGBColor(220, 38, 38)
                p_miss.add_run(_clean_text(item))

        if faqs:
            doc.add_heading("3.4. Bộ câu hỏi trọng điểm đối chiếu (Key Legal FAQ):", level=3)
            for f in faqs:
                p_q = doc.add_paragraph()
                p_q.add_run(f"Q: {_clean_text(f.get('question', ''))}").bold = True
                doc.add_paragraph(f"A: {_clean_text(f.get('answer', ''))}")

    # 4. MA TRẬN 3 KỊCH BẢN ĐÀM PHÁN (SCENARIOS MATRIX)
    scenarios = audit_data.get("negotiation_scenarios") or {}
    if scenarios:
        doc.add_heading("4. CHIẾN LƯỢC & MA TRẬN 3 KỊCH BẢN ĐÀM PHÁN", level=2)
        
        aggr = scenarios.get("aggressive") or {}
        bal = scenarios.get("balanced") or {}
        cons = scenarios.get("conservative") or {}

        # Kịch bản 1: Cứng rắn
        p_a = doc.add_paragraph()
        run_a = p_a.add_run("🔴 Kịch bản Cứng rắn (Thế Áp Đảo / Vị thế mạnh): ")
        run_a.bold = True
        run_a.font.color.rgb = RGBColor(220, 38, 38)
        p_a.add_run(_clean_text(aggr.get("strategy", "")))

        # Kịch bản 2: Cân bằng
        p_b = doc.add_paragraph()
        run_b = p_b.add_run("🟡 Kịch bản Cân bằng (Win - Win / Tuân thủ trần pháp luật): ")
        run_b.bold = True
        run_b.font.color.rgb = RGBColor(202, 138, 4)
        p_b.add_run(_clean_text(bal.get("strategy", "")))

        # Kịch bản 3: Dự phòng
        p_c = doc.add_paragraph()
        run_c = p_c.add_run("🟢 Kịch bản Dự phòng (Thế Yếu / Phòng thủ giảm thiểu rủi ro): ")
        run_c.bold = True
        run_c.font.color.rgb = RGBColor(22, 163, 74)
        p_c.add_run(_clean_text(cons.get("strategy", "")))

    # 5. MA TRẬN BẢNG RỦI RO ĐIỀU KHOẢN (CLAUSE AUDIT MATRIX)
    clauses = audit_data.get("clauses") or []
    if clauses:
        doc.add_heading("5. BẢNG CHI TIẾT RỦI RO TỪNG ĐIỀU KHOẢN (CLAUSE MATRIX)", level=2)
        table = doc.add_table(rows=1, cols=4)
        table.style = "Table Grid"
        hdr = table.rows[0].cells
        hdr[0].text = "Điều khoản"
        hdr[1].text = "Chủ đề / Nội dung"
        hdr[2].text = "Mức độ rủi ro"
        hdr[3].text = "Hành động khuyến nghị"

        for c in clauses:
            row = table.add_row().cells
            row[0].text = _clean_text(c.get("ref", ""))
            row[1].text = _clean_text(c.get("topic", ""))
            row[2].text = _clean_text(c.get("status", ""))
            action_text = _clean_text(c.get("action", ""))
            note_text = _clean_text(c.get("note", ""))
            row[3].text = f"{action_text}\n({note_text})" if note_text else action_text

    # 6. TRÍCH DẪN NGUYÊN VĂN & SỬA ĐỔI REDLINE DIFF
    quote = audit_data.get("source_quote", "")
    redline = audit_data.get("redline_diff") or {}
    if quote or redline:
        doc.add_heading("6. TRÍCH DẪN ĐIỀU KHOẢN NGUY HIỂM & ĐỀ XUẤT SỬA ĐỔI (REDLINE DIFF)", level=2)
        if quote:
            p_q = doc.add_paragraph(_clean_text(quote))
            p_q.style = "Intense Quote"

        if redline:
            p_orig = doc.add_paragraph()
            p_orig.add_run("• Bản gốc bất lợi: ").bold = True
            run_del = p_orig.add_run(_clean_text(redline.get("original", "")))
            run_del.font.strike = True
            run_del.font.color.rgb = RGBColor(180, 40, 20)

            p_rev = doc.add_paragraph()
            p_rev.add_run("• Đề xuất sửa đổi: ").bold = True
            run_ins = p_rev.add_run(_clean_text(redline.get("revised", "")))
            run_ins.font.underline = True
            run_ins.font.color.rgb = RGBColor(22, 163, 74)

    # 7. CĂN CỨ PHÁP LUẬT ĐỐI CHIẾU
    laws = audit_data.get("retrieved_laws") or []
    if laws:
        doc.add_heading("7. CĂN CỨ PHÁP LUẬT VIỆT NAM ĐỐI CHIẾU (LEGAL RAG)", level=2)
        for l in laws:
            p_l = doc.add_paragraph(style="List Bullet")
            p_l.add_run(f"{l.get('law_name', '')} - {l.get('article', '')}: {l.get('title', '')}").bold = True

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


# ================= MULTI-FORMAT EXPORTERS (CSV / MARKDOWN / JSON / PDF A4) =================


def _get_summary(audit_data: dict) -> str:
    return _clean_text(audit_data.get("executive_summary") or audit_data.get("summary") or "")


def _extract_clause_fields(c: dict) -> tuple[str, str, str, str]:
    ref = _clean_text(c.get("ref") or c.get("clause") or c.get("name") or "")
    topic = _clean_text(c.get("topic") or c.get("content") or c.get("summary") or c.get("issue") or "")
    level = _clean_text(c.get("status") or c.get("severity") or c.get("level") or "")
    action = _clean_text(c.get("action") or c.get("suggestion") or "")
    note = _clean_text(c.get("note") or "")
    full_action = f"{action} ({note})" if (action and note) else (action or note)
    return ref, topic, level, full_action


def _extract_scenarios(audit_data: dict) -> dict[str, str]:
    raw = audit_data.get("negotiation_scenarios") or audit_data.get("scenarios") or {}
    if not isinstance(raw, dict):
        return {}
    out = {}
    for key in ("aggressive", "balanced", "conservative"):
        val = raw.get(key)
        if isinstance(val, dict):
            text = _clean_text(val.get("strategy") or val.get("description") or "")
        else:
            text = _clean_text(val or "")
        if text:
            out[key] = text
    return out


def generate_audit_csv(file_name: str, audit_data: dict) -> bytes:
    """Xuất bảng tổng hợp điều khoản rủi ro định dạng CSV (UTF-8-SIG BOM mở trực tiếp trên Excel không lỗi font)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Tài liệu", "Điểm rủi ro (/100)", "Mức độ tổng thể", "Điều khoản", "Chủ đề / Nội dung", "Mức độ rủi ro", "Khuyến nghị xử lý"])

    risk_score = audit_data.get("risk_score", 0)
    risk_level = audit_data.get("risk_level", "N/A")
    clauses = audit_data.get("clauses") or []
    if clauses:
        for c in clauses:
            ref, topic, level, full_action = _extract_clause_fields(c)
            writer.writerow([
                file_name,
                risk_score,
                risk_level,
                ref,
                topic,
                level,
                full_action,
            ])
    else:
        writer.writerow([
            file_name,
            risk_score,
            risk_level,
            "Tổng quan",
            _get_summary(audit_data),
            risk_level,
            _clean_text(audit_data.get("recommendation", "")),
        ])

    return buf.getvalue().encode("utf-8-sig")


def generate_audit_markdown(file_name: str, audit_data: dict) -> bytes:
    """Xuất báo cáo thẩm định chuẩn Markdown (.md) dùng cho Notion / GitHub / Confluence."""
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    summary_text = _get_summary(audit_data) or "Chưa có dữ liệu."
    lines = [
        f"# Báo Cáo Thẩm Định Pháp Lý — {file_name}",
        f"*Thời điểm xuất: {now_str} · Hệ thống SecureDoc AI*",
        "",
        f"- **Điểm rủi ro:** `{audit_data.get('risk_score', 0)}/100` ({audit_data.get('risk_level', 'N/A')})",
        "",
        "## 1. Nhận Định Tổng Quan",
        summary_text,
        "",
        f"**Khuyến nghị hành động:** {_clean_text(audit_data.get('recommendation', ''))}",
        "",
    ]

    clauses = audit_data.get("clauses") or []
    if clauses:
        lines.append("## 2. Bảng Chi Tiết Điều Khoản Rủi Ro")
        lines.append("| Điều khoản | Chủ đề / Nội dung | Mức độ | Hành động khuyến nghị |")
        lines.append("| :--- | :--- | :---: | :--- |")
        for c in clauses:
            ref, topic, level, full_action = _extract_clause_fields(c)
            lines.append(
                f"| {ref.replace('|', '/')} | {topic.replace('|', '/')} | {level.replace('|', '/')} | {full_action.replace('|', '/')} |"
            )
        lines.append("")

    redline = audit_data.get("redline_diff") or {}
    if redline.get("original") or redline.get("revised"):
        lines.append("## 3. Đề Xuất Sửa Đổi Điều Khoản (Redline Diff)")
        if redline.get("original"):
            lines.append(f"- **Bản gốc bất lợi:** ~~{_clean_text(redline['original'])}~~")
        if redline.get("revised"):
            lines.append(f"- **Đề xuất sửa đổi:** **{_clean_text(redline['revised'])}**")
        lines.append("")

    scenarios = _extract_scenarios(audit_data)
    if scenarios:
        lines.append("## 4. Ma Trận 3 Kịch Bản Đàm Phán")
        if scenarios.get("aggressive"):
            lines.append(f"- **🔴 Kịch bản Cứng rắn:** {scenarios['aggressive']}")
        if scenarios.get("balanced"):
            lines.append(f"- **🟡 Kịch bản Cân bằng (Win-Win):** {scenarios['balanced']}")
        if scenarios.get("conservative"):
            lines.append(f"- **🟢 Kịch bản Phòng thủ:** {scenarios['conservative']}")
        lines.append("")

    laws = audit_data.get("retrieved_laws") or []
    if laws:
        lines.append("## 5. Căn Cứ Pháp Luật Việt Nam Đối Chiếu (Legal RAG)")
        for l in laws:
            lines.append(f"- **{l.get('law_name', '')} — {l.get('article', '')}:** {l.get('title', '')}")

    return "\n".join(lines).encode("utf-8")


def generate_audit_json(file_name: str, audit_data: dict) -> bytes:
    """Xuất toàn bộ dữ liệu thẩm định dạng JSON có cấu trúc chuẩn tích hợp ERP/API."""
    payload = {
        "exported_at": datetime.now().isoformat(),
        "system": "SecureDoc AI — Enterprise Legal Copilot",
        "file_name": file_name,
        "audit": audit_data,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def generate_audit_print_html(file_name: str, audit_data: dict) -> bytes:
    """Tạo bản báo cáo chuẩn khổ giấy A4 (tiếng Việt 100% sắc nét) tự động mở hộp thoại Lưu/In PDF."""
    esc = lambda v: html.escape(_clean_text(str(v or "")))
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    score = int(audit_data.get("risk_score", 0) or 0)
    level = esc(audit_data.get("risk_level", "N/A"))
    score_color = "#DC2626" if score >= 65 else ("#D97706" if score >= 35 else "#059669")

    clause_rows = ""
    for c in (audit_data.get("clauses") or []):
        ref, topic, sev, full_action = _extract_clause_fields(c)
        clause_rows += f"""
        <tr>
          <td><b>{esc(ref)}</b></td>
          <td>{esc(topic)}</td>
          <td><span class="badge">{esc(sev)}</span></td>
          <td>{esc(full_action)}</td>
        </tr>"""

    redline = audit_data.get("redline_diff") or {}
    redline_html = ""
    if redline.get("original") or redline.get("revised"):
        redline_html = f"""
        <h2>3. Đề Xuất Sửa Đổi Điều Khoản (Redline Diff)</h2>
        <div class="redline-box">
          <p><b style="color:#DC2626;">• Bản gốc bất lợi:</b> <del style="color:#B91C1C;">{esc(redline.get('original'))}</del></p>
          <p><b style="color:#059669;">• Đề xuất sửa đổi:</b> <span style="color:#047857;font-weight:600;">{esc(redline.get('revised'))}</span></p>
        </div>"""

    scenarios = _extract_scenarios(audit_data)
    scenarios_html = ""
    if scenarios:
        scenarios_html = f"""
        <h2>4. Ma Trận 3 Kịch Bản Đàm Phán</h2>
        <div class="grid3">
          <div class="box red"><b>🔴 Cứng rắn</b><p>{esc(scenarios.get('aggressive'))}</p></div>
          <div class="box amber"><b>🟡 Cân bằng (Win-Win)</b><p>{esc(scenarios.get('balanced'))}</p></div>
          <div class="box green"><b>🟢 Phòng thủ</b><p>{esc(scenarios.get('conservative'))}</p></div>
        </div>"""

    laws_html = ""
    laws = audit_data.get("retrieved_laws") or []
    if laws:
        items = "".join(f"<li><b>{esc(l.get('law_name'))} — {esc(l.get('article'))}:</b> {esc(l.get('title'))}</li>" for l in laws)
        laws_html = f"<h2>5. Căn Cứ Pháp Luật Việt Nam Đối Chiếu (Legal RAG)</h2><ul>{items}</ul>"

    doc_html = f"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<title>Báo Cáo Thẩm Định Pháp Lý — {esc(file_name)}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>
  @page {{ size: A4; margin: 16mm; }}
  body {{ font-family: 'Inter', system-ui, sans-serif; color: #0F172A; margin: 0; padding: 24px; background: #F8FAFC; }}
  .sheet {{ max-width: 820px; margin: 0 auto; background: #fff; padding: 36px 40px; border-radius: 14px; box-shadow: 0 8px 30px rgba(15,23,42,0.08); }}
  .toolbar {{ max-width: 820px; margin: 0 auto 14px; display: flex; justify-content: flex-end; gap: 10px; }}
  .btn {{ padding: 9px 18px; border-radius: 999px; border: none; background: #0047FF; color: #fff; font-weight: 600; font-size: 13px; cursor: pointer; }}
  .head {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #0047FF; padding-bottom: 14px; margin-bottom: 20px; }}
  .brand {{ font-size: 18px; font-weight: 700; color: #0047FF; }}
  .meta {{ font-size: 12px; color: #64748B; text-align: right; }}
  .score-card {{ display: flex; align-items: center; gap: 18px; padding: 16px 20px; border-radius: 12px; background: #F8FAFF; border: 1px solid #DBEAFE; margin-bottom: 20px; }}
  .score-num {{ font-size: 32px; font-weight: 700; color: {score_color}; min-width: 96px; text-align: center; }}
  h1 {{ font-size: 20px; margin: 0 0 6px; color: #0F2147; }}
  h2 {{ font-size: 14.5px; color: #0047FF; margin: 22px 0 10px; text-transform: uppercase; letter-spacing: .03em; }}
  p, li {{ font-size: 13px; line-height: 1.6; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; margin-top: 8px; }}
  th, td {{ border: 1px solid #E2E8F0; padding: 8px 10px; text-align: left; vertical-align: top; }}
  th {{ background: #F1F5F9; font-weight: 700; color: #0F2147; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 999px; background: #EFF6FF; color: #1E40AF; font-weight: 600; font-size: 11.5px; }}
  .redline-box {{ padding: 12px 16px; border-radius: 10px; background: #F8FAFC; border: 1px solid #E2E8F0; }}
  .grid3 {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }}
  .box {{ padding: 12px; border-radius: 10px; border: 1px solid #E2E8F0; font-size: 12.5px; }}
  .box.red {{ background: #FEF2F2; border-color: #FECACA; }}
  .box.amber {{ background: #FFFBEB; border-color: #FDE68A; }}
  .box.green {{ background: #ECFDF5; border-color: #A7F3D0; }}
  .footer {{ margin-top: 28px; padding-top: 12px; border-top: 1px solid #E2E8F0; font-size: 11px; color: #94A3B8; text-align: center; }}
  @media print {{ body {{ background: #fff; padding: 0; }} .sheet {{ box-shadow: none; padding: 0; }} .toolbar {{ display: none; }} }}
</style>
</head>
<body>
  <div class="toolbar">
    <button class="btn" onclick="window.print()">🖨️ Lưu / In báo cáo PDF (A4)</button>
  </div>
  <div class="sheet">
    <div class="head">
      <div><div class="brand">✦ SecureDoc AI</div><div style="font-size:12px;color:#475569;">Báo Cáo Thẩm Định Rủi Ro &amp; Đối Chiếu Pháp Luật Việt Nam</div></div>
      <div class="meta"><b>Tài liệu:</b> {esc(file_name)}<br><b>Ngày xuất:</b> {now_str}</div>
    </div>
    <div class="score-card">
      <div class="score-num">{score}/100</div>
      <div><div style="font-weight:700;font-size:15px;color:#0F2147;">Mức độ rủi ro: {level}</div><div style="font-size:12.5px;color:#475569;margin-top:4px;">{esc(audit_data.get('recommendation'))}</div></div>
    </div>
    <h2>1. Nhận Định Pháp Lý Tổng Quan</h2>
    <p>{esc(_get_summary(audit_data))}</p>
    <h2>2. Bảng Chi Tiết Điều Khoản Rủi Ro</h2>
    <table><thead><tr><th style="width:16%">Điều khoản</th><th style="width:40%">Chủ đề / Nội dung</th><th style="width:14%">Mức độ</th><th style="width:30%">Đề xuất xử lý</th></tr></thead><tbody>{clause_rows or '<tr><td colspan="4">Không phát hiện điều khoản rủi ro đáng kể.</td></tr>'}</tbody></table>
    {redline_html}
    {scenarios_html}
    {laws_html}
    <div class="footer">Tài liệu được tạo tự động bởi SecureDoc AI · Bảo mật PII Token Vault &amp; Legal Vector RAG</div>
  </div>
  <script>window.addEventListener('load', () => setTimeout(() => window.print(), 350));</script>
</body>
</html>"""
    return doc_html.encode("utf-8")
