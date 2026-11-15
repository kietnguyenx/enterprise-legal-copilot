# src/exporter.py — Corporate Legal Audit Word (.docx) Generator
import io
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
