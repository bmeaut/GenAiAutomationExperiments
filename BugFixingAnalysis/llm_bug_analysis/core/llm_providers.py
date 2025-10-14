import os
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dotenv import load_dotenv


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate_fix(self, prompt: str) -> Dict[str, Any]:
        """Generate a fix given a prompt. Returns dict with response text and metadata."""
        pass


class GeminiProvider(LLMProvider):
    """Google Gemini 2.5 provider."""

    def __init__(self, model: str = "gemini-2.5-pro", api_key: Optional[str] = None):

        # lazy import - only load when Gemini is actually used
        from google import genai

        self.model = model

        if api_key is None:
            api_key = self._load_api_key_from_env()

        if not api_key:
            raise ValueError(
                f"Gemini API key not found! Set GOOGLE_API_KEY in .env file "
                "or pass api_key parameter."
            )

        self.client = genai.Client(api_key=api_key)

    def _load_api_key_from_env(self) -> Optional[str]:
        """Load API key from .env file in project root."""
        script_path = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(script_path))
        env_path = os.path.join(project_root, ".env")

        load_dotenv(dotenv_path=env_path)
        return os.getenv("GOOGLE_API_KEY")

    def generate_fix(self, prompt: str) -> Dict[str, Any]:
        """
        Generate a bug fix using Gemini API.
        """
        # lazy import
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

            self._validate_response(response)

            usage_metadata = self._extract_usage_metadata(response)

            if response.text is None:
                self._raise_empty_response_error(response)

            return {
                "text": response.text,
                "metadata": usage_metadata,
            }

        except Exception as e:
            raise ValueError(
                f"Gemini API call failed: {type(e).__name__}: {str(e)}"
            ) from e

    def _validate_response(self, response) -> None:
        """
        Validate that the API response has expected structure.
        """
        if response is None:
            raise ValueError("Gemini API returned None response object")

        if not hasattr(response, "text"):
            raise ValueError(
                f"Gemini response missing 'text' attribute. "
                f"Response type: {type(response)}"
            )

    def _extract_usage_metadata(self, response) -> Dict[str, Any]:
        """
        Extract token usage and completion metadata from response.
        """
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

    def _raise_empty_response_error(self, response) -> None:
        """
        Raise detailed error when response.text is None.
        """
        finish_reason = getattr(response, "finish_reason", "UNKNOWN")
        safety_ratings = getattr(response, "safety_ratings", None)
        candidates = getattr(response, "candidates", None)
        usage = getattr(response, "usage_metadata", None)

        error_details = [
            f"finish_reason: {finish_reason}",
            f"safety_ratings: {safety_ratings}",
            f"usage_metadata: {usage}",
            f"candidates: {candidates}",
        ]

        raise ValueError(
            "Gemini API returned None text. This usually means:\n"
            "  - Response was blocked by safety filters\n"
            "  - Token limit was exceeded (check max_output_tokens)\n"
            "  - Model encountered an error during generation\n\n"
            "Details:\n" + "\n".join(error_details)
        )


def get_llm_provider(model: str = "gemini-2.5-pro") -> LLMProvider:
    """
    Get LLM provider instance.
    """
    available_models = {
        "gemini-2.5-pro": "gemini-2.5-pro",
        "gemini-2.5-flash": "gemini-2.5-flash",
        "gemini-2.5-flash-lite": "gemini-2.5-flash-lite",
    }

    if model not in available_models:
        available = ", ".join(f"'{m}'" for m in available_models.keys())
        raise ValueError(f"Unknown model '{model}'. Available: {available}")

    resolved_model = available_models[model]
    return GeminiProvider(model=resolved_model)
