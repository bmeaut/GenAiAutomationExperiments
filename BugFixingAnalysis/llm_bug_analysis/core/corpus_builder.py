import json
import ast
import re
import threading
from pathlib import Path
from typing import Any, Callable
from github import Github, GithubException
from github.Commit import Commit
from github.Repository import Repository
from github.Issue import Issue

from .logger import log
from .github_client import GitHubClient
from .ast_utility import ASTUtils
from .pipeline import PipelineController

ProgressCallback = Callable[[int, int, str], None]


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

        self.bug_fix_keywords = config.get("bug_fix_keywords", [])
        self.bug_fix_phrases = config.get("bug_fix_phrases", [])
        self.bug_label_terms = config.get("bug_label_terms", [])
        self.false_positive_patterns = config.get("false_positive_patterns", [])
        self.hard_skip_keywords = config.get("hard_skip_keywords", [])

    def has_bug_label(self, issue: Issue) -> bool:
        label_names = [label.name.lower() for label in issue.labels]
        return any(
            term in label for term in self.bug_label_terms for label in label_names
        )

    def is_likely_bug_fix(self, title: str, body: str) -> bool:
        """Check if a commit/PR is likely a bug fix by checking for indicators."""
        title_lower = title.lower()
        body_lower = (body or "").lower()

        has_bug_keyword = any(
            keyword in title_lower for keyword in self.bug_fix_keywords
        )
        has_bug_phrase = any(
            phrase in body_lower[:5000] for phrase in self.bug_fix_phrases
        )

        if not has_bug_keyword and not has_bug_phrase:
            return False

        if any(pattern in title_lower for pattern in self.false_positive_patterns):
            return False

        for keyword in self.hard_skip_keywords:
            if keyword in title_lower or keyword in body_lower[:200]:
                return False

        return True


