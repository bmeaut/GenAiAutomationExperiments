import csv
import datetime
from pathlib import Path
from typing import Any


class ResultsLogger:
    """Manages results file for analysis."""

    HEADERS = [
        "timestamp",
        "repo_name",
        "bug_commit_sha",
        "file_path",
        "commit_message",
        "issue_title",
        "issue_body",
        "llm_model",
        "llm_provider",
        "llm_prompt_tokens",
        "llm_completion_tokens",
        "llm_thinking_tokens",
        "llm_total_tokens",
        "complexity_before_cc",
        "complexity_before_cognitive",
        "complexity_before_avg_params",
        "complexity_before_total_tokens",
        "llm_patch_applied",
        "llm_tests_passed",
        "ai_lines_added",
        "ai_lines_deleted",
        "ai_total_diff",
        "complexity_after_llm_cc",
        "complexity_after_llm_cognitive",
        "complexity_after_llm_avg_params",
        "complexity_after_llm_total_tokens",
        "human_tests_passed",
        "human_lines_added",
        "human_lines_deleted",
        "human_total_diff",
        "complexity_after_human_cc",
        "complexity_after_human_cognitive",
        "complexity_after_human_avg_params",
        "complexity_after_human_total_tokens",
    ]

    def __init__(self, results_path: str | Path):
        self.results_path = Path(results_path)
        self._initialize_file()

    def _initialize_file(self):
        """Create CSV file with headers if it doesn't exist."""
        if not self.results_path.exists():
            self.results_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.results_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self.HEADERS)

    def log(self, bug_data: dict[str, Any]):
        """Append analysis results to CSV."""
        with open(self.results_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            ai_results = bug_data.get("ai_results", {})
            human_results = bug_data.get("human_results", {})
            comp_before = bug_data.get("comp_before", {})

            llm_metadata = ai_results.get("llm_metadata", {})
            ai_stats = ai_results.get("patch_stats", {})
            ai_comp = ai_results.get("complexity", {})
            human_stats = human_results.get("patch_stats", {})
            human_comp = human_results.get("complexity", {})

            file_paths_str = "; ".join(bug_data.get("changed_files", []))

            writer.writerow(
                [
                    datetime.datetime.now().isoformat(),
                    bug_data.get("repo_name"),
                    bug_data.get("bug_commit_sha"),
                    file_paths_str,
                    bug_data.get("commit_message"),
                    bug_data.get("issue_title"),
                    bug_data.get("issue_body"),
                    llm_metadata.get("model", "N/A"),
                    llm_metadata.get("provider", "N/A"),
                    llm_metadata.get("prompt_tokens", "N/A"),
                    llm_metadata.get("completion_tokens", "N/A"),
                    llm_metadata.get("thinking_tokens", "N/A"),
                    llm_metadata.get("total_tokens", "N/A"),
                    comp_before.get("total_cc"),
                    comp_before.get("total_cognitive"),
                    comp_before.get("avg_params"),
                    comp_before.get("total_tokens"),
                    ai_results.get("applied_ok"),
                    ai_results.get("tests_passed"),
                    ai_stats.get("lines_added", "SKIPPED"),
                    ai_stats.get("lines_deleted", "SKIPPED"),
                    ai_stats.get("total", "SKIPPED"),
                    ai_comp.get("total_cc"),
                    ai_comp.get("total_cognitive"),
                    ai_comp.get("avg_params"),
                    ai_comp.get("total_tokens"),
                    human_results.get("tests_passed"),
                    human_stats.get("lines_added", "SKIPPED"),
                    human_stats.get("lines_deleted", "SKIPPED"),
                    human_stats.get("total", "SKIPPED"),
                    human_comp.get("total_cc"),
                    human_comp.get("total_cognitive"),
                    human_comp.get("avg_params"),
                    human_comp.get("total_tokens"),
                ]
            )
