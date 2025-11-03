# main.py

import tkinter as tk
from tkinter import messagebox
from gui.app import BugAnalysisGUI
import threading


def main():
    # GUI configuration and startup
    root = tk.Tk()
    root.title("LLM Bug Analysis Framework")
    root.geometry("800x900")
    root.resizable(True, True)

    app = BugAnalysisGUI(master=root)
    app.pack(fill="both", expand=True)

    def on_closing():
        """This function is called when the user clicks the 'X' button."""
        # check for non-daemon threads
        if threading.active_count() > 1:
            if messagebox.askokcancel(
                "Quit?", "An analysis is still running. Are you sure you want to quit?"
            ):
                root.destroy()
        else:
            # no analysis, safe to close
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)

    root.mainloop()


if __name__ == "__main__":
    main()
