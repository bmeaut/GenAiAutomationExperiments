import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from core.logger import log
from .project_handler import ProjectHandler


class DebugHelper:
    """Handles patch failures and test debugging."""

    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root)
        self.logs_dir = self.project_root / "results" / "test_logs"
        self.failed_patches_dir = self.project_root / "results" / "failed_patches"
        self.debug_dir = self.project_root / "results" / "patch_debug"

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
        self.debug_dir.mkdir(parents=True, exist_ok=True)

        safe_name = bug["repo_name"].replace("/", "_")
        sha = bug["bug_commit_sha"]
        debug_file = f"{safe_name}_{sha[:7]}_debug.json"
        debug_path = self.debug_dir / debug_file

        debug_path.write_text(json.dumps(patch_validation, indent=2), encoding="utf-8")
        log(f"  --> Debug info saved to: {debug_path}")

    def handle_patch_failure(
        self,
        patch_path: str,
        bug: dict[str, Any],
        handler: ProjectHandler,
    ) -> bool:
        """Pause for manual debugging when patch fails."""
        log("\n" + "=" * 60)
        log(">>> DEBUG MODE: Patch failed to apply. Execution is PAUSED.")

        # save broken patch
        self.failed_patches_dir.mkdir(parents=True, exist_ok=True)

        safe_name = bug["repo_name"].replace("/", "_")
        sha = bug["bug_commit_sha"]
        saved_patch = f"{safe_name}_{sha[:7]}.patch"
        saved_path = self.failed_patches_dir / saved_patch

        shutil.copy(patch_path, saved_path)

        log(f">>> FAILED PATCH SAVED TO: {saved_path}")
        log(f">>> Repo is here: {handler.repo_path}")
        log(">>> ")
        log(">>> You can now:")
        log(f"   • Edit the patch file: {saved_path}")
        log(f"   • Apply manually: git apply llm.patch")
        log(f"   • Or just fix the files directly")
        log(">>> ")
        log(">>> Press Enter to retry patch application...")
        input()

        log(">>> Retrying patch validation...")
        recheck = handler.validate_and_debug_patch_detailed(patch_path)

        if recheck.get("valid"):
            log(">>> Patch valid! Applying...")
            return handler.apply_patch(patch_path)

        log(">>> Patch still broken. Checking for manual edits...")

        try:
            # check git status
            result = subprocess.run(
                ["git", "diff", "--cached"],
                cwd=str(handler.repo_path),
                capture_output=True,
                text=True,
            )

            if result.stdout.strip():
                log(">>> Found staged changes.")
                return True

            result = subprocess.run(
                ["git", "diff"],
                cwd=str(handler.repo_path),
                capture_output=True,
                text=True,
            )

            if result.stdout.strip():
                log(">>> Found unstaged changes - staging them...")
                subprocess.run(
                    ["git", "add", "-A"],
                    cwd=str(handler.repo_path),
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return True

            log(">>> No changes found. Patch application failed.")
            return False

        except Exception as e:
            log(f">>> ERROR checking for manual changes: {e}")
            return False
