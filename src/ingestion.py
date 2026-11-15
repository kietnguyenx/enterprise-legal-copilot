import io
from pypdf import PdfReader
from docx import Document


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Đọc file PDF"""
    reader = PdfReader(io.BytesIO(file_bytes))
    full_text = ""
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            full_text += f"\n--- Trang {i+1} ---\n" + text
    return full_text


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Đọc file Word (.docx) bao gồm cả đoạn văn và bảng biểu"""
    doc = Document(io.BytesIO(file_bytes))
    full_text = []

    for para in doc.paragraphs:
        if para.text.strip():
            full_text.append(para.text)

    for table in doc.tables:
        for row in table.rows:
            row_data = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_data:
                full_text.append(" | ".join(row_data))

    return "\n".join(full_text)


def extract_text(file_obj) -> str:
    """Hàm thông minh: Tự nhận diện đuôi file để đọc PDF, DOCX, TXT, CSV, MD"""
    file_bytes = file_obj.read()
    if len(file_bytes) < 20:
        raise ValueError("File này bị rỗng hoặc dung lượng quá nhỏ!")

    file_name = file_obj.name.lower()
    if file_name.endswith(".pdf"):
        text = extract_text_from_pdf(file_bytes)
    elif file_name.endswith(".docx"):
        text = extract_text_from_docx(file_bytes)
    elif file_name.endswith((".txt", ".csv", ".md")):
        text = file_bytes.decode("utf-8", errors="ignore")
    else:
        raise ValueError("Hệ thống hỗ trợ định dạng .pdf, .docx, .txt, .csv, .md")

    if not text.strip():
        raise ValueError("Không tìm thấy nội dung chữ trong tài liệu này!")

    return text
