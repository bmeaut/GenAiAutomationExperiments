import os
import re
import json
import time
from typing import Dict, Any, Optional, Callable
from .context_builder import ContextBuilder
from .llm_providers import get_llm_provider
from abc import ABC, abstractmethod

FILE_WRITE_DELAY = 0.5


class LLMResponseHandler(ABC):
    """
    Abstract base class for LLM response handlers.

    Uses Template Method pattern - defines the algorithm structure,
    subclasses implement specific steps.
    """

    def __init__(self, log_callback: Callable[[str], None]):
        self.log: Callable[[str], None] = log_callback
        # does type checker need this or overkill?

    def get_response(self, prompt: str) -> Dict[str, Any]:
        """
        Template method - orchestrates getting response from LLM.

        This method defines the algorithm that all handlers follow:
        1. Log start
        2. Fetch the response (implemented by subclass)
        3. Return structured result with text and metadata
        """
        #  1: log that we're starting
        self._log_start()

        # 2: fetch response (subclasses implement this)
        response_text = self._fetch_response(prompt)

        # 3: build and return result
        return {"text": response_text, "metadata": self._get_metadata()}

    @abstractmethod
    def _fetch_response(self, prompt: str) -> str:
        """
        Fetch response from LLM.

        Subclasses must implement this to define HOW to get the response
        (API call, file, stdin, etc.)
        """
        pass

    @abstractmethod
    def _log_start(self) -> None:
        """
        Log that we're starting to fetch response.

        Subclasses implement this to show provider-specific messages.
        """
        pass

    def _get_metadata(self) -> Dict[str, int]:
        """
        Get metadata about the response (token counts, etc.).

        Default implementation returns zeros.
        Subclasses can override to provide real data.
        """
        return {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "thinking_tokens": 0,
            "total_tokens": 0,
        }


class GeminiResponseHandler(LLMResponseHandler):
    """Handler for Gemini API responses."""

    def __init__(self, model: str, log_callback: Callable[[str], None]):
        super().__init__(log_callback)
        self.model = model
        self._metadata = {}

    def _log_start(self) -> None:
        self.log(f"  --> Using Gemini API ({self.model})")
        self.log(f"  --> Generating fix...")

    def _fetch_response(self, prompt: str) -> str:

        try:

            llm = get_llm_provider(self.model)
            result = llm.generate_fix(prompt)

            self._metadata = result.get("metadata", {})

            self._log_token_usage()

            return result.get("text", "")

        except Exception as e:
            self.log(f"  --> ERROR: Gemini API call failed: {e}")
            return ""  # verbose error handling in GeminiProvider

    def _get_metadata(self) -> Dict[str, int]:
        return self._metadata

    def _log_token_usage(self) -> None:
        total = self._metadata.get("total_tokens", 0)
        prompt = self._metadata.get("prompt_tokens", 0)
        thinking = self._metadata.get("thinking_tokens", 0)
        completion = self._metadata.get("completion_tokens", 0)

        self.log(
            f"  --> Token usage: {total} total "
            f"({prompt} prompt + {thinking} thinking + {completion} completion)"
        )


