import tkinter as tk
from tkinter import messagebox
from pathlib import Path
import threading
import os
import sys

from .gui.app import BugAnalysisGUI


def main():
    """Launch the GUI application."""

    try:
        content = Path("/proc/version").read_text().lower()
        if "microsoft" not in content and "wsl" not in content:
            print(
                "ERROR: Tool requires WSL (Windows Subsystem for Linux)",
                file=sys.stderr,
            )
            print("\nRun from WSL2 on Windows.", file=sys.stderr)
            sys.exit(1)
    except FileNotFoundError:
        print(
            "ERROR: Tool requires WSL.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not os.environ.get("DISPLAY"):
        print("ERROR: DISPLAY environment variable not set.", file=sys.stderr)
        print("\nTo fix: check README.", file=sys.stderr)
        print(file=sys.stderr)
        print("\nMake sure you have an X server running (VcXsrv or Windows 11 WSLg).")
        sys.exit(1)

    try:
        root = tk.Tk()
        root.title("LLM Bug Analysis Framework")
        root.geometry("800x900")
        root.resizable(True, True)

        app = BugAnalysisGUI(master=root)
        app.pack(fill="both", expand=True)

        def on_closing():
            """Asks for confirmation before closing the application."""
            # check for non-daemon threads
            if threading.active_count() > 1:
                if messagebox.askokcancel(
                    "Quit?", "Background task ongoing, still want to quit?"
                ):
                    root.destroy()
            else:
                # no analysis, safe to close
                root.destroy()

        root.protocol("WM_DELETE_WINDOW", on_closing)
        root.mainloop()

    except Exception as e:
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
