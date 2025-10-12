import pytest
import os
import shutil
from unittest.mock import MagicMock, patch, call
from llm_bug_analysis.core import cleanup_manager


def test_register_temp_dir():
    """Test registering a temporary directory."""
    cleanup_manager._active_temp_dirs.clear()

    cleanup_manager.register_temp_dir("/tmp/test1")
    assert "/tmp/test1" in cleanup_manager._active_temp_dirs

    cleanup_manager.register_temp_dir("/tmp/test2")
    assert len(cleanup_manager._active_temp_dirs) == 2


def test_register_temp_dir_no_duplicates():
    """Test that registering the same directory twice doesn't create duplicates."""
    cleanup_manager._active_temp_dirs.clear()

    cleanup_manager.register_temp_dir("/tmp/test")
    cleanup_manager.register_temp_dir("/tmp/test")

    assert len(cleanup_manager._active_temp_dirs) == 1


def test_unregister_temp_dir():
    """Test unregistering a temporary directory."""
    cleanup_manager._active_temp_dirs.clear()
    cleanup_manager.register_temp_dir("/tmp/test")

    cleanup_manager.unregister_temp_dir("/tmp/test")
    assert "/tmp/test" not in cleanup_manager._active_temp_dirs


def test_unregister_temp_dir_nonexistent():
    """Test unregistering a directory that was never registered doesn't raise error."""
    cleanup_manager._active_temp_dirs.clear()

    # should not raise exception
    cleanup_manager.unregister_temp_dir("/tmp/nonexistent")


def test_clear_venv_cache_directory_exists(tmp_path, mocker):
    """Test clearing venv cache when directory exists."""
    cache_dir = tmp_path / "venv_cache"
    cache_dir.mkdir()
    (cache_dir / "test_file.txt").write_text("test")

    mocker.patch(
        "llm_bug_analysis.core.cleanup_manager.VENV_CACHE_PATH", str(cache_dir)
    )

    log_callback = MagicMock()
    cleanup_manager.clear_venv_cache(log_callback)

    assert not cache_dir.exists()
    assert log_callback.call_count >= 2
    log_callback.assert_any_call("--- Starting venv cache cleanup ---")
    log_callback.assert_any_call("  --> Cache cleared successfully.")


def test_clear_venv_cache_directory_not_exists(mocker):
    """Test clearing venv cache when directory doesn't exist."""
    mocker.patch(
        "llm_bug_analysis.core.cleanup_manager.VENV_CACHE_PATH", "/nonexistent/path"
    )
    mocker.patch("os.path.exists", return_value=False)

    log_callback = MagicMock()
    cleanup_manager.clear_venv_cache(log_callback)

    log_callback.assert_any_call("  Cache directory not found. Nothing to do.")


def test_clear_venv_cache_deletion_fails(tmp_path, mocker):
    """Test handling of deletion failure."""
    cache_dir = tmp_path / "venv_cache"
    cache_dir.mkdir()

    mocker.patch(
        "llm_bug_analysis.core.cleanup_manager.VENV_CACHE_PATH", str(cache_dir)
    )
    mocker.patch("shutil.rmtree", side_effect=PermissionError("Permission denied"))

    log_callback = MagicMock()
    cleanup_manager.clear_venv_cache(log_callback)

    # should log error but not crash
    assert any("ERROR" in str(call) for call in log_callback.call_args_list)


def test_final_cleanup_empty():
    """Test final cleanup with no active directories."""
    cleanup_manager._active_temp_dirs.clear()

    with patch("builtins.print") as mock_print:
        cleanup_manager.final_cleanup()

        mock_print.assert_any_call(
            "[Cleanup Manager] No leftover directories to clean."
        )


def test_final_cleanup_removes_directories(tmp_path):
    """Test final cleanup removes registered directories."""
    cleanup_manager._active_temp_dirs.clear()

    test_dir1 = tmp_path / "temp1"
    test_dir2 = tmp_path / "temp2"
    test_dir1.mkdir()
    test_dir2.mkdir()

    cleanup_manager.register_temp_dir(str(test_dir1))
    cleanup_manager.register_temp_dir(str(test_dir2))

    cleanup_manager.final_cleanup()

    assert not test_dir1.exists()
    assert not test_dir2.exists()
    assert len(cleanup_manager._active_temp_dirs) == 0


def test_final_cleanup_handles_deletion_error(tmp_path, mocker):
    """Test final cleanup handles deletion errors gracefully."""
    cleanup_manager._active_temp_dirs.clear()

    test_dir = tmp_path / "temp"
    cleanup_manager.register_temp_dir(str(test_dir))

    mocker.patch("shutil.rmtree", side_effect=PermissionError("Cannot delete"))

    with patch("builtins.print") as mock_print:
        cleanup_manager.final_cleanup()

        # should print error but not crash
        assert any("ERROR" in str(call) for call in mock_print.call_args_list)


def test_set_log_callback():
    """Test setting the log callback."""
    mock_callback = MagicMock()
    cleanup_manager.set_log_callback(mock_callback)

    cleanup_manager._log("test message")
    mock_callback.assert_called_once_with("test message")


def test_log_without_callback():
    """Test logging without a callback uses print."""
    cleanup_manager._log_callback = None

    with patch("builtins.print") as mock_print:
        cleanup_manager._log("test message")
        mock_print.assert_called_once_with("test message")
