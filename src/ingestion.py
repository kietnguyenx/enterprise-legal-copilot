import io
import os
import logging
from pypdf import PdfReader
from docx import Document

logger = logging.getLogger("securedoc.ingestion")

_IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}

_OCR_PROMPT = (
    "Bạn là hệ thống OCR pháp lý chuyên nghiệp. Hãy trích xuất TOÀN BỘ văn bản tiếng Việt "
    "(bao gồm số điều, khoản, bảng biểu, số tiền, ngày tháng và thông tin các bên) từ tài liệu hợp đồng "
    "hoặc hình ảnh chụp/scan này một cách chính xác tuyệt đối, giữ nguyên cấu trúc các Điều/Khoản. "
    "Chỉ trả về nội dung văn bản đã trích xuất, không thêm lời bình luận."
)


def _ocr_with_gemini_vision(file_bytes: bytes, mime_type: str) -> str:
    """Sử dụng Gemini Multimodal Vision để đọc chữ từ ảnh chụp hợp đồng hoặc PDF scan dấu đỏ."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("Tài liệu dạng ảnh/PDF scan cần cấu hình GEMINI_API_KEY để chạy OCR tự động.")

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        part = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
        for model_name in ("gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-2.5-flash"):
            try:
                resp = client.models.generate_content(
                    model=model_name,
                    contents=[part, _OCR_PROMPT],
                )
                text = (getattr(resp, "text", None) or "").strip()
                if text:
                    logger.info(f"✅ OCR Gemini Vision ({model_name}) trích xuất thành công {len(text)} ký tự.")
                    return text
            except Exception as model_err:
                logger.warning(f"OCR model {model_name} lỗi ({model_err}), thử model dự phòng...")
        raise ValueError("Gemini Vision OCR không thể đọc được chữ từ tài liệu này.")
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Lỗi khi chạy OCR tài liệu scan/ảnh: {e}")


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Đọc file PDF (tự động chuyển sang Gemini Vision OCR nếu là PDF scan không có lớp chữ)."""
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
    except Exception as e:
        raise ValueError(f"Tệp PDF bị hỏng hoặc không đúng định dạng: {e}")

    if reader.is_encrypted:
        raise ValueError("Tệp PDF đang được bảo vệ bằng mật khẩu. Vui lòng gỡ mật khẩu trước khi tải lên.")

    full_text = ""
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            full_text += f"\n--- Trang {i+1} ---\n" + text

    # Nếu PDF scan không có lớp chữ (hoặc quá ít chữ) -> tự động kích hoạt Gemini Vision OCR
    if len(full_text.strip()) < 30:
        logger.info("🔍 Phát hiện PDF dạng scan/ảnh, tự động kích hoạt Gemini Vision OCR...")
        return _ocr_with_gemini_vision(file_bytes, "application/pdf")

    return full_text


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Đọc file Word (.docx) bao gồm cả đoạn văn và bảng biểu."""
    try:
        doc = Document(io.BytesIO(file_bytes))
    except Exception as e:
        raise ValueError(f"Tệp Word (.docx) bị hỏng hoặc không đúng định dạng: {e}")

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
    """Hàm thông minh: Tự nhận diện đuôi file để đọc PDF, DOCX, TXT, CSV, MD và Ảnh OCR (PNG/JPG/WEBP)."""
    file_bytes = file_obj.read()
    if len(file_bytes) < 20:
        raise ValueError("File này bị rỗng hoặc dung lượng quá nhỏ!")

    file_name = (getattr(file_obj, "name", None) or "").lower()
    if file_name.endswith(".pdf"):
        text = extract_text_from_pdf(file_bytes)
    elif file_name.endswith(".docx"):
        text = extract_text_from_docx(file_bytes)
    elif file_name.endswith((".txt", ".csv", ".md")):
        # Hỗ trợ cả UTF-8-SIG (BOM) và UTF-16 từ Excel Windows
        if file_bytes.startswith((b"\xff\xfe", b"\xfe\xff")):
            text = file_bytes.decode("utf-16", errors="ignore")
        else:
            text = file_bytes.decode("utf-8-sig", errors="ignore")
    else:
        matched_mime = next((mime for ext, mime in _IMAGE_MIME_TYPES.items() if file_name.endswith(ext)), None)
        if matched_mime:
            text = _ocr_with_gemini_vision(file_bytes, matched_mime)
        else:
            raise ValueError("Hệ thống hỗ trợ định dạng .pdf, .docx, .txt, .csv, .md và ảnh hợp đồng (.png, .jpg, .jpeg, .webp)")

    if not text.strip():
        raise ValueError("Không tìm thấy nội dung chữ trong tài liệu này!")

    return text
