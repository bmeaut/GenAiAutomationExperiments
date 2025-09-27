import shutil
import atexit
import os
from typing import Callable, Optional

# cache path definition
script_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(script_path)))
VENV_CACHE_PATH = os.path.join(project_root, "venv_cache")

_log_callback: Optional[Callable[[str], None]] = None


def set_log_callback(log_func: Callable[[str], None]):
    global _log_callback
    _log_callback = log_func


def _log(message: str):
    if _log_callback:
        _log_callback(message)
    else:
        print(message)


# keep note of temp directories
# set to avoid duplicates
_active_temp_dirs = set()


def register_temp_dir(path: str):
    print(f"[Cleanup Manager] Registered: {path}")
    _active_temp_dirs.add(path)


def unregister_temp_dir(path: str):
    print(f"[Cleanup Manager] Unregistered: {path}")
    _active_temp_dirs.discard(
        path
    )  # .discard() doesn't raise an error if path is not found


def clear_venv_cache(log_callback: Callable[[str], None]):
    """Finds and safely deletes the entire venv_cache directory."""
    log_callback("--- Starting venv cache cleanup ---")
    if os.path.exists(VENV_CACHE_PATH):
        try:
            log_callback(f"  Deleting cache directory: {VENV_CACHE_PATH}")
            shutil.rmtree(VENV_CACHE_PATH)
            log_callback("  --> Cache cleared successfully.")
        except Exception as e:
            log_callback(f"  --> ERROR: Failed to delete cache. Reason: {e}")
    else:
        log_callback("  Cache directory not found. Nothing to do.")
    log_callback("--- Cache cleanup finished ---")


def final_cleanup():
    print("[Cleanup Manager] Running final cleanup on application exit...")
    if not _active_temp_dirs:
        print("[Cleanup Manager] No leftover directories to clean.")
        return

    for path in list(_active_temp_dirs):
        print(f"[Cleanup Manager] Removing leftover directory: {path}")
        try:
            shutil.rmtree(path)
            unregister_temp_dir(path)
        except Exception as e:
            print(f"[Cleanup Manager] ERROR: Failed to remove {path}: {e}")


# call final_cleanup on exit,
atexit.register(final_cleanup)
