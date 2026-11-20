# 📄 SecureDoc AI — Enterprise Legal Copilot
*Hệ thống Compound AI thẩm định rủi ro hợp đồng, bảo vệ PII hai chiều và đối chiếu Pháp luật Việt Nam bằng Vector RAG.*

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase%20Async-336791?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-Multimodal%20%26%20Vision%20OCR-4285F4?style=flat&logo=google&logoColor=white)](https://ai.google.dev/)
[![Ollama](https://img.shields.io/badge/Ollama-Qwen%202.5%20Local-black?style=flat&logo=ollama&logoColor=white)](https://ollama.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/Pytest-36%2F36%20Passed-brightgreen?style=flat&logo=pytest&logoColor=white)](tests/)

🌐 **Live Demo:** https://securedocai.onrender.com

---

## 📌 Tổng Quan

**SecureDoc AI** tự động hóa quy trình rà soát hợp đồng cho doanh nghiệp và phòng pháp chế:
* **Đa định dạng & OCR:** Đọc trực tiếp PDF, Word (`.docx`), TXT, CSV, MD, **PDF scan** và **ảnh chụp hợp đồng (`.png`, `.jpg`, `.webp`)** qua Gemini Multimodal Vision OCR.
* **Smart PII Token Vault (2 chiều):** Tự động ẩn danh SĐT, CCCD, Email, STK trước khi gửi lên Cloud LLM (không che nhầm giá trị tiền hợp đồng như `1000000000 VND`) và hỗ trợ giải mã PII gốc có kiểm soát khi xuất file `.docx`.
* **Vietnamese Legal Vector RAG:** Đối chiếu điều khoản với kho luật Việt Nam (*Bộ luật Dân sự 2015, Luật Thương mại 2005, Bộ luật Lao động 2019, Nghị định 13/2023/NĐ-CP, Luật SHTT*) và đề xuất **Ma trận 3 kịch bản đàm phán** (*Cứng rắn / Cân bằng Win-Win / Phòng thủ*).
* **Hybrid LLM Router & Semantic Cache:** Kết hợp Gemini Cloud và Ollama Local (Qwen 2.5) cho dữ liệu nội bộ; bộ đệm N-gram Semantic Cache (SHA-256 toàn văn bản) giảm độ trễ câu hỏi lặp xuống `<50ms`.
* **Xác thực, Phân quyền & Bảo mật:** Supabase Google OAuth JWT, cô lập dữ liệu theo user (`User Isolation`), phân quyền **Admin RBAC** cho bảng **AI System & RAG Inspector**, kiểm duyệt chuẩn Gmail/DNS, cùng lớp phòng thủ chống *Path Traversal, SSRF, Prompt Injection Bypass* và *Cache Poisoning*.

---

## 🏗️ Kiến Trúc Hệ Thống

```mermaid
flowchart LR
    U["User SPA (Google OAuth)"] --> GW["FastAPI Gateway (JWT & RBAC)"]
    GW --> ETL["ETL & OCR + PII Vault / Guardrails"]
    ETL --> CACHE{"N-gram Cache (SHA-256)"}
    CACHE -->|"Hit (<50ms)"| OUT["SSE Stream & Audit Canvas (.docx)"]
    CACHE -->|"Miss"| RAG["Legal Vector RAG + Hybrid LLM Router"]
    RAG --> OUT
    RAG --> DB["PostgreSQL (Supabase) + SQLite Failover"]
```

---

## 🖼️ Giao Diện Chính

| Cổng Đăng Nhập (Google OAuth) | Trang Chủ (Workspace) | Không Gian Thẩm Định Hợp Đồng (Live Audit Canvas) |
| :---: | :---: | :---: |
| ![Auth Portal](docs/screenshots/auth_portal.png) | ![Home Workspace](docs/screenshots/home_workspace.png) | ![Audit Canvas](docs/screenshots/audit_canvas.png) |

---

## 🛠️ Công Nghệ Sử Dụng

| Thành Phần | Công Nghệ |
| :--- | :--- |
| **Backend & Auth** | Python 3.11+, FastAPI, Uvicorn, `slowapi`, Supabase JWT (HS256) & RBAC |
| **AI & OCR** | Google Gemini (`google-genai`, Vision OCR), Ollama (`qwen2.5`), NumPy Vector RAG |
| **Document & Export** | `pypdf`, `python-docx`, `beautifulsoup4`, `httpx` |
| **Database** | PostgreSQL (Supabase), SQLAlchemy 2.0 Async (`asyncpg`, `aiosqlite`, `greenlet`) |
| **Frontend & DevOps** | Vanilla HTML5/CSS3/ES6+, SSE Streaming, `pytest`, Docker & Render |

---

## 📂 Cấu Trúc Thư Mục

```text
SecureDoc-AI/
├── data/laws/                # Kho 19 điều luật Việt Nam (0 trùng lặp) cho Vector RAG
├── docs/screenshots/         # Ảnh chụp giao diện
├── scripts/eval_rag.py       # Benchmark đo RAG Recall@3, PII Accuracy & Guardrails
├── src/
│   ├── llm/                  # Gemini Cloud, Ollama Local & Hybrid Router
│   ├── prompts/              # System Prompts (BLUF & 3 Kịch bản đàm phán)
│   ├── routers/              # analytics, audit, feedback, laws, sessions
│   ├── services/             # Session management service
│   ├── analyzer.py           # Auditor Orchestrator, Multi-section RAG & Safe JSON
│   ├── auth.py               # Supabase JWT Verification, User Isolation & Admin RBAC
│   ├── cache.py              # Thread-safe N-gram Semantic Cache (Atomic Write)
│   ├── database.py           # Async SQLAlchemy 2.0 + Auto SQLite Failover
│   ├── email_validator.py    # Kiểm duyệt chuẩn Gmail, chặn email rác & DNS check
│   ├── exporter.py           # Xuất báo cáo Word (.docx)
│   ├── guardrails.py         # Chống Prompt Injection & Bypass (\u200B, \n)
│   ├── ingestion.py          # Multi-format ETL & Gemini Vision OCR
│   ├── legal_kb.py           # Vector RAG Engine (Cosine Similarity)
│   ├── legal_sync.py         # Cào luật từ URL kèm SSRF Protection
│   ├── models.py             # ORM Models (User, Document, AuditSession, HITLFeedback)
│   ├── privacy.py            # Smart PII Token Vault 2 chiều
│   └── telemetry.py          # Đo Token, Cost ($) & Latency p95
├── tests/
│   ├── test_core.py          # 16 Unit & Integration Tests cốt lõi
│   └── test_qa_bootcamp.py   # 20 Security, Edge-Case, RBAC & Email Tests
├── web/                      # index.html, auth.html, app.js, style.css
├── docker-compose.yml
├── Dockerfile
├── pytest.ini
├── requirements.txt
└── server.py
```

---

## 🚀 Cài Đặt & Chạy Dự Án

### 1. Cài đặt môi trường
```bash
git clone https://github.com/kietnguyenx/enterprise-legal-copilot.git
cd enterprise-legal-copilot

python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Cấu hình `.env`
Sao chép `.env.example` thành `.env`:
```env
GEMINI_API_KEY=your_gemini_api_key_here
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/postgres   # Tùy chọn (tự failover sang SQLite)
ADMIN_EMAILS=admin@gmail.com                                     # Email có quyền Admin xem AI System & RAG
SUPABASE_ANON_KEY=your_supabase_anon_key                         # Tùy chọn (gửi email xác nhận thật)
OLLAMA_BASE_URL=http://localhost:11434                           # Tùy chọn (Local LLM)
```

### 3. Khởi chạy
```bash
# Chạy cục bộ
uvicorn server:app --host 127.0.0.1 --port 8000 --reload

# Hoặc chạy bằng Docker Compose
docker compose up --build -d
```
* **Trang chủ:** `http://127.0.0.1:8000` · **Đăng nhập:** `http://127.0.0.1:8000/auth` · **API Docs:** `http://127.0.0.1:8000/docs`

---

## 🧪 Kiểm Thử & Đánh Giá

```bash
# Chạy toàn bộ 36 bài kiểm thử tự động (Core + Security/QA + RBAC)
pytest

# Chạy benchmark đánh giá RAG Recall@3, PII Vault & Guardrails
python scripts/eval_rag.py
```

| Hạng Mục | Kết Quả |
| :--- | :---: |
| **Pytest Suite (Core + Security/QA + RBAC)** | **36 / 36 Passed (100%)** |
| **Legal Vector RAG (`Recall@3`)** | **10 / 10 (100.0%)** |
| **Smart PII Token Vault Accuracy** | **7 / 7 (100.0%)** |
| **Input Guardrails Block Rate** | **5 / 5 (100.0%)** |

---

## 📡 API Endpoints Chính

| Method | Endpoint | Chức Năng |
| :---: | :--- | :--- |
| `GET` | `/api/auth/me` | Xác thực & đồng bộ hồ sơ user từ JWT / Database |
| `POST` | `/api/auth/validate-email` | Kiểm duyệt chuẩn Gmail, chặn email rác & kiểm tra DNS |
| `GET` | `/api/health`, `/api/models` | Kiểm tra sức khỏe hệ thống & danh sách model AI |
| `POST` | `/api/upload` | Tải lên & thẩm định hợp đồng (PDF, DOCX, TXT, CSV, MD, ảnh OCR) |
| `POST` | `/api/chat` | Chat pháp lý SSE Streaming (Guardrails + Semantic Cache) |
| `GET` | `/api/sessions` | Quản lý lịch sử phiên thẩm định cô lập theo user |
| `GET` | `/api/sessions/{id}/export` | Xuất báo cáo `.docx` (hỗ trợ `?restore_original_pii=true`) |
| `POST` | `/api/feedback` | Ghi nhận phản hồi Human-in-the-Loop (👍/👎) |
| `GET` / `POST` | `/api/laws/*` | Tra cứu Vector RAG, upload file luật & cào luật từ URL *(Admin)* |
| `GET` / `POST` | `/api/telemetry`, `/api/cache/*` | Giám sát độ trễ `p95`, chi phí & xóa Semantic Cache *(Admin)* |
