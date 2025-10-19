import shutil
import atexit
from pathlib import Path

from core.logger import log


VENV_CACHE_PATH = Path(__file__).parent.parent.parent / "venv_cache"

# no duplicates
_active_temp_dirs: set[Path] = set()


def register_temp_dir(path: str | Path):
    log(f"[Cleanup Manager] Registered: {path}")
    _active_temp_dirs.add(Path(path))


def unregister_temp_dir(path: str | Path):
    log(f"[Cleanup Manager] Unregistered: {path}")
    _active_temp_dirs.discard(Path(path))


def clear_venv_cache():
    """Finds and safely deletes the entire venv_cache directory."""
    log("--- Starting venv cache cleanup ---")
    if VENV_CACHE_PATH.exists():
        try:
            log(f"  Deleting cache directory: {VENV_CACHE_PATH}")
            shutil.rmtree(VENV_CACHE_PATH)
            log("  --> Cache cleared successfully.")
        except Exception as e:
            log(f"  --> ERROR: Failed to delete cache. Reason: {e}")
    else:
        log("  Cache directory not found. Nothing to do.")
    log("--- Cache cleanup finished ---")


def final_cleanup():
    log("[Cleanup Manager] Running final cleanup on application exit...")
    if not _active_temp_dirs:
        log("[Cleanup Manager] No leftover directories to clean.")
        return

    for path in list(_active_temp_dirs):
        log(f"[Cleanup Manager] Removing leftover directory: {path}")
        try:
            shutil.rmtree(path)
            unregister_temp_dir(path)
        except Exception as e:
            log(f"[Cleanup Manager] ERROR: Failed to remove {path}: {e}")


# call final_cleanup on exit
atexit.register(final_cleanup)
