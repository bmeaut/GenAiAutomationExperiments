import json
import csv
import os
from . import project_handler, analysis, llm_manager
from typing import Callable, Dict, Any
import subprocess


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


def _save_test_failure_log(
    project_root: str,
    repo_name: str,
    commit_sha: str,
    run_type: str,
    error: subprocess.CalledProcessError,
):
    """Saves the detailed stdout and stderr from a failed test run to a log file."""
    logs_dir = os.path.join(project_root, "results", "test_logs")
    os.makedirs(logs_dir, exist_ok=True)
    repo_name_safe = repo_name.replace("/", "_")
    log_filename = f"{repo_name_safe}_{commit_sha[:7]}_{run_type}.log"
    log_path = os.path.join(logs_dir, log_filename)

    log_content = (
        f"TEST RUN FAILED\n"
        f"-----------------\n"
        f"Repository: {repo_name}\nCommit SHA: {commit_sha}\nRun Type:   {run_type}\n"
        f"Return Code: {error.returncode}\n-----------------\n\n"
        f"--- STDOUT ---\n{error.stdout}\n\n--- STDERR ---\n{error.stderr}\n"
    )
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(log_content)
    return log_path


def _run_ai_fix_evaluation(
    bug: Dict[str, Any],
    handler: project_handler.ProjectHandler,
    test_command: str,
    log_callback: Callable,
    project_root: str,
    config: Dict[str, Any],
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

    full_test_command_list = test_command.split()

    exclusions = config.get("test_exclusions", {}).get(bug["repo_name"], {})

    ignore_list = exclusions.get("ignore_paths", [])
    full_test_command_list = test_command.split()
    if ignore_list:
        log_callback(f"    --> Ignoring {len(ignore_list)} known flaky test(s).")
        for test_to_deselect in ignore_list:
            full_test_command_list.extend(["--ignore", test_to_deselect])

    deselect_list = exclusions.get("deselect_nodes", [])
    if deselect_list:
        log_callback(f"    --> Deselecting {len(deselect_list)} test(s) as configured.")
        for path_to_ignore in deselect_list:
            full_test_command_list.extend(["--deselect", path_to_ignore])

    tests_passed = False
    try:
        result = handler.run_tests_in_venv(full_test_command_list)
        tests_passed = True
        summary_line = "No summary line found."
        for line in result.stdout.splitlines():
            if "passed" in line and "in" in line and "s" in line:
                summary_line = line.strip("=")
        log_callback(f"    --> AI Fix Tests PASSED. Summary: {summary_line}")

    except subprocess.CalledProcessError as e:
        tests_passed = False
        log_callback(f"    --> AI Fix Tests FAILED. Return code: {e.returncode}")
        # save detailed log
        log_path = _save_test_failure_log(
            project_root, bug["repo_name"], fix_sha, "ai_fix", e
        )
        log_callback(f"    --> Detailed logs saved to: {log_path}")

    comp_after_llm = analysis.analyze_files(
        handler.repo_path, [full_file_path], log_callback
    )

    return {
        "applied_ok": applied_ok,
        "tests_passed": tests_passed,
        "complexity": comp_after_llm,
        "changed_files": [full_file_path],
    }


def _run_human_fix_evaluation(
    bug: Dict[str, Any],
    handler: project_handler.ProjectHandler,
    test_command: str,
    changed_files: list[str],
    log_callback: Callable,
    project_root: str,
    config: Dict[str, Any],
) -> Dict[str, Any]:

    log_callback("  Evaluating Human Fix...")

    handler.reset_to_commit(bug["parent_commit_sha"])
    handler.checkout(bug["bug_commit_sha"])

    full_test_command_list = test_command.split()

    exclusions = config.get("test_exclusions", {}).get(bug["repo_name"], {})

    ignore_list = exclusions.get("ignore_paths", [])
    full_test_command_list = test_command.split()
    if ignore_list:
        log_callback(f"    --> Ignoring {len(ignore_list)} known flaky test(s).")
        for test_to_deselect in ignore_list:
            full_test_command_list.extend(["--ignore", test_to_deselect])

    deselect_list = exclusions.get("deselect_nodes", [])
    if deselect_list:
        log_callback(f"    --> Deselecting {len(deselect_list)} test(s) as configured.")
        for path_to_ignore in deselect_list:
            full_test_command_list.extend(["--deselect", path_to_ignore])

    tests_passed = False
    try:

        result = handler.run_tests_in_venv(full_test_command_list)
        tests_passed = True
        summary_line = "No summary line found."
        for line in result.stdout.splitlines():
            if "passed" in line and "in" in line and "s" in line:
                summary_line = line.strip("= ")
        log_callback(f"    --> Human Fix Tests PASSED. Summary: {summary_line}")

    except subprocess.CalledProcessError as e:
        tests_passed = False
        log_callback(f"    --> Human Fix Tests FAILED. Return code: {e.returncode}")
        log_path = _save_test_failure_log(
            project_root, bug["repo_name"], bug["bug_commit_sha"], "human_fix", e
        )
        log_callback(f"    --> Detailed logs saved to: {log_path}")

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
    """The main operator for the analysis pipeline, uses persistent handler for each repository."""
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

    # group bugs by repository for efficiency,
    # so environment setup/teardown is minimized
    bugs_by_repo = {}
    for bug in corpus:
        repo_name = bug["repo_name"]
        if repo_name not in bugs_by_repo:
            bugs_by_repo[repo_name] = []
        bugs_by_repo[repo_name].append(bug)

    _initialize_results_file(results_path)

    # process one repository at a time
    for repo_name, bugs in bugs_by_repo.items():
        log_callback(f"\n--- Starting Analysis for Repository: {repo_name} ---")

        handler = project_handler.ProjectHandler(repo_name, log_callback)

        try:

            # setup repo and install dependencies once
            handler.setup()
            if not handler.setup_virtual_environment():
                log_callback(
                    f"  --> CRITICAL: Failed to set up venv. Skipping all commits for this repo."
                )
                continue

            # iterate through commits in the same venv
            for bug in bugs:
                log_callback(
                    f"\n  --- Analyzing Commit: {bug['bug_commit_sha'][:7]} ---"
                )
                # parent_sha = bug["parent_commit_sha"]
                # fix_sha = bug["bug_commit_sha"]
                results = {**bug}

                if not skip_llm_fix:
                    results["ai_results"] = _run_ai_fix_evaluation(
                        bug, handler, test_command, log_callback, project_root, config
                    )
                    if "error" in results["ai_results"]:
                        continue
                    changed_files = results["ai_results"].get("changed_files", [])
                else:
                    log_callback("  --> Skipping AI Fix evaluation as requested.")
                    results["ai_results"] = {
                        "applied_ok": "SKIPPED",
                        "tests_passed": "SKIPPED",
                        "complexity": {
                            "total_cc": "SKIPPED",
                            "total_cognitive": "SKIPPED",
                        },
                    }
                    # still need to find out which files were changed for the human analysis.
                    changed_files = handler.get_changed_files(bug["bug_commit_sha"])

                handler.checkout(
                    bug["parent_commit_sha"]
                )  # reset to parent for human fix

                # always run the human evaluation, for easier tesing
                results["comp_before"] = analysis.analyze_files(
                    handler.repo_path, changed_files, log_callback
                )
                results["human_results"] = _run_human_fix_evaluation(
                    bug,
                    handler,
                    test_command,
                    changed_files,
                    log_callback,
                    project_root,
                    config,
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
            log_callback(f"  FATAL ERROR during analysis of {repo_name}: {e}")
        finally:
            # the handler and the venv are cleaned up only after all commits are done
            handler.cleanup()
