import json
import csv
import os
from . import project_handler, analysis, llm_manager
from typing import Callable, Dict, Any, Optional
import subprocess
import datetime
import threading


def _analyze_patch(patch_text: str) -> Dict[str, int]:
    """Parses a diff/patch string to count changed lines"""
    added = 0
    deleted = 0

    for line in patch_text.splitlines():
        stripped_line = line.strip()

        if stripped_line.startswith("+") and not stripped_line.startswith("+++"):
            added += 1
        elif stripped_line.startswith("-") and not stripped_line.startswith("---"):
            deleted += 1

    return {"lines_added": added, "lines_deleted": deleted, "total": added + deleted}


def _initialize_results_file(path: str):
    """Creates the results CSV file and writes the header row if it doesn't exist."""
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "timestamp",
                    "repo_name",
                    "bug_commit_sha",
                    "file_path",
                    "commit_message",
                    "issue_title",
                    "issue_body",
                    "llm_model",
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


def _run_tests_with_exclusions(
    handler: project_handler.ProjectHandler,
    test_command: str,
    repo_name: str,
    commit_sha: str,
    run_type: str,
    config: Dict[str, Any],
    log_callback: Callable,
    project_root: str,
) -> bool:
    """Constructs the full pytest command with exclusions and runs it."""

    full_test_command_list = test_command.split()
    exclusions = config.get("test_exclusions", {}).get(repo_name, {})

    ignore_list = exclusions.get("ignore_paths", [])
    if ignore_list:
        log_callback(f"    --> Ignoring {len(ignore_list)} path(s)")
        for path_to_ignore in ignore_list:
            full_test_command_list.extend(["--ignore", path_to_ignore])

    deselect_list = exclusions.get("deselect_nodes", [])
    if deselect_list:
        log_callback(f"    --> Deselecting {len(deselect_list)} test(s) as configured.")
        for test_to_deselect in deselect_list:
            full_test_command_list.extend(["--deselect", test_to_deselect])

    try:
        result = handler.run_tests_in_venv(full_test_command_list)
        summary_line = "No summary line found."
        for line in result.stdout.splitlines():
            if "passed" in line and "in" in line and "s" in line:
                summary_line = line.strip("=")
        log_callback(f"    --> Tests PASSED. Summary: {summary_line}")
        return True

    except subprocess.CalledProcessError as e:
        log_callback(f"    --> Tests FAILED. Return code: {e.returncode}")
        # save detailed log
        log_path = _save_test_failure_log(
            project_root, repo_name, commit_sha, run_type, e
        )
        log_callback(f"    --> Detailed logs saved to: {log_path}")
        return False