class IssueLinker:
    """Handles linking commits to GitHub issues/PRs."""

    def __init__(self, repo: Repository, bug_filter: BugFixFilter):
        self.repo = repo
        self.filter = bug_filter

    def extract_issue_data(self, commit_message: str) -> dict[str, str] | None:
        """Extract issue data from commit message."""
        issue_number = self._find_primary_issue(commit_message)
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

    def _extract_all_issue_numbers(self, text: str) -> list[int]:
        """Find all #123 references in text."""
        matches = re.findall(r"#(\d+)", text)
        return [int(num) for num in matches]

    def _find_primary_issue(self, text: str) -> int | None:
        """Find the most likely issue number that this commit fixes."""
        # "fixes #123", "closes #456", "resolves #789", etc.
        keyword_pattern = r"(?i)(fix(?:es|ed|ing)?|close(?:s|d|ing)?|resolve(?:s|d|ing)?)\s*:?\s*#(\d+)"
        keyword_matches = re.findall(keyword_pattern, text)

        if keyword_matches:
            issue_num = int(keyword_matches[0][1])
            log(f"    --> Found keyword-linked issue #{issue_num}")
            return issue_num

        all_issues = self._extract_all_issue_numbers(text)

        if all_issues:
            # use last
            issue_num = all_issues[-1]
            if len(all_issues) > 1:
                log(
                    f"    --> Found {len(all_issues)} issues: {all_issues}, using #{issue_num}"
                )
            return issue_num

        return None

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

        linked_issue = self._find_linked_issue(pr_body)
        if linked_issue:
            return linked_issue

        if self.filter.has_bug_label(pr):
            log(f"    --> Has bug label")
            return self._create_issue_data(pr.title, pr_body, "PR description")

        if self.filter.is_likely_bug_fix(pr.title, pr_body):
            log(f"    --> Looks like a bug fix based on keywords")
            return self._create_issue_data(pr.title, pr_body, "PR description")

        log(f"    --> Not a bug fix, skipping PR #{pr.number}.")
        return None

    def _find_linked_issue(self, pr_body: str) -> dict[str, str] | None:
        """Look for 'Fixes #123' style issue links with pattern matching."""
        # - fix/fixes/fixed/fixing, close/closes/closed/closing, resolve/resolves/resolved/resolving
        # - "fixes #123", "fixes: #123", "fixes:#123"
        pattern = r"(?i)(fix(?:es|ed|ing)?|close(?:s|d|ing)?|resolve(?:s|d|ing)?)\s*:?\s*(?:#(\d+)|https?://github\.com/[^/]+/[^/]+/issues/(\d+))"
        match = re.search(pattern, pr_body)

        if not match:
            return None

        linked_number = int(match.group(2) if match.group(2) else match.group(3))
        log(f"    --> Found linked issue #{linked_number}")

        try:
            linked_issue = self.repo.get_issue(number=linked_number)

            if linked_issue.pull_request:
                log(
                    f"    --> Linked #{linked_number} is a PR (possible regression fix)"
                )

                has_bug_label = self.filter.has_bug_label(linked_issue)
                is_bug_fix = self.filter.is_likely_bug_fix(
                    linked_issue.title, linked_issue.body or ""
                )

                if has_bug_label or is_bug_fix:
                    log(f"    --> Linked PR #{linked_number} appears to be bug-related")
                    return self._create_issue_data(
                        linked_issue.title,
                        linked_issue.body or "",
                        f"PR #{linked_number} (regression fix)",
                    )
                else:
                    log(
                        f"    --> Linked PR #{linked_number} is not bug-related, skipping"
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

    def __init__(self, repo: Repository, bug_filter: BugFixFilter, config: dict):
        self.repo = repo
        self.issue_linker = IssueLinker(repo, bug_filter)
        self.test_patterns = config.get("test_patterns", [])

    def is_functional_change(self, parent_sha, commit_sha, file_path) -> bool:
        try:
            content_before = self._get_file_content(file_path, parent_sha)
            content_after = self._get_file_content(file_path, commit_sha)

            tree_before = ASTUtils.parse_string(
                content_before, f"{file_path}@{parent_sha}"
            )
            tree_after = ASTUtils.parse_string(
                content_after, f"{file_path}@{commit_sha}"
            )

            # if parsing failes, probably functional change
            if not tree_before or not tree_after:
                return True

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

    def _categorize_files(self, py_files: list) -> dict:
        """Separate source files from test files."""
        test_files = []
        source_files = []

        for f in py_files:
            is_test = any(pattern in f.filename for pattern in self.test_patterns)
            if is_test:
                test_files.append(f.filename)
            else:
                source_files.append(f.filename)

        return {
            "test_files": test_files,
            "source_files": source_files,
            "all_files": [f.filename for f in py_files],
        }

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

        file_categorization = self._categorize_files(py_files)

        # requirement: must modify both source and test files
        if not file_categorization["source_files"]:
            log(f"  Skipping commit {commit.sha[:7]}: Only test files modified.")
            return None

        if not file_categorization["test_files"]:
            log(f"  Skipping commit {commit.sha[:7]}: No test files modified.")
            return None

        log(f"    --> Source files: {file_categorization['source_files']}")
        log(f"    --> Test files: {file_categorization['test_files']}")

        changed_files = file_categorization["all_files"]
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

        # if all filters passed: valid data point (hopium)
        return {
            "repo_name": self.repo.full_name,
            "bug_commit_sha": commit.sha,
            "parent_commit_sha": parent_sha,
            "commit_message": commit_message.split("\n")[0],
            "commit_date": commit.commit.author.date.isoformat(),
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

    def _process_repository(
        self,
        repo_name: str,
        progress_callback: ProgressCallback | None = None,
        stop_event: threading.Event | None = None,
        resume_event: threading.Event | None = None,
    ) -> list[dict[str, Any]]:
        """Find bugfix commits in a single repo."""
        log(f"Processing repository: {repo_name}")

        if not self.github_client or not self.config:
            raise RuntimeError("Load config and init GitHub client first")

        bugs = []

        try:
            repo = self.github_client.get_repo(repo_name)

            bug_filter = BugFixFilter(self.config)
            analyzer = CommitAnalyzer(repo, bug_filter, self.config)

            max_depth = self.config["commit_search_depth"]
            max_bugs = self.config["max_commits_per_repo"]

            if progress_callback:
                progress_callback(0, max_bugs, f"Processing {repo_name}...")

            commit_count = 0
            # paginated list did not work with simple for loop
            for commit in repo.get_commits():
                status, _ = PipelineController.check_pause_and_stop(
                    resume_event,
                    stop_event,
                    pause_msg="  Commit processing paused - waiting...",
                    resume_msg="  Commit processing resumed",
                )
                if status == "stopped":
                    break

                commit_count += 1
                if commit_count > max_depth:
                    log(f"  Searched {max_depth} commits, stopping.")
                    break

                bug_data = analyzer.process_commit(
                    commit, self.config["commit_keywords"]
                )

                if bug_data:
                    bugs.append(bug_data)
                    log(
                        f"  Found FUNCTIONAL fix ({len(bugs)}/{max_bugs}): "
                        f"{bug_data['bug_commit_sha'][:7]} - {bug_data['commit_message']}"
                    )

                    if progress_callback:
                        progress_callback(
                            len(bugs),
                            max_bugs,
                            f"Found {len(bugs)}/{max_bugs} bugs in {repo_name}",
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

    def _load_existing_corpus(self) -> list[dict[str, Any]]:
        """Load corpus.json if it exists."""
        project_root = Path(__file__).parent.parent
        corpus_path = project_root / "corpus.json"

        if not corpus_path.exists():
            log("No existing corpus found, starting fresh")
            return []

        try:
            existing = json.loads(corpus_path.read_text())
            if not isinstance(existing, list):
                log("WARNING: Invalid corpus format, starting fresh")
                return []
            log(f"Loaded existing corpus: {len(existing)} bugs")
            return existing
        except Exception as e:
            log(f"WARNING: Could not load corpus.json: {e}")
            return []

    def build(
        self,
        progress_callback: ProgressCallback | None = None,
        stop_event: threading.Event | None = None,
        resume_event: threading.Event | None = None,
    ) -> None:
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

        # so corpus building can be resumed
        all_bugs = self._load_existing_corpus()
        processed_repo_names = set(bug["repo_name"] for bug in all_bugs)

        if processed_repo_names:
            log(
                f"Found {len(all_bugs)} existing bugs from {len(processed_repo_names)} repos"
            )

        total_repos = len(config["repositories"])
        processed_repos = len(processed_repo_names)

        for repo_idx, repo_url in enumerate(config["repositories"], 1):
            status, _ = PipelineController.check_pause_and_stop(
                resume_event,
                stop_event,
                pause_msg="Corpus building paused - waiting...",
                resume_msg="Corpus building resumed",
                stop_msg=f"\nWARNING: Corpus building stopped by user\n"
                f"Progress saved: {len(all_bugs)} bugs from {processed_repos} repos",
            )
            if status == "stopped":
                break

            repo_name = repo_url.replace("https://github.com/", "")

            if repo_name in processed_repo_names:
                log(f"Skipping {repo_name} (already in corpus)")
                continue

            if progress_callback:
                progress_callback(
                    processed_repos,
                    total_repos,
                    f"Processing repo {repo_idx}/{total_repos}: {repo_name}",
                )

            bugs = self._process_repository(
                repo_name, progress_callback, stop_event, resume_event
            )
            all_bugs.extend(bugs)

            # incremental after each repo
            self._save_corpus(all_bugs)
            if bugs:
                log(f"  Saved {len(bugs)} bugs to corpus.json ({len(all_bugs)} total)")

            processed_repos += 1

        if progress_callback:
            progress_callback(
                total_repos, total_repos, f"Completed! Found {len(all_bugs)} bugs"
            )

        log(f"Done! Found {len(all_bugs)} bug fixes total.")
