import json
import ast
import re
from pathlib import Path
from typing import Any
from github import Github, GithubException
from github.Commit import Commit
from github.Repository import Repository
from github.Issue import Issue

from core.logger import log
from .github_client import GitHubClient


class DocstringStripper(ast.NodeTransformer):
    """Strips docstrings from Python AST nodes for comparison."""

    def _strip_docstring(self, node):
        if ast.get_docstring(node):
            node.body = node.body[1:]
        self.generic_visit(node)
        return node

    def visit_FunctionDef(self, node):
        return self._strip_docstring(node)

    def visit_AsyncFunctionDef(self, node):
        return self._strip_docstring(node)

    def visit_ClassDef(self, node):
        return self._strip_docstring(node)

    def visit_Module(self, node):
        return self._strip_docstring(node)


class BugFixFilter:
    """Filters for identifying bugfix commits vs. features/refactors."""

    def __init__(self, config: dict):

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
        """Looks for keywords like "fix", "bug", "issue" and filters doc/test fixes."""

        title_lower = title.lower()
        body_lower = (body or "").lower()

        for keyword in self.skip_keywords:
            if keyword in title_lower or keyword in body_lower[:200]:
                return False

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

    def __init__(self, repo: Repository, bug_filter: BugFixFilter):
        self.repo = repo
        self.filter = bug_filter

    def extract_issue_data(self, commit_message: str) -> dict[str, str] | None:
        """Extract issue data from commit message."""
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
            log(
                f"    --> Could not fetch #{issue_number}. "
                f"Might be private or deleted."
            )
            return None

    def _extract_issue_number(self, text: str) -> int | None:
        """Find first #123 ref in text."""
        match = re.search(r"#(\d+)", text)
        return int(match.group(1)) if match else None

    def _create_issue_data(self, title: str, body: str, source: str) -> dict[str, str]:
        log(f"    --> Got {source}: {title}")
        return {
            "issue_title": title,
            "issue_body": body or "No description provided.",
        }

    def _process_issue(self, issue: Issue) -> dict[str, str]:
        """Get data from a direct issue reference."""
        log(f"    --> Found Issue #{issue.number}: {issue.title}")

        if self.filter.has_bug_label(issue):
            log(f"    --> Has bug label")

        return self._create_issue_data(
            issue.title, issue.body or "", f"Issue #{issue.number}"
        )

    def _process_pull_request(self, pr: Issue) -> dict[str, str] | None:
        """Get bug data from PR."""
        log(f"    --> Found PR #{pr.number}: {pr.title}")

        pr_body = pr.body or ""

        # find linked issue if it exists
        linked_issue = self._find_linked_issue(pr_body)
        if linked_issue:
            return linked_issue

        # check for bug label
        if self.filter.has_bug_label(pr):
            log(f"    --> Has bug label")
            return self._create_issue_data(pr.title, pr_body, "PR description")

        # heuristic check
        if self.filter.is_likely_bug_fix(pr.title, pr_body):
            log(f"    --> Looks like a bug fix based on keywords")
            return self._create_issue_data(pr.title, pr_body, "PR description")

        log(f"    --> Not a bug fix, skipping PR #{pr.number}.")
        return None

    def _find_linked_issue(self, pr_body: str) -> dict[str, str] | None:
        """Look for 'Fixes #123' style issue links."""
        link_keywords = ["fixes", "closes", "resolves"]
        pattern = rf"(?i)({'|'.join(link_keywords)})\s+#(\d+)"
        match = re.search(pattern, pr_body)

        if not match:
            return None

        linked_number = int(match.group(2))
        log(f"    --> Found linked issue #{linked_number}")

        try:
            linked_issue = self.repo.get_issue(number=linked_number)

            if linked_issue.pull_request:
                log(
                    f"    --> WARNING: Linked #{linked_number} is also a PR, "
                    f"not an issue."
                )
                return None

            if self.filter.has_bug_label(linked_issue):
                log(f"    --> Linked issue has bug label")

            return self._create_issue_data(
                linked_issue.title, linked_issue.body or "", f"Issue #{linked_number}"
            )

        except GithubException:
            log(f"    --> WARNING: Could not fetch linked Issue #{linked_number}.")
            return None


