import json
import csv
import os
import shutil
from . import project_handler, llm_manager
from .analysis import analyze_files

from typing import Callable, Dict, Any, Optional
from git import Repo
import subprocess
import datetime
import threading


def gather_and_budget_context(
    repo: Repo, bug_data: dict, log_callback: Callable, token_budget: int = 4000
) -> Dict[str, str]:
    """
    Runs multiple context strategies and combines them intelligently within a token budget.
    """
    from . import project_handler
    from .context_extraction import (
        BuggyCodeContextGatherer,
        StructuralDependencyGatherer,
        HistoricalContextGatherer,
    )

    final_snippets = {}
    total_tokens = 0

    # the buggy code itself must be included.
    log_callback(
        "  Running CRITICAL context strategy: Bug Knowledge (Local Code Snippets)"
    )
    buggy_code_strategy = BuggyCodeContextGatherer(repo, log_callback)
    critical_snippets = buggy_code_strategy.gather(bug_data)

    if not critical_snippets:
        log_callback(
            "  --> FATAL: Could not extract the primary buggy code. Aborting context gathering."
        )
        return {}

    for key, content in critical_snippets.items():
        snippet_tokens = len(content.split()) * 4 // 3
        if total_tokens + snippet_tokens > token_budget:
            log_callback(
                f"    Warning: Critical snippet '{key[:50]}...' is too large for the budget. Including it anyway and stopping."
            )
            final_snippets[key] = content
            total_tokens += snippet_tokens
            return (
                final_snippets  # stop immediately if even critical context is too big
            )

        final_snippets[key] = content
        total_tokens += snippet_tokens

    # order of priority: local code, then structural, then historical.
    supplementary_strategies = [
        StructuralDependencyGatherer(repo, log_callback),
        HistoricalContextGatherer(repo, log_callback),
    ]

    temp_handler = project_handler.ProjectHandler(bug_data["repo_name"], log_callback)
    temp_handler.repo = repo
    changed_files = temp_handler.get_changed_files(bug_data["bug_commit_sha"])

    for strategy in supplementary_strategies:
        if total_tokens >= token_budget:
            log_callback(
                "  --> Token budget reached. Stopping supplementary context gathering."
            )
            break

        log_callback(f"  Running context strategy: {strategy.name}")
        try:
            # pass the changed_files list to the gather method
            new_snippets = strategy.gather(bug_data, changed_files=changed_files)
            for key, content in new_snippets.items():
                # estimate tokens
                snippet_tokens = len(content.split()) * 4 // 3

                if total_tokens + snippet_tokens > token_budget:
                    log_callback(
                        f"    Skipping snippet '{key[:50]}...': Exceeds token budget."
                    )
                    continue  # skip this snippet and try the next one

                final_snippets[key] = content
                total_tokens += snippet_tokens
        except Exception as e:
            log_callback(f"    ERROR in strategy {strategy.name}: {e}")

    log_callback(
        f"  Context gathering complete. Total estimated tokens: {total_tokens}"
    )
    return final_snippets


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
    debug_on_failure: bool = False,
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
        results["comp_before"] = analyze_files(
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
            if handler.repo:
                buggy_code_context = gather_and_budget_context(
                    handler.repo, bug, log_callback
                )
            else:
                log_callback(
                    "  --> CRITICAL ERROR: Repo object not initialized in handler. Skipping context gathering."
                )
                buggy_code_context = {}

            if not buggy_code_context:
                log_callback(
                    "  --> ERROR: Failed to extract any code context for the LLM."
                )
                return

            llm_response_text = llm_manager.generate_fix_manually(
                bug, buggy_code_context
            )

            cleaned_patch = llm_manager.extract_patch_from_llm_response(
                llm_response_text
            )

            if cleaned_patch is None:
                log_callback(
                    "  --> ERROR: Failed to extract valid patch from LLM response."
                )
                results["ai_results"] = {
                    "applied_ok": False,
                    "tests_passed": False,
                    "complexity": {
                        "total_cc": "EXTRACTION_FAILED",
                        "total_cognitive": "EXTRACTION_FAILED",
                        "avg_params": "EXTRACTION_FAILED",
                        "total_tokens": "EXTRACTION_FAILED",
                    },
                    "patch_stats": {
                        "lines_added": 0,
                        "lines_deleted": 0,
                        "total": 0,
                    },
                }
                # continue to human fix evaluation
                handler.reset_to_commit(parent_sha)
            else:

                ai_patch_stats = _analyze_patch(cleaned_patch)
                log_callback(
                    f"  --> AI Patch Stats: +{ai_patch_stats.get('lines_added', 0)} / -{ai_patch_stats.get('lines_deleted', 0)} lines."
                )

                # patch extraction succeeded, continue with application
                # the pipeline creates the patch file
                temp_patch_path = os.path.join(handler.repo_path, "llm.patch")
                with open(temp_patch_path, "w", encoding="utf-8") as f:
                    f.write(cleaned_patch)

                # the handler is given a path to the patch file
                handler.checkout(parent_sha)

                # validation before applying
                patch_validation = handler.validate_and_debug_patch_detailed(
                    temp_patch_path
                )

            # the handler is given a path to the patch file
            handler.checkout(parent_sha)

            # validation before applying
            patch_validation = handler.validate_and_debug_patch_detailed(
                temp_patch_path
            )
            if not patch_validation["valid"]:
                log_callback(f"  --> Patch validation failed:")
                for error in patch_validation["errors"]:
                    log_callback(f"      ERROR: {error}")

                # log detailed analysis
                for file_path, analysis in patch_validation.get(
                    "file_analysis", {}
                ).items():
                    log_callback(f"      File: {file_path}")
                    if isinstance(analysis, dict):
                        for hunk_key, hunk_analysis in analysis.items():
                            if hunk_key.startswith("hunk_") and isinstance(
                                hunk_analysis, dict
                            ):
                                issues = hunk_analysis.get("issues", [])
                                if issues:
                                    log_callback(
                                        f"        {hunk_key}: {', '.join(issues)}"
                                    )
                                if hunk_analysis.get("suggested_location"):
                                    log_callback(
                                        f"        Suggested location: line {hunk_analysis['suggested_location']}"
                                    )

                # save debug info
                if debug_on_failure:
                    debug_dir = os.path.join(project_root, "results", "patch_debug")
                    os.makedirs(debug_dir, exist_ok=True)
                    repo_name_safe = bug["repo_name"].replace("/", "_")
                    debug_file = f"{repo_name_safe}_{fix_sha[:7]}_debug.json"
                    debug_path = os.path.join(debug_dir, debug_file)

                    with open(debug_path, "w") as f:
                        json.dump(patch_validation, f, indent=2)

                    log_callback(f"  --> Debug info saved to: {debug_path}")

            applied_ok = handler.apply_patch(temp_patch_path)

            # pause for inspection if patch failed
            if not applied_ok and debug_on_failure:
                log_callback("\n" + "=" * 60)
                log_callback(
                    ">>> DEBUG MODE: Patch failed to apply. Execution is PAUSED."
                )

                failed_patches_dir = os.path.join(
                    project_root, "results", "failed_patches"
                )
                os.makedirs(failed_patches_dir, exist_ok=True)
                repo_name_safe = bug["repo_name"].replace("/", "_")
                permanent_patch_filename = f"{repo_name_safe}_{fix_sha[:7]}.patch"
                permanent_patch_path = os.path.join(
                    failed_patches_dir, permanent_patch_filename
                )

                shutil.copy(temp_patch_path, permanent_patch_path)

                log_callback(f">>> FAILED PATCH SAVED TO: {permanent_patch_path}")
                log_callback(f">>> Live Crime Scene: {handler.repo_path}")
                input(">>> Press Enter in THIS terminal to continue... ")
                log_callback("=" * 60 + "\n")

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
                ai_comp = analyze_files(
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

            log_callback("  Resetting repository to clean 'before' state...")
            handler.reset_to_commit(parent_sha)

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
        human_comp = analyze_files(
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
    debug_on_failure: bool = False,
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
                    debug_on_failure,
                )

        except Exception as e:
            log_callback(f"  FATAL ERROR during analysis of {repo_name}: {e}")
        finally:
            # handler and venv are cleaned up only after all
            # commits for that repository are finished
            handler.cleanup()
