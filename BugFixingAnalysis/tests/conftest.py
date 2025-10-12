import pytest
import json
import os


@pytest.fixture
def tmp_project_root(tmp_path):
    """Create a temporary project root with dummy config and corpus files."""
    # create dummy config.json
    config_data = {
        "repositories": ["https://github.com/user/repo"],
        "commit_keywords": ["fix"],
        "max_commits_per_repo": 1,
        "test_command": "pytest",
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config_data))

    # create dummy corpus.json
    corpus_data = [
        {
            "repo_name": "user/repo",
            "bug_commit_sha": "abc1234",
            "parent_commit_sha": "def5678",
            "commit_message": "fix: a test bug",
            "issue_title": "Test Issue",
            "issue_body": "This is a test issue body.",
        }
    ]
    corpus_file = tmp_path / "corpus.json"
    corpus_file.write_text(json.dumps(corpus_data))

    # create a dummy .env file
    env_file = tmp_path / ".env"
    env_file.write_text('GITHUB_TOKEN="fake_token"')

    # create results directory
    (tmp_path / "results").mkdir()

    # temporarily change the working directory to the tmp_path for the test
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(original_cwd)
