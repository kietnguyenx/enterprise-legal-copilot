"""
SecureDoc AI — Global System Configuration & Constants
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"
DATA_DIR = BASE_DIR / "data"
LAWS_DIR = DATA_DIR / "laws"
STORE_PATH = DATA_DIR / "web_sessions.json"
MAX_UPLOAD_BYTES = 15 * 1024 * 1024

MODELS = [
    {"id": "gemini-3.5-flash", "label": "Gemini 3.5 Flash"},
    {"id": "gemini-3.8-flash", "label": "Gemini 3.8 Flash"},
    {"id": "gemini-3.5-flash-lite", "label": "Gemini 3.5 Flash Lite"},
    {"id": "ollama:qwen3.5", "label": "Qwen 3.5"},
]
MODEL_IDS = {m["id"] for m in MODELS}


def resolve_model(model: str | None) -> str:
    """Xác định model hợp lệ hoặc trả về mặc định"""
    return model if model in MODEL_IDS else MODELS[0]["id"]


def format_human_size(n: int) -> str:
    """Định dạng kích thước file sang KB/MB"""
    return f"{n / 1024 / 1024:.1f} MB" if n > 1024 * 1024 else f"{max(1, n // 1024)} KB"
