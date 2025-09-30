import os
import ast
import shutil
import subprocess
import tempfile
import git
from git import Optional, Repo, Commit as GitCommit, Blob
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
    venv_path: str
    project_type: str

    def __init__(self, repo_name: str, log_callback: Callable[[str], None]):
        self.repo_name = repo_name
        self.repo_url = f"https://github.com/{repo_name}.git"
        self.log = log_callback
        self.repo_path = tempfile.mkdtemp()
        self.repo = None
        # persistent venv for handler lifetime
        self.venv_path = os.path.join(self.repo_path, "venv")
        self.project_type = "pip"  # will be determined during setup.

        cleanup_manager.register_temp_dir(self.repo_path)

    def get_human_patch(self, fix_commit_sha: str, file_path: str) -> str:
        """Gets the raw diff/patch string for the human's fix of a specific file."""
        if not self.repo:
            return ""

        try:
            commit: GitCommit = self.repo.commit(fix_commit_sha)
            parent: GitCommit = commit.parents[0]

            # find modified file
            diffs = parent.diff(commit, paths=[file_path], create_patch=True)

            for diff in diffs:
                patch_content = diff.diff

                if patch_content:
                    return (
                        bytes(patch_content).decode("utf-8", "ignore")
                        if isinstance(patch_content, (bytes, bytearray, memoryview))
                        else patch_content
                    )
                else:
                    self.log(f"    Warning: No patch content found for {file_path}.")
                    return ""  # diff object exists but empty

            return ""  # diff iterator empty

        except Exception as e:
            self.log(
                f"    Warning: Could not get human patch for {file_path}. Reason: {e}"
            )
            return ""

    def setup_virtual_environment(self) -> bool:
        """
        Creates and installs all dependencies into a single, persistent venv
        for this project's entire analysis run.
        """
        try:
            self.log(
                "  Setting up persistent virtual environment for this repository..."
            )

            self.log("  --> Step 1: Creating the venv directory...")
            subprocess.run(
                ["python", "-m", "venv", self.venv_path],
                check=True,
                capture_output=True,
            )
            self.log("      --> Success.")

            bin_dir = "bin" if os.name != "nt" else "Scripts"
            pip_exe = os.path.join(self.venv_path, bin_dir, "pip")

            pyproject_path = os.path.join(self.repo_path, "pyproject.toml")
            if os.path.exists(pyproject_path):
                with open(pyproject_path, "r") as f:
                    content = f.read()
                if "[tool.poetry]" in content:
                    self.project_type = "poetry"
                elif os.path.exists(os.path.join(self.repo_path, "uv.lock")):
                    self.project_type = "uv"
                else:
                    self.project_type = "pip"

            self.log(f"  --> Project type identified as: {self.project_type}")

            self.log("  --> Installing core build & test tools...")
            self._execute_in_venv(
                [
                    "pip",
                    "install",
                    "--upgrade",
                    "pip",
                    "poetry",
                    "uv",
                    "pytest",
                    "pytest-cov",
                    "anyio",
                ]
            )
            self.log("      --> Success.")

            self.log("  Installing project-specific dependencies...")
            self._install_project_dependencies()

            return True

        except subprocess.CalledProcessError as e:
            self.log(f"  --> CRITICAL FAILURE: A command failed to execute.")
            self.log(f"  --> Stderr: {e.stderr}")
            return False
        except Exception as e:

            import traceback

            self.log(
                f"  --> FATAL ERROR during venv setup. The error was NOT a subprocess failure."
            )
            self.log(f"  --> Exception Type: {type(e).__name__}")
            self.log(f"  --> Exception Details: {e}")
            self.log(f"  --> Full Traceback:\n{traceback.format_exc()}")
            return False

    def _install_project_dependencies(self):
        """
        Private helper that runs the definitive, prioritized dependency
        installation hierarchy.
        """
        pyproject_path = os.path.join(self.repo_path, "pyproject.toml")

        # 1: handle poetry projects first
        if self.project_type == "poetry":
            self.log("  Poetry project detected. Installing with 'poetry install'...")
            self._execute_in_venv(["poetry", "install"])
            return

        # 2: modern projects with 'uv'
        if self.project_type == "uv":
            self.log("  'uv.lock' found. Installing with 'uv sync'...")
            self._execute_in_venv(["uv", "sync"])
            return

        # 3: for all other projects, look for a requirements file first.
        req_file = self._find_requirements_file()
        if req_file:
            self.log(f"  Found explicit requirements file: '{req_file}'. Installing...")
            self.project_type = "pip"
            # We must install the package itself in addition to the requirements file.
            self._execute_in_venv(["pip", "install", "-e", "."])
            self._execute_in_venv(
                [
                    "pip",
                    "install",
                    "-r",
                    req_file,
                ]
            )
            return

        # 4: handle other modern projects (flit, hatch, setuptools) using standard pip
        if os.path.exists(pyproject_path):
            self.log("  --> Fallback: Installing from pyproject.toml with extras...")
            self.project_type = "pip"
            self._execute_in_venv(["pip", "install", "-e", ".[dev,test,tests,typing]"])
            return

        self.log(
            "  --> Warning: No dependency installation method found."
        )  # Allow to proceed even if no deps, tests might still run

    def run_tests_in_venv(self, test_command: list[str]) -> subprocess.CompletedProcess:
        """Runs a command inside the already-built virtual environment."""
        self.log(
            f"  Running test suite with command: '{test_command}' (runner: {self.project_type})"
        )

        return self._execute_in_venv(test_command, project_type=self.project_type)

    def _find_requirements_file(self) -> Optional[str]:
        patterns = [
            "*requirements-dev.txt",
            "*requirements_dev.txt",
            "*requirements-test*.txt",
            "*test-requirements.txt",
            "*requirements.txt",
        ]
        for pattern in patterns:
            for match in glob.glob(
                os.path.join(self.repo_path, pattern), recursive=True
            ) + glob.glob(
                os.path.join(self.repo_path, "requirements", pattern), recursive=True
            ):
                return match
        return None

    def setup(self):
        """
        Clones the full, complete repository into the temporary directory.
        The '--no-shallow' flag is critical to have the entire
        commit history available for analysis.
        """
        self.log(f"  Cloning {self.repo_url} into {self.repo_path}")
        self.repo = Repo.clone_from(self.repo_url, self.repo_path)

        self.log("  --> Ensuring full commit history is available...")
        try:
            self.repo.git.fetch("--unshallow")
            self.log("  --> Full history fetched successfully.")
        except git.GitCommandError as e:
            # already full clone?
            if (
                "fatal: --unshallow on a complete repository does not make sense"
                in e.stderr
            ):
                self.log("  --> Repository was already a full clone. Continuing.")
            else:
                # # different error
                raise e

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
        using the correct method.
        """
        bin_dir = "bin" if os.name != "nt" else "Scripts"

        # 1. get a copy of the current environment's variables.
        env = os.environ.copy()

        # 2. unset VIRTUAL_ENV to prevent conflicts from nested environments.
        #    this forces tools like poetry and uv to use the venv.
        if "VIRTUAL_ENV" in env:
            del env["VIRTUAL_ENV"]

        # 3. prepend the venv's bin directory to the PATH to find executables.
        venv_bin_path = os.path.join(self.venv_path, bin_dir)
        env["PATH"] = f"{venv_bin_path}{os.pathsep}{env['PATH']}"

        if project_type == "poetry":
            full_command = ["poetry", "run"] + command
        elif project_type == "uv":
            full_command = ["uv", "run"] + command
        else:
            exe_path = os.path.join(self.repo_path, "venv", bin_dir, command[0])
            full_command = [exe_path] + command[1:]

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
