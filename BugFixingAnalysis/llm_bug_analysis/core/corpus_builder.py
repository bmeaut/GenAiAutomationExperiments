# core/corpus_builder.py

import json
import ast
import re
from github import Github, GithubException
from github.Commit import Commit
import os
from dotenv import load_dotenv
from typing import Optional, Dict, Any


class DocstringStripper(ast.NodeTransformer):
    """Gets rid of documentation strings."""

    """Used by is_functional_change"""

    def visit_FunctionDef(self, node):
        # node is a function definition that gets eaten by this function
        if ast.get_docstring(node):
            node.body = node.body[1:]  # strips the first line
        self.generic_visit(node)  # iterate further
        return node  # must return the node to the tree

    def visit_ClassDef(self, node):
        if ast.get_docstring(node):
            node.body = node.body[1:]
        self.generic_visit(node)
        return node

    def visit_Module(self, node):
        if ast.get_docstring(node):
            node.body = node.body[1:]
        self.generic_visit(node)
        return node


def is_functional_change(repo, parent_sha, commit_sha, file_path):
    """Checks if a commit introduced a functional code change."""
    """A simple docstring updating commit will change .py files, so a simpler check wasn't enough."""

    try:
        content_before = repo.get_contents(
            file_path, ref=parent_sha
        ).decoded_content.decode(
            "utf-8"
        )  # parent commit >> buggy state
        content_after = repo.get_contents(
            file_path, ref=commit_sha
        ).decoded_content.decode("utf-8")
        tree_before = ast.parse(content_before)
        tree_after = ast.parse(content_after)
        stripper = DocstringStripper()
        return ast.unparse(stripper.visit(tree_before)) != ast.unparse(
            stripper.visit(tree_after)
        )  # if they differ, functional change

    # if content can't be fetched, might as well assume function change
    except Exception:
        return True


def _load_configuration(log_callback) -> Optional[Dict[str, Any]]:
    """Loads settings from config.json and .env, returning a config dict or None on error."""
    script_path = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(script_path))
    config_path = os.path.join(project_root, "config.json")
    env_path = os.path.join(project_root, ".env")

    # load token
    load_dotenv(dotenv_path=env_path)
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        log_callback(f"ERROR: GITHUB_TOKEN not found in {env_path}")
        return None

    try:
        with open(config_path, "r") as f:
            config = json.load(f)

        # ensure the required 'repositories' key exists.
        if "repositories" not in config:
            raise KeyError("'repositories' key is missing from config.json")

        # set defaults for optional keys.
        config["commit_keywords"] = config.get(
            "commit_keywords",
            [
                "fix",
                "bug",
                "error",
                "issue",
                "defect",
                "fault",
                "flaw",
                "mistake",
                "incorrect",
                "wrong",
                "fail",
                "solve",
                "patch",
                "repair",
                "resolve",
                "close",
            ],
        )
        config["max_commits_per_repo"] = config.get("max_commits_per_repo", 5)
        config["commit_search_depth"] = config.get(
            "commit_search_depth", 300
        )  # only looking at relatively recent commits
        config["token"] = token

        return config

    except (FileNotFoundError, KeyError, Exception) as e:
        log_callback(f"ERROR: Failed to load configuration - {e}")
        return None


