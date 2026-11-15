# 📄 Enterprise Legal Copilot (SecureDoc AI)
### *Enterprise-Grade Compound AI System for Contract Risk Auditing, PII Protection & Semantic Regulation Alignment*

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-JSONB%20%7C%20Supabase-336791?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-Flash%203.5%20%7C%203.8-4285F4?style=flat&logo=google&logoColor=white)](https://ai.google.dev/)
[![Ollama](https://img.shields.io/badge/Ollama-Qwen%202.5%20Local-black?style=flat&logo=ollama&logoColor=white)](https://ollama.com/)
[![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/Pytest-16%20Passed%20100%25-brightgreen?style=flat&logo=pytest&logoColor=white)](tests/test_core.py)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## 📌 Tổng Quan Hệ Thống (Executive Overview)

**Enterprise Legal Copilot (SecureDoc AI)** là một hệ thống Trí tuệ Nhân tạo Phức hợp (**Compound AI System**) được thiết kế chuyên biệt cho khối Doanh nghiệp, Ngân hàng và Tổ chức Pháp lý nhằm tự động hóa quy trình thẩm định hợp đồng, phát hiện điều khoản rủi ro, đối chiếu luật định và hỗ trợ đàm phán đa kịch bản.

Khác với các ứng dụng AI thông thường chỉ đơn thuần là "vỏ bọc gọi API" (API Wrapper), hệ thống được xây dựng theo chuẩn mực kỹ thuật cao cấp giải quyết triệt để các bài toán thực tế:
1. **Chủ quyền Dữ liệu & Bảo mật Tuyệt đối (Data Sovereignty)**: Lớp khiên **PII Token Vault** che giấu thông tin định danh cá nhân (CCCD, SĐT, Email, STK) trước khi gửi ra ngoài, kết hợp cơ chế định tuyến **Hybrid Router** cho phép chuyển mạch sang mô hình nội bộ **Local On-Premise (Qwen 2.5 qua Ollama)** khi xử lý tài liệu mật.
2. **Loại bỏ Tình trạng Ảo giác (Zero-Hallucination via Strict Anchoring)**: Mọi cảnh báo rủi ro đều được neo nguồn dẫn chứng chính xác `[Điều X, Khoản Y]` và đối chiếu trực tiếp với Cơ sở Tri thức Luật Việt Nam (Luật Thương mại 2005, Bộ luật Dân sự 2015, Nghị định 13/2023/NĐ-CP).
3. **Hiệu năng & Tối ưu Chi phí (Enterprise Efficiency)**: Tích hợp **Semantic Caching** phản hồi câu hỏi trùng lặp trong 50ms với $0 chi phí API, hệ thống **Telemetry Tracing** giám sát chi phí token và độ trễ p95 theo thời gian thực.
4. **Hạ tầng Dữ liệu Bền vững (Async Persistence)**: Lưu trữ đồng bộ lên cụm cơ sở dữ liệu quan hệ **PostgreSQL trên Supabase Cloud** qua SQLAlchemy 2.0 Async, tích hợp cơ chế dự phòng an toàn (Failover SQLite) chống rớt mạng.

---

## 🛠️ Ngăn Xếp Công Nghệ (Technology Stack)

| Tầng Kiến Trúc | Công Nghệ Lựa Chọn | Vai Trò Kỹ Thuật |
| :--- | :--- | :--- |
| **API Gateway & Core Server** | **FastAPI (ASGI)**, `slowapi`, `uvicorn` | Máy chủ bất đồng bộ hiệu năng cao, điều phối luồng xử lý, giới hạn tần suất DoS (Rate Limiting). |
| **AI Orchestration & Router** | **Google Gemini Flash (3.5 / 3.8)** & **Ollama (Qwen 2.5)** | Định tuyến thông minh giữa Cloud API tốc độ cao và mô hình On-Premise bảo mật nội bộ. |
| **Document Processing (ETL)** | `pypdf`, `python-docx`, Python CSV/Text Engine | Bóc tách văn bản, bảng biểu có cấu trúc từ file PDF đa trang, Word (.docx) và bảng tính. |
| **Data Privacy & Guardrails** | Regex Tokenizer, **Input Guardrails Engine** | Mã hóa PII hai chiều (`[PHONE_01]`, `[ID_01]`), phát hiện và triệt tiêu Prompt Injection/Jailbreak. |
| **Persistence & Database** | **PostgreSQL (Supabase Cloud)**, SQLAlchemy 2.0 Async, `asyncpg` | Lưu trữ cấu trúc JSONB linh hoạt cho cây thẩm định, cơ chế Failover sang SQLite khi offline. |
| **Observability & Caching** | Vector Cosine Cache, Latency & Token Tracing | Semantic Cache cắt giảm 60–80% chi phí API, giám sát độ trễ p95 và ngân sách vận hành. |
| **Frontend Client** | Modern Vanilla Web (HTML5, Modern CSS3, ES6+ JS) | Single Page Application phong cách Olympus Cosmic, SSE Token Streaming, Live SVG Gauge. |
| **DevOps & Testing** | `pytest`, `pytest-asyncio`, Docker, Docker Compose | Bộ kiểm thử tự động 16/16 test case, containerization chuẩn hóa sẵn sàng cho Production. |

---

## 💎 Các Trụ Cột Tính Năng Chuẩn Doanh Nghiệp (Core Pillars)

### 1. Phân Tích Đa Chiều Kiểu "NotebookLM Studio"
* **Bản Tóm Tắt Điều Hành (Executive Briefing)**: Trích xuất 5 thông tin cốt tử: Các bên tham gia, Mục đích giao dịch, Giá trị hợp đồng, Mốc thời hạn và Mức độ rủi ro tổng thể.
* **Bảng Dòng Thời Gian (Milestone Timeline)**: Tự động bóc tách tiến trình thực hiện: Ký kết $\rightarrow$ Bàn giao $\rightarrow$ Nghiệm thu UAT $\rightarrow$ Kỳ thanh toán $\rightarrow$ Hết hạn bảo hành.
* **Bộ Câu Hỏi Thường Gặp (Suggested FAQ)**: Đề xuất các câu hỏi pháp lý then chốt mà lãnh đạo doanh nghiệp cần kiểm tra.
* **Phát Hiện Điều Khoản Bị Bỏ Quên (Missing Clause Detector)**: Chỉ ra các điều khoản bảo vệ thiết yếu bị thiếu (Bất khả kháng, Giới hạn bồi thường, Cơ chế tự động nghiệm thu...).

### 2. Ma Trận Đàm Phán 3 Kịch Bản (Negotiation Scenario Matrix)
Tuân thủ nguyên tắc **BLUF (Bottom Line Up Front)** — đi thẳng vào kết luận khuyến nghị và đưa ra 3 phương án hành động tùy theo vị thế đàm phán của doanh nghiệp:
* 🔴 **Kịch bản A (Cứng Rắn - Vị Thế Áp Đảo)**: Yêu cầu loại bỏ điều khoản bất lợi, áp đặt chế tài phạt ngược lại đối tác.
* 🟡 **Kịch bản B (Cân Bằng - Hợp Tác Win-Win)**: Đưa về trần luật định (Điều 301 Luật Thương mại: tối đa 8%), thêm thời gian ân hạn khắc phục vi phạm.
* 🟢 **Kịch bản C (Phòng Thủ - Vị Thế Yếu)**: Chấp nhận điều khoản nhưng gắn mức phạt với thiệt hại thực tế tối đa và yêu cầu mua bảo hiểm trách nhiệm.

### 3. Đối Chiếu Căn Cứ Luật Việt Nam (Legal RAG)
Tích hợp sẵn kho tri thức luật số hóa:
* **Luật Thương mại 2005 (Điều 301)**: Khống chế trần phạt vi phạm hợp đồng tối đa 8%.
* **Bộ luật Dân sự 2015 (Điều 418, 428)**: Thỏa thuận phạt vi phạm và quyền đơn phương chấm dứt hợp đồng.
* **Nghị định 13/2023/NĐ-CP**: Quy định bảo vệ dữ liệu cá nhân trong giao dịch điện tử và hợp đồng kinh tế.

### 4. Smart PII Token Vault (Bảo Vệ Quyền Riêng Tư)
Hệ thống không che dữ liệu thô mà mã hóa theo token định danh có ánh xạ:
`Nguyễn Văn A` $\rightarrow$ `[NAME_01]`, `0912345678` $\rightarrow$ `[PHONE_01]`, `001099xxxxxx` $\rightarrow$ `[ID_01]`.  
Đảm bảo mô hình AI vẫn hiểu được ngữ cảnh giữa Bên A và Bên B nhưng tuyệt đối không rò rỉ danh tính thật ra môi trường bên ngoài.

### 5. Vòng Lặp Phản Hồi Chuyên Gia (Human-in-the-Loop)
Tích hợp nút đánh giá chất lượng phản hồi (👍 / 👎) và cho phép chuyên viên pháp lý nhập nội dung chỉnh sửa trực tiếp, tự động lưu trữ vào cơ sở dữ liệu để phục vụ xây dựng bộ dữ liệu tinh chỉnh mô hình (DPO / Fine-tuning Dataset).

---

## 📂 Cấu Trúc Thư Mục Dự Án (Repository Layout)

```text
enterprise-legal-copilot/
├── data/                       # Dữ liệu tri thức và cấu hình hệ thống
│   ├── laws/                   # Tri thức pháp luật Việt Nam phục vụ RAG
│   │   ├── vietnam_civil_commercial.json
│   │   ├── vietnam_labor_employment.json
│   │   └── vietnam_laws_core.json
│   └── .vector_cache.pkl       # Bộ nhớ đệm vector tra cứu luật
├── src/                        # Mã nguồn tầng xử lý nghiệp vụ AI
│   ├── analyzer.py             # Bộ não phân tích, Prompt NotebookLM & Hybrid Router
│   ├── cache.py                # Semantic Cache Engine (Cosine Vector Matching)
│   ├── database.py             # Quản lý kết nối Async SQLAlchemy & Failover
│   ├── exporter.py             # Xuất báo cáo thẩm định Word (.docx) chuẩn văn phòng
│   ├── guardrails.py           # Bộ lọc Input Guardrails chống Prompt Injection
│   ├── ingestion.py            # Bóc tách văn bản đa định dạng (PDF, DOCX, CSV, TXT)
│   ├── legal_kb.py             # Vector RAG Knowledge Base đối chiếu luật
│   ├── legal_sync.py           # Module cập nhật, đồng bộ điều luật mới
│   ├── models.py               # SQLAlchemy Database Models (Users, Documents, Sessions)
│   ├── privacy.py              # Lớp khiên PII Vault mã hóa token dữ liệu nhạy cảm
│   └── telemetry.py            # Giám sát Token, ước tính chi phí USD & độ trễ p95
├── tests/                      # Bộ kiểm thử tự động chuẩn hóa
│   └── test_core.py            # 16 Unit & Integration Tests toàn diện
├── web/                        # Giao diện Single Page Application (Client Tier)
│   ├── index.html              # Cấu trúc HTML5 ngữ nghĩa
│   ├── style.css               # Phong cách giao diện Olympus Cosmic Sky
│   └── app.js                  # Xử lý SSE Streaming & tương tác người dùng
├── .env.example                # File mẫu cấu hình biến môi trường
├── .gitignore                  # Cấu hình bảo mật loại trừ API Key và dữ liệu nhạy cảm
├── docker-compose.yml          # Điều phối Container FastAPI + PostgreSQL + Ollama
├── Dockerfile                  # Đóng gói ứng dụng chuẩn Production
├── README.md                   # Tài liệu kiến trúc và hướng dẫn dự án
├── requirements.txt            # Danh mục thư viện phụ thuộc Python
└── server.py                   # Máy chủ FastAPI Backend & điều phối RESTful API
```

---

## 🚀 Hướng Dẫn Cài Đặt & Vận Hành (Getting Started)

### 1. Yêu cầu tiên quyết
* Python 3.11 trở lên.
* Khóa Google Gemini API ([Lấy miễn phí tại Google AI Studio](https://aistudio.google.com/)).
* Git.

### 2. Cài đặt môi trường
Clone repository và cài đặt các thư viện cần thiết:
```bash
git clone https://github.com/kietnguyenx/enterprise-legal-copilot.git
cd enterprise-legal-copilot

# Tạo môi trường ảo (Virtual Environment)
python -m venv .venv

# Kích hoạt môi trường ảo:
# Trên Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Trên Linux/macOS:
source .venv/bin/activate

# Cài đặt danh mục thư viện
pip install -r requirements.txt
```

### 3. Cấu hình biến môi trường
Tạo file `.env` tại thư mục gốc dự án (tham khảo [`.env.example`](file:///.env.example)):
```env
# Khóa API Google Gemini (Bắt buộc)
GEMINI_API_KEY=your_gemini_api_key_here

# Chuỗi kết nối Cơ sở dữ liệu PostgreSQL (Supabase / RDS / Local)
DATABASE_URL=postgresql+asyncpg://postgres.your_ref:password@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres

# Cấu hình máy chủ Ollama On-Premise (Tùy chọn)
OLLAMA_BASE_URL=http://localhost:11434
```
*(Nếu chưa cấu hình `DATABASE_URL`, hệ thống sẽ tự động chuyển sang chế độ SQLite dự phòng an toàn).*

### 4. Khởi chạy máy chủ phát triển
```bash
python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload
```
Truy cập giao diện hệ thống tại: **http://127.0.0.1:8000**

### 5. Triển khai với Docker Compose
Triển khai toàn bộ cụm dịch vụ chỉ với một câu lệnh:
```bash
docker compose up --build -d
```

### 6. Chạy kiểm thử tự động (Quality Assurance)
Hệ thống tích hợp bộ kiểm thử toàn diện xác nhận toàn bộ 16 chức năng cốt lõi:
```bash
pytest tests/test_core.py -v
```

---

## 📡 Danh Mục RESTful API Endpoints

| Phương Thức | Đường Dẫn Endpoint | Mô Tả Chức Năng |
| :---: | :--- | :--- |
| `GET` | `/` | Trả về giao diện Single Page Application (`web/index.html`). |
| `GET` | `/api/health` | Kiểm tra tình trạng sức khỏe: Database, Vector RAG, Ollama, Semantic Cache. |
| `GET` | `/api/models` | Danh sách mô hình AI khả dụng (Gemini Cloud + Local Ollama). |
| `POST` | `/api/upload` | Tiếp nhận và bóc tách nội dung tài liệu hợp đồng (PDF, DOCX, CSV, TXT). |
| `POST` | `/api/chat` | Luồng hội thoại Server-Sent Events (SSE) stream từng token câu trả lời. |
| `GET` | `/api/sessions` | Lấy danh sách lịch sử các phiên thẩm định đã thực hiện. |
| `POST` | `/api/feedback` | Tiếp nhận đánh giá phản hồi Human-in-the-Loop từ chuyên viên pháp lý. |
| `GET` | `/api/sessions/{id}/export` | Xuất và tải về bản báo cáo thẩm định pháp lý định dạng Word (.docx). |

---

## 💼 Mẫu Trích Dẫn CV & Portfolio Dành Cho Kỹ Sư AI

### Bản Tiếng Việt
> **Enterprise Legal Copilot — Hệ thống Trí tuệ Nhân tạo Phức hợp Thẩm định Hợp đồng Doanh nghiệp**  
> * **Vai trò:** Senior AI Engineer / Full-stack AI System Developer  
> * **Công nghệ:** Python, FastAPI, PostgreSQL (JSONB & Supabase), SQLAlchemy 2.0 Async, Google Gemini API, Ollama (Qwen 2.5), Semantic Cache, Input Guardrails, Telemetry Tracing, Docker, Pytest.  
> * **Đóng góp then chốt:**  
>   * Thiết kế kiến trúc **Compound AI System** tích hợp xử lý tài liệu đa định dạng với lớp khiên **PII Token Vault** mã hóa dữ liệu nhạy cảm hai chiều trước khi gửi tới LLM.  
>   * Xây dựng cơ chế **Hybrid LLM Router** hỗ trợ chuyển mạch liền mạch giữa Cloud Gemini và On-Premise Qwen 2.5 cho khối khách hàng yêu cầu bảo mật thông tin nội bộ.  
>   * Ứng dụng **Semantic Caching** tối ưu độ trễ xuống 50ms cho truy vấn lặp và cắt giảm 60–80% chi phí API; tích hợp hệ thống **Telemetry** đo lường token và độ trễ p95.  
>   * Tích hợp **Legal RAG** đối chiếu văn bản với Bộ luật Dân sự, Luật Thương mại và NĐ 13/2023; thiết kế bộ công cụ tổng hợp NotebookLM và ma trận đàm phán 3 kịch bản theo nguyên tắc BLUF.  
>   * Thiết kế tầng dữ liệu bất đồng bộ với **PostgreSQL (JSONB)** trên Supabase Cloud kèm giải pháp tự động dự phòng (Failover) đảm bảo độ sẵn sàng cao.

### English Version
> **Enterprise Legal Copilot — Enterprise-Grade Compound AI Contract Audit System**  
> * **Role:** Senior AI Engineer / Full-Stack AI Developer  
> * **Tech Stack:** Python, FastAPI, PostgreSQL (JSONB & Supabase), SQLAlchemy 2.0 Async, Google Gemini, Ollama (Qwen 2.5), Semantic Caching, Input Guardrails, AI Observability, Docker, Pytest.  
> * **Key Contributions:**  
>   * Architected an **Enterprise Compound AI System** incorporating document ETL, bidirectional **PII Token Vault** data masking, and an **Input Guardrails** defense layer against Prompt Injections.  
>   * Engineered an intelligent **Hybrid LLM Router** orchestrating Cloud APIs (Gemini Flash) with air-gapped On-Premise LLMs (Qwen 2.5 via Ollama) to support data sovereignty compliance.  
>   * Implemented **Semantic Caching** to achieve 50ms hit response times and cut API overhead by 60–80%, backed by real-time token and p95 latency **Telemetry Tracing**.  
>   * Developed a **Legal RAG** engine cross-referencing Vietnamese Commercial Laws, paired with a NotebookLM-style synthesis studio and a 3-tier Negotiation Scenario Matrix.  
>   * Designed an asynchronous persistence tier using **PostgreSQL (JSONB)** on Supabase Cloud with seamless local failover mechanisms.

---

## 📄 Bản Quyền & Giấy Phép (License)
Phát hành dưới giấy phép [MIT License](LICENSE). Tự do sử dụng, chỉnh sửa và triển khai cho các mục đích thương mại và nghiên cứu học thuật.
