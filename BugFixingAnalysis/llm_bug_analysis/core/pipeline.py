import json
import csv
import os
from . import project_handler, analysis, llm_manager
from typing import Callable, Dict, Any


def _initialize_results_file(path: str):
    """Creates the results CSV file and writes the header row if it doesn't exist."""
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "repo_name",
                    "bug_commit_sha",
                    "parent_commit_sha",
                    "llm_model",
                    "complexity_before_cc",
                    "complexity_before_cognitive",
                    "llm_patch_applied",
                    "llm_tests_passed",
                    "complexity_after_llm_cc",
                    "complexity_after_llm_cognitive",
                    "human_tests_passed",
                    "complexity_after_human_cc",
                    "complexity_after_human_cognitive",
                ]
            )


def _run_ai_fix_evaluation(
    bug: Dict[str, Any],
    handler: project_handler.ProjectHandler,
    test_command: str,
    log_callback: Callable,
) -> Dict[str, Any]:

    log_callback("  Evaluating AI Fix...")

    parent_sha = bug["parent_commit_sha"]
    fix_sha = bug["bug_commit_sha"]

    buggy_code_context = handler.get_relevant_code_context(fix_sha)
    if not buggy_code_context:
        log_callback("  --> Skipping: Could not extract relevant .py code snippets.")
        return {"error": "Snippet extraction failed."}

    context_key = list(buggy_code_context.keys())[0]
    full_file_path = context_key.split(" ")[2]

    is_full_file_patch = False
    if len(buggy_code_context) > 1:
        log_callback(
            "  --> Warning: Multiple snippets found. Using full file for robust patching."
        )
        original_snippet = handler.get_full_file_content(full_file_path, parent_sha)
        llm_context = {f"Full file content from {full_file_path}": original_snippet}
        is_full_file_patch = True
    else:
        original_snippet = buggy_code_context[context_key]
        llm_context = buggy_code_context

    llm_fix_patch = llm_manager.generate_fix_manually(bug, llm_context)

    handler.checkout(parent_sha)
    applied_ok = handler.apply_patch(
        patch_text=llm_fix_patch,
        original_snippet=original_snippet,
        full_file_path=full_file_path,
        is_full_file=is_full_file_patch,
    )

    llm_tests_passed = False
    comp_after_llm = {"total_cc": "N/A", "total_cognitive": "N/A"}
    if applied_ok:
        llm_tests_passed = handler.run_tests(test_command, fix_sha, "ai_fix")
        comp_after_llm = analysis.analyze_files(
            handler.repo_path, [full_file_path], log_callback
        )
    else:
        log_callback("  --> LLM patch failed to apply. Tests will not be run.")

    return {
        "applied_ok": applied_ok,
        "tests_passed": llm_tests_passed,
        "complexity": comp_after_llm,
        "changed_files": [full_file_path],
    }


def _run_human_fix_evaluation(
    bug: Dict[str, Any],
    handler: project_handler.ProjectHandler,
    test_command: str,
    changed_files: list[str],
    log_callback: Callable,
) -> Dict[str, Any]:

    log_callback("  Evaluating Human Fix...")

    handler.reset_to_commit(bug["parent_commit_sha"])
    handler.checkout(bug["bug_commit_sha"])

    tests_passed = handler.run_tests(test_command, bug["bug_commit_sha"], "human_fix")
    complexity = analysis.analyze_files(handler.repo_path, changed_files, log_callback)

    return {"tests_passed": tests_passed, "complexity": complexity}


def _log_results(results_path: str, bug_data: Dict[str, Any]):
    """Appends a single row of results to the CSV file."""
    with open(results_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                bug_data.get("repo_name"),
                bug_data.get("bug_commit_sha"),
                bug_data.get("parent_commit_sha"),
                "manual-llm",
                bug_data.get("comp_before", {}).get("total_cc"),
                bug_data.get("comp_before", {}).get("total_cognitive"),
                bug_data.get("ai_results", {}).get("applied_ok"),
                bug_data.get("ai_results", {}).get("tests_passed"),
                bug_data.get("ai_results", {}).get("complexity", {}).get("total_cc"),
                bug_data.get("ai_results", {})
                .get("complexity", {})
                .get("total_cognitive"),
                bug_data.get("human_results", {}).get("tests_passed"),
                bug_data.get("human_results", {}).get("complexity", {}).get("total_cc"),
                bug_data.get("human_results", {})
                .get("complexity", {})
                .get("total_cognitive"),
            ]
        )


