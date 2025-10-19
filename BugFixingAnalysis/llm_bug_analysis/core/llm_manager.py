import re
import json
import time
from pathlib import Path
from typing import Any
from abc import ABC, abstractmethod

from .context_builder import ContextBuilder
from .llm_providers import get_llm_provider, LLMProvider
from core.logger import log

FILE_WRITE_DELAY = 0.5


class LLMResponseHandler(ABC):
    """Base for different response sources (API, file, etc.)"""

    def get_response(self, prompt: str) -> dict[str, Any]:
        self._log_start()
        response_text = self._fetch_response(prompt)
        return {"text": response_text, "metadata": self._get_metadata()}

    @abstractmethod
    def _fetch_response(self, prompt: str) -> str:
        """Actually get the response, implemented by subclass."""
        pass

    @abstractmethod
    def _log_start(self) -> None:
        """Log what's happening."""
        pass

    @abstractmethod
    def _get_metadata(self) -> dict[str, int]:
        """Token counts and other stats."""
        # TODO: add elapsed time
        pass


class APIResponseHandler(LLMResponseHandler):
    """Handles API-based LLM providers."""

    def __init__(self, llm_provider: LLMProvider):
        super().__init__()
        self.llm_provider = llm_provider
        self._metadata = {}

    def _log_start(self) -> None:
        provider = self.llm_provider.__class__.__name__.replace("Provider", "")
        model = getattr(self.llm_provider, "model", "unknown")
        log(f"  --> Using {provider} API ({model})")

    def _fetch_response(self, prompt: str) -> str:
        try:
            result = self.llm_provider.generate_fix(prompt)
            self._metadata = result.get("metadata", {})
            self._log_token_usage()
            return result.get("text", "")
        except Exception as e:
            provider = self.llm_provider.__class__.__name__
            log(f"  --> ERROR: {provider} API failed: {e}")
            return ""

    def _get_metadata(self) -> dict[str, int]:
        return self._metadata

    def _log_token_usage(self) -> None:
        total = self._metadata.get("total_tokens", 0)
        prompt = self._metadata.get("prompt_tokens", 0)
        thinking = self._metadata.get("thinking_tokens", 0)
        completion = self._metadata.get("completion_tokens", 0)

        log(
            f"  --> Tokens: {total} total "
            f"({prompt} prompt + {thinking} thinking + {completion} completion)"
        )


class ManualResponseHandler(LLMResponseHandler):
    """File based workflow for mainly testing."""

    def __init__(
        self,
        project_root: str | Path,
        timeout: int = 300,
        check_interval: int = 2,
    ):
        super().__init__()
        self.project_root = Path(project_root)
        self.timeout = timeout
        self.check_interval = check_interval

        self.prompt_file = self.project_root / "llm_prompt.txt"
        self.response_file = self.project_root / "llm_response.txt"

    def _log_start(self) -> None:
        log(f"  --> Prompt saved: {self.prompt_file}")
        log(f"  --> Waiting for: {self.response_file}")
        log("")
        log("  Copy llm_prompt.txt -> chosen LLM -> save as llm_response.txt")
        log("  (Or press CTRL+C to type the response directly)")

    def _fetch_response(self, prompt: str) -> str:
        self._save_prompt(prompt)

        try:
            response = self._wait_for_response_file()
            if response:
                return response

            log(f"  --> Timeout after {self.timeout}s")

        except KeyboardInterrupt:
            log("\n  --> Switching to manual input...")

        return self._get_stdin_response()

    def _save_prompt(self, prompt: str) -> None:
        self.prompt_file.write_text(prompt, encoding="utf-8")

    def _wait_for_response_file(self) -> str | None:
        elapsed = 0

        while elapsed < self.timeout:
            if self.response_file.exists():
                log(f"  --> Found response file after {elapsed}s!")
                time.sleep(FILE_WRITE_DELAY)  # let file finish writing

                try:
                    text = self.response_file.read_text(encoding="utf-8")
                    self._cleanup_files()
                    return text
                except Exception as e:
                    log(f"  --> ERROR: Can't read response file: {e}")
                    return None

            if elapsed % 10 == 0 and elapsed > 0:
                log(f"  --> Still waiting... ({elapsed}s)")

            time.sleep(self.check_interval)
            elapsed += self.check_interval

        return None

    def _get_metadata(self) -> dict[str, int]:
        """Manual mode, no tokens to count."""
        return {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "thinking_tokens": 0,
            "total_tokens": 0,
        }

    def _get_stdin_response(self) -> str:
        """Read response from terminal."""
        log("")
        log("  Paste the response below, then press Ctrl+D:")
        log("")

        lines = []
        try:
            while True:
                lines.append(input())
        except EOFError:
            pass

        self._cleanup_files()
        return "\n".join(lines)

    def _cleanup_files(self) -> None:
        """Delete temporary files."""
        for f in [self.prompt_file, self.response_file]:
            try:
                if f.exists():
                    f.unlink()
            except Exception as e:
                log(f"  --> Warning: Couldn't delete {f}: {e}")


