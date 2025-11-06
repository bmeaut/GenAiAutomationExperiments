from pathlib import Path
from typing import Any

from .logger import log
from .project_handler import ProjectHandler
from .analysis import analyze_files
from .patch_generator import PatchGenerator
from .debug_helper import DebugHelper
from .llm_manager import LLMManager


class PatchEvaluator:
    """Tests and compares AI vs human bugfixes."""

    def __init__(
        self,
        test_command: str,
        config: dict[str, Any],
        debug_helper: DebugHelper,
        project_root: Path,
        context_cache_dir: Path | None = None,
        llm_response_cache_dir: Path | None = None,
    ):
        self.test_command = test_command
        self.config = config
        self.debug_helper = debug_helper
        self.project_root = Path(project_root)
        self.context_cache_dir = context_cache_dir
        self.llm_manager = LLMManager(
            project_root, context_cache_dir, llm_response_cache_dir
        )

    def evaluate_ai_fix(
        self,
        bug: dict[str, Any],
        handler: ProjectHandler,
        parent_sha: str,
        changed_files: list,
        debug_mode: bool,
        llm_fix: dict[str, Any],
    ) -> dict[str, Any]:
        """Evaluate pre-generated AI fix from stage 2."""
        log("  Evaluating AI Fix with AAG/RAG...")

        # start at buggy state
        handler.checkout(parent_sha)

        # TODO: validate LLM results, here or somewhere else?
        if not llm_fix or not llm_fix.get("intent"):
            log("  --> ERROR: Invalid or missing llm_fix from stage 2.")
            return self._failed_results("INTENT_PARSE_FAILED")

        intent = llm_fix["intent"]
        log(f"  --> Fix Analysis: {intent.get('analysis', 'N/A')}")
        log(f"  --> Fix Type: {intent.get('fix_type', 'N/A')}")
        log(
            f"  --> Target: {intent.get('target_file', 'N/A')}.{intent.get('target_class', 'N/A')}"
        )
        log(f"  --> Confidence: {intent.get('confidence', 0.0)}")

        generator = PatchGenerator(handler.repo_path)
        patch = generator.generate(intent)

        if not patch:
            log("  --> ERROR: Failed to generate patch from intent.")
            return self._failed_results("PATCH_GENERATION_FAILED")

        log("  --> Patch generated successfully")

        stats = PatchGenerator.count_patch_stats(patch)
        log(f"  --> Patch: +{stats['lines_added']}/-{stats['lines_deleted']} lines")

        metadata = {
            "provider": llm_fix.get("provider", "unknown"),
            "model": llm_fix.get("model", "unknown"),
            "prompt_tokens": llm_fix.get("metadata", {}).get("prompt_tokens", 0),
            "completion_tokens": llm_fix.get("metadata", {}).get(
                "completion_tokens", 0
            ),
            "thinking_tokens": llm_fix.get("metadata", {}).get("thinking_tokens", 0),
            "total_tokens": llm_fix.get("metadata", {}).get("total_tokens", 0),
            "generation_time_seconds": llm_fix.get("metadata", {}).get(
                "generation_time_seconds", 0
            ),
        }

        # apply and test the patch
        result = self._test_ai_patch(
            patch, stats, handler, parent_sha, changed_files, bug, debug_mode
        )

        result["llm_metadata"] = metadata
        return result

    def evaluate_human_fix(
        self,
        handler: ProjectHandler,
        fix_sha: str,
        changed_files: list,
        bug: dict[str, Any],
    ) -> dict[str, Any]:
        """Test human written fix."""
        import time

        log("  Evaluating Human Fix...")

        handler.checkout(fix_sha)

        repo_path = Path(handler.repo_path)
        existing_files = [f for f in changed_files if (repo_path / f).exists()]

        complexity = analyze_files(str(handler.repo_path), existing_files)

        # get patch stats
        patch_text = handler.get_human_patch(fix_sha)
        stats = PatchGenerator.count_patch_stats(patch_text)
        log(
            f"    --> Human Patch Stats: +{stats['lines_added']}/-{stats['lines_deleted']} lines"
        )

        # run tests
        test_start = time.time()
        test_ok = handler.venv.run_tests(
            test_command=self.test_command,
            config=self.config,
            repo_name=bug["repo_name"],
            commit_sha=bug["bug_commit_sha"],
            run_type="human_fix",
            debug_helper=self.debug_helper,
        )
        test_time = time.time() - test_start

        return {
            "tests_passed": test_ok,
            "test_time_seconds": test_time,
            "complexity": complexity,
            "patch_stats": stats,
        }

    def _test_ai_patch(
        self,
        patch: str,
        patch_stats: dict[str, int],
        handler: ProjectHandler,
        parent_sha: str,
        changed_files: list,
        bug: dict[str, Any],
        debug_mode: bool,
    ) -> dict[str, Any]:
        """Apply AI patch and run tests."""
        import time

        repo_path = Path(handler.repo_path)
        patch_file = repo_path / "llm.patch"
        patch_file.write_text(patch, encoding="utf-8")

        handler.checkout(parent_sha)

        validation = handler.validate_and_debug_patch_detailed(str(patch_file))

        if not validation["valid"]:
            self.debug_helper.log_validation_errors(validation)
            self.debug_helper.save_debug_info(validation, bug)

        # try to apply
        ok = handler.apply_patch(str(patch_file))

        if not ok and debug_mode:
            ok = self.debug_helper.handle_patch_failure(str(patch_file), bug, handler)

        if not ok:
            handler.reset_to_commit(parent_sha)
            return {
                "applied_ok": False,
                "tests_passed": False,
                "complexity": self.na_complexity(),
                "patch_stats": patch_stats,
            }

        # applied successfully - analyze and test
        existing_files = [f for f in changed_files if (repo_path / f).exists()]
        complexity = analyze_files(str(handler.repo_path), existing_files)

        human_sha = bug.get("bug_commit_sha", "")
        if human_sha:
            test_files = self._get_changed_test_files(handler, human_sha)
            if test_files:
                self._copy_human_tests_to_ai_workspace(handler, human_sha, test_files)

        test_start = time.time()
        tests_ok = handler.venv.run_tests(
            test_command=self.test_command,
            config=self.config,
            repo_name=bug["repo_name"],
            commit_sha=bug["bug_commit_sha"],
            run_type="ai_fix",
            debug_helper=self.debug_helper,
        )
        test_time = time.time() - test_start

        handler.reset_to_commit(parent_sha)

        return {
            "applied_ok": True,
            "tests_passed": tests_ok,
            "test_time_seconds": test_time,
            "complexity": complexity,
            "patch_stats": patch_stats,
        }

    def _failed_results(self, reason: str) -> dict[str, Any]:
        """Results dictionary for failed AI fix."""
        return {
            "applied_ok": False,
            "tests_passed": False,
            "test_time_seconds": 0.0,
            "complexity": {
                "total_cc": reason,
                "total_cognitive": reason,
                "avg_params": reason,
                "total_tokens": reason,
            },
            "patch_stats": {
                "lines_added": 0,
                "lines_deleted": 0,
                "total": 0,
            },
            "llm_metadata": {
                "provider": "FAILED",
                "model": "FAILED",
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "thinking_tokens": 0,
                "total_tokens": 0,
                "generation_time_seconds": 0.0,
            },
        }

    def na_complexity(self) -> dict[str, str]:
        """Dictionary for patch that couldn't apply."""
        return {
            "total_cc": "N/A",
            "total_cognitive": "N/A",
            "avg_params": "N/A",
            "total_tokens": "N/A",
        }

    def _is_test_file(self, filepath: Path | str) -> bool:
        """Check if a file is part of the test suite."""
        path = Path(filepath)

        if path.name.startswith("test_") or path.name.endswith("_test.py"):
            return True
        if "test" in path.parts:
            return True
        if path.parent.name in ("tests", "test"):
            return True

        return False

    def _get_changed_test_files(
        self,
        handler: ProjectHandler,
        human_sha: str,
    ) -> list[str]:
        """Get list test file that were changed in human fix."""
        all_changed = handler.get_changed_files(human_sha)

        test_files = [f for f in all_changed if self._is_test_file(f)]
        if test_files:
            log(f"    --> Found {len(test_files)} changed test file(s):")
            for tf in test_files:
                log(f"        - {tf}")

        return test_files

    def _copy_human_tests_to_ai_workspace(
        self, handler: ProjectHandler, human_sha: str, test_files: list[str]
    ) -> bool:
        """Copy human's test files into AI patched version."""
        if not test_files:
            return True

        log(f"    --> Copying {len(test_files)} human test file(s)...")

        for test_file in test_files:
            try:
                human_content = handler.get_file_at_commit(human_sha, test_file)

                if human_content is None:
                    log(
                        f"        WARNING: Test file {test_file} not found in human fix."
                    )
                    continue

                test_path = handler.repo_path / Path(test_file)
                test_path.parent.mkdir(parents=True, exist_ok=True)
                test_path.write_text(human_content, encoding="utf-8")

                log(f"        - Copied {test_file}")

            except Exception as e:
                log(f"        ERROR: Failed to copy {test_file}: {e}")
                return False

        return True