class CommitAnalyzer:
    """Checks if commits actually change code (not just comments)."""

    def __init__(self, repo: Repository, bug_filter: BugFixFilter):
        self.repo = repo
        self.issue_linker = IssueLinker(repo, bug_filter)

    def is_functional_change(self, parent_sha, commit_sha, file_path) -> bool:
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

        # get_contents returns single file for specific paths
        if isinstance(content_file, list):
            raise ValueError(f"Expected single file, got list for {file_path}")

        return content_file.decoded_content.decode("utf-8")

    def process_commit(
        self, commit: Commit, keywords: list[str]
    ) -> dict[str, Any] | None:
        """Check if it's a valid bug fix."""

        # skip merges
        if len(commit.parents) != 1:
            return None

        # mentions fix/bug/etc
        commit_message = commit.commit.message
        if not any(keyword in commit_message.lower() for keyword in keywords):
            return None

        # must be linked to a real issue
        issue_data = self.issue_linker.extract_issue_data(commit_message)
        if not issue_data:
            return None

        py_files = [f for f in commit.files if f.filename.endswith(".py")]
        if not py_files:
            return None

        changed_files = [f.filename for f in py_files]
        log(f"    --> Changed files: {changed_files}")

        parent_sha = commit.parents[0].sha
        changed_code = any(
            self.is_functional_change(parent_sha, commit.sha, py_file.filename)
            for py_file in py_files
        )

        if not changed_code:
            log(
                f"  Skipping commit {commit.sha[:7]}: Changes are only in comments/docstrings."
            )
            return None

        # if all filters passed, that means a valid data point
        return {
            "repo_name": self.repo.full_name,
            "bug_commit_sha": commit.sha,
            "parent_commit_sha": parent_sha,
            "commit_message": commit_message.split("\n")[0],
            "changed_files": changed_files,
            **issue_data,
        }


class CorpusBuilder:
    """Builds a collection of bugfix commits from GitHub repos."""

    def __init__(self):

        self.config: dict[str, Any] | None = None
        self.github_client: Github | None = None

    def _load_configuration(self) -> bool:
        """Load repos and filters from config.json."""

        project_root = Path(__file__).parent.parent
        config_path = project_root / "config.json"

        try:
            with open(config_path) as f:
                config = json.load(f)

            if "repositories" not in config:
                raise KeyError("Missing 'repositories' in config.json")

            # defaults
            config.setdefault("max_commits_per_repo", 3)
            config.setdefault("commit_search_depth", 300)

            self.config = config
            return True

        except FileNotFoundError:
            log(f"ERROR: config.json not found at {config_path}")
            return False
        except KeyError as e:
            log(f"ERROR: {e}")
            return False
        except json.JSONDecodeError as e:
            log(f"ERROR: Invalid JSON - {e}")
            return False

    def _process_repository(self, repo_name: str) -> list[dict[str, Any]]:
        """Find bugfix commits in a single repo."""
        log(f"Processing repository: {repo_name}")

        if not self.github_client or not self.config:
            raise RuntimeError("Load config and init GitHub client first")

        bugs = []

        try:
            repo = self.github_client.get_repo(repo_name)

            bug_filter = BugFixFilter(self.config)
            analyzer = CommitAnalyzer(repo, bug_filter)

            max_depth = self.config["commit_search_depth"]
            max_bugs = self.config["max_commits_per_repo"]

            commit_count = 0
            # paginated list did not work with simple for loop
            for commit in repo.get_commits():
                commit_count += 1
                if commit_count > max_depth:
                    log(f"  Searched {max_depth} commits, stopping.")
                    break

                # Process the commit
                bug_data = analyzer.process_commit(
                    commit, self.config["commit_keywords"]
                )

                if bug_data:
                    bugs.append(bug_data)
                    log(
                        f"  Found FUNCTIONAL fix ({len(bugs)}/{max_bugs}): "
                        f"{bug_data['bug_commit_sha'][:7]} - {bug_data['commit_message']}"
                    )

                # stop after finding enough
                if len(bugs) >= max_bugs:
                    log(f"  Reached limit of {max_bugs} for {repo_name}.")
                    break

        except GithubException as e:
            log(f"ERROR processing {repo_name}: {e}")

        return bugs

    def _save_corpus(self, bug_corpus: list[dict[str, Any]]) -> None:
        """Save the bugs to corpus.json."""
        project_root = Path(__file__).parent.parent
        corpus_path = project_root / "corpus.json"

        with open(corpus_path, "w") as f:
            json.dump(bug_corpus, f, indent=2)

    def build(self) -> None:
        """Build the bugfix corpus from configured repos."""
        if not self._load_configuration():
            return

        config = self.config
        if config is None:
            return

        try:
            self.github_client = GitHubClient.get_client()
        except ValueError as e:
            log(f"ERROR: {e}")
            return

        all_bugs = []

        for repo_url in config["repositories"]:
            repo_name = repo_url.replace("https://github.com/", "")
            bugs = self._process_repository(repo_name)
            all_bugs.extend(bugs)

        self._save_corpus(all_bugs)
        log(f"Done! Found {len(all_bugs)} bug fixes total.")
