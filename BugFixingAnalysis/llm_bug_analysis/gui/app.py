import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog
import json
import threading
from typing import Optional
from core import corpus_builder, pipeline


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
        self.load_config()

    def create_widgets(self):

        # Repository Management Section
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

        # Main Control Buttons Section
        control_frame = tk.LabelFrame(self, text="Controls")
        control_frame.pack(fill="x", expand=False, pady=10)

        tk.Checkbutton(
            control_frame,
            text="Skip LLM Fix (Dry Run to test dependencies)",
            variable=self.skip_llm_var,
        ).pack(fill="x")

        tk.Button(
            control_frame, text="1. Build Bug Corpus", command=self.run_corpus_builder
        ).pack(fill="x")
        tk.Button(
            control_frame, text="2. Run Analysis Pipeline", command=self.run_pipeline
        ).pack(fill="x")

        # --- Log Viewer Section ---
        log_frame = tk.LabelFrame(self, text="Logs")
        log_frame.pack(fill="both", expand=True, pady=5)
        self.log_text = scrolledtext.ScrolledText(
            log_frame, state="disabled", height=15
        )
        self.log_text.pack(fill="both", expand=True)

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
        def _update_log():
            self.log_text.config(state="normal")
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.config(state="disabled")
            self.log_text.see(tk.END)  # auto-scroll to the end

        self.winfo_toplevel().after(0, _update_log)

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
