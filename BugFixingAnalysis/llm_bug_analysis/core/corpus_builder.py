import json
import ast
import re
import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional, Dict, Any, Callable
from github import Github, GithubException
from github.Commit import Commit
from github.Repository import Repository
from github.Issue import Issue


class DocstringStripper(ast.NodeTransformer):
    """
    AST transformer that removes docstrings from Python code.
    Used to detect functional changes vs documentation-only changes.
    Subfunctions are called by Python's AST framework.
    """

    def _strip_docstring(self, node):
        """Helper to strip docstring from a node if present."""
        if ast.get_docstring(node):
            node.body = node.body[1:]
        self.generic_visit(node)
        return node

    def visit_FunctionDef(self, node):
        """Remove docstring from function definitions."""
        return self._strip_docstring(node)

    def visit_AsyncFunctionDef(self, node):
        """Remove docstring from async function definitions."""
        return self._strip_docstring(node)

    def visit_ClassDef(self, node):
        """Remove docstring from class definitions."""
        return self._strip_docstring(node)

    def visit_Module(self, node):
        """Remove docstring from module."""
        return self._strip_docstring(node)


class BugFixFilter:
    """Filters for identifying real bug fix commits."""

    def __init__(self, config: Dict):

        self.skip_keywords = config.get("skip_keywords", [])
        self.bug_fix_keywords = config.get("bug_fix_keywords", [])
        self.bug_fix_phrases = config.get("bug_fix_phrases", [])
        self.bug_label_terms = config.get("bug_label_terms", [])

    def has_bug_label(self, issue: Issue) -> bool:
        label_names = [label.name.lower() for label in issue.labels]
        return any(
            term in label for term in self.bug_label_terms for label in label_names
        )

    def is_likely_bug_fix(self, title: str, body: str) -> bool:
        """
        Use heuristics to determine if a commit is likely a bug fix.
        """
        title_lower = title.lower()
        body_lower = (body or "").lower()

        # check skip keywords first (early exit)
        for keyword in self.skip_keywords:
            if keyword in title_lower or keyword in body_lower[:200]:
                return False

        # check bug fix keywords in title
        for keyword in self.bug_fix_keywords:
            if keyword in title_lower:
                # filter out doc/test fixes
                if any(
                    skip in title_lower
                    for skip in [
                        "fix typo",
                        "fix spelling",
                        "fix doc",
                        "fix test marker",
                    ]
                ):
                    return False
                return True

        # check bug fix phrases in body (maybe should also in title?)
        for phrase in self.bug_fix_phrases:
            if phrase in body_lower[:500]:
                return True

        return False


class IssueLinker:
    """Handles linking commits to GitHub issues/PRs."""

    def __init__(self, repo: Repository, bug_filter: BugFixFilter, log_callback):
        self.repo = repo
        self.filter = bug_filter  # already have it, why not use it
        self.log = log_callback

    def extract_issue_data(self, commit_message: str) -> Optional[dict[str, str]]:
        """
        Extract issue data from commit message.

        Priority order:
        1. Direct issue reference (#123) with bug label -> Use issue
        2. PR with linked issue -> Use linked issue
        3. PR without linked issue but has bug label -> Use PR as pseudo-issue
        4. PR that looks like bug fix (heuristic) -> Use PR as pseudo-issue
        """
        issue_number = self._extract_issue_number(commit_message)
        if not issue_number:
            return None

        try:
            issue = self.repo.get_issue(number=issue_number)

            if issue.pull_request:
                return self._process_pull_request(issue)
            else:
                return self._process_issue(issue)

        except GithubException:
            self.log(
                f"    --> Could not fetch reference #{issue_number}. "
                f"It may be private or deleted. Skipping."
            )
            return None

    def _extract_issue_number(self, text: str) -> Optional[int]:
        """Extract first issue/PR number from text."""
        match = re.search(r"#(\d+)", text)
        return int(match.group(1)) if match else None

    def _create_issue_data(self, title: str, body: str, source: str) -> Dict[str, str]:
        """Create a standardized issue data dict."""
        self.log(f"    --> Successfully fetched {source}: {title}")
        return {
            "issue_title": title,
            "issue_body": body or "No description provided.",
        }

    def _process_issue(self, issue: Issue) -> Dict[str, str]:
        """Process a direct issue reference."""
        self.log(f"    --> Found Issue #{issue.number}: {issue.title}")

        if self.filter.has_bug_label(issue):
            self.log(f"    --> Issue has bug label - confirmed bug!")

        return self._create_issue_data(
            issue.title, issue.body or "", f"Issue #{issue.number}"
        )

    def _process_pull_request(self, pr: Issue) -> Optional[dict[str, str]]:
        """Process a pull request to extract issue data."""
        self.log(f"    --> Found PR #{pr.number}: {pr.title}")

        pr_body = pr.body or ""

        # step 1: find linked issue if it exists
        linked_issue = self._find_linked_issue(pr_body)
        if linked_issue:
            return linked_issue

        # step 2: check for bug label - can a PR even have that? TODO
        if self.filter.has_bug_label(pr):
            self.log(f"    --> PR has bug label/type - confirmed bug!")
            return self._create_issue_data(pr.title, pr_body, "PR description")

        # step 3: heuristic check
        if self.filter.is_likely_bug_fix(pr.title, pr_body):
            self.log(
                f"    --> PR #{pr.number} has no linked issue or bug label, "
                f"but appears to be a bug fix (heuristic)."
            )
            return self._create_issue_data(pr.title, pr_body, "PR description")

        # step 4: not a bug fix
        self.log(
            f"    --> PR #{pr.number} does not link to an issue and "
            f"doesn't appear to be a bug fix. Skipping."
        )
        return None

    def _find_linked_issue(self, pr_body: str) -> Optional[dict[str, str]]:
        """Find and fetch linked issue from PR body."""
        link_keywords = ["fixes", "closes", "resolves"]
        pattern = rf"(?i)({'|'.join(link_keywords)})\s+#(\d+)"
        match = re.search(pattern, pr_body)

        if not match:
            return None

        linked_number = int(match.group(2))
        self.log(
            f"    --> Found linked Issue #{linked_number} in PR body. Fetching it."
        )

        try:
            linked_issue = self.repo.get_issue(number=linked_number)

            if linked_issue.pull_request:
                self.log(
                    f"    --> WARNING: Linked #{linked_number} is also a PR, "
                    f"not an issue."
                )
                return None

            if self.filter.has_bug_label(linked_issue):
                self.log(f"    --> Linked issue has bug label/type - confirmed bug!")

            return self._create_issue_data(
                linked_issue.title, linked_issue.body or "", f"Issue #{linked_number}"
            )

        except GithubException:
            self.log(f"    --> WARNING: Could not fetch linked Issue #{linked_number}.")
            return None


