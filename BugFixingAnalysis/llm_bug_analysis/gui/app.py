import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog, ttk
import json
import threading
from core import corpus_builder, pipeline


class ANSIColor:
    """ANSI terminal color codes for console output."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    GRAY = "\033[90m"


class BugAnalysisGUI(tk.Frame):
    """
    Main GUI application for the LLM Bug Analysis Framework.

    Provides interface for:
    - Managing target repositories
    - Building bug corpus from GitHub commits
    - Running AI-assisted bug fix analysis
    - Comparing AI vs human bug fixes
    """

    def __init__(self, master=None):

        super().__init__(master)

        # analysis options
        self.dry_run_enabled = tk.BooleanVar(value=False)
        self.debug_mode_enabled = tk.BooleanVar(value=False)

        self.llm_provider = tk.StringVar(value="manual")
        self.llm_model = tk.StringVar(value="gemini-2.5-flash")

        self.pipeline_resume_event = threading.Event()
        self.pipeline_resume_event.set()
        self.pipeline_stop_event = threading.Event()

        self.status_message = tk.StringVar(value="Idle")

        self.corpus_data: list[dict] = []

        self.pack(pady=20, padx=20, fill="both", expand=True)
        self._create_widgets()
        self._configure_log_colors()
        self._load_configuration()
        self._update_model_dropdown_state()
        self._load_bug_corpus()

    # pylance says event is unused, but it's needed for the bind call
    # None is needed for manual call
    def _on_llm_provider_changed(self, _event: tk.Event | None = None):
        """Enable/disable model dropdown based on provider selection."""
        self._update_model_dropdown_state()

    def _update_model_dropdown_state(self):
        """Update the model dropdown state based on current provider selection."""
        if self.llm_provider.get() == "manual":
            self.model_dropdown.config(state="disabled")
        else:
            self.model_dropdown.config(state="readonly")

    def _create_widgets(self):
        """Build all GUI components."""
        self._create_repository_section()
        self._create_control_section()
        self._create_corpus_viewer()
        self._create_log_viewer()
        self._create_status_bar()

    def _create_repository_section(self):
        """Create repository management UI section."""
        repo_frame = tk.LabelFrame(self, text="Target Repositories")
        repo_frame.pack(fill="x", expand=False, pady=5)

        self.repository_listbox = tk.Listbox(repo_frame)
        self.repository_listbox.pack(side="left", fill="both", expand=True)

        button_container = tk.Frame(repo_frame)
        tk.Button(button_container, text="Add", command=self._add_repository).pack(
            fill="x"
        )
        tk.Button(
            button_container, text="Remove", command=self._remove_repository
        ).pack(fill="x")
        button_container.pack(side="right", fill="y")

    def _create_control_section(self):
        """Create main control panel UI section."""
        control_frame = tk.LabelFrame(self, text="Controls")
        control_frame.pack(fill="x", expand=False, pady=10)

        self._create_pipeline_controls(control_frame)
        self._create_analysis_options(control_frame)
        self._create_llm_configuration(control_frame)
        self._create_action_buttons(control_frame)

    def _create_pipeline_controls(self, parent: tk.Widget):
        """Create pause/resume/stop pipeline controls."""
        control_container = tk.Frame(parent)
        control_container.pack(fill="x", padx=5, pady=5)

        self.pause_button = tk.Button(
            control_container,
            text="Pause",
            command=self._pause_analysis_pipeline,
            state=tk.DISABLED,
        )
        self.pause_button.pack(side="left", expand=True, fill="x", padx=2)

        self.resume_button = tk.Button(
            control_container,
            text="Resume",
            command=self._resume_analysis_pipeline,
            state=tk.DISABLED,
        )
        self.resume_button.pack(side="left", expand=True, fill="x", padx=2)

        self.stop_button = tk.Button(
            control_container,
            text="Stop",
            command=self._stop_analysis_pipeline,
            state=tk.DISABLED,
            fg="red",
        )
        self.stop_button.pack(side="left", expand=True, fill="x", padx=2)

    def _create_analysis_options(self, parent: tk.Widget):
        """Create analysis option checkboxes."""
        options_container = tk.Frame(parent)
        options_container.pack(fill="x", padx=5, pady=2)

        tk.Checkbutton(
            options_container,
            text="Skip LLM Fix (Dry Run)",
            variable=self.dry_run_enabled,
        ).pack(side="left")

        tk.Checkbutton(
            options_container,
            text="Pause on Failure (Debug)",
            variable=self.debug_mode_enabled,
        ).pack(side="left", padx=10)

        tk.Button(options_container, text="Clear Log", command=self._clear_log).pack(
            side="right"
        )

    def _create_llm_configuration(self, parent: tk.Widget):
        """Create LLM provider and model selection controls."""
        llm_container = tk.Frame(parent)
        llm_container.pack(fill="x", padx=5, pady=5)

        tk.Label(llm_container, text="LLM Provider:").pack(side="left", padx=5)

        provider_selector = ttk.Combobox(
            llm_container,
            textvariable=self.llm_provider,
            values=["manual", "gemini"],
            state="readonly",
            width=15,
        )
        provider_selector.pack(side="left", padx=5)
        provider_selector.bind("<<ComboboxSelected>>", self._on_llm_provider_changed)

        tk.Label(llm_container, text="Model:").pack(side="left", padx=5)

        self.model_dropdown = ttk.Combobox(
            llm_container,
            textvariable=self.llm_model,
            values=["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"],
            state="readonly",
            width=20,
        )
        self.model_dropdown.pack(side="left", padx=5)

        # init dropdown state
        self._on_llm_provider_changed(None)

    def _create_action_buttons(self, parent: tk.Widget):
        """Create main action buttons for corpus building and analysis."""
        self.action_button_container = tk.Frame(parent)
        self.action_button_container.pack(fill="x", expand=True)

        tk.Button(
            self.action_button_container,
            text="1. Build Bug Corpus",
            command=self._build_bug_corpus,
        ).pack(fill="x")

        tk.Button(
            self.action_button_container,
            text="2. Run Analysis Pipeline",
            command=self._run_full_analysis,
        ).pack(fill="x")

    def _create_corpus_viewer(self):
        """Create bug corpus viewer and single commit runner."""
        corpus_frame = tk.LabelFrame(self, text="Bug Corpus")
        corpus_frame.pack(fill="both", expand=True, pady=5)

        self.corpus_listbox = tk.Listbox(corpus_frame, height=8)
        self.corpus_listbox.pack(side="left", fill="both", expand=True)

        controls_container = tk.Frame(corpus_frame)
        tk.Button(
            controls_container,
            text="Run Selected",
            command=self._run_selected_bug_analysis,
        ).pack(fill="x", pady=2)
        controls_container.pack(side="right", fill="y", padx=5)

    def _create_log_viewer(self):
        """Create scrollable log viewer."""
        log_frame = tk.LabelFrame(self, text="Logs")
        log_frame.pack(fill="both", expand=True, pady=5)

        self.log_viewer = scrolledtext.ScrolledText(
            log_frame, state="disabled", height=15
        )
        self.log_viewer.pack(fill="both", expand=True)

    def _create_status_bar(self):
        """Create bottom status bar."""
        status_bar = tk.Label(
            self, textvariable=self.status_message, bd=1, relief=tk.SUNKEN, anchor=tk.W
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _configure_log_colors(self):
        """Configure color tags for log viewer."""
        self.log_viewer.tag_config("SUCCESS", foreground="#2E8B57")
        self.log_viewer.tag_config("ERROR", foreground="#B22222")
        self.log_viewer.tag_config("WARNING", foreground="#DAA520")
        self.log_viewer.tag_config("HEADING", foreground="#4682B4")
        self.log_viewer.tag_config("INFO", foreground="black")
        self.log_viewer.tag_config("DEBUG", foreground="gray50")

    def _pause_analysis_pipeline(self):
        """Clears the resume event, causing the pipeline to wait."""
        if self.pipeline_resume_event.is_set():
            self.pipeline_resume_event.clear()
            self._set_status("Paused...")
            self.pause_button.config(state=tk.DISABLED)
            self.resume_button.config(state=tk.NORMAL)
            self._log_message(
                ">>> Pipeline paused by user. Click 'Resume' to continue."
            )

    def _resume_analysis_pipeline(self):
        """Sets the resume event, allowing the pipeline to continue."""
        if not self.pipeline_resume_event.is_set():
            self.pipeline_resume_event.set()
            self._set_status("Busy: Resuming analysis...")
            self.pause_button.config(state=tk.NORMAL)
            self.resume_button.config(state=tk.DISABLED)
            self._log_message(">>> Pipeline resumed by user.")

    def _stop_analysis_pipeline(self):
        """Sets the stop event, signaling the pipeline to terminate gracefully."""
        self._set_status("Stopping...")
        # this way the thread isn't stuck paused when trying to stop
        self.pipeline_resume_event.set()
        self.pipeline_stop_event.set()
        self._toggle_analysis_controls(False)  # disable buttons
        self._log_message(
            ">>> Stop signal sent. The pipeline will halt after the current task."
        )

    def _toggle_analysis_controls(self, is_running: bool):
        """Helper to enable/disable all relevant buttons when a task starts/stops."""
        action_button_state = tk.DISABLED if is_running else tk.NORMAL

        # disable while task is running
        for child in self.action_button_container.winfo_children():
            if isinstance(child, (tk.Button, tk.Checkbutton, tk.Radiobutton)):
                child.config(state=action_button_state)

        self.pause_button.config(state=tk.NORMAL if is_running else tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL if is_running else tk.DISABLED)
        # resume should always be disabled when a task is not paused
        self.resume_button.config(state=tk.DISABLED)

    def _clear_log(self):
        """Clears all text from the log viewer widget."""
        # widget must be 'normal' to modify it, then 'disabled' again.
        self.log_viewer.config(state="normal")
        self.log_viewer.delete("1.0", tk.END)  # '1.0' means line 1, character 0
        self.log_viewer.config(state="disabled")

    def _add_repository(self):
        repo_name = simpledialog.askstring(
            "Add Repository", "Enter repository URL or name (e.g., Textualize/rich):"
        )

        if repo_name:
            repo_name = repo_name.strip()
            if not repo_name.startswith("https://github.com/"):
                full_url = f"https://github.com/{repo_name}"
            else:
                full_url = repo_name

            self.repository_listbox.insert(tk.END, full_url)
            self._save_configuration()

    def _remove_repository(self):
        selected = self.repository_listbox.curselection()
        if selected:
            self.repository_listbox.delete(selected[0])
            self._save_configuration()

    def _load_configuration(self):
        try:
            with open("config.json", "r") as f:
                config = json.load(f)
                self.repository_listbox.delete(
                    0, tk.END
                )  # clear existing entries first
                for repo in config.get("repositories", []):
                    self.repository_listbox.insert(tk.END, repo)

                self.llm_provider.set(config.get("llm_provider", "manual"))
                self.llm_model.set(config.get("llm_model", "gemini-2.5-flash"))

        except FileNotFoundError:
            self._log_message("config.json not found. Using defaults.")
        except json.JSONDecodeError:
            self._log_message("ERROR: Could not parse config.json.")

    def _save_configuration(self):
        repos = list(self.repository_listbox.get(0, tk.END))
        config_data = {}
        # read the existing config first to avoid overwriting other settings
        try:
            with open("config.json", "r") as f:
                config_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

        config_data["repositories"] = repos
        config_data["llm_provider"] = self.llm_provider.get()
        config_data["llm_model"] = self.llm_model.get()

        with open("config.json", "w") as f:
            json.dump(config_data, f, indent=2)

    def _set_status(self, message: str):
        """Updates the status bar's text."""
        # after: ensures the GUI update happens on the main thread
        self.master.after(0, lambda: self.status_message.set(message))

    def _log_message(self, message: str):
        """
        Log a message with automatic color coding based on content.
        Outputs to both GUI log viewer and console.
        """
        log_tag, console_color = self._classify_log_message(message)

        print(f"{console_color}{message}{ANSIColor.RESET}")

        def update_gui_log():
            self.log_viewer.config(state="normal")
            self.log_viewer.insert(tk.END, message + "\n", log_tag)
            self.log_viewer.config(state="disabled")
            self.log_viewer.see(tk.END)

        self.master.after(0, update_gui_log)

    def _classify_log_message(self, message: str) -> tuple[str, str]:
        """
        Classify log message to determine appropriate tag and color.
        """
        stripped = message.lstrip()

        if any(
            keyword in stripped
            for keyword in ["FATAL ERROR", "CRITICAL FAILURE", "FAILED"]
        ):
            return "ERROR", ANSIColor.RED

        if any(
            keyword in stripped
            for keyword in ["Tests PASSED", "--> Success", "Found FUNCTIONAL fix"]
        ):
            return "SUCCESS", ANSIColor.GREEN

        if "Warning:" in stripped:
            return "WARNING", ANSIColor.YELLOW

        if stripped.startswith("---") or "Processing repository:" in stripped:
            return "HEADING", ANSIColor.BLUE

        if "[DEBUG]" in stripped:
            return "DEBUG", ANSIColor.GRAY

        return "INFO", ANSIColor.RESET

    def _build_bug_corpus(self):
        """Build bug corpus from configured repositories."""
        self._set_status("Busy: Building bug corpus...")
        self._save_configuration()

        def build_task():
            corpus_builder.build(self._log_message)
            self._load_bug_corpus()
            self._set_status("Idle")

        threading.Thread(target=build_task, daemon=True).start()

    def _load_bug_corpus(self):
        """Load bug corpus data from corpus.json and populate viewer."""
        self.corpus_listbox.delete(0, tk.END)
        self.bug_corpus = []

        try:
            with open("corpus.json", "r") as corpus_file:
                self.bug_corpus = json.load(corpus_file)

            for index, bug_data in enumerate(self.bug_corpus):
                display_text = f"{index+1:03d}: {bug_data['repo_name']} - {bug_data['commit_message']}"
                self.corpus_listbox.insert(tk.END, display_text)

            self._log_message(
                f"Successfully loaded {len(self.bug_corpus)} bugs into the corpus viewer."
            )
        except (FileNotFoundError, json.JSONDecodeError):
            self._log_message("Could not load corpus.json. Please build the corpus.")

    def _run_selected_bug_analysis(self):
        """Run analysis pipeline for a single selected bug from corpus."""
        selection = self.corpus_listbox.curselection()

        if not selection:
            messagebox.showwarning(
                "No Selection", "Please select a commit from the corpus list to run."
            )
            return

        if not self.bug_corpus:
            messagebox.showerror(
                "Error", "Corpus data is not loaded. Please build the corpus first."
            )
            return

        selected_bug = self.bug_corpus[selection[0]]
        self._run_analysis_pipeline(single_bug=selected_bug)

    def _run_full_analysis(self):
        """Run analysis pipeline for the entire bug corpus."""
        try:
            with open("corpus.json") as corpus_file:
                if not json.load(corpus_file):
                    self._log_message(
                        "ERROR: corpus.json is empty. Please build the corpus first."
                    )
                    messagebox.showerror(
                        "Error", "Corpus is empty. Please build the corpus first."
                    )
                    return
        except (FileNotFoundError, json.JSONDecodeError):
            self._log_message(
                "ERROR: corpus.json not found or invalid. Please build the corpus first."
            )
            messagebox.showerror(
                "Error", "Corpus not found or invalid. Please build the corpus first."
            )
            return

        self._run_analysis_pipeline(single_bug=None)

    def _run_analysis_pipeline(self, single_bug: dict | None = None):
        """
        Run the analysis pipeline in a background thread.
        If single_bug is provided, only that bug is processed.
        """
        self._reset_pipeline_state()
        self._save_configuration()

        provider = self.llm_provider.get()
        is_dry_run = self.dry_run_enabled.get()

        if single_bug:
            status = (
                f"Busy: Running single commit with {provider}..."
                if not is_dry_run
                else "Busy: Running single commit (Dry Run)..."
            )
            completion_message = ">>> Single commit analysis finished."
        else:
            status = (
                f"Busy: Running pipeline with {provider}..."
                if not is_dry_run
                else "Busy: Running analysis pipeline (Dry Run)..."
            )
            completion_message = ">>> Full pipeline finished."

        self._set_status(status)

        def analysis_task():
            self._toggle_analysis_controls(is_running=True)
            try:
                pipeline.run(
                    self._log_message,
                    skip_llm_fix=is_dry_run,
                    single_bug_data=single_bug,
                    resume_event=self.pipeline_resume_event,
                    stop_event=self.pipeline_stop_event,
                    debug_on_failure=self.debug_mode_enabled.get(),
                    llm_provider=provider,
                    llm_model=self.llm_model.get(),
                )
            finally:
                self._toggle_analysis_controls(is_running=False)
                self._set_status("Idle")
                if not self.pipeline_stop_event.is_set():
                    self._log_message(completion_message)

        threading.Thread(target=analysis_task, daemon=True).start()

    def _reset_pipeline_state(self):
        """Reset pipeline control events for a new run."""
        self.pipeline_stop_event.clear()
        self.pipeline_resume_event.set()
