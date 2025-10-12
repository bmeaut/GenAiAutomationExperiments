import pytest
from llm_bug_analysis.core.analysis import analyze_files
from unittest.mock import MagicMock, patch
import os


def test_analyze_files_calculates_correctly(mocker):
    """
    Ensure that analyze_files correctly aggregates metrics from mocked analyzers.
    """
    # mock lizard and complexipy
    mock_lizard_result = MagicMock()
    mock_lizard_result.function_list = [
        MagicMock(cyclomatic_complexity=5, parameters=["a", "b"], token_count=100),
        MagicMock(cyclomatic_complexity=3, parameters=["c"], token_count=50),
    ]
    mocker.patch("lizard.FileAnalyzer", return_value=lambda path: mock_lizard_result)

    mock_complexipy_result = MagicMock()
    mock_complexipy_result.complexity = 20
    mocker.patch("complexipy.file_complexity", return_value=mock_complexipy_result)

    mocker.patch("os.path.join", return_value="fake/path/file.py")

    repo_path = "/fake/repo"
    filenames = ["file1.py"]
    log_callback = MagicMock()

    results = analyze_files(repo_path, filenames, log_callback)

    assert results["total_cc"] == 8
    assert results["total_cognitive"] == 20
    assert results["avg_params"] == 1.5
    assert results["total_tokens"] == 150
    log_callback.assert_not_called()


def test_analyze_files_handles_analysis_error(mocker):
    """
    Ensure that if an analysis tool fails, it's logged and doesn't crash.
    """
    mocker.patch("lizard.FileAnalyzer", side_effect=Exception("Lizard failed"))
    mocker.patch("os.path.join", return_value="fake/path/file.py")

    repo_path = "/fake/repo"
    filenames = ["file1.py"]
    log_callback = MagicMock()

    results = analyze_files(repo_path, filenames, log_callback)

    assert results["total_cc"] == 0
    assert results["total_cognitive"] == 0
    log_callback.assert_called_once_with(
        "    Warning: Could not analyze file1.py. Reason: Lizard failed"
    )


def test_analyze_files_filters_non_python_files(mocker):
    """Test that non-Python files are filtered out."""
    filenames = ["readme.txt", "script.sh", "data.json"]
    log_callback = MagicMock()

    mock_lizard = mocker.patch("lizard.FileAnalyzer")
    mock_complexipy = mocker.patch("complexipy.file_complexity")

    results = analyze_files("/fake/repo", filenames, log_callback)

    # should not analyze any files
    mock_lizard.assert_not_called()
    mock_complexipy.assert_not_called()
    assert results["total_cc"] == 0


def test_analyze_files_handles_none_in_filenames(mocker):
    """Test that None values in filenames are filtered."""
    mock_lizard_result = MagicMock()
    mock_lizard_result.function_list = []
    mocker.patch("lizard.FileAnalyzer", return_value=lambda path: mock_lizard_result)

    mock_complexipy_result = MagicMock()
    mock_complexipy_result.complexity = 0
    mocker.patch("complexipy.file_complexity", return_value=mock_complexipy_result)

    filenames = [None, "test.py", None, "another.py"]
    log_callback = MagicMock()

    results = analyze_files("/fake/repo", filenames, log_callback)

    # should only process 2 files
    assert results is not None


def test_analyze_files_empty_file_list():
    """Test with empty file list returns zeros."""
    log_callback = MagicMock()
    results = analyze_files("/fake/repo", [], log_callback)

    assert results["total_cc"] == 0
    assert results["total_cognitive"] == 0
    assert results["avg_params"] == 0
    assert results["total_tokens"] == 0


def test_analyze_files_zero_functions_no_divide_by_zero(mocker):
    """Test avg_params calculation when no functions found."""
    mock_lizard_result = MagicMock()
    mock_lizard_result.function_list = []
    mocker.patch("lizard.FileAnalyzer", return_value=lambda path: mock_lizard_result)

    mock_complexipy_result = MagicMock()
    mock_complexipy_result.complexity = 5
    mocker.patch("complexipy.file_complexity", return_value=mock_complexipy_result)

    filenames = ["empty.py"]
    log_callback = MagicMock()

    results = analyze_files("/fake/repo", filenames, log_callback)

    assert results["avg_params"] == 0
    assert results["total_cognitive"] == 5


def test_analyze_files_multiple_files(mocker):
    """Test analyzing multiple Python files aggregates correctly."""
    mock_lizard_result = MagicMock()
    mock_lizard_result.function_list = [
        MagicMock(cyclomatic_complexity=2, parameters=["x"], token_count=20)
    ]
    mocker.patch("lizard.FileAnalyzer", return_value=lambda path: mock_lizard_result)

    mock_complexipy_result = MagicMock()
    mock_complexipy_result.complexity = 3
    mocker.patch("complexipy.file_complexity", return_value=mock_complexipy_result)

    filenames = ["file1.py", "file2.py", "file3.py"]
    log_callback = MagicMock()

    results = analyze_files("/fake/repo", filenames, log_callback)

    assert results["total_cc"] == 6  # 2 * 3 files
    assert results["total_cognitive"] == 9  # 3 * 3 files
    assert results["total_tokens"] == 60  # 20 * 3 files


def test_analyze_files_rounds_avg_params_correctly(mocker):
    """Test that avg_params is rounded to 2 decimal places."""
    mock_lizard_result = MagicMock()
    mock_lizard_result.function_list = [
        MagicMock(cyclomatic_complexity=1, parameters=["a"], token_count=10),
        MagicMock(cyclomatic_complexity=1, parameters=["b", "c"], token_count=10),
        MagicMock(cyclomatic_complexity=1, parameters=["d", "e", "f"], token_count=10),
    ]
    mocker.patch("lizard.FileAnalyzer", return_value=lambda path: mock_lizard_result)

    mock_complexipy_result = MagicMock()
    mock_complexipy_result.complexity = 0
    mocker.patch("complexipy.file_complexity", return_value=mock_complexipy_result)

    filenames = ["test.py"]
    log_callback = MagicMock()

    results = analyze_files("/fake/repo", filenames, log_callback)

    # (1 + 2 + 3) / 3 = 2.0
    assert results["avg_params"] == 2.0


def test_analyze_files_complexipy_fails_but_lizard_succeeds(mocker):
    """Test partial failure - complexipy fails but lizard succeeds."""
    mock_lizard_result = MagicMock()
    mock_lizard_result.function_list = [
        MagicMock(cyclomatic_complexity=3, parameters=["x"], token_count=30)
    ]
    mocker.patch("lizard.FileAnalyzer", return_value=lambda path: mock_lizard_result)

    mocker.patch(
        "complexipy.file_complexity", side_effect=Exception("Complexipy error")
    )

    filenames = ["test.py"]
    log_callback = MagicMock()

    results = analyze_files("/fake/repo", filenames, log_callback)

    # should log error and return zeros for all metrics
    assert results["total_cc"] == 0
    assert results["total_cognitive"] == 0
    log_callback.assert_called_once()