class ManualResponseHandler(LLMResponseHandler):
    """Handler for manual file-based workflow."""

    def __init__(
        self,
        project_root: str,
        log_callback: Callable[[str], None],
        timeout_seconds: int = 300,
        poll_interval: int = 2,
    ):
        """
        Initialize manual handler.

        Args:
            project_root: Path to save prompt/response files
            log_callback: Function to log messages
            timeout_seconds: Max time to wait for response file (default: 5 minutes)
            poll_interval: Seconds between file checks (default: 2)
        """
        super().__init__(log_callback)
        self.project_root = project_root
        self.timeout_seconds = timeout_seconds
        self.poll_interval = poll_interval

        self.prompt_file = os.path.join(project_root, "llm_prompt.txt")
        self.response_file = os.path.join(project_root, "llm_response.txt")

    def _log_start(self) -> None:
        """Log instructions for manual workflow."""
        self.log(f"  --> Prompt saved to: {self.prompt_file}")
        self.log(f"  --> Waiting for response file: {self.response_file}")
        self.log("  --> Please:")
        self.log("      1. Copy the prompt from llm_prompt.txt")
        self.log("      2. Paste it to your LLM")
        self.log("      3. Save the LLM's response as llm_response.txt")
        self.log("      4. The tool will auto-continue when the file appears!")
        self.log("")
        self.log("  --> Or press Ctrl+C to enter response manually...")

    def _fetch_response(self, prompt: str) -> str:
        """Get response via file or stdin."""

        self._save_prompt(prompt)

        try:

            response = self._wait_for_response_file()
            if response:
                return response

            # timeout - fall back to stdin
            self.log(
                f"  --> Timeout after {self.timeout_seconds}s waiting for response file"
            )
            self.log("  --> Falling back to manual input mode...")

        except KeyboardInterrupt:
            # user pressed ctrl+c - fall back to stdin
            pass

        return self._get_stdin_response()

    def _save_prompt(self, prompt: str) -> None:
        """Save prompt to file."""
        with open(self.prompt_file, "w", encoding="utf-8") as f:
            f.write(prompt)

    def _wait_for_response_file(self) -> Optional[str]:
        """Wait for response file to appear."""
        elapsed = 0

        while elapsed < self.timeout_seconds:

            if os.path.exists(self.response_file):
                self.log(f"  --> Response file detected after {elapsed}s!")

                # small delay to ensure file is fully written
                time.sleep(FILE_WRITE_DELAY)

                try:
                    with open(self.response_file, "r", encoding="utf-8") as f:
                        response_text = f.read()
                except Exception as e:
                    self.log(f"  --> ERROR: Could not read response file: {e}")
                    return None

                self._cleanup_files()

                return response_text

            # show progress
            if elapsed % 10 == 0 and elapsed > 0:
                self.log(f"  --> Still waiting... ({elapsed}s elapsed)")

            # wait before next check
            time.sleep(self.poll_interval)
            elapsed += self.poll_interval

        # timeout - no file found
        return None

    def _get_stdin_response(self) -> str:
        """Get response from standard command line."""
        self.log("")
        self.log("  --> Manual input mode activated")
        self.log("  --> Paste the LLM response below and press Ctrl+D on a new line:")
        self.log("")

        lines = []
        try:
            while True:
                line = input()
                lines.append(line)
        except EOFError:
            pass  # user pressed ctrl+d - done reading

        self._cleanup_files()

        return "\n".join(lines)

    def _cleanup_files(self) -> None:
        """Delete prompt and response files."""
        self.log("  --> Cleaning up prompt and response files...")

        for filepath in [self.prompt_file, self.response_file]:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception as e:
                self.log(f"  --> Warning: Could not delete {filepath}: {e}")

        self.log("  --> Files cleaned up")


