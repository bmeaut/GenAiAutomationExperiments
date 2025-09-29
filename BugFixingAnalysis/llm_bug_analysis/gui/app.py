import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog
import json
import threading
from typing import Optional
from core import corpus_builder, pipeline, cleanup_manager


# ANSI color codes for terminal
class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    GRAY = "\033[90m"


class Application(tk.Frame):
    """
    The main GUI for the LLM Bug Analysis Framework.
    Builds UI widgets and connects them to the backend logic.
    """

    def __init__(self, master=None):
        super().__init__(master)

        self.skip_llm_var = tk.BooleanVar(value=False)

        self.pack(pady=20, padx=20, fill="both", expand=True)
        self.create_widgets()

        # Tkinter tags for GUI log text coloring

        self.log_text.tag_config("SUCCESS", foreground="#2E8B57")
        self.log_text.tag_config("ERROR", foreground="#B22222")
        self.log_text.tag_config("WARNING", foreground="#DAA520")
        self.log_text.tag_config("HEADING", foreground="#4682B4")
        self.log_text.tag_config("INFO", foreground="black")
        self.log_text.tag_config("DEBUG", foreground="gray50")

        self.load_config()

    def create_widgets(self):

        # repository management section
        repo_frame = tk.LabelFrame(self, text="Target Repositories")
        repo_frame.pack(fill="x", expand=False, pady=5)

        self.repo_listbox = tk.Listbox(repo_frame)
        self.repo_listbox.pack(side="left", fill="both", expand=True)

        repo_btn_frame = tk.Frame(repo_frame)
        tk.Button(repo_btn_frame, text="Add", command=self.add_repo).pack(fill="x")
        tk.Button(repo_btn_frame, text="Remove", command=self.remove_repo).pack(
            fill="x"
        )
        repo_btn_frame.pack(side="right", fill="y")

        # main control buttons section
        control_frame = tk.LabelFrame(self, text="Controls")
        control_frame.pack(fill="x", expand=False, pady=10)

        # frame to hold top-row widgets
        options_frame = tk.Frame(control_frame)
        options_frame.pack(fill="x", padx=5, pady=2)

        tk.Checkbutton(
            options_frame,
            text="Skip LLM Fix (Dry Run to test dependencies)",
            variable=self.skip_llm_var,
        ).pack(side="left")

        tk.Button(
            options_frame, text="Clean Cache", command=self.clean_cache, fg="red"
        ).pack(side="right")

        # frame to hold main buttons
        actions_frame = tk.Frame(control_frame)
        actions_frame.pack(fill="x", expand=True)

        tk.Button(
            actions_frame, text="1. Build Bug Corpus", command=self.run_corpus_builder
        ).pack(fill="x")
        tk.Button(
            actions_frame, text="2. Run Analysis Pipeline", command=self.run_pipeline
        ).pack(fill="x")

        # log viewer section
        log_frame = tk.LabelFrame(self, text="Logs")
        log_frame.pack(fill="both", expand=True, pady=5)
        self.log_text = scrolledtext.ScrolledText(
            log_frame, state="disabled", height=15
        )
        self.log_text.pack(fill="both", expand=True)

    def clean_cache(self):
        """
        Asks the user for confirmation and then clears the venv_cache
        directory in a separate thread.
        """
        # ask for confirmation
        if messagebox.askyesno(
            "Confirm Cache Deletion",
            "Are you sure you want to delete the entire venv cache?\n"
            "This will force all dependencies to be re-installed on the next run.",
        ):
            # run deletion in a separate thread to not block GUI
            threading.Thread(
                target=cleanup_manager.clear_venv_cache, args=(self.log,), daemon=True
            ).start()

    def add_repo(self):
        repo_name = simpledialog.askstring(
            "Add Repository", "Enter repository URL or name (e.g., tiangolo/fastapi):"
        )

        if repo_name:
            repo_name = repo_name.strip()
            if not repo_name.startswith("https://github.com/"):
                full_url = f"https://github.com/{repo_name}"
            else:
                full_url = repo_name

            self.repo_listbox.insert(tk.END, full_url)
            self.save_config()

    def remove_repo(self):
        selected = self.repo_listbox.curselection()
        if selected:
            self.repo_listbox.delete(selected[0])
            self.save_config()

    def load_config(self):
        try:
            with open("config.json", "r") as f:
                config = json.load(f)
                self.repo_listbox.delete(0, tk.END)  # clear existing entries first
                for repo in config.get("repositories", []):
                    self.repo_listbox.insert(tk.END, repo)
        except FileNotFoundError:
            self.log("config.json not found. Using defaults.")
        except json.JSONDecodeError:
            self.log("ERROR: Could not parse config.json.")

    def save_config(self):
        repos = list(self.repo_listbox.get(0, tk.END))
        config_data = {}
        # read the existing config first to avoid overwriting other settings
        try:
            with open("config.json", "r") as f:
                config_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

        config_data["repositories"] = repos
        with open("config.json", "w") as f:
            json.dump(config_data, f, indent=2)

    def log(self, message: str):
        """
        Analyzes message to determine log level, then prints
        a colored, tagged version into the GUI log box.
        """
        tag = "INFO"
        console_color = ANSI.RESET

        stripped_message = message.lstrip()

        if (
            "FATAL ERROR" in stripped_message
            or "CRITICAL FAILURE" in stripped_message
            or "FAILED" in stripped_message
        ):
            tag = "ERROR"
            console_color = ANSI.RED
        elif "Tests PASSED" in stripped_message or "--> Success" in stripped_message:
            tag = "SUCCESS"
            console_color = ANSI.GREEN
        elif "Warning:" in stripped_message:
            tag = "WARNING"
            console_color = ANSI.YELLOW
        elif stripped_message.startswith("---"):
            tag = "HEADING"
            console_color = ANSI.BLUE
        elif "[DEBUG]" in stripped_message:
            tag = "DEBUG"
            console_color = ANSI.GRAY
        else:
            tag = "INFO"
            console_color = ANSI.RESET

        # debug for GUI issues
        print(f"{console_color}{message}{ANSI.RESET}")

        def _update_gui_log(msg, tag_to_apply):
            self.log_text.config(state="normal")
            self.log_text.insert(tk.END, msg + "\n", tag_to_apply)
            self.log_text.config(state="disabled")
            self.log_text.see(tk.END)

        self.master.after(0, lambda: _update_gui_log(message, tag))

        # def _update_log():
        #     self.log_text.config(state="normal")
        #     self.log_text.insert(tk.END, message + "\n")
        #     self.log_text.config(state="disabled")
        #     self.log_text.see(tk.END)  # auto-scroll to the end

        # self.winfo_toplevel().after(0, _update_log)

    def run_corpus_builder(self):
        self.log("Starting corpus builder...")
        threading.Thread(
            target=corpus_builder.build, args=(self.log,), daemon=True
        ).start()

    def run_pipeline(self):
        try:
            with open("corpus.json") as f:
                if not json.load(f):
                    self.log(
                        "ERROR: corpus.json is empty. Please build the corpus first."
                    )
                    messagebox.showerror(
                        "Error", "Corpus is empty. Please build the corpus first."
                    )
                    return
        except FileNotFoundError:
            self.log("ERROR: corpus.json not found. Please build the corpus first.")
            messagebox.showerror(
                "Error", "Corpus not found. Please build the corpus first."
            )
            return

        skip_llm_fix = self.skip_llm_var.get()

        if skip_llm_fix:
            self.log("Starting analysis pipeline in DRY RUN mode (skipping LLM fix)...")
        else:
            self.log("Starting analysis pipeline in FULL mode...")

        threading.Thread(
            target=pipeline.run,
            args=(self.log, skip_llm_fix),
            daemon=False,  # don't terminate with the GUI instantly
        ).start()
