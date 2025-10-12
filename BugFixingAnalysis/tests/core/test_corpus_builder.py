# tests/core/test_corpus_builder.py
import pytest
from unittest.mock import MagicMock, patch
from llm_bug_analysis.core import corpus_builder
from github.Commit import Commit


# mock the GithubException
class MockGithubException(Exception):
    pass


@pytest.fixture
def mock_github(mocker):
    """Fixture to mock the entire github library interaction."""
    # create mock objects for the GitHub API hierarchy

    # use spec=Commit to make the mock pass isinstance checks
    mock_commit = MagicMock(spec=Commit)
    mock_commit.sha = "abc1234"
    mock_commit.commit.message = "fix: this is a bug fix for #123"
    mock_commit.parents = [MagicMock(sha="def5678")]
    mock_commit.files = [MagicMock(filename="src/main.py")]

    mock_issue = MagicMock()
    mock_issue.title = "A real issue"
    mock_issue.body = "Something is broken."

    mock_repo = MagicMock()
    mock_repo.get_commits.return_value = [mock_commit]
    mock_repo.get_issue.return_value = mock_issue
    mock_repo.full_name = "user/repo"

    mock_github_instance = MagicMock()
    mock_github_instance.get_repo.return_value = mock_repo

    mocker.patch(
        "llm_bug_analysis.core.corpus_builder.Github", return_value=mock_github_instance
    )
    mocker.patch(
        "llm_bug_analysis.core.corpus_builder.is_functional_change", return_value=True
    )
    mocker.patch(
        "llm_bug_analysis.core.corpus_builder.GithubException", MockGithubException
    )

    return mock_github_instance


def test_build_corpus_success(mock_github, mocker):
    """
    Test the successful creation of a corpus by mocking the config loader.
    """
    log_callback = MagicMock()

    # 1. define the exact config we want the test to use.
    test_config = {
        "repositories": ["https://github.com/user/repo"],
        "commit_keywords": ["fix"],
        "max_commits_per_repo": 1,
        "commit_search_depth": 100,
        "token": "fake_token",
    }

    # 2. mock the configuration loader to return our test config.
    mocker.patch(
        "llm_bug_analysis.core.corpus_builder._load_configuration",
        return_value=test_config,
    )

    # 3. mock the json.dump function to check what gets written to the file.
    mock_dump = mocker.patch("json.dump")
    # mock 'open' to prevent the function from actually writing a file
    mocker.patch("builtins.open", mocker.mock_open())

    # 4. run the function we are testing.
    corpus_builder.build(log_callback)

    # 5. assert the results.
    # check that the final log message has the correct count.
    log_callback.assert_any_call("Corpus build complete. Found 1 actionable bug fixes.")

    # check that json.dump was called with the correct data.
    mock_dump.assert_called_once()
    written_data = mock_dump.call_args[0][0]  # Get the first argument passed to dump
    assert len(written_data) == 1
    assert written_data[0]["bug_commit_sha"] == "abc1234"
    assert written_data[0]["issue_title"] == "A real issue"


def test_fetch_issue_data_no_issue_number():
    """Test that commit messages without issue numbers return None."""
    result = corpus_builder._fetch_issue_data(
        "A commit message", MagicMock(), MagicMock()
    )
    assert result is None


def test_fetch_issue_data_api_fails(mocker):
    """Test that if the GitHub API fails to find an issue, it returns None."""
    mock_repo = MagicMock()
    mock_repo.get_issue.side_effect = MockGithubException()
    log_callback = MagicMock()

    mocker.patch(
        "llm_bug_analysis.core.corpus_builder.GithubException", MockGithubException
    )

    result = corpus_builder._fetch_issue_data("fix(#123)", mock_repo, log_callback)

    assert result is None
    log_callback.assert_called_with(
        "    --> Could not fetch issue #123 (it might be a PR or private). Skipping."
    )
