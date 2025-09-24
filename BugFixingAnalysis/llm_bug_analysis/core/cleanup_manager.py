import shutil
import atexit

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
