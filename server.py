# server.py — Enterprise FastAPI Gateway for SecureDoc AI
"""
SecureDoc AI — Enterprise Legal AI Copilot & Risk Audit System
Modular API Gateway orchestrating Clean Architecture Routers, Static Web Assets, and Database Lifespan.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from src.config import WEB_DIR
from src.database import init_db
from src.limiter import limiter
from src.routers import (
    analytics_router,
    sessions_router,
    audit_router,
    feedback_router,
    laws_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Khởi tạo kết nối và bảng cơ sở dữ liệu khi máy chủ khởi động"""
    await init_db()
    yield


# Khởi tạo ứng dụng FastAPI chính
app = FastAPI(
    title="SecureDoc AI - Enterprise Legal Copilot",
    description="Enterprise-grade Compound AI System for Automated Contract Risk Auditing",
    version="2.0.0",
    lifespan=lifespan,
)

# Cấu hình Rate Limiting chống DoS Throttling
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Gắn thư mục tĩnh phục vụ giao diện Web Single Page Application (Olympus Cosmic)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/", tags=["Root"])
def index():
    """Phục vụ trang chủ giao diện web (tắt cache trình duyệt để luôn nhận bản mới nhất)"""
    return FileResponse(WEB_DIR / "index.html", headers={"Cache-Control": "no-store, no-cache, must-revalidate"})

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """Phục vụ favicon website hoặc trả về 204 nếu chưa có file"""
    icon_path = WEB_DIR / "favicon.ico"
    if icon_path.exists():
        return FileResponse(icon_path)
    return Response(status_code=204)

@app.get("/auth", tags=["Auth"])
@app.get("/login", tags=["Auth"])
@app.get("/register", tags=["Auth"])
@app.get("/forgot-password", tags=["Auth"])
def auth_page():
    """Phục vụ giao diện xác thực (Đăng nhập, Đăng ký, Quên mật khẩu)"""
    return FileResponse(WEB_DIR / "auth.html", headers={"Cache-Control": "no-store, no-cache, must-revalidate"})


# Đăng ký các APIRouter phân tách theo miền nghiệp vụ (Domain-Driven Design)
app.include_router(analytics_router)
app.include_router(sessions_router)
app.include_router(audit_router)
app.include_router(feedback_router)
app.include_router(laws_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
