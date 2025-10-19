import os
from pathlib import Path
from abc import ABC, abstractmethod
from typing import Any
from dotenv import load_dotenv


class LLMProvider(ABC):

    @abstractmethod
    def generate_fix(self, prompt: str) -> dict[str, Any]:
        """Generate a fix from prompt."""
        pass


class GeminiProvider(LLMProvider):
    """Google Gemini API provider."""

    SUPPORTED_MODELS = {
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
    }

    def __init__(self, model: str = "gemini-2.5-pro"):

        if model not in self.SUPPORTED_MODELS:
            models = ", ".join(f"'{m}'" for m in sorted(self.SUPPORTED_MODELS))
            raise ValueError(f"Unknown model '{model}'. Supported: {models}")

        # lazy import - only load when Gemini is actually used
        from google import genai

        self.model = model

        api_key = self._load_key()

        if not api_key:
            raise ValueError(
                f"Gemini API key not found! Set GOOGLE_API_KEY in .env file "
            )

        self.client = genai.Client(api_key=api_key)

    def _load_key(self) -> str | None:
        """Load API key from .env in project root."""
        project_root = Path(__file__).parent.parent
        env_path = project_root / ".env"

        load_dotenv(dotenv_path=env_path)
        return os.getenv("GOOGLE_API_KEY")

    def generate_fix(self, prompt: str) -> dict[str, Any]:
        """Call Gemini API to generate fix."""
        from google.genai import types

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=30000,
                    thinking_config=types.ThinkingConfig(thinking_budget=-1),
                ),
            )

            if not response or not hasattr(response, "text"):
                raise ValueError(f"Bad response structure: {type(response)}")

            if response.text is None:
                self._handle_empty_response(response)

            return {
                "text": response.text,
                "metadata": self._get_usage(response),
            }

        except Exception as e:
            raise ValueError(f"Gemini API failed: {e}") from e

    def _get_usage(self, response) -> dict[str, Any]:
        """Get token usage and finish reason from response."""
        # TODO: maybe add elapsed time?
        usage = getattr(response, "usage_metadata", None)

        finish_reason = "UNKNOWN"
        if response.candidates:
            finish_reason = str(
                getattr(response.candidates[0], "finish_reason", "UNKNOWN")
            )

        return {
            "prompt_tokens": getattr(usage, "prompt_token_count", 0) if usage else 0,
            "completion_tokens": (
                getattr(usage, "candidates_token_count", 0) if usage else 0
            ),
            "thinking_tokens": (
                getattr(usage, "thoughts_token_count", 0) if usage else 0
            ),
            "total_tokens": getattr(usage, "total_token_count", 0) if usage else 0,
            "finish_reason": finish_reason,
        }

    def _handle_empty_response(self, response) -> None:

        finish_reason = getattr(response, "finish_reason", "UNKNOWN")
        safety_ratings = getattr(response, "safety_ratings", None)
        usage = getattr(response, "usage_metadata", None)

        error_details = [
            f"finish_reason: {finish_reason}",
            f"safety_ratings: {safety_ratings}",
            f"usage_metadata: {usage}",
        ]

        raise ValueError(
            "Gemini API returned empty response. Possibly means:\n"
            "  - Safety filters blocked it\n"
            "  - Hit token limit (check max_output_tokens)\n"
            "  - Internal model error\n\n"
            f"{chr(10).join(error_details)}"
        )


def get_llm_provider(
    provider: str = "gemini",
    model: str = "gemini-2.5-flash",
) -> LLMProvider:

    provider = provider.lower()

    if provider == "gemini":
        return GeminiProvider(model=model)

    raise ValueError(f"Unsupported provider '{provider}'. " f"Supported: 'gemini'")