class IntentParser:
    """Parses LLM responses to extract intended structured fix."""

    # pre-compiled regex maybe needed for batch processing?
    # llm thinking response is so much slower, not worth it in current use case
    JSON_PATTERNS = [
        (r"```json\s*\n(.*?)\n```", 1, "```json block"),
        (r"```\s*\n(.*?)\n```", 1, "``` block"),
        (r"\{.*\}", 0, "JSON object directly"),
    ]

    def __init__(self, log_callback: Callable[[str], None]):
        self.log = log_callback

    def parse(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Parse LLM response to extract JSON intent."""
        if not response_text or not response_text.strip():
            self.log("  --> ERROR: Empty response")
            return None

        self._debug_response(response_text)

        # 1: extract JSON from response
        json_text = self._extract_json(response_text)
        if not json_text:
            self.log("  --> ERROR: Could not find JSON in response")
            return None

        self._debug_extracted_json(json_text)

        # 2: try to parse
        intent = self._parse_json(json_text)
        if intent:
            return self._validate_intent(intent)

        # 3: try to fix and parse again
        self.log("  --> Attempting to fix JSON and retry...")
        json_text_cleaned = self._clean_json(json_text)
        intent = self._parse_json(json_text_cleaned)

        if intent:
            return self._validate_intent(intent)

        # 4: all parsing failed
        self._debug_failed_json(json_text_cleaned)
        return None

    def _extract_json(self, response_text: str) -> Optional[str]:
        """Extract JSON from response text."""

        for pattern, group_idx, description in self.JSON_PATTERNS:
            match = re.search(pattern, response_text, re.DOTALL)
            if match:
                self.log(f"DEBUG: Found JSON in {description}")
                return match.group(group_idx)

        self.log("DEBUG: Using entire response as JSON")
        return response_text

    def _parse_json(self, json_text: str) -> Optional[Dict[str, Any]]:
        """Parse JSON text."""
        try:
            intent = json.loads(json_text)
            self.log("  --> Successfully parsed JSON intent")
            return intent
        except json.JSONDecodeError as e:
            self.log(f"  --> ERROR: Failed to parse JSON: {e}")
            self.log(f"  --> Error at line {e.lineno}, column {e.colno}")
            return None

    def _clean_json(self, json_text: str) -> str:
        """Fix common JSON issues."""

        # remove trailing commas
        cleaned = re.sub(r",(\s*[}\]])", r"\1", json_text)

        # strip whitespace
        cleaned = cleaned.strip()

        return cleaned

    def _validate_intent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate intent has required fields.

        Logs warnings for missing fields but returns intent anyway
        (might not need all fields).
        """

        required_fields = ["fix_type", "target_file", "new_code"]
        missing = [f for f in required_fields if f not in intent]

        if missing:
            self.log(f"  --> WARNING: Missing required fields: {missing}")

        return intent

    def _debug_response(self, response_text: str) -> None:
        """Debug: Log response summary."""
        self.log("\n" + "=" * 60)
        self.log("DEBUG: Parsing LLM Intent")
        self.log(f"DEBUG: Response length: {len(response_text)} chars")
        self.log(f"DEBUG: First 200 chars: {response_text[:200]}")
        self.log("=" * 60 + "\n")

    def _debug_extracted_json(self, json_text: str) -> None:
        """Debug: Log extracted JSON summary."""
        self.log(f"DEBUG: Extracted JSON length: {len(json_text)} chars")
        self.log(f"DEBUG: First 300 chars of JSON: {json_text[:300]}")

    def _debug_failed_json(self, json_text: str) -> None:
        """Debug: Log failed JSON for inspection."""
        self.log(f"DEBUG: Failed JSON text:\n{json_text[:500]}")


def generate_fix_with_intent(
    bug: Dict[str, Any],
    repo_path: str,
    log_callback: Callable,
    provider: str = "gemini",
    model: str = "gemini-2.5-flash",
) -> Dict[str, Any]:
    """
    Generate fix using AAG/RAG context and ask for structured response.
    """
    # 1: build rich context using AAG/RAG
    builder = ContextBuilder(
        repo_path=repo_path, max_snippets=5, debug=True, log_callback=log_callback
    )
    context, context_text = builder.build_and_format(bug, log_callback)

    # 2: build prompt from template
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    prompt = _build_prompt(bug, context_text, project_root, log_callback)

    # 3: get response from LLM using appropriate handler
    handler = _create_response_handler(provider, model, project_root, log_callback)
    result = handler.get_response(prompt)

    response_text = result.get("text", "")
    metadata = result.get("metadata", {})

    result_model = model if provider == "gemini" else "manual"

    # 4: validate we got a response
    if not response_text or not response_text.strip():
        log_callback("  --> ERROR: No response received!")
        return {
            "intent": None,
            "context": context,
            "prompt": prompt,
            "raw_response": "",
            "provider": provider,
            "model": result_model,
            "metadata": metadata,
        }

    log_callback(f"  --> Response received ({len(response_text)} chars)")

    # 5: parse the JSON response
    parser = IntentParser(log_callback)
    intent = parser.parse(response_text)

    # 6: return complete result
    return {
        "intent": intent,
        "context": context,
        "prompt": prompt,
        "raw_response": response_text,
        "provider": provider,
        "model": result_model,
        "metadata": metadata,
    }


def _build_prompt(
    bug: Dict[str, Any],
    context_text: str,
    project_root: str,
    log_callback: Callable,
) -> str:
    """Build prompt from template and bug data."""
    template_path = os.path.join(
        project_root, "llm_bug_analysis", "prompts", "generate_fix.txt"
    )

    if not os.path.exists(template_path):
        error_msg = f"ERROR: Prompt template not found at {template_path}"
        log_callback(f"  --> {error_msg}")
        raise FileNotFoundError(error_msg)

    with open(template_path, "r", encoding="utf-8") as f:
        prompt_template = f.read()

    return prompt_template.format(
        repo_name=bug.get("repo_name", "Unknown"),
        bug_commit_sha=bug.get("bug_commit_sha", "Unknown")[:7],
        issue_title=bug.get("issue_title", "No title"),
        issue_body=bug.get("issue_body", "No description provided"),
        code_context=context_text,
    )


def _create_response_handler(
    provider: str,
    model: str,
    project_root: str,
    log_callback: Callable,
) -> LLMResponseHandler:
    """Create response handler based on provider."""
    if provider.lower() == "gemini":
        return GeminiResponseHandler(model, log_callback)
    else:
        return ManualResponseHandler(project_root, log_callback)
