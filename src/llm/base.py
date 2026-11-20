"""
SecureDoc AI — LLM Provider Abstract Interface
Defines the standard contract for all language model providers.
"""
from typing import Protocol, Generator


class BaseLLMProvider(Protocol):
    """Protocol for LLM Providers (Gemini, Ollama, OpenAI, etc.)"""

    def generate(self, prompt: str, model: str, json_mode: bool = False) -> str:
        """Sinh văn bản đồng bộ từ LLM"""
        ...

    def stream(self, prompt: str, model: str) -> Generator[str, None, None]:
        """Stream token thời gian thực từ LLM"""
        ...
