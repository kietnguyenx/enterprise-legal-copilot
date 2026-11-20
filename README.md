# 📄 SecureDoc AI — Enterprise Legal Copilot
### *Production-Oriented Compound AI System for Vietnamese Contract Risk Auditing, Bidirectional PII Protection & Legal Vector RAG*

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase%20Async-336791?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-Multimodal%20%26%20Vision%20OCR-4285F4?style=flat&logo=google&logoColor=white)](https://ai.google.dev/)
[![Ollama](https://img.shields.io/badge/Ollama-Qwen%202.5%20On--Prem-black?style=flat&logo=ollama&logoColor=white)](https://ollama.com/)
[![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/Pytest-36%2F36%20Passed%20(100%25)-brightgreen?style=flat&logo=pytest&logoColor=white)](tests/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## 📌 Executive Overview

**SecureDoc AI** là một hệ thống **Compound AI System** được thiết kế cho khối Doanh nghiệp, Ngân hàng và Phòng Pháp chế tại Việt Nam nhằm tự động hóa quy trình thẩm định hợp đồng, phát hiện rủi ro pháp lý, đối chiếu luật định và đề xuất chiến lược đàm phán.

Khác với các ứng dụng "API Wrapper" gọi thẳng LLM công cộng, SecureDoc AI giải quyết 4 bài toán kỹ thuật cốt lõi khi đưa GenAI vào môi trường doanh nghiệp:
1. **Data Sovereignty & Bidirectional Privacy:** Lớp khiên **Smart PII Token Vault** mã hóa 2 chiều thông tin nhạy cảm (`SĐT`, `CCCD`, `Email`, `STK`) trước khi gửi lên Cloud LLM — đồng thời không che nhầm giá trị tiền hợp đồng (`1000000000 VND`) và hỗ trợ **giải mã có kiểm soát** khi chuyên viên xuất báo cáo `.docx`. Hỗ trợ **Hybrid Router** chuyển mạch sang **Ollama Local (Qwen 2.5)** cho tài liệu tối mật.
2. **Grounded Legal RAG & Anti-Hallucination:** Đối chiếu hợp đồng trực tiếp với kho tri thức pháp luật Việt Nam (*Bộ luật Dân sự 2015, Luật Thương mại 2005, Bộ luật Lao động 2019, Nghị định 13/2023/NĐ-CP, Luật SHTT*) kết hợp lấy mẫu **đầu–giữa–cuối** cho hợp đồng dài và parser JSON tự phục hồi.
3. **Production Security & User Isolation:** Tích hợp **Supabase Google OAuth + Backend JWT Verification**, phân tách dữ liệu phiên theo từng tài khoản (`403 Forbidden` khi truy cập chéo), cùng lớp phòng thủ **Defense-in-Depth** chống *Path Traversal, SSRF, Prompt Injection Bypass (`\u200B`, `\n`), Cache Poisoning* và *Token Exhaustion DoS*.
4. **AI Observability & Cost Efficiency:** Bộ đệm **N-gram Thread-safe Semantic Cache** (chống va chạm SHA-256 toàn văn bản, lưu atomic), giám sát thời gian thực độ trễ `p95`, chi phí USD và giao diện **AI System & RAG Inspector** trực tiếp trên web.

---

## 🏗️ Kiến Trúc Hệ Thống (System Architecture)

```mermaid
flowchart TD
    U["👤 User / Legal Officer (SPA Web + Google OAuth)"] -->|"Bearer JWT + File/Query"| GW["⚡ FastAPI Gateway & Rate Limiter (server.py)"]
    GW --> AUTH["🔐 JWT Auth & User Isolation (src/auth.py)"]
    AUTH --> ETL["📄 ETL & Gemini Vision OCR (PDF/DOCX/Scan Images)"]
    ETL --> SEC["🛡️ PII Token Vault & Input Guardrails"]
    SEC --> CACHE{"⚡ N-gram Semantic Cache (SHA-256 Doc Hash)"}
    CACHE -->|"Cache Hit (<50ms, $0)"| SSE["📡 SSE Token Streaming & Live Audit Canvas"]
    CACHE -->|"Cache Miss"| RAG["⚖️ Vietnamese Legal Vector RAG (19 Unique Articles)"]
    RAG --> ROUTER["🔀 Hybrid LLM Router (Gemini Cloud <-> Local Ollama)"]
    ROUTER --> JSON["🧩 Safe JSON Parser & 3-Scenario Matrix"]
    JSON --> SSE
    JSON --> DB["🗄️ Async PostgreSQL (Supabase) + Auto SQLite Failover"]
    SSE --> EXP["📥 Word (.docx) Exporter (Optional PII Restore)"]
    GW --> OBS["📊 Telemetry Tracing & AI System Inspector UI"]
```

---

## 🖼️ Giao Diện Thực Tế (Product Showcase)

| Cổng Xác Thực (Google OAuth / Supabase) | AI System Inspector (Observability & Cache) | Kho Luật Vector RAG (Live Semantic Search) |
| :---: | :---: | :---: |
| ![Auth Portal](docs/screenshots/auth_portal.png) | ![Observability](docs/screenshots/system_inspector_obs.png) | ![RAG Inspector](docs/screenshots/system_inspector_rag.png) |

---

## 📊 Kết Quả Đánh Giá & Kiểm Thử (Measured Benchmarks)

Mọi chỉ số dưới đây đều được đo đạc thực tế và có thể tái lập 100% tại máy cục bộ mà không tốn chi phí API:

| Hạng Mục Đánh Giá | Kết Quả Đo Thực Tế | Lệnh Tái Lập |
| :--- | :---: | :--- |
| **Automated Test Suite (Core + 20-Bug QA/Security + RBAC/Email)** | **36 / 36 Passed (100%)** | `pytest` |
| **Legal Vector RAG Retrieval (`Recall@3`)** | **10 / 10 (100.0%)** | `python scripts/eval_rag.py` |
| **Smart PII Token Vault Accuracy (Mask PII + Keep Currency)** | **7 / 7 (100.0%)** | `python scripts/eval_rag.py` |
| **Input Guardrails Attack Block Rate (incl. `\u200B` & `\n` bypass)** | **5 / 5 (100.0%)** | `python scripts/eval_rag.py` |

---

## 🛡️ Bảo Mật & Độ Tin Cậy Đã Kiểm Chứng (Security & Resilience Hardening)

Toàn bộ các lỗ hổng thực tế phổ biến trong hệ thống AI Production đã được kiểm thử và khóa bằng Regression Tests trong [`tests/test_qa_bootcamp.py`](tests/test_qa_bootcamp.py):

* **Application Security:** Chặn **Path Traversal** (`../`) & kiểm soát đuôi/dung lượng file tải luật (`/api/laws/upload`); chặn **SSRF** tới `localhost` / dải IP nội bộ / cloud metadata (`/api/laws/sync-url`); giới hạn độ dài tin nhắn chống **Token Exhaustion DoS** (`/api/chat`); validate `top_k` (`1..20`).
* **AI & Data Integrity:** Làm sạch ký tự tàng hình (`\u200B`) trước khi quét regex và bật `re.DOTALL` chống bypass Guardrails; băm **SHA-256 toàn văn bản** chống va chạm Cache giữa 2 hợp đồng cùng mẫu bìa; chống **Cache Poisoning** khi stream LLM bị đứt; kết hợp **Unigram + Bigram + Trigram** để phân biệt câu đảo chủ ngữ (`Bên A` vs `Bên B`).
* **Infrastructure Resilience:** **Thread-safe Atomic File Write** (`.tmp` $\rightarrow$ `replace`) cho Semantic Cache; chuyển mạch **SQLite Async Failover thực sự** khi Supabase Cloud mất kết nối; **Safe JSON Repair & Fallback** khi LLM trả sai cú pháp JSON; hỗ trợ **OCR tự động** cho PDF scan & ảnh chụp dấu đỏ (`.png`, `.jpg`, `.webp`).

---

## 🛠️ Ngăn Xếp Công Nghệ (Technology Stack)

| Tầng Kiến Trúc | Công Nghệ | Vai Trò |
| :--- | :--- | :--- |
| **API Gateway & Auth** | **FastAPI (ASGI)**, `slowapi`, **Supabase JWT (HS256)** | RESTful API bất đồng bộ, Rate Limiting, xác thực JWT & User Isolation (RBAC). |
| **AI & Multimodal OCR** | **Google Gemini (`google-genai`)** & **Ollama (Qwen 2.5)** | Thẩm định hợp đồng, Gemini Vision OCR cho ảnh/PDF scan, Hybrid Cloud/Local Failover. |
| **Document ETL & Export** | `pypdf`, `python-docx`, `beautifulsoup4`, `httpx` | Bóc tách PDF/DOCX/TXT/CSV/Ảnh (hỗ trợ `UTF-8-SIG`/`UTF-16`) và xuất báo cáo `.docx`. |
| **Privacy & Guardrails** | Context-aware Regex Tokenizer, Input Guardrails | Mã hóa PII 2 chiều (giữ nguyên giá trị tiền tệ) & chặn Prompt Injection/Jailbreak. |
| **Persistence** | **PostgreSQL (Supabase)**, SQLAlchemy 2.0 Async, `aiosqlite` | Lưu trữ cấu trúc JSON/JSONB cho `users`, `audit_sessions`, `hitl_feedback` + Auto Failover. |
| **Observability & Cache** | N-gram Cosine Semantic Cache, Latency/Cost Tracer | Cắt giảm chi phí API, đo độ trễ `p95`, hiển thị trực tiếp trên **AI System & RAG Inspector**. |
| **Frontend & QA** | Vanilla HTML5/CSS3/ES6+, SSE Streaming, `pytest`, Docker | Giao diện SPA Bespoke, 34 automated tests, containerization sẵn sàng deploy. |

---

## 📂 Cấu Trúc Thư Mục Dự Án (Repository Layout)

```text
SecureDoc-AI/
├── .github/workflows/ci-cd.yml   # GitHub Actions CI/CD (Pytest & Docker)
├── data/
│   └── laws/                     # 19 điều luật Việt Nam duy nhất (0 trùng lặp) cho Vector RAG
├── docs/screenshots/             # Ảnh chụp giao diện thực tế
├── scripts/
│   └── eval_rag.py               # Script đánh giá định lượng RAG Recall@3, PII & Guardrails
├── src/
│   ├── llm/                      # Strategy Pattern: Gemini Cloud, Ollama Local & Hybrid Router
│   ├── prompts/                  # System Prompts (BLUF, 3 Kịch bản đàm phán, Strict Anchoring)
│   ├── routers/                  # Domain-Driven FastAPI Routers
│   │   ├── analytics.py          # /api/auth/me, /api/health, /api/models, /api/telemetry, /api/cache/*
│   │   ├── audit.py              # /api/upload (OCR + Audit), /api/chat (SSE Stream)
│   │   ├── feedback.py           # /api/feedback (HITL) & /api/sessions/{id}/export (.docx + PII restore)
│   │   ├── laws.py               # /api/laws/* (Upload, Sync URL, List, Vector Search)
│   │   └── sessions.py           # /api/sessions/* (User-Isolated CRUD)
│   ├── services/session_service.py
│   ├── analyzer.py               # Auditor Orchestrator, Multi-section RAG & Safe JSON Fallback
│   ├── auth.py                   # Supabase JWT Verification & User Isolation Dependency
│   ├── cache.py                  # Thread-safe N-gram Semantic Cache (Atomic Persistence)
│   ├── config.py                 # Cấu hình hệ thống & danh mục model
│   ├── database.py               # Async SQLAlchemy 2.0 + Real SQLite Failover
│   ├── exporter.py               # Xuất báo cáo thẩm định Word (.docx)
│   ├── guardrails.py             # Input Guardrails chống Prompt Injection & Bypass
│   ├── ingestion.py              # Multi-format ETL + Gemini Multimodal Vision OCR
│   ├── legal_kb.py               # Vector RAG Engine (Cosine Similarity)
│   ├── legal_sync.py             # Online Legal Scraper kèm SSRF Protection
│   ├── models.py                 # SQLAlchemy ORM Schema (User, Document, AuditSession, HITLFeedback)
│   ├── privacy.py                # Bidirectional Smart PII Token Vault
│   └── telemetry.py              # Token, Cost ($) & p95 Latency Tracing
├── tests/
│   ├── test_core.py              # 16 Unit & Integration Tests cốt lõi
│   └── test_qa_bootcamp.py       # 18 Security, Edge-Case & Resilience Regression Tests
├── web/
│   ├── index.html                # Workspace SPA + Live Audit Canvas + AI System & RAG Inspector
│   ├── auth.html                 # Cổng Đăng nhập / Đăng ký / Quên mật khẩu (Google OAuth)
│   ├── app.js                    # Auth Bearer Fetch, SSE Streaming & Inspector Logic
│   └── style.css                 # Giao diện Olympus Cosmic Sky
├── pytest.ini                    # Cấu hình Pytest chuẩn hóa (chạy gọn bằng lệnh `pytest`)
├── docker-compose.yml            # FastAPI + PostgreSQL + Ollama
├── Dockerfile
└── server.py                     # FastAPI Application Entrypoint
```

---

## 🚀 Hướng Dẫn Cài Đặt & Chạy Dự Án (Quickstart)

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

### 2. Cấu hình biến môi trường (`.env`)
Sao chép `.env.example` thành `.env` và điền thông tin:
```env
GEMINI_API_KEY=your_gemini_api_key_here
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/postgres   # Tùy chọn (tự failover sang SQLite)
SUPABASE_JWT_SECRET=your_supabase_jwt_secret                     # Tùy chọn (bật kiểm tra chữ ký HS256)
OLLAMA_BASE_URL=http://localhost:11434                           # Tùy chọn (On-Premise Local LLM)
```

### 3. Khởi chạy hệ thống
```bash
# Chạy cục bộ (Development)
python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload

# Hoặc chạy trọn bộ bằng Docker Compose
docker compose up --build -d
```
* **Trang chủ & Thẩm định:** `http://127.0.0.1:8000`
* **Cổng Đăng nhập (Google OAuth):** `http://127.0.0.1:8000/auth`
* **Swagger API Docs:** `http://127.0.0.1:8000/docs`

### 4. Chạy Kiểm thử & Đánh giá AI
```bash
# Chạy toàn bộ 34 bài kiểm thử (Core + QA/Security Regression Suite)
pytest

# Chạy benchmark đo lường định lượng RAG Recall@3, PII & Guardrails
python scripts/eval_rag.py
```

---

## 📡 Danh Mục RESTful API Chính

| Method | Endpoint | Mô Tả |
| :---: | :--- | :--- |
| `GET` | `/api/auth/me` | Xác thực & đồng bộ hồ sơ người dùng từ Supabase JWT. |
| `GET` | `/api/health` | Kiểm tra sức khỏe Database, Ollama Local, Vector RAG, Cache & Telemetry. |
| `GET` | `/api/models` | Danh sách model khả dụng (Gemini Cloud + Local Ollama). |
| `POST` | `/api/upload` | Tải lên & thẩm định tài liệu (PDF, DOCX, TXT, CSV, MD, ảnh OCR `.png/.jpg/.webp`). |
| `POST` | `/api/chat` | Hội thoại pháp lý thời gian thực (SSE Streaming + Guardrails + Semantic Cache). |
| `GET` | `/api/sessions` | Danh sách phiên thẩm định thuộc quyền sở hữu của user hiện tại. |
| `GET` | `/api/sessions/{id}/export` | Xuất báo cáo `.docx` (hỗ trợ `?restore_original_pii=true` giải mã PII gốc). |
| `POST` | `/api/feedback` | Ghi nhận phản hồi Human-in-the-Loop (👍/👎 & hiệu đính chuyên viên). |
| `GET` / `POST` | `/api/laws/list`, `/search`, `/upload`, `/sync-url` | Quản trị, tra cứu Vector RAG và nạp bổ sung văn bản pháp luật. |
| `GET` / `POST` | `/api/telemetry`, `/api/cache/stats`, `/api/cache/clear` | Giám sát độ trễ `p95`, chi phí token và quản lý Semantic Cache. |

---

## 💼 Tóm Tắt Cho CV / Portfolio (AI Engineer Intern)

### Tiếng Việt
> **SecureDoc AI — Hệ thống AI Thẩm Định Hợp Đồng & Bảo Mật Pháp Lý Doanh Nghiệp**  
> * **Vai trò:** AI Engineer / Full-Stack AI Developer  
> * **Công nghệ:** Python, FastAPI, PostgreSQL (Supabase Async), SQLAlchemy 2.0, Google Gemini (Multimodal Vision OCR), Ollama (Qwen 2.5), Vector RAG, Semantic Cache, Pytest, Docker.  
> * **Điểm nhấn kỹ thuật:**  
>   * Xây dựng hệ thống **Compound AI** đọc đa định dạng (gồm cả **PDF scan & ảnh chụp dấu đỏ** qua Gemini Vision OCR), tích hợp **PII Token Vault 2 chiều** (ẩn danh trước khi gửi AI, giải mã có kiểm soát khi xuất `.docx`; giữ nguyên giá trị tiền tệ).  
>   * Triển khai **Vietnamese Legal Vector RAG** đạt **100% Recall@3** trên bộ benchmark pháp lý nội bộ, kết hợp **Hybrid LLM Router** (Gemini Cloud $\leftrightarrow$ Local Ollama) và **N-gram Semantic Cache** giảm độ trễ câu hỏi lặp xuống `<50ms`.  
>   * Thiết kế xác thực **Supabase Google OAuth JWT & User Isolation**, giao diện **AI System & RAG Inspector** trực quan, cùng bộ **34/34 bài kiểm thử tự động (`pytest`)** phòng chống Path Traversal, SSRF, Prompt Injection Bypass và Cache Poisoning.

### English Version
> **SecureDoc AI — Enterprise Legal Contract Auditing & Privacy-First Compound AI System**  
> * **Role:** AI Engineer / Full-Stack AI Developer  
> * **Tech Stack:** Python, FastAPI, PostgreSQL (Supabase Async), SQLAlchemy 2.0, Google Gemini (Multimodal Vision OCR), Ollama (Qwen 2.5), Vector RAG, Semantic Caching, Pytest, Docker.  
> * **Key Achievements:**  
>   * Built a privacy-first **Compound AI pipeline** supporting PDF/DOCX/scanned image OCR (Gemini Vision) with a bidirectional **PII Token Vault** (context-aware masking preserving contract currency values + opt-in restoration on `.docx` export).  
>   * Engineered a **Vietnamese Legal Vector RAG** engine achieving **100% Recall@3** on an automated evaluation suite, paired with a **Hybrid Cloud/On-Premise LLM Router** and a thread-safe **N-gram Semantic Cache** (`<50ms` hit latency).  
>   * Hardened production security & reliability with **Supabase JWT User Isolation**, real **SQLite Async Failover**, an interactive **AI System & RAG Inspector**, and a **34/34 passing `pytest` suite** covering Path Traversal, SSRF, Guardrails bypass, and Cache Poisoning.

---

## 📄 License
Phát hành dưới giấy phép [MIT License](LICENSE).
