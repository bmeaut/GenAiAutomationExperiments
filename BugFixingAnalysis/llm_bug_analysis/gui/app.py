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
        # status bar
        self.status_var = tk.StringVar(value="Idle")

        self.corpus_data = []

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

        tk.Button(options_frame, text="Clear Log", command=self.clear_log).pack(
            side="right"
        )

        # frame to hold main buttons
        actions_frame = tk.Frame(control_frame)
        actions_frame.pack(fill="x", expand=True)

        tk.Button(
            actions_frame, text="1. Build Bug Corpus", command=self.run_corpus_builder
        ).pack(fill="x")
        tk.Button(
            actions_frame, text="2. Run Analysis Pipeline", command=self.run_pipeline
        ).pack(fill="x")

        # corpus viewer and single run
        corpus_frame = tk.LabelFrame(self, text="Bug Corpus")
        corpus_frame.pack(fill="both", expand=True, pady=5)

        self.corpus_listbox = tk.Listbox(corpus_frame, height=8)
        self.corpus_listbox.pack(side="left", fill="both", expand=True)

        corpus_controls_frame = tk.Frame(corpus_frame)
        tk.Button(
            corpus_controls_frame, text="Run Selected", command=self.run_selected_commit
        ).pack(fill="x", pady=2)
        corpus_controls_frame.pack(side="right", fill="y", padx=5)

        # log viewer section
        log_frame = tk.LabelFrame(self, text="Logs")
        log_frame.pack(fill="both", expand=True, pady=5)
        self.log_text = scrolledtext.ScrolledText(
            log_frame, state="disabled", height=15
        )
        self.log_text.pack(fill="both", expand=True)

        status_bar = tk.Label(
            self, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def clear_log(self):
        """Clears all text from the log viewer widget."""
        # widget must be made 'normal' to modify it, then 'disabled' again.
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)  # '1.0' means line 1, character 0
        self.log_text.config(state="disabled")

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

    def set_status(self, message: str):
        """Updates the status bar's text."""
        # after: ensures the GUI update happens on the main thread
        self.master.after(0, lambda: self.status_var.set(message))

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
        elif (
            "Tests PASSED" in stripped_message
            or "--> Success" in stripped_message
            or "Found FUNCTIONAL fix" in stripped_message
        ):
            tag = "SUCCESS"
            console_color = ANSI.GREEN
        elif "Warning:" in stripped_message:
            tag = "WARNING"
            console_color = ANSI.YELLOW
        elif (
            stripped_message.startswith("---")
            or "Processing repository:" in stripped_message
        ):
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
        self.set_status("Busy: Building bug corpus...")

        def _build_and_update_status():
            corpus_builder.build(self.log)
            # This will run after the build is complete.
            self.load_corpus_to_gui()
            self.set_status("Idle")

        threading.Thread(target=_build_and_update_status, daemon=True).start()

    def load_corpus_to_gui(self):
        """Loads corpus.json data and populates the listbox."""
        self.corpus_listbox.delete(0, tk.END)
        self.corpus_data = []
        try:
            with open("corpus.json", "r") as f:
                self.corpus_data = json.load(f)

            for i, bug in enumerate(self.corpus_data):
                display_text = (
                    f"{i+1:03d}: {bug['repo_name']} - {bug['commit_message']}"
                )
                self.corpus_listbox.insert(tk.END, display_text)
            self.log(
                f"Successfully loaded {len(self.corpus_data)} bugs into the corpus viewer."
            )
        except (FileNotFoundError, json.JSONDecodeError):
            self.log("Could not load corpus.json. Please build the corpus.")

    def run_selected_commit(self):
        """Runs the analysis pipeline for only the selected commit."""
        selected_indices = self.corpus_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning(
                "No Selection", "Please select a commit from the corpus list to run."
            )
            return

        selected_index = selected_indices[0]
        selected_bug_data = self.corpus_data[selected_index]

        skip_llm_fix = self.skip_llm_var.get()
        if skip_llm_fix:
            self.set_status(f"Busy: Running single commit (Dry Run)...")
        else:
            self.set_status(f"Busy: Running single commit (Full Run)...")

        def _run_and_update_status():

            pipeline.run(self.log, skip_llm_fix, single_bug_data=selected_bug_data)
            self.set_status("Idle")

        threading.Thread(target=_run_and_update_status, daemon=True).start()

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

        if self.skip_llm_var.get():
            self.set_status("Busy: Running analysis pipeline (Dry Run)...")
        else:
            self.set_status("Busy: Running analysis pipeline (Full Run)...")

        def _run_and_update_status():
            skip_llm_fix = self.skip_llm_var.get()
            pipeline.run(self.log, skip_llm_fix)
            # will run after pipeline is complete
            self.set_status("Idle")

        threading.Thread(target=_run_and_update_status, daemon=True).start()