def run(log_callback, skip_llm_fix: bool = False):
    """The main operator for the analysis pipeline."""
    # load config, init results
    script_path = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(script_path))
    config_path = os.path.join(project_root, "config.json")
    corpus_path = os.path.join(project_root, "corpus.json")
    results_path = os.path.join(project_root, "results", "results.csv")

    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        with open(corpus_path, "r") as f:
            corpus = json.load(f)
        test_command = config.get("test_command", "pytest")
    except FileNotFoundError as e:
        log_callback(f"ERROR: {e.filename} not found.")
        return

    _initialize_results_file(results_path)

    # main loop: process each bug
    for bug in corpus:
        log_callback(
            f"\n--- Analyzing {bug['repo_name']} | Fix: {bug['bug_commit_sha'][:7]} ---"
        )
        handler = project_handler.ProjectHandler(bug["repo_name"], log_callback)
        try:
            handler.setup()

            results = {**bug}  # start with basic info

            if not skip_llm_fix:
                ai_results = _run_ai_fix_evaluation(
                    bug, handler, test_command, log_callback
                )
                if "error" in ai_results:
                    continue
                results["ai_results"] = ai_results
                changed_files = ai_results.get("changed_files", [])
            else:
                log_callback("  --> Skipping AI Fix evaluation as requested.")
                results["ai_results"] = {
                    "applied_ok": "SKIPPED",
                    "tests_passed": "SKIPPED",
                    "complexity": {"total_cc": "SKIPPED", "total_cognitive": "SKIPPED"},
                }
                # still need to find out which files were changed for the human analysis.
                changed_files = handler.get_changed_files(bug["bug_commit_sha"])

            # always run the human evaluation, for easier tesing
            results["comp_before"] = analysis.analyze_files(
                handler.repo_path, changed_files, log_callback
            )
            results["human_results"] = _run_human_fix_evaluation(
                bug, handler, test_command, changed_files, log_callback
            )

            log_callback(
                f"  Complexity Before: CC={results['comp_before']['total_cc']}, Cognitive={results['comp_before']['total_cognitive']}"
            )
            log_callback(
                f"  Complexity After LLM: CC={results['ai_results']['complexity']['total_cc']}, Cognitive={results['ai_results']['complexity']['total_cognitive']}"
            )
            log_callback(
                f"  Complexity After Human: CC={results['human_results']['complexity']['total_cc']}, Cognitive={results['human_results']['complexity']['total_cognitive']}"
            )

            _log_results(results_path, results)

        except Exception as e:
            log_callback(
                f"  FATAL ERROR during analysis of {bug['bug_commit_sha'][:7]}: {e}"
            )
        finally:
            handler.cleanup()


# def run(log_callback, skip_llm_fix: bool = False):
#     """
#     The main entry point for the analysis pipeline. It iterates through the
#     bug corpus and evaluates LLM and human fixes.
#     """
#     # build absolute paths from the script's location to ensure the application
#     # can be run from any directory without breaking file access.
#     script_path = os.path.abspath(__file__)
#     project_root = os.path.dirname(os.path.dirname(script_path))
#     config_path = os.path.join(project_root, "config.json")
#     corpus_path = os.path.join(project_root, "corpus.json")
#     results_dir = os.path.join(project_root, "results")
#     results_path = os.path.join(results_dir, "results.csv")

#     try:
#         with open(config_path, "r") as f:
#             config = json.load(f)
#         test_command = config.get("test_command", "pytest")

#         with open(corpus_path, "r") as f:
#             corpus = json.load(f)

#     except FileNotFoundError as e:
#         log_callback(f"ERROR: {e.filename} not found. Please ensure config.json and corpus.json exist.")
#         return

#     # Create the results CSV and write the header row if the file doesn't already exist.
#     if not os.path.exists(results_path):
#         os.makedirs(results_dir, exist_ok=True)
#         with open(results_path, "w", newline="", encoding="utf-8") as f:
#             writer = csv.writer(f)
#             writer.writerow([
#                 "repo_name", "bug_commit_sha", "parent_commit_sha", "llm_model",
#                 "complexity_before_cc", "complexity_before_cognitive",
#                 "llm_patch_applied", "llm_tests_passed",
#                 "complexity_after_llm_cc", "complexity_after_llm_cognitive",
#                 "human_tests_passed",
#                 "complexity_after_human_cc", "complexity_after_human_cognitive"
#             ])

#     for bug in corpus:
#         repo_name = bug["repo_name"]
#         parent_sha = bug["parent_commit_sha"]
#         fix_sha = bug["bug_commit_sha"]
#         log_callback(f"\n--- Analyzing {repo_name} | Fix: {fix_sha[:7]} ---")

