"""
SecureDoc AI — Google Gemini Cloud Provider
Handles interactions with Google Gemini Flash 3.5 / 3.8 models via official google-genai SDK.
"""
import os
import logging
from typing import Generator
from google import genai
from google.genai import types

FALLBACK_MODELS = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.8-flash"]


def get_gemini_client() -> genai.Client:
    """Khởi tạo Gemini API Client"""
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def call_gemini(prompt: str, model_candidate: str = "gemini-3.5-flash", json_mode: bool = False) -> str:
    """Gọi Gemini Cloud API đơn lẻ"""
    client = get_gemini_client()
    config = types.GenerateContentConfig(response_mime_type="application/json") if json_mode else None
    response = client.models.generate_content(
        model=model_candidate,
        contents=prompt,
        config=config,
    )
    return response.text


def stream_gemini(prompt: str, model_candidate: str = "gemini-3.5-flash") -> Generator[str, None, None]:
    """Stream token từ Gemini Cloud API"""
    client = get_gemini_client()
    stream = client.models.generate_content_stream(
        model=model_candidate,
        contents=prompt,
    )
    for chunk in stream:
        if getattr(chunk, "text", None):
            yield chunk.text
