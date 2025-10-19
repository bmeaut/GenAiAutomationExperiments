from typing import Callable

_log_callback: Callable[[str], None] | None = None


def set_callback(callback: Callable[[str], None]):
    """Set where log messages should go (GUI vs console)."""
    # TODO: do I need to log to file also?
    global _log_callback
    _log_callback = callback


def log(message: str):
    if _log_callback:
        _log_callback(message)
    else:
        print(message)


def reset():
    # TODO: for testing?
    global _log_callback
    _log_callback = None
