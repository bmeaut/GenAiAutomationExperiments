import toml
import os
import ast
import shutil
import subprocess
import tempfile
import git
from git import Repo, Commit as GitCommit, Blob
from typing import Callable, Dict, Any
from core import cleanup_manager
import glob


def _extract_code_context(repo: Repo, commit_sha: str, log: Callable) -> Dict[str, Any]:
    """
    Look through commit to find the functions/classes that were
    changed and returns their source code from the parent commit.
    """
    commit: GitCommit = repo.commit(commit_sha)
    if not commit.parents:
        log("  Warning: Initial commit, cannot extract context.")
        return {}

    parent: GitCommit = commit.parents[0]
    diffs = parent.diff(commit, create_patch=True)
    context_snippets = {}

    for diff in diffs:
        if not diff.a_path or not str(diff.a_path).endswith(".py"):
            continue
        try:
            buggy_code = (parent.tree / diff.a_path).data_stream.read().decode("utf-8")
            buggy_code_lines = buggy_code.splitlines()
            tree = ast.parse(buggy_code)

            # find the line numbers that were changed from the diff patch.
            changed_lines = set()
            patch_content = diff.diff
            if patch_content is None:
                continue

            patch_text = (
                bytes(patch_content).decode("utf-8", errors="ignore")
                if isinstance(patch_content, (bytes, bytearray, memoryview))
                else patch_content
            )

            for line in patch_text.splitlines():
                if line.startswith("@@"):
                    try:
                        hunk_info = line.split("@@")[1].strip()
                        original_file_hunk = hunk_info.split(" ")[0]
                        line_num = int(
                            original_file_hunk.split(",")[0].replace("-", "")
                        )
                        changed_lines.add(line_num)
                    except (IndexError, ValueError):
                        continue

            if not changed_lines:
                continue

            # find the functions/classes containing these changed lines.
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    start_line, end_line = node.lineno, getattr(
                        node, "end_lineno", node.lineno
                    )
                    if hasattr(node, "decorator_list") and node.decorator_list:
                        start_line = min(d.lineno for d in node.decorator_list)

                    if any(start_line <= l <= end_line for l in changed_lines):
                        snippet_lines = buggy_code_lines[start_line - 1 : end_line]
                        snippet = "\n".join(snippet_lines)
                        if snippet:
                            context_key = f"Snippet from {diff.a_path} (lines {start_line}-{end_line})"
                            context_snippets[context_key] = snippet
                            break
        except Exception as e:
            log(
                f"    Warning: Could not extract context for {diff.a_path}. Reason: {e}"
            )

    if not context_snippets:
        log("    Warning: Could not extract any function/class context.")
    return context_snippets


def _apply_llm_patch(
    repo: Repo,
    patch_text: str,
    original_snippet: str,
    full_file_path: str,
    is_full_file: bool,
    log: Callable,
) -> bool:
    """Applies an LLM's patch, handling both snippet replacement and direct file patching."""
    full_source_path = os.path.join(repo.working_dir, full_file_path)

    # when patching the entire file, use git apply.
    if is_full_file:
        log("  Applying patch directly to full file...")
        patch_file_path = os.path.join(repo.working_dir, "llm.patch")
        with open(patch_file_path, "w", encoding="utf-8") as f:
            f.write(patch_text)
        try:
            repo.git.apply(["--check", patch_file_path])
            repo.git.apply(patch_file_path)
            log("  --> Patch applied successfully.")
            return True
        except git.GitCommandError as e:
            log(f"  --> FAILED to apply patch. Stderr: {e.stderr}")
            return False
        finally:
            os.remove(patch_file_path)

    # when patching a snippet, use 'patch'
    if original_snippet not in open(full_source_path, "r", encoding="utf-8").read():
        log("  --> CRITICAL ERROR: Original snippet not found in file. Cannot replace.")
        return False

    patch_dir = tempfile.mkdtemp()
    try:
        snippet_path = os.path.join(patch_dir, "snippet.py")
        patch_file = os.path.join(patch_dir, "llm.patch")
        with open(snippet_path, "w", encoding="utf-8") as f:
            f.write(original_snippet)
        with open(patch_file, "w", encoding="utf-8") as f:
            f.write(patch_text)

        command = ["patch", snippet_path, patch_file]
        result = subprocess.run(command, cwd=patch_dir, capture_output=True, text=True)
        if result.returncode != 0:
            log(f"  --> FAILED to apply patch to snippet. Stderr: {result.stderr}")
            return False

        with open(snippet_path, "r", encoding="utf-8") as f:
            patched_snippet = f.read()
        with open(full_source_path, "r", encoding="utf-8") as f:
            full_buggy_code = f.read()

        new_full_code = full_buggy_code.replace(original_snippet, patched_snippet)
        with open(full_source_path, "w", encoding="utf-8") as f:
            f.write(new_full_code)

        log(f"  Successfully updated '{full_file_path}' with the patched snippet.")
        return True
    finally:
        shutil.rmtree(patch_dir)