class IntentParser:
    """Parse LLM responses to extract fix."""

    JSON_PATTERNS = [
        (r"```json\s*\n(.*?)\n```", 1, "```json block"),
        (r"```\s*\n(.*?)\n```", 1, "``` block"),
        (r"\{.*\}", 0, "JSON object directly"),
    ]

    def parse(self, text: str) -> dict[str, Any] | None:
        """Parse LLM response to extract from JSON format."""
        if not text or not text.strip():
            log("  --> ERROR: Empty response")
            return None

        json_str = self._extract_json(text)
        if not json_str:
            log("  --> ERROR: No JSON found in response")
            return None

        intent = self._try_parse(json_str)
        if intent:
            return self._validate(intent)

        log("  --> Trying to fix JSON...")
        fixed = self._clean_json(json_str)
        intent = self._try_parse(fixed)

        if intent:
            return self._validate(intent)

        log(f"  --> JSON parsing failed. First 500 chars:\n{fixed[:500]}")
        return None

    def _extract_json(self, text: str) -> str | None:
        """Find JSON in response (handles markdown code blocks)."""
        for pattern, group, description in self.JSON_PATTERNS:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                log(f"DEBUG: Found JSON in {description}")
                return match.group(group)

        return text  # whole response fallback

    def _try_parse(self, json_str: str) -> dict[str, Any] | None:
        try:
            log("  --> Successfully parsed JSON intent")
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            log(f"  --> ERROR: at line {e.lineno}, column {e.colno}: {e.msg}")
            return None

    def _clean_json(self, json_str: str) -> str:
        """Fix common JSON issues (trailing commas, etc.)."""
        cleaned = re.sub(r",(\s*[}\]])", r"\1", json_str)
        return cleaned.strip()

    def _validate(self, intent: dict[str, Any]) -> dict[str, Any]:
        """Check required fields in response."""
        required = ["fix_type", "target_file", "new_code"]
        missing = [f for f in required if f not in intent]

        if missing:
            log(f"  --> WARNING: Missing fields: {', '.join(missing)}")

        return intent


class LLMManager:
    """Manager for LLM interactions."""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)

    def generate_fix_with_intent(
        self,
        bug: dict[str, Any],
        repo_path: Path,
        provider: str = "gemini",
        model: str = "gemini-2.5-flash",
    ) -> dict[str, Any]:
        """Generate fix using TODO:."""

        builder = ContextBuilder(repo_path=repo_path, max_snippets=5, debug=True)
        context, context_text = builder.build_and_format(bug)

        prompt = self._build_prompt(bug, context_text)
        handler = self._create_response_handler(provider, model)
        result = handler.get_response(prompt)

        text = result.get("text", "")
        metadata = result.get("metadata", {})
        result_model = model if provider == "gemini" else "manual"

        if not text or not text.strip():
            log("  --> ERROR: No response received!")
            return {
                "intent": None,
                "context": context,
                "prompt": prompt,
                "raw_response": "",
                "provider": provider,
                "model": result_model,
                "metadata": metadata,
            }

        log(f"  --> Response: ({len(text)} chars)")

        parser = IntentParser()
        intent = parser.parse(text)

        return {
            "intent": intent,
            "context": context,
            "prompt": prompt,
            "raw_response": text,
            "provider": provider,
            "model": result_model,
            "metadata": metadata,
        }

    def _build_prompt(
        self,
        bug: dict[str, Any],
        context_text: str,
    ) -> str:
        """Fill prompt with context."""
        template_path = (
            self.project_root / "llm_bug_analysis" / "prompts" / "generate_fix.txt"
        )

        if not template_path.exists():
            raise FileNotFoundError(f"Prompt template not found: {template_path}")

        template = template_path.read_text(encoding="utf-8")

        return template.format(
            repo_name=bug.get("repo_name", "Unknown"),
            bug_commit_sha=bug.get("bug_commit_sha", "Unknown")[:7],
            issue_title=bug.get("issue_title", "No title"),
            issue_body=bug.get("issue_body", "No description"),
            code_context=context_text,
        )

    def _create_response_handler(
        self,
        provider: str,
        model: str,
    ) -> LLMResponseHandler:
        """Factory for response handlers."""
        provider = provider.lower()

        if provider == "manual":
            return ManualResponseHandler(self.project_root)

        llm_provider = get_llm_provider(provider, model)
        return APIResponseHandler(llm_provider)
