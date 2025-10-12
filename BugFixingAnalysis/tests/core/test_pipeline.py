import pytest
from llm_bug_analysis.core import pipeline
from unittest.mock import MagicMock, patch, mock_open
import subprocess
import os


def test_analyze_patch_basic():
    """Test the patch analysis function with a sample diff."""
    patch_text = """
--- a/file.py
+++ b/file.py
@@ -1,5 +1,5 @@
- removed line 1
- removed line 2
+ added line 1
  context line
+ added line 2
"""
    stats = pipeline._analyze_patch(patch_text)
    assert stats["lines_added"] == 2
    assert stats["lines_deleted"] == 2
    assert stats["total"] == 4


def test_analyze_patch_only_additions():
    """Test patch with only additions."""
    patch_text = """
+++ b/file.py
@@ -1,3 +1,5 @@
 existing line
+new line 1
+new line 2
"""
    stats = pipeline._analyze_patch(patch_text)
    assert stats["lines_added"] == 2
    assert stats["lines_deleted"] == 0
    assert stats["total"] == 2


def test_analyze_patch_only_deletions():
    """Test patch with only deletions."""
    patch_text = """
--- a/file.py
@@ -1,5 +1,3 @@
-deleted line 1
-deleted line 2
 remaining line
"""
    stats = pipeline._analyze_patch(patch_text)
    assert stats["lines_added"] == 0
    assert stats["lines_deleted"] == 2
    assert stats["total"] == 2


def test_analyze_patch_empty():
    """Test analyzing an empty patch."""
    stats = pipeline._analyze_patch("")
    assert stats["lines_added"] == 0
    assert stats["lines_deleted"] == 0
    assert stats["total"] == 0


def test_initialize_results_file_creates_new(tmp_path):
    """Test creating a new results file."""
    results_file = tmp_path / "results.csv"

    with patch("os.path.exists", return_value=False), patch(
        "builtins.open", mock_open()
    ) as mock_file:
        pipeline._initialize_results_file(str(results_file))

        mock_file.assert_called_once()


def test_save_test_failure_log(tmp_path, mocker):
    """Test saving test failure logs."""
    mocker.patch(
        "llm_bug_analysis.core.pipeline.os.path.join",
        side_effect=lambda *args: "/".join(args),
    )
    mocker.patch("llm_bug_analysis.core.pipeline.os.makedirs")

    error = subprocess.CalledProcessError(
        returncode=1, cmd="pytest", output="stdout content", stderr="stderr content"
    )

    with patch("builtins.open", mock_open()) as mock_file:
        result = pipeline._save_test_failure_log(
            project_root="/project",
            repo_name="user/repo",
            commit_sha="abc123def",
            run_type="human_fix",
            error=error,
        )

        assert "user_repo" in result
        assert "abc123" in result
        mock_file.assert_called_once()


def test_run_tests_with_exclusions_success(mocker):
    """Test that the test command is constructed and called correctly."""
    mock_handler = MagicMock()
    mock_handler.run_tests_in_venv.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="== 10 passed in 5.00s =="
    )

    config = {
        "test_exclusions": {
            "user/repo": {
                "ignore_paths": ["tests/ignore.py"],
                "deselect_nodes": ["tests/test_slow.py::test_a"],
            }
        }
    }
    log_callback = MagicMock()

    result = pipeline._run_tests_with_exclusions(
        handler=mock_handler,
        test_command="pytest -v",
        repo_name="user/repo",
        commit_sha="abc1234",
        run_type="human_fix",
        config=config,
        log_callback=log_callback,
        project_root="/tmp",
    )

    assert result is True
    mock_handler.run_tests_in_venv.assert_called_once()


def test_run_tests_with_exclusions_no_exclusions(mocker):
    """Test running tests when no exclusions are configured."""
    mock_handler = MagicMock()
    mock_handler.run_tests_in_venv.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="== 5 passed =="
    )

    config = {"test_exclusions": {}}
    log_callback = MagicMock()

    result = pipeline._run_tests_with_exclusions(
        handler=mock_handler,
        test_command="pytest",
        repo_name="user/repo",
        commit_sha="abc123",
        run_type="llm_fix",
        config=config,
        log_callback=log_callback,
        project_root="/tmp",
    )

    assert result is True
    mock_handler.run_tests_in_venv.assert_called_with(["pytest"])


def test_run_tests_with_exclusions_test_failure(mocker):
    """Test handling of test failures."""
    error = subprocess.CalledProcessError(
        returncode=1, cmd="pytest", output="FAILED", stderr="errors"
    )

    mock_handler = MagicMock()
    mock_handler.run_tests_in_venv.side_effect = error

    config = {"test_exclusions": {}}
    log_callback = MagicMock()

    mocker.patch(
        "llm_bug_analysis.core.pipeline._save_test_failure_log",
        return_value="/log/path",
    )

    result = pipeline._run_tests_with_exclusions(
        handler=mock_handler,
        test_command="pytest",
        repo_name="user/repo",
        commit_sha="abc123",
        run_type="human_fix",
        config=config,
        log_callback=log_callback,
        project_root="/tmp",
    )

    assert result is False
    log_callback.assert_called()


def test_log_results(tmp_path, mocker):
    """Test logging results to CSV."""
    results_file = tmp_path / "results.csv"

    bug_data = {
        "repo_name": "user/repo",
        "bug_commit_sha": "abc123",
        "commit_message": "fix",
        "issue_title": "Test Bug",
        "issue_body": "body",
        "changed_files": ["a.py"],
        "comp_before": {},
        "ai_results": {},
        "human_results": {},
    }

    with patch("builtins.open", mock_open()), patch("csv.writer") as mock_csv_writer:

        mock_writer_instance = mock_csv_writer.return_value

        pipeline._log_results(str(results_file), bug_data)

        mock_csv_writer.assert_called_once()

        mock_writer_instance.writerow.assert_called_once()
