import os
import ast
import shutil
import subprocess
import tempfile
import git
from git import Optional, Repo, Commit as GitCommit, Blob
from typing import Callable, Dict, Any, List
from . import cleanup_manager
import glob
from . import context_extraction


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

    def validate_and_debug_patch_detailed(self, patch_file_path: str) -> Dict[str, Any]:
        """Enhanced patch validation with detailed analysis."""
        debug_info = {
            "valid": False,
            "errors": [],
            "warnings": [],
            "patch_content": "",
            "analysis": {},
            "file_analysis": {},
        }

        try:
            with open(patch_file_path, "r", encoding="utf-8") as f:
                patch_content = f.read()
            debug_info["patch_content"] = patch_content

            if not patch_content.strip():
                debug_info["errors"].append("Patch file is empty")
                return debug_info

            # parse patch to analyze each file change
            file_changes = self._parse_patch_hunks(patch_content)
            debug_info["file_analysis"] = file_changes

            # check if target files exist and analyze context
            for file_path, hunks in file_changes.items():
                full_path = os.path.join(self.repo_path, file_path)
                if not os.path.exists(full_path):
                    debug_info["errors"].append(
                        f"Target file does not exist: {file_path}"
                    )
                    continue

                # read current file content
                with open(full_path, "r", encoding="utf-8") as f:
                    current_lines = f.readlines()

                # check each hunk
                for i, hunk in enumerate(hunks):
                    hunk_analysis = self._analyze_hunk_context(
                        current_lines, hunk, file_path
                    )
                    hunk["analysis"] = hunk_analysis

            # try dry run
            try:
                if self.repo is not None:
                    result = self.repo.git.apply(
                        ["--check", "--verbose", patch_file_path]
                    )
                    debug_info["valid"] = True
                    debug_info["analysis"]["dry_run"] = "PASSED"
            except git.GitCommandError as e:
                debug_info["errors"].append(f"Dry run failed: {e.stderr}")
                debug_info["analysis"]["dry_run"] = "FAILED"
                debug_info["analysis"]["git_error"] = str(e.stderr)

            return debug_info

        except Exception as e:
            debug_info["errors"].append(f"Validation failed: {str(e)}")
            return debug_info

    def _parse_patch_hunks(self, patch_content: str) -> Dict[str, List[Dict]]:
        """Parse patch content into structured hunks per file."""
        import re

        files = {}
        current_file = None
        lines = patch_content.splitlines()

        i = 0
        while i < len(lines):
            line = lines[i]

            if line.startswith("---"):
                # extract source file path
                source_path = line[4:].strip()
                if source_path.startswith("a/"):
                    source_path = source_path[2:]
            elif line.startswith("+++"):
                # extract target file path
                target_path = line[4:].strip()
                if target_path.startswith("b/"):
                    target_path = target_path[2:]
                current_file = target_path
                files[current_file] = []
            elif line.startswith("@@") and current_file:
                # parse hunk header
                match = re.match(
                    r"@@\s*-(\d+)(?:,(\d+))?\s*\+(\d+)(?:,(\d+))?\s*@@", line
                )
                if match:
                    hunk = {
                        "old_start": int(match.group(1)),
                        "old_count": int(match.group(2)) if match.group(2) else 1,
                        "new_start": int(match.group(3)),
                        "new_count": int(match.group(4)) if match.group(4) else 1,
                        "context_before": [],
                        "removals": [],
                        "additions": [],
                        "context_after": [],
                    }

                    # parse hunk content
                    i += 1
                    while i < len(lines) and not lines[i].startswith("@@"):
                        hunk_line = lines[i]
                        if hunk_line.startswith(" "):
                            if not hunk["removals"] and not hunk["additions"]:
                                hunk["context_before"].append(hunk_line[1:])
                            else:
                                hunk["context_after"].append(hunk_line[1:])
                        elif hunk_line.startswith("-"):
                            hunk["removals"].append(hunk_line[1:])
                        elif hunk_line.startswith("+"):
                            hunk["additions"].append(hunk_line[1:])
                        i += 1

                    files[current_file].append(hunk)
                    continue

            i += 1

        return files

    def _analyze_hunk_context(
        self, file_lines: List[str], hunk: Dict, file_path: str
    ) -> Dict:
        """Analyze if a hunk's context matches the actual file."""
        analysis = {
            "context_match": False,
            "line_range_valid": False,
            "suggested_location": None,
            "issues": [],
        }

        start_line = hunk["old_start"] - 1  # Convert to 0-based
        end_line = start_line + hunk["old_count"]

        # check if line range is valid
        if start_line >= 0 and end_line <= len(file_lines):
            analysis["line_range_valid"] = True

            # check context match
            expected_context = (
                hunk["context_before"] + hunk["removals"] + hunk["context_after"]
            )
            actual_lines = [
                line.rstrip("\n\r") for line in file_lines[start_line:end_line]
            ]

            # calculate similarity
            import difflib

            similarity = difflib.SequenceMatcher(
                None, expected_context, actual_lines
            ).ratio()

            if similarity > 0.8:
                analysis["context_match"] = True
            else:
                analysis["issues"].append(f"Context similarity only {similarity:.2f}")

                # try to find better location
                better_location = self._find_better_hunk_location(file_lines, hunk)
                if better_location:
                    analysis["suggested_location"] = better_location
        else:
            analysis["issues"].append(
                f"Line range {start_line}-{end_line} exceeds file length {len(file_lines)}"
            )

        return analysis

    def _find_better_hunk_location(
        self, file_lines: List[str], hunk: Dict
    ) -> Optional[int]:
        """Find a better location for applying the hunk using fuzzy matching."""
        import difflib

        search_pattern = hunk["context_before"] + hunk["removals"]
        if not search_pattern:
            return None

        best_ratio = 0
        best_location = None

        # search in a reasonable range around the expected location
        start_search = max(0, hunk["old_start"] - 20)
        end_search = min(len(file_lines), hunk["old_start"] + 20)

        for i in range(start_search, end_search - len(search_pattern) + 1):
            candidate_lines = [
                line.rstrip("\n\r") for line in file_lines[i : i + len(search_pattern)]
            ]
            ratio = difflib.SequenceMatcher(
                None, search_pattern, candidate_lines
            ).ratio()

            if ratio > best_ratio and ratio > 0.7:
                best_ratio = ratio
                best_location = i + 1  # Convert back to 1-based

        return best_location

    def get_human_patch(self, fix_commit_sha: str) -> str:
        """Gets the raw diff/patch string for the human's fix of a specific file."""
        if not self.repo:
            return ""

        try:
            commit: GitCommit = self.repo.commit(fix_commit_sha)
            if not commit.parents:
                return ""
            parent: GitCommit = commit.parents[0]

            # find modified file
            diffs = parent.diff(commit, create_patch=True)

            patch_parts = []
            for diff_item in diffs:
                patch_content = diff_item.diff

                if patch_content:
                    patch_text = (
                        bytes(patch_content).decode("utf-8", "ignore")
                        if isinstance(patch_content, (bytes, bytearray, memoryview))
                        else str(patch_content)
                    )
                    patch_parts.append(patch_text)

            return "\n".join(patch_parts)

        except Exception as e:
            self.log(
                f"    Warning: Could not get human patch for {fix_commit_sha[:7]}. Reason: {e}"
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

    def run_tests_in_venv(
        self, command_parts: list[str]
    ) -> subprocess.CompletedProcess:
        """Runs a command inside the already-built virtual environment."""
        self.log(
            f"  Running test suite with command: '{' '.join(command_parts)}' (runner: {self.project_type})"
        )

        return self._execute_in_venv(command_parts, project_type=self.project_type)

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

    def apply_patch(self, patch_file_path: str) -> bool:
        """Applies a patch with multiple fallback strategies."""
        if not self.repo or not os.path.exists(patch_file_path):
            self.log("ERROR: Repository not initialized or patch file missing")
            return False

        # strategy 1: direct git apply
        try:
            self.repo.git.apply(["--check", patch_file_path])
            self.repo.git.apply(patch_file_path)
            self.log("  --> Patch applied successfully (direct)")
            return True
        except git.GitCommandError as e:
            self.log(f"  --> Direct apply failed: {e.stderr}")

        # strategy 2: git apply with whitespace fixes
        try:
            self.repo.git.apply(["--whitespace=fix", patch_file_path])
            self.log("  --> Patch applied with whitespace fixes")
            return True
        except git.GitCommandError as e:
            self.log(f"  --> Whitespace fix apply failed: {e.stderr}")

        # strategy 3: git apply ignoring whitespace
        try:
            self.repo.git.apply(["--ignore-whitespace", patch_file_path])
            self.log("  --> Patch applied ignoring whitespace")
            return True
        except git.GitCommandError as e:
            self.log(f"  --> Ignore whitespace apply failed: {e.stderr}")

        self.log("  --> All patch application strategies failed")
        return False

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
