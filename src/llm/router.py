"""
SecureDoc AI — Enterprise Hybrid LLM Router
Orchestrates intelligent model dispatching, cloud vs on-premise routing, and automatic failover.
"""
import logging
from typing import Generator
from src.llm.gemini_provider import call_gemini, stream_gemini, FALLBACK_MODELS
from src.llm.ollama_provider import call_ollama, stream_ollama


def call_with_fallback(prompt: str, primary_model: str = "gemini-3.5-flash", json_mode: bool = False) -> str:
    """Hybrid Router: Tự động chuyển model dự phòng nếu model chính bị bận hoặc lỗi (Cloud Gemini + Local Ollama)"""
    # Nếu chọn mô hình On-Premise Ollama
    if primary_model.startswith("ollama") or "qwen" in primary_model.lower():
        try:
            return call_ollama(prompt, model=primary_model, json_mode=json_mode)
        except Exception as e:
            logging.warning(f"Ollama local model ({primary_model}) không phản hồi ({e}), tự động chuyển sang Cloud Gemini...")
            primary_model = "gemini-3.5-flash"

    models_to_try = [primary_model] + [m for m in FALLBACK_MODELS if m != primary_model]

    last_err = None
    for model_candidate in models_to_try:
        try:
            return call_gemini(prompt, model_candidate=model_candidate, json_mode=json_mode)
        except Exception as e:
            last_err = e
            logging.warning(f"Model {model_candidate} gặp lỗi ({e}), đang chuyển sang model dự phòng...")
            continue

    raise RuntimeError(f"Tất cả mô hình đều bận, vui lòng thử lại sau giây lát: {last_err}")


def stream_with_fallback(prompt: str, primary_model: str = "gemini-3.5-flash") -> Generator[str, None, None]:
    """Hybrid Router Streaming: Stream token và tự động chuyển về Cloud nếu Ollama gặp sự cố"""
    if primary_model.startswith("ollama") or "qwen" in primary_model.lower():
        try:
            for chunk in stream_ollama(prompt, model=primary_model):
                yield chunk
            return
        except Exception as e:
            logging.warning(f"Ollama stream ({primary_model}) gặp lỗi ({e}), tự động chuyển về Cloud Gemini...")
            primary_model = "gemini-3.5-flash"

    models_to_try = [primary_model] + [m for m in FALLBACK_MODELS if m != primary_model]

    last_err = None
    for model_candidate in models_to_try:
        try:
            for chunk in stream_gemini(prompt, model_candidate=model_candidate):
                yield chunk
            return
        except Exception as e:
            last_err = e
            logging.warning(f"Stream model {model_candidate} gặp lỗi ({e}), đang chuyển sang model dự phòng...")
            continue

    yield f"Hệ thống đang bận, vui lòng thử lại sau giây lát: {last_err}"
