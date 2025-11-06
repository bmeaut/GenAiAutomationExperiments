import shutil
import atexit
from pathlib import Path

from .logger import log

# no duplicates
_active_temp_dirs: set[Path] = set()


def register_temp_dir(path: str | Path):
    log(f"[Cleanup Manager] Registered: {path}")
    _active_temp_dirs.add(Path(path))


def unregister_temp_dir(path: str | Path):
    log(f"[Cleanup Manager] Unregistered: {path}")
    _active_temp_dirs.discard(Path(path))


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