class ProjectHandler:
    """Manages all Git and local environment operations for a single analysis run."""

    repo_name: str
    repo_url: str
    log: Callable[[str], None]
    repo_path: str
    repo: Repo | None

    def __init__(self, repo_name: str, log_callback: Callable[[str], None]):
        self.repo_name = repo_name
        self.repo_url = f"https://github.com/{repo_name}.git"
        self.log = log_callback
        self.repo_path = tempfile.mkdtemp()
        self.repo = None
        cleanup_manager.register_temp_dir(self.repo_path)

    def setup(self):
        self.log(f"  Cloning {self.repo_url} into {self.repo_path}")
        self.repo = Repo.clone_from(self.repo_url, self.repo_path)

    def checkout(self, commit_sha: str):
        if self.repo:
            self.repo.git.checkout(commit_sha)

    def reset_to_commit(self, commit_sha: str):
        if self.repo:
            self.repo.git.reset("--hard", commit_sha)

    def get_relevant_code_context(self, fix_commit_sha: str) -> Dict[str, Any]:
        """A wrapper that calls the helper function to extract code context."""
        return (
            _extract_code_context(self.repo, fix_commit_sha, self.log)
            if self.repo
            else {}
        )

    def apply_patch(
        self,
        patch_text: str,
        original_snippet: str,
        full_file_path: str,
        is_full_file: bool,
    ) -> bool:
        """A wrapper that calls the helper function to apply a patch."""
        # also trying out ternary conditional operator [inline if-else]
        return (
            _apply_llm_patch(
                self.repo,
                patch_text,
                original_snippet,
                full_file_path,
                is_full_file,
                self.log,
            )
            if self.repo
            else False
        )

    def _execute_in_venv(
        self,
        command: list[str],
        project_type: str = "pip",  # can be 'pip', 'poetry', or 'uv'
        timeout: int = 1200,
    ) -> subprocess.CompletedProcess:
        """
        Executes a command within the project's virtual environment,
        using the correct method for either Poetry or standard pip projects.
        """
        bin_dir = "bin" if os.name != "nt" else "Scripts"

        # 1. get a copy of the current environment's variables.
        env = os.environ.copy()

        # 2. unset VIRTUAL_ENV to prevent conflicts from nested environments.
        #    this forces tools like poetry and uv to use the venv.
        if "VIRTUAL_ENV" in env:
            del env["VIRTUAL_ENV"]

        # 3. prepend the venv's bin directory to the PATH to find executables.
        venv_bin_path = os.path.join(self.repo_path, "venv", bin_dir)
        env["PATH"] = f"{venv_bin_path}{os.pathsep}{env['PATH']}"

        if project_type == "poetry":
            full_command = ["poetry", "run"] + command
        elif project_type == "uv":
            full_command = ["uv", "run"] + command
        else:
            full_command = command

        return subprocess.run(
            full_command,
            cwd=self.repo_path,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            env=env,
        )

    def run_tests(self, test_command: str, commit_sha: str, run_type: str) -> bool:
        """
        Creates a venv, installs dependencies using a pragmatic, prioritized
        hierarchy of modern tools, and runs the test suite. This is the final version.
        """
        try:
            # Step 1: Create the virtual environment.
            self.log("  Creating isolated Python virtual environment...")
            subprocess.run(
                ["python", "-m", "venv", "venv"],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
            )
            project_type = "pip"

            # Step 2: Upgrade core build tools.
            self.log("  Installing/upgrading core build tools (pip, poetry)...")
            self._execute_in_venv(
                ["pip", "install", "--upgrade", "pip", "poetry", "uv"]
            )

            self.log("  Attempting to install project dependencies...")
            installed_deps = False
            pyproject_path = os.path.join(self.repo_path, "pyproject.toml")

            # 1: handle poetry projects first
            if os.path.exists(pyproject_path):
                with open(pyproject_path, "r") as f:
                    content = f.read()
                if "[tool.poetry]" in content:
                    project_type = "poetry"
                    self.log(
                        "  Poetry project detected. Installing with 'poetry install'..."
                    )
                    try:
                        self._execute_in_venv(["poetry", "install"])
                        self.log("    --> Success.")
                        installed_deps = True
                    except subprocess.CalledProcessError as e:
                        self.log(
                            f"    --> FAILED to install poetry dependencies. Stderr: {e.stderr}"
                        )
                        return False

            # 2: modern projects with 'uv'
            if not installed_deps and os.path.exists(pyproject_path):
                project_type = (
                    "uv"  # assume uv will be the runner if pyproject.toml exists.
                )
                self.log(
                    "  Modern project detected. Attempting to install with 'uv'..."
                )
                try:
                    # 'uv sync' command is standard if a lock file exists.
                    if os.path.exists(os.path.join(self.repo_path, "uv.lock")):
                        self.log("    'uv.lock' found. Installing with 'uv sync'...")
                        self._execute_in_venv(["uv", "sync"])
                    else:
                        # otherwise, install from pyproject.toml, including common dev groups.
                        self.log(
                            "    No lock file. Installing from pyproject.toml with 'uv pip install'..."
                        )
                        # install the project and all specified dependency groups.
                        self._execute_in_venv(
                            ["uv", "pip", "install", "-e", ".[dev,test,tests,typing]"]
                        )

                    self.log("    --> Success.")
                    installed_deps = True
                except subprocess.CalledProcessError as e:
                    self.log(f"    --> FAILED to install with uv. Stderr: {e.stderr}")

            # 3: for all other projects, look for a requirements file first.
            if not installed_deps:
                # glob: find any file that looks like a dev/test requirements file.
                req_file_patterns = [
                    "*requirements-dev.txt",
                    "*requirements_dev.txt",
                    "*requirements-test*.txt",
                    "*test-requirements.txt",
                ]
                found_req_file = None
                for pattern in req_file_patterns:
                    # search both the root and a 'requirements/' subdirectory.
                    for match in glob.glob(
                        os.path.join(self.repo_path, pattern), recursive=True
                    ) + glob.glob(
                        os.path.join(self.repo_path, "requirements", pattern),
                        recursive=True,
                    ):
                        found_req_file = match
                        break
                    if found_req_file:
                        break

                if found_req_file:
                    self.log(
                        f"  Found explicit requirements file: '{os.path.relpath(found_req_file, self.repo_path)}'. Installing..."
                    )
                    try:
                        # We must install the package itself in addition to the requirements file.
                        self._execute_in_venv(["pip", "install", "-e", "."])
                        self._execute_in_venv(
                            [
                                "pip",
                                "install",
                                "-r",
                                os.path.relpath(found_req_file, self.repo_path),
                            ]
                        )
                        self.log("    --> Success.")
                        installed_deps = True
                    except subprocess.CalledProcessError as e:
                        self.log(
                            f"    --> FAILED to install from {os.path.basename(found_req_file)}. Stderr: {e.stderr}"
                        )

            # test execution
            self.log(f"  Running test suite with command: '{test_command}'")
            try:

                result = self._execute_in_venv(
                    test_command.split(), project_type=project_type
                )
                self.log("  Tests PASSED.")
                summary_line = "No summary line found."
                for line in result.stdout.splitlines():
                    if "passed" in line and "in" in line and "s" in line:
                        summary_line = line.strip("= ")
                self.log(f"    --> Summary: {summary_line}")
                return True
            except subprocess.CalledProcessError as e:
                self.log(f"  Tests FAILED. Return code: {e.returncode}")

                # save the complete test output to a file for later analysis.
                logs_dir = os.path.join(os.getcwd(), "results", "test_logs")
                os.makedirs(logs_dir, exist_ok=True)
                repo_name_safe = self.repo_name.replace("/", "_")
                log_filename = f"{repo_name_safe}_{commit_sha[:7]}_{run_type}.log"
                log_path = os.path.join(logs_dir, log_filename)

                log_content = (
                    f"TEST RUN FAILED\n"
                    f"-----------------\n"
                    f"Repository: {self.repo_name}\nCommit SHA: {commit_sha}\nRun Type:   {run_type}\n"
                    f"Return Code: {e.returncode}\n-----------------\n\n"
                    f"--- STDOUT ---\n{e.stdout}\n\n"
                    f"--- STDERR ---\n{e.stderr}\n"
                )
                with open(log_path, "w", encoding="utf-8") as f:
                    f.write(log_content)
                self.log(f"  --> Detailed test logs saved to: {log_path}")

                return False

        except Exception as e:
            stderr = getattr(e, "stderr", "N/A")
            self.log(
                f"  FATAL ERROR during test setup or execution: {e}\n  Stderr: {stderr}"
            )
            return False

    def get_changed_files(self, fix_commit_sha: str) -> list[str]:
        """
        Gets a simple list of .py file paths changed in a specific commit.
        This is used for the 'dry run' mode.
        """
        if not self.repo:
            self.log("  ERROR: Repository not initialized.")
            return []

        try:
            commit: GitCommit = self.repo.commit(fix_commit_sha)
            if not commit.parents:
                self.log(
                    f"  Warning: Initial commit {fix_commit_sha[:7]} has no parents."
                )
                return [
                    str(item.path)
                    for item in commit.tree.traverse()
                    if isinstance(item, Blob) and str(item.path).endswith(".py")
                ]

            parent: GitCommit = commit.parents[0]
            # create_patch=False makes this a very fast diff operation.
            diffs = parent.diff(commit, create_patch=False)

            changed_py_files = []
            for diff_item in diffs:
                path = diff_item.b_path if diff_item.b_path else diff_item.a_path
                if path and str(path).endswith(".py"):
                    changed_py_files.append(str(path))

            return changed_py_files

        except Exception as e:
            self.log(
                f"  ERROR: Could not get changed files for commit {fix_commit_sha[:7]}: {e}"
            )
            return []

    def get_full_file_content(self, filename: str, commit_sha: str) -> str:
        """Gets the full, raw content of a single file at a specific commit."""
        if not self.repo:
            return ""
        try:
            commit: GitCommit = self.repo.commit(commit_sha)
            blob = commit.tree / filename
            return blob.data_stream.read().decode("utf-8")
        except Exception as e:
            self.log(f"    Warning: Could not read full file {filename}: {e}")
            return ""

    def cleanup(self):
        """Removes the temporary repository directory."""
        self.log(f"  Cleaning up temporary directory: {self.repo_path}")
        shutil.rmtree(self.repo_path, ignore_errors=True)
        cleanup_manager.unregister_temp_dir(self.repo_path)
