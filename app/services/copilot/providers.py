"""Abstract LLM Provider strategy pattern implementation for Copilot."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod

try:
    import google.generativeai as genai
    HAS_GEMINI_SDK = True
except ImportError:
    genai = None
    HAS_GEMINI_SDK = False


class LLMProvider(ABC):
    """Abstract interface for LLM operations."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider dependencies and configuration are available."""
        pass

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_instruction: str,
        history: list[dict[str, str]],
        model_name: str,
    ) -> str:
        """Generate response text given prompt, system instructions, and history."""
        pass


class GeminiProvider(LLMProvider):
    """Google Gemini model provider implementation."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self._initialized = False
        if HAS_GEMINI_SDK and genai is not None and self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self._initialized = True
            except Exception as e:
                print(f"[copilot-providers] Failed to configure Gemini SDK: {e}")

    def is_available(self) -> bool:
        return self._initialized

    def generate(
        self,
        prompt: str,
        system_instruction: str,
        history: list[dict[str, str]],
        model_name: str,
    ) -> str:
        if not self.is_available() or genai is None:
            raise RuntimeError("Gemini provider is not available or configured.")

        # Format history to match Gemini SDK expectations (user -> user, assistant -> model)
        formatted_history = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            formatted_history.append({"role": role, "parts": [msg["content"]]})

        model = genai.GenerativeModel(model_name, system_instruction=system_instruction)
        chat = model.start_chat(history=formatted_history)
        response = chat.send_message(prompt)
        return response.text.strip()