def _fetch_issue_data(commit_message, repo, log_callback) -> Optional[Dict[str, Any]]:
    """
    Finds and fetches data for a GitHub issue referenced in a commit message.
    It also "chases" links within a PR body to find the real issue.
    Returns the issue data dictionary if successful, otherwise returns None.
    """

    # find the first issue/PR number in the commit message
    primary_match = re.search(r"#(\d+)", commit_message)
    if not primary_match:
        return None

    issue_number = int(primary_match.group(1))
    try:

        issue_obj = repo.get_issue(number=issue_number)

        if issue_obj.pull_request:
            # this object is a pull request, not a pure issue
            log_callback(f"    --> Found PR #{issue_number}: {issue_obj.title}")

            issue_title = issue_obj.title
            issue_body = issue_obj.body or ""  # ensure body is a string

            # perform link-chasing within the PR body to find the *real* issue
            link_keywords = ["fixes", "closes", "resolves"]
            body_match = re.search(
                rf"(?i)({'|'.join(link_keywords)})\s+#(\d+)", issue_body
            )

            if body_match:
                linked_issue_number = int(body_match.group(2))
                log_callback(
                    f"    --> Found linked Issue #{linked_issue_number} in PR body. Fetching it."
                )
                try:
                    linked_issue_obj = repo.get_issue(number=linked_issue_number)
                    # the linked issue's title and body are the true source of context
                    issue_title = linked_issue_obj.title
                    issue_body = linked_issue_obj.body or "No issue body provided."
                    log_callback(
                        f"    --> Successfully fetched linked Issue: {issue_title}"
                    )
                except GithubException:
                    log_callback(
                        f"    --> WARNING: Could not fetch linked Issue #{linked_issue_number}. Using PR content instead."
                    )
        else:
            # this object is a pure issue
            log_callback(f"    --> Found Issue #{issue_number}: {issue_obj.title}")
            issue_title = issue_obj.title
            issue_body = issue_obj.body or "No issue body provided."

        return {
            "issue_title": issue_title,
            "issue_body": issue_body,
        }
    except GithubException:
        log_callback(
            f"    --> Could not fetch reference #{issue_number}. It may be private or deleted. Skipping."
        )
        return None


def _process_commit(commit, repo, keywords, log_callback) -> Optional[Dict[str, Any]]:
    """
    Analyzes a single commit to determine if it's a valid, scannable bug fix.
    A commit is only valid if it's linked to a real, fetchable GitHub Issue.
    """
    # filter 1: skip merges
    if len(commit.parents) != 1:
        return None

    # filter 2: keywords from config
    commit_message = commit.commit.message
    if not any(keyword in commit_message.lower() for keyword in keywords):
        return None

    # filter 3: commit must be linked to a real issue
    issue_data = _fetch_issue_data(commit_message, repo, log_callback)
    if not issue_data:
        return None  # no issue data means invalid commit for the experiment

    # filter 4: only interested in .py files
    py_files_changed = [f for f in commit.files if f.filename.endswith(".py")]
    if not py_files_changed:
        return None

    # functional change or just mistyped comment
    parent_sha = commit.parents[0].sha
    has_functional_change = any(
        is_functional_change(repo, parent_sha, commit.sha, py_file.filename)
        for py_file in py_files_changed
    )
    if not has_functional_change:
        log_callback(
            f"  Skipping commit {commit.sha[:7]}: Changes are only in comments/docstrings."
        )
        return None

    # if all filters passed, that means a valid data point
    return {
        "repo_name": repo.full_name,
        "bug_commit_sha": commit.sha,
        "parent_commit_sha": parent_sha,
        "commit_message": commit_message.split("\n")[0],
        **issue_data,  # merge the returned issue data dictionary
    }


def build(log_callback):
    """
    The main operator for the corpus building process. It loads the configuration
    and then iterates through repositories and commits to find valid bug fixes.
    """
    config = _load_configuration(log_callback)
    if not config:
        return  # stop

    g = Github(config["token"])
    bug_corpus = []

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    corpus_path = os.path.join(project_root, "corpus.json")

    # clean up URL (I like it more if it's enough to paste it into the GUI)
    for repo_url in config["repositories"]:
        repo_name = repo_url.replace("https://github.com/", "")
        log_callback(f"Processing repository: {repo_name}")
        found_count = 0
        try:
            repo = g.get_repo(repo_name)

            for commit_obj in repo.get_commits()[: config["commit_search_depth"]]:
                if isinstance(commit_obj, Commit):
                    bug_data = _process_commit(
                        commit_obj, repo, config["commit_keywords"], log_callback
                    )

                    if bug_data:
                        bug_corpus.append(bug_data)
                        found_count += 1
                        log_callback(
                            f"  Found FUNCTIONAL fix ({found_count}/{config['max_commits_per_repo']}): {bug_data['bug_commit_sha'][:7]} - {bug_data['commit_message']}"
                        )

                if found_count >= config["max_commits_per_repo"]:
                    log_callback(
                        f"  Reached limit of {config['max_commits_per_repo']} for {repo_name}."
                    )
                    break

        except GithubException as e:
            log_callback(f"ERROR processing {repo_name}: {e}")

    with open(corpus_path, "w") as f:
        json.dump(bug_corpus, f, indent=2)

    log_callback(
        f"Corpus build complete. Found {len(bug_corpus)} actionable bug fixes."
    )