def _log_results(results_path: str, bug_data: Dict[str, Any]):
    """Appends a single row of results to the CSV file."""
    with open(results_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        ai_results = bug_data.get("ai_results", {})
        human_results = bug_data.get("human_results", {})
        comp_before = bug_data.get("comp_before", {})
        ai_stats = ai_results.get("patch_stats", {})
        human_stats = human_results.get("patch_stats", {})
        ai_comp = ai_results.get("complexity", {})
        human_comp = human_results.get("complexity", {})

        file_paths_str = "; ".join(bug_data.get("changed_files", []))

        writer.writerow(
            [
                datetime.datetime.now().isoformat(),  # timestamp
                bug_data.get("repo_name"),
                bug_data.get("bug_commit_sha"),
                file_paths_str,
                bug_data.get("commit_message"),
                bug_data.get("issue_title"),
                bug_data.get("issue_body"),
                "manual_llm",
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


def _process_bug(
    bug: Dict[str, Any],
    handler: project_handler.ProjectHandler,
    test_command: str,
    skip_llm_fix: bool,
    log_callback: Callable,
    project_root: str,
    config: Dict[str, Any],
):
    """
    This function contains the core analysis logic for a single bug commit.
    """
    fix_sha = bug["bug_commit_sha"]
    parent_sha = bug["parent_commit_sha"]
    log_callback(f"\n  --- Analyzing Commit: {fix_sha[:7]} ---")

    try:
        results = {**bug}

        # 1. get complete changed files list
        # file path should be stores to results later
        all_changed_files = handler.get_changed_files(fix_sha)
        if not all_changed_files:
            log_callback("  --> Skipping: No Python files were changed in this commit.")
            return

        # 2. analyze the 'before' state.
        log_callback("  Analyzing 'before' state...")
        handler.checkout(bug["parent_commit_sha"])
        # filter for created files
        files_in_before_state = [
            f
            for f in all_changed_files
            if os.path.exists(os.path.join(handler.repo_path, f))
        ]
        results["comp_before"] = analysis.analyze_files(
            handler.repo_path, files_in_before_state, log_callback
        )
        log_callback(
            f"    --> Complexity Before: CC={results['comp_before'].get('total_cc')}, "
            f"Cognitive={results['comp_before'].get('total_cognitive')}, "
            f"Avg Params={results['comp_before'].get('avg_params')}, "
            f"Total Tokens={results['comp_before'].get('total_tokens')}"
        )

        # 3. handle LLM fix state
        if not skip_llm_fix:
            log_callback("  Evaluating AI Fix...")
            # get all relevant code snippets from all changed files
            buggy_code_context = handler.get_relevant_code_context(fix_sha)
            if not buggy_code_context:
                log_callback(
                    "  --> ERROR: Failed to extract any code context for the LLM."
                )
                return

            llm_fix_patch = llm_manager.generate_fix_manually(bug, buggy_code_context)
            ai_patch_stats = _analyze_patch(llm_fix_patch)
            log_callback(
                f"  --> AI Patch Stats: +{ai_patch_stats.get('lines_added', 0)} / -{ai_patch_stats.get('lines_deleted', 0)} lines."
            )

            handler.checkout(parent_sha)
            applied_ok = handler.apply_patch(llm_fix_patch)

            ai_tests_passed = False
            ai_comp = {
                "total_cc": "N/A",
                "total_cognitive": "N/A",
                "avg_params": "N/A",
                "total_tokens": "N/A",
            }
            if applied_ok:
                files_in_ai_state = [
                    f
                    for f in all_changed_files
                    if os.path.exists(os.path.join(handler.repo_path, f))
                ]
                ai_comp = analysis.analyze_files(
                    handler.repo_path, files_in_ai_state, log_callback
                )

                ai_tests_passed = _run_tests_with_exclusions(
                    handler,
                    test_command,
                    repo_name=bug["repo_name"],
                    commit_sha=bug["bug_commit_sha"],
                    run_type="ai_fix",
                    config=config,
                    log_callback=log_callback,
                    project_root=project_root,
                )

            results["ai_results"] = {
                "applied_ok": applied_ok,
                "tests_passed": ai_tests_passed,
                "complexity": ai_comp,
                "patch_stats": ai_patch_stats,
            }

        else:
            log_callback("  --> Skipping AI Fix evaluation as requested.")
            results["ai_results"] = {
                "applied_ok": "SKIPPED",
                "tests_passed": "SKIPPED",
                "complexity": {
                    "total_cc": "SKIPPED",
                    "total_cognitive": "SKIPPED",
                    "avg_params": "SKIPPED",
                    "total_tokens": "SKIPPED",
                },
            }

        # 4. handle human fix
        log_callback("  Evaluating Human Fix...")
        handler.checkout(fix_sha)  # reset to parent for human fix

        # handle deleted files
        files_in_human_state = [
            f
            for f in all_changed_files
            if os.path.exists(os.path.join(handler.repo_path, f))
        ]
        human_comp = analysis.analyze_files(
            handler.repo_path, files_in_human_state, log_callback
        )

        human_patch_text = handler.get_human_patch(fix_sha)
        human_patch_stats = _analyze_patch(human_patch_text)
        log_callback(
            f"    --> Human Patch Stats: +{human_patch_stats.get('lines_added', 0)} / -{human_patch_stats.get('lines_deleted', 0)} lines."
        )

        human_tests_passed = _run_tests_with_exclusions(
            handler,
            test_command,
            repo_name=bug["repo_name"],
            commit_sha=bug["bug_commit_sha"],
            run_type="human_fix",
            config=config,
            log_callback=log_callback,
            project_root=project_root,
        )

        results["human_results"] = {
            "tests_passed": human_tests_passed,
            "complexity": human_comp,
            "patch_stats": human_patch_stats,
        }

        log_callback(
            f"    --> Complexity After LLM: CC={results.get('ai_results', {}).get('complexity', {}).get('total_cc')}, "
            f"Cognitive={results.get('ai_results', {}).get('complexity', {}).get('total_cognitive')}, "
            f"Avg Params={results.get('ai_results', {}).get('complexity', {}).get('avg_params')}, "
            f"Total Tokens={results.get('ai_results', {}).get('complexity', {}).get('total_tokens')}"
        )
        log_callback(
            f"    --> Complexity After Human: CC={results.get('human_results', {}).get('complexity', {}).get('total_cc')}, "
            f"Cognitive={results.get('human_results', {}).get('complexity', {}).get('total_cognitive')}, "
            f"Avg Params={results.get('human_results', {}).get('complexity', {}).get('avg_params')}, "
            f"Total Tokens={results.get('human_results', {}).get('complexity', {}).get('total_tokens')}"
        )

        _log_results(os.path.join(project_root, "results", "results.csv"), results)

    except Exception as e:
        log_callback(f"  FATAL ERROR during analysis of {fix_sha[:7]}: {e}")


def run(
    log_callback: Callable,
    skip_llm_fix: bool = False,
    single_bug_data: Optional[Dict[str, Any]] = None,
    resume_event: Optional[threading.Event] = None,
    stop_event: Optional[threading.Event] = None,
):
    """The main operator for the analysis pipeline, uses persistent handler for each repository."""

    # default events if not provided
    if resume_event is None:
        resume_event = threading.Event()
        resume_event.set()
    if stop_event is None:
        stop_event = threading.Event()

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

    if single_bug_data:
        # if a single bug is provided, process only that one
        repo_name = single_bug_data["repo_name"]
        bugs_by_repo = {repo_name: [single_bug_data]}
        log_callback("--- Running analysis for a single selected commit ---")
    else:
        # otherwise, load and process the entire corpus, grouped by repository
        log_callback("--- Running analysis for the entire corpus ---")
        with open(corpus_path, "r") as f:
            corpus = json.load(f)
        bugs_by_repo = {}
        for bug in corpus:
            repo_name = bug["repo_name"]
            if repo_name not in bugs_by_repo:
                bugs_by_repo[repo_name] = []
            bugs_by_repo[repo_name].append(bug)

    # process one repository at a time
    for repo_name, bugs in bugs_by_repo.items():
        if stop_event.is_set():
            log_callback("--> Stop signal received. Halting analysis.")
            break

        log_callback(f"\n--- Starting Analysis for Repository: {repo_name} ---")

        # create one handler for the entire repository
        handler = project_handler.ProjectHandler(repo_name, log_callback)
        try:
            # setup the repo and install dependencies once per repository.
            handler.setup()
            if not handler.setup_virtual_environment():
                log_callback(
                    f"  --> CRITICAL: Failed to set up venv. Skipping all commits for this repo."
                )
                continue

            # iterate through the commits using the same venv
            for bug in bugs:

                if not resume_event.is_set():
                    log_callback("--> Pipeline paused. Waiting for resume signal...")
                    # this call will block the thread until another thread calls resume_event.set()
                    resume_event.wait()
                    log_callback("--> Pipeline resumed.")

                if stop_event.is_set():
                    log_callback(
                        "--> Stop signal received. Halting analysis for this repository."
                    )
                    break  # exit the inner loop over bugs.

                _process_bug(
                    bug,
                    handler,
                    test_command,
                    skip_llm_fix,
                    log_callback,
                    project_root,
                    config,
                )

        except Exception as e:
            log_callback(f"  FATAL ERROR during analysis of {repo_name}: {e}")
        finally:
            # handler and venv are cleaned up only after all
            # commits for that repository are finished
            handler.cleanup()
