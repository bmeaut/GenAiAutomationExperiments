from pathlib import Path
from typing import Any

from core.logger import log
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
        patch_cache_dir: Path | None = None,
    ):
        self.test_command = test_command
        self.config = config
        self.debug_helper = debug_helper
        self.project_root = Path(project_root)
        self.context_cache_dir = context_cache_dir
        self.patch_cache_dir = patch_cache_dir
        self.llm_manager = LLMManager(project_root, context_cache_dir, patch_cache_dir)

    def evaluate_ai_fix(
        self,
        bug: dict[str, Any],
        handler: ProjectHandler,
        parent_sha: str,
        changed_files: list,
        debug_mode: bool,
        llm_fix: dict[str, Any] | None = None,  # optional for pregenerated result
        context_text: str | None = None,  # optional prebuilt context TODO: both??
        llm_provider: str = "gemini",
        llm_model: str = "gemini-2.5-flash",
    ) -> dict[str, Any]:
        """Generate and evaluate the AI fix (or use pre-generated)"""
        log("  Evaluating AI Fix with AAG/RAG...")

        # start at buggy state
        handler.checkout(parent_sha)

        if llm_fix is None:
            if context_text is None:
                from core.context_builder import ContextBuilder

                builder = ContextBuilder(
                    repo_path=handler.repo_path,
                    max_snippets=5,
                    debug=True,
                    cache_dir=self.context_cache_dir,
                )

                if "changed_files" not in bug:
                    bug["changed_files"] = changed_files

                # TODO: do I need this context here?
                context, context_text = builder.build_and_format(bug)
                log(f"  --> Added changed files: {changed_files}")

                # generate fix
                llm_fix = self.llm_manager.generate_fix(
                    bug, context_text, llm_provider, llm_model
                )

        # TODO: validate LLM results, here or somewhere else?
        if not llm_fix or not llm_fix.get("intent"):
            log("  --> ERROR: Failed to get valid fix from LLM.")
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
        test_ok = handler.venv.run_tests(
            test_command=self.test_command,
            config=self.config,
            repo_name=bug["repo_name"],
            commit_sha=bug["bug_commit_sha"],
            run_type="human_fix",
            debug_helper=self.debug_helper,
        )

        return {
            "tests_passed": test_ok,
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

        tests_ok = handler.venv.run_tests(
            test_command=self.test_command,
            config=self.config,
            repo_name=bug["repo_name"],
            commit_sha=bug["bug_commit_sha"],
            run_type="ai_fix",
            debug_helper=self.debug_helper,
        )

        handler.reset_to_commit(parent_sha)

        return {
            "applied_ok": True,
            "tests_passed": tests_ok,
            "complexity": complexity,
            "patch_stats": patch_stats,
        }

    def _failed_results(self, reason: str) -> dict[str, Any]:
        """Results dictionary for failed AI fix."""
        return {
            "applied_ok": False,
            "tests_passed": False,
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