class CommitAnalyzer:
    """Analyzes commits to determine if they contain functional bug fixes."""

    def __init__(self, repo: Repository, bug_filter: BugFixFilter, log_callback):

        self.repo = repo
        self.log = log_callback
        self.issue_linker = IssueLinker(
            repo, bug_filter, log_callback
        )  # class only used by CommitAnalyzer

    def is_functional_change(self, parent_sha, commit_sha, file_path) -> bool:
        """Checks if a commit introduced a functional code change."""

        try:
            content_before = self._get_file_content(file_path, parent_sha)
            content_after = self._get_file_content(file_path, commit_sha)

            tree_before = ast.parse(content_before)
            tree_after = ast.parse(content_after)

            stripper = DocstringStripper()
            code_before = ast.unparse(stripper.visit(tree_before))
            code_after = ast.unparse(stripper.visit(tree_after))

            return code_before != code_after

        # if content can't be fetched, might as well assume function change
        except Exception:
            return True

    def _get_file_content(self, file_path: str, ref: str) -> str:
        """Get file content at specific commit."""

        content_file = self.repo.get_contents(file_path, ref=ref)

        # get_contents can return a list or single file
        # for a specific file path, it should always be a single file
        if isinstance(content_file, list):
            raise ValueError(f"Expected single file, got list for {file_path}")

        return content_file.decoded_content.decode("utf-8")

    def process_commit(
        self, commit: Commit, keywords: list[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Analyzes a commit to determine if it's a valid bug fix.

        A commit must pass all these filters:
        1. Not a merge commit
        2. Contains bug fix keywords
        3. Linked to a GitHub issue/PR
        4. Modifies Python files
        5. Has functional code changes (not just docs)
        """
        # filter 1: skip merges
        if len(commit.parents) != 1:
            return None

        # filter 2: keywords from config
        commit_message = commit.commit.message
        if not any(keyword in commit_message.lower() for keyword in keywords):
            return None

        # filter 3: commit must be linked to a real issue
        issue_data = self.issue_linker.extract_issue_data(commit_message)
        if not issue_data:
            return None

        # filter 4: only interested in changes to .py files
        py_files_changed = [f for f in commit.files if f.filename.endswith(".py")]
        if not py_files_changed:
            return None

        # filter 5: functional change or just mistyped comment
        parent_sha = commit.parents[0].sha
        has_functional_change = any(
            self.is_functional_change(parent_sha, commit.sha, py_file.filename)
            for py_file in py_files_changed
        )

        if not has_functional_change:
            self.log(
                f"  Skipping commit {commit.sha[:7]}: Changes are only in comments/docstrings."
            )
            return None

        # if all filters passed, that means a valid data point
        return {
            "repo_name": self.repo.full_name,
            "bug_commit_sha": commit.sha,
            "parent_commit_sha": parent_sha,
            "commit_message": commit_message.split("\n")[0],
            **issue_data,  # merge the returned issue data dictionary
        }


class CorpusBuilder:
    """
    Main corpus builder orchestrator.

    Coordinates the process of:
    1. Loading configuration from config.json and .env
    2. Connecting to GitHub API
    3. Processing repositories to find bug fixes
    4. Saving results to corpus.json

    All filter keywords must be defined in config.json.
    """

    def __init__(self, log_callback: Callable[[str], None]):

        self.log = log_callback
        self.config: Optional[Dict[str, Any]] = None
        self.github_client: Optional[Github] = None

    def _load_configuration(self) -> bool:
        """
        Load configuration from config.json and .env.
        """
        # script_path = os.path.abspath(__file__)
        project_root = Path(__file__).parent.parent
        config_path = project_root / "config.json"
        env_path = project_root / ".env"

        # load GitHub token
        load_dotenv(dotenv_path=env_path)
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            self.log(f"ERROR: GITHUB_TOKEN not found in {env_path}")
            return False

        # load config file
        try:
            with open(config_path) as f:
                config = json.load(f)

            # validate required keys
            required_keys = ["repositories"]
            missing_keys = [key for key in required_keys if key not in config]
            if missing_keys:
                raise KeyError(
                    f"Missing required keys in config.json: {', '.join(missing_keys)}"
                )

            # validate optional keys with defaults
            config.setdefault("max_commits_per_repo", 3)
            config.setdefault("commit_search_depth", 300)

            # store config
            config["token"] = token
            self.config = config

            return True

        except FileNotFoundError:
            self.log(f"ERROR: config.json not found at {config_path}")
            return False
        except KeyError as e:
            self.log(f"ERROR: {e}")
            return False
        except json.JSONDecodeError as e:
            self.log(f"ERROR: Invalid JSON in config.json - {e}")
            return False

    def _process_repository(self, repo_name: str) -> list[Dict[str, Any]]:
        """
        Process a single repository to find bug fixes.
        """
        self.log(f"Processing repository: {repo_name}")

        # Assert preconditions
        # TODO: can I make these assumptions?
        assert self.github_client is not None, "GitHub client must be initialized"
        assert self.config is not None, "Config must be loaded"

        bugs = []

        try:
            repo = self.github_client.get_repo(repo_name)

            # create filter and analyzer for this repository
            bug_filter = BugFixFilter(self.config)
            analyzer = CommitAnalyzer(repo, bug_filter, self.log)

            # process commits up to defined search depth
            commits = repo.get_commits()[: self.config["commit_search_depth"]]

            for commit in commits:
                if not isinstance(commit, Commit):
                    continue

                bug_data = analyzer.process_commit(
                    commit, self.config["commit_keywords"]
                )

                if bug_data:
                    bugs.append(bug_data)
                    self.log(
                        f"  Found FUNCTIONAL fix ({len(bugs)}/{self.config['max_commits_per_repo']}): "
                        f"{bug_data['bug_commit_sha'][:7]} - {bug_data['commit_message']}"
                    )

                if len(bugs) >= self.config["max_commits_per_repo"]:
                    self.log(
                        f"  Reached limit of {self.config['max_commits_per_repo']} "
                        f"for {repo_name}."
                    )
                    break

        except GithubException as e:
            self.log(f"ERROR processing {repo_name}: {e}")

        return bugs

    def _save_corpus(self, bug_corpus: list[Dict[str, Any]]) -> None:
        """
        Save the bug corpus to corpus.json.
        """
        project_root = Path(__file__).parent.parent
        corpus_path = project_root / "corpus.json"

        with open(corpus_path, "w") as f:
            json.dump(bug_corpus, f, indent=2)

    def build(self) -> None:
        """Build the bug fix corpus from configured repositories."""
        # step 1
        if not self._load_configuration():
            return  # error already logged

        # help type checker TODO maybe assert?
        config = self.config
        if config is None:
            return

        # step 2
        self.github_client = Github(config["token"])

        assert self.github_client is not None

        bug_corpus = []

        # step 3
        for repo_url in config["repositories"]:
            repo_name = repo_url.replace("https://github.com/", "")
            bugs = self._process_repository(repo_name)
            bug_corpus.extend(bugs)

        # step 4
        self._save_corpus(bug_corpus)

        self.log(
            f"Corpus build complete. Found {len(bug_corpus)} actionable bug fixes."
        )


def build(log_callback: Callable[[str], None]):
    """
    Build bug fix corpus from configured repositories.
    """
    builder = CorpusBuilder(log_callback)
    builder.build()
