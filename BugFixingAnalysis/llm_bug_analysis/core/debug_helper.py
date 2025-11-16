from __future__ import annotations
import json
import subprocess
from pathlib import Path
from typing import Any

from .logger import log


class DebugHelper:
    """Handles patch failures and test debugging."""

    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root)
        self.logs_dir = self.project_root / "results" / "test_logs"
        self.failed_patches_dir = (
            self.project_root / "results" / "debug" / "failed_patches"
        )
        self.validation_errors_dir = (
            self.project_root / "results" / "debug" / "validation_errors"
        )

    def save_test_failure_log(
        self,
        repo_name: str,
        commit_sha: str,
        run_type: str,
        error: subprocess.CalledProcessError,
    ) -> Path:
        """Save stdout/stderr from failed test run."""
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        repo_name_safe = repo_name.replace("/", "_")
        log_filename = f"{repo_name_safe}_{commit_sha[:7]}_{run_type}.log"
        log_path = self.logs_dir / log_filename

        log_content = (
            f"TEST RUN FAILED\n"
            f"-----------------\n"
            f"Repo:    {repo_name}\n"
            f"Commit:  {commit_sha}\n"
            f"Type:    {run_type}\n"
            f"Exit:    {error.returncode}\n"
            f"-----------------\n\n"
            f"--- STDOUT ---\n{error.stdout}\n\n"
            f"--- STDERR ---\n{error.stderr}\n"
        )

        log_path.write_text(log_content, encoding="utf-8")
        return log_path

    def log_validation_errors(self, patch_validation: dict):
        """Log why a patch failed validation."""
        log("  --> Patch validation failed:")

        for error in patch_validation.get("errors", []):
            log(f"      ERROR: {error}")

        for file_path, analysis in patch_validation.get("file_analysis", {}).items():
            log(f"      File: {file_path}")
            if not isinstance(analysis, dict):
                continue

            for hunk_key, hunk_data in analysis.items():
                if not hunk_key.startswith("hunk_") or not isinstance(hunk_data, dict):
                    continue

                issues = hunk_data.get("issues", [])
                if issues:
                    log(f"        {hunk_key}: {', '.join(issues)}")

                suggested = hunk_data.get("suggested_location")
                if suggested:
                    log(f"        Try line {suggested} instead?")

    def save_debug_info(self, patch_validation: dict, bug: dict[str, Any]):
        """Save detailed information for failed patches."""
        self.validation_errors_dir.mkdir(parents=True, exist_ok=True)

        safe_name = bug["repo_name"].replace("/", "_")
        sha = bug["bug_commit_sha"]
        debug_file = f"{safe_name}_{sha[:7]}_validation.json"
        debug_path = self.validation_errors_dir / debug_file

        debug_path.write_text(json.dumps(patch_validation, indent=2), encoding="utf-8")
        log(f"  --> Validation errors saved to: {debug_path}")