#         handler = project_handler.ProjectHandler(repo_name, log_callback)
#         try:
#             handler.setup()

#             # --- THIS IS THE FIX ---
#             # We get the context and the list of changed files up front,
#             # as this information is needed for BOTH the AI and Human analysis paths.
#             buggy_code_context = handler.get_relevant_code_context(fix_sha)
#             if not buggy_code_context:
#                 log_callback(f"  Skipping commit {fix_sha[:7]}: Could not extract relevant .py code snippets.")
#                 continue

#             # This variable is now guaranteed to exist for the rest of the function.
#             context_key = list(buggy_code_context.keys())[0]
#             full_file_path = context_key.split(' ')[2]
#             changed_files = [full_file_path]

#             # --- AI Fix Evaluation (Now Conditional) ---
#             llm_tests_passed = "SKIPPED"
#             comp_after_llm = {"total_cc": "SKIPPED", "total_cognitive": "SKIPPED"}
#             applied_ok = "SKIPPED"

#             if not skip_llm_fix:
#                 log_callback(f"  Extracted {len(buggy_code_context)} snippet(s) from '{full_file_path}'.")

#                 # Determine context strategy (full file vs. snippet)
#                 is_full_file_patch = False
#                 if len(buggy_code_context) > 1:
#                     log_callback("  --> Warning: Multiple snippets found. Using full file for robust patching.")
#                     original_snippet = handler.get_full_file_content(full_file_path, parent_sha)
#                     llm_context = {f"Full file content from {full_file_path}": original_snippet}
#                     is_full_file_patch = True
#                 else:
#                     original_snippet = buggy_code_context[context_key]
#                     llm_context = buggy_code_context

#                 comp_before = analysis.analyze_files(handler.repo_path, changed_files, log_callback)
#                 log_callback(f"  Complexity Before: CC={comp_before['total_cc']}, Cognitive={comp_before['total_cognitive']}")

#                 llm_fix_patch = llm_manager.generate_fix_manually(bug, llm_context)

#                 handler.checkout(parent_sha)
#                 applied_ok = handler.apply_patch(
#                     patch_text=llm_fix_patch,
#                     original_snippet=original_snippet,
#                     full_file_path=full_file_path,
#                     is_full_file=is_full_file_patch
#                 )

#                 if applied_ok:
#                     llm_tests_passed = handler.run_tests(test_command, fix_sha, "ai_fix")
#                     comp_after_llm = analysis.analyze_files(handler.repo_path, changed_files, log_callback)
#                 else:
#                     llm_tests_passed = False
#                     log_callback("  LLM patch failed to apply. Tests will not be run.")
#             else:
#                 log_callback("  --> Skipping AI Fix evaluation as requested.")
#                 # We still need the 'before' complexity for the final report.
#                 comp_before = analysis.analyze_files(handler.repo_path, changed_files, log_callback)
#                 log_callback(f"  Complexity Before: CC={comp_before['total_cc']}, Cognitive={comp_before['total_cognitive']}")

#             # --- Human Fix Evaluation ---
#             log_callback("  Evaluating Human Fix...")
#             handler.reset_to_commit(parent_sha)
#             handler.checkout(fix_sha)

#             human_tests_passed = handler.run_tests(test_command, fix_sha, "human_fix")
#             comp_after_human = analysis.analyze_files(handler.repo_path, changed_files, log_callback)
#             log_callback(f"  Complexity After Human: CC={comp_after_human['total_cc']}, Cognitive={comp_after_human['total_cognitive']}")

#             # Log all the data to the CSV file
#             with open(results_path, "a", newline="", encoding="utf-8") as f:
#                 writer = csv.writer(f)
#                 writer.writerow([
#                     repo_name, fix_sha, parent_sha, "manual-llm",
#                     comp_before["total_cc"], comp_before["total_cognitive"],
#                     applied_ok, llm_tests_passed,
#                     comp_after_llm["total_cc"], comp_after_llm["total_cognitive"],
#                     human_tests_passed,
#                     comp_after_human["total_cc"], comp_after_human["total_cognitive"]
#                 ])

#         except Exception as e:
#             # this broad exception handler is a safety net to ensure that a single,
#             # unexpected error on one bug doesn't terminate the entire analysis run.
#             log_callback(f"  FATAL ERROR during analysis of {fix_sha[:7]}: {e}")
#         finally:
#             # the finally block guarantees that the temporary directory is cleaned up,
#             # even if a fatal error occurred during the analysis.
#             handler.cleanup()
