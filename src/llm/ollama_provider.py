"""
SecureDoc AI — On-Premise Ollama Provider
Handles local LLM inference (e.g. Qwen 3.5) for air-gapped private deployments.
"""
import os
import json
import urllib.request
from typing import Generator

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def check_ollama_status() -> bool:
    """Kiểm tra máy chủ Ollama on-premise có đang chạy hay không"""
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags", headers={"User-Agent": "SecureDoc-AI"})
        with urllib.request.urlopen(req, timeout=1.2) as resp:
            return resp.status == 200
    except Exception:
        return False


def call_ollama(prompt: str, model: str = "qwen3.5:latest", json_mode: bool = False) -> str:
    """Gọi mô hình nội bộ Ollama on-premise"""
    clean_model = model.replace("ollama:", "")
    payload = {
        "model": clean_model,
        "prompt": prompt,
        "stream": False,
    }
    if json_mode:
        payload["format"] = "json"
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res.get("response", "")


def stream_ollama(prompt: str, model: str = "qwen3.5:latest") -> Generator[str, None, None]:
    """Stream token từ mô hình nội bộ Ollama on-premise"""
    clean_model = model.replace("ollama:", "")
    payload = {
        "model": clean_model,
        "prompt": prompt,
        "stream": True,
    }
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        for line in resp:
            if line:
                chunk = json.loads(line.decode("utf-8"))
                text = chunk.get("response", "")
                if text:
                    yield text
