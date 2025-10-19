import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog, ttk
import json
import threading
from pathlib import Path
from core import logger
from core.pipeline import AnalysisPipeline
from core.logger import log
from core.corpus_builder import CorpusBuilder


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
    """Main GUI application."""

    def __init__(self, master=None):

        super().__init__(master)
        logger.set_callback(self._log_message)
        self.project_root = Path(__file__).parent.parent.resolve()
        self.config_path = self.project_root / "config.json"
        self.corpus_path = self.project_root / "corpus.json"

        # analysis options
        self.dry_run_enabled = tk.BooleanVar(value=False)
        self.debug_mode_enabled = tk.BooleanVar(value=False)

        self.llm_provider = tk.StringVar(value="manual")
        self.llm_model = tk.StringVar(value="gemini-2.5-flash")

        self.resume_event = threading.Event()
        self.resume_event.set()
        self.stop_event = threading.Event()

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
    def _on_llm_provider_changed(self, _event=None):
        """Enable/disable model dropdown list."""
        self._update_model_dropdown_state()

    def _update_model_dropdown_state(self):

        if self.llm_provider.get() == "manual":
            self.model_dropdown.config(state="disabled")
        else:
            self.model_dropdown.config(state="readonly")

    def _create_widgets(self):
        """Build all GUI components."""
        self._build_repository_section()
        self._setup_controls()
        self._add_corpus_viewer()
        self._create_log_viewer()
        self._add_status_bar()

    def _build_repository_section(self):
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

    def _setup_controls(self):
        controls = tk.LabelFrame(self, text="Controls")
        controls.pack(fill="x", expand=False, pady=10)

        self._add_pause_stop(controls)
        self._create_analysis_options(controls)
        self._add_llm_dropdown(controls)
        self._create_action_buttons(controls)

    def _add_pause_stop(self, parent):
        """Pause/resume/stop pipeline controls."""
        controls = tk.Frame(parent)
        controls.pack(fill="x", padx=5, pady=5)

        self.pause_button = tk.Button(
            controls,
            text="Pause",
            command=self._pause_pipeline,
            state=tk.DISABLED,
        )
        self.pause_button.pack(side="left", expand=True, fill="x", padx=2)

        self.resume_button = tk.Button(
            controls,
            text="Resume",
            command=self._resume_pipeline,
            state=tk.DISABLED,
        )
        self.resume_button.pack(side="left", expand=True, fill="x", padx=2)

        self.stop_button = tk.Button(
            controls,
            text="Stop",
            command=self._stop_pipeline,
            state=tk.DISABLED,
            fg="red",
        )
        self.stop_button.pack(side="left", expand=True, fill="x", padx=2)

    def _create_analysis_options(self, parent):
        """Checkboxes for dry run and debug mode."""
        options = tk.Frame(parent)
        options.pack(fill="x", padx=5, pady=2)

        tk.Checkbutton(
            options,
            text="Skip LLM Fix (Dry Run)",
            variable=self.dry_run_enabled,
        ).pack(side="left")

        tk.Checkbutton(
            options,
            text="Pause on Failure (Debug)",
            variable=self.debug_mode_enabled,
        ).pack(side="left", padx=10)

        tk.Button(options, text="Clear Log", command=self._clear_log).pack(side="right")

    def _add_llm_dropdown(self, parent):
        """Dropdown for models and manual mode."""
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

    def _create_action_buttons(self, parent):
        self.action_buttons = tk.Frame(parent)
        self.action_buttons.pack(fill="x", expand=True)

        tk.Button(
            self.action_buttons,
            text="1. Build Bug Corpus",
            command=self._build_bug_corpus,
        ).pack(fill="x")

        tk.Button(
            self.action_buttons,
            text="2. Run Analysis Pipeline",
            command=self._run_all_bugs,
        ).pack(fill="x")

    def _add_corpus_viewer(self):
        """Create commit viewer and single commit runner."""
        corpus_frame = tk.LabelFrame(self, text="Bug Corpus")
        corpus_frame.pack(fill="both", expand=True, pady=5)

        self.corpus_listbox = tk.Listbox(corpus_frame, height=8)
        self.corpus_listbox.pack(side="left", fill="both", expand=True)

        controls = tk.Frame(corpus_frame)
        tk.Button(
            controls,
            text="Run Selected",
            command=self._run_selected_bug,
        ).pack(fill="x", pady=2)
        controls.pack(side="right", fill="y", padx=5)

    def _create_log_viewer(self):
        """Create scrollable log viewer."""
        log_frame = tk.LabelFrame(self, text="Logs")
        log_frame.pack(fill="both", expand=True, pady=5)

        self.log_viewer = scrolledtext.ScrolledText(
            log_frame, state="disabled", height=15
        )
        self.log_viewer.pack(fill="both", expand=True)

    def _add_status_bar(self):
        status_bar = tk.Label(
            self, textvariable=self.status_message, bd=1, relief=tk.SUNKEN, anchor=tk.W
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _configure_log_colors(self):
        """Configure the color of specific logged messages."""
        self.log_viewer.tag_config("SUCCESS", foreground="#2E8B57")
        self.log_viewer.tag_config("ERROR", foreground="#B22222")
        self.log_viewer.tag_config("WARNING", foreground="#DAA520")
        self.log_viewer.tag_config("HEADING", foreground="#4682B4")
        self.log_viewer.tag_config("INFO", foreground="black")
        self.log_viewer.tag_config("DEBUG", foreground="gray50")

    def _pause_pipeline(self):
        if self.resume_event.is_set():
            self.resume_event.clear()
            self._set_status("Paused...")
            self.pause_button.config(state=tk.DISABLED)
            self.resume_button.config(state=tk.NORMAL)
            log(">>> Pipeline paused by user. Click 'Resume' to continue.")

    def _resume_pipeline(self):
        if not self.resume_event.is_set():
            self.resume_event.set()
            self._set_status("Busy: Resuming analysis...")
            self.pause_button.config(state=tk.NORMAL)
            self.resume_button.config(state=tk.DISABLED)
            log(">>> Pipeline resumed by user.")

    def _stop_pipeline(self):
        """End early after current task."""
        self._set_status("Stopping...")
        # this way the thread isn't stuck paused when trying to stop
        self.resume_event.set()
        self.stop_event.set()
        self._toggle_controls(False)
        log(">>> Pipeline stopped by user. It will end early after current task.")

    def _toggle_controls(self, is_running):
        button_state = tk.DISABLED if is_running else tk.NORMAL

        # disable while task is running
        for child in self.action_buttons.winfo_children():
            if isinstance(child, (tk.Button, tk.Checkbutton, tk.Radiobutton)):
                child.config(state=button_state)

        self.pause_button.config(state=tk.NORMAL if is_running else tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL if is_running else tk.DISABLED)
        # resume disabled when a task is not paused
        self.resume_button.config(state=tk.DISABLED)

    def _clear_log(self):
        """Clear all text from log viewer."""

        self.log_viewer.config(state="normal")
        self.log_viewer.delete("1.0", tk.END)
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
            config = json.loads(self.config_path.read_text())
            self.repository_listbox.delete(0, tk.END)

            for repo in config.get("repositories", []):
                self.repository_listbox.insert(tk.END, repo)

            self.llm_provider.set(config.get("llm_provider", "manual"))
            self.llm_model.set(config.get("llm_model", "gemini-2.5-flash"))

        except FileNotFoundError:
            log(f"config.json not found at {self.config_path}")
        except json.JSONDecodeError:
            log("ERROR: Could not parse config.json.")

    def _save_configuration(self):
        repos = list(self.repository_listbox.get(0, tk.END))
        config_data = {}

        # read the existing config first to avoid overwriting other settings
        try:
            config_data = json.loads(self.config_path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            pass

        config_data["repositories"] = repos
        config_data["llm_provider"] = self.llm_provider.get()
        config_data["llm_model"] = self.llm_model.get()

        self.config_path.write_text(json.dumps(config_data, indent=2))

    def _set_status(self, message):
        """Update status bar text."""
        # after() is needed, so the GUI update happens on the main thread
        self.master.after(0, lambda: self.status_message.set(message))

    def _log_message(self, message):
        """Log message with color coding to GUI and console."""
        log_tag, console_color = self._color_log_message(message)

        # TODO: delete later
        print(f"{console_color}{message}{ANSIColor.RESET}")

        def update_gui_log():
            self.log_viewer.config(state="normal")
            self.log_viewer.insert(tk.END, message + "\n", log_tag)
            self.log_viewer.config(state="disabled")
            self.log_viewer.see(tk.END)

        self.master.after(0, update_gui_log)

    def _color_log_message(self, message) -> tuple[str, str]:
        """Choose tag (and color) based on message keywords."""
        stripped = message.lstrip()

        if any(
            keyword in stripped for keyword in ["ERROR", "CRITICAL FAILURE", "FAILED"]
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
            builder = CorpusBuilder()
            builder.build()

            self._load_bug_corpus()
            self._set_status("Idle")

        threading.Thread(target=build_task, daemon=True).start()

    def _validate_corpus_ready(self) -> bool:
        """Check if corpus.json exists and is valid."""
        if not self.bug_corpus:
            self._show_corpus_error("not_loaded")
            return False

        return True

    def _show_corpus_error(self, error_type: str):
        error_configs = {
            "empty": {
                "title": "Empty Corpus",
                "message": "corpus.json is empty.",
                "log": "ERROR: corpus.json is empty.",
            },
            "not_found": {
                "title": "Corpus File Missing",
                "message": "corpus.json not found.",
                "log": "ERROR: corpus.json not found.",
            },
            "corrupted": {
                "title": "Invalid Corpus File",
                "message": "corpus.json is corrupted.",
                "log": "ERROR: corpus.json is corrupted.",
            },
            "not_loaded": {
                "title": "Corpus Not Loaded",
                "message": "The bug corpus is not loaded.",
                "log": "ERROR: Corpus not loaded in memory.",
            },
        }

        config = error_configs[error_type]
        log(config["log"])

        full_message = f"{config['message']}\n\nWould you like to build the corpus now?"

        if messagebox.askyesno(config["title"], full_message):
            self._build_bug_corpus()

    def _load_bug_corpus(self):
        """Load data from corpus.json and fill viewer."""
        self.corpus_listbox.delete(0, tk.END)
        self.bug_corpus = []

        try:
            self.bug_corpus = json.loads(self.corpus_path.read_text())

            if not self.bug_corpus:
                self._show_corpus_error("empty")
                return False

            for index, bug_data in enumerate(self.bug_corpus):
                display_text = f"{index+1:03d}: {bug_data['repo_name']} - {bug_data['commit_message']}"
                self.corpus_listbox.insert(tk.END, display_text)

            log(f"Successfully loaded {len(self.bug_corpus)} bugs into the viewer.")
            return True

        except FileNotFoundError:
            self._show_corpus_error("not_found")
            return False
        except json.JSONDecodeError:
            self._show_corpus_error("corrupted")
            return False

    def _run_selected_bug(self):
        """Run analysis for a selected bug."""
        selection = self.corpus_listbox.curselection()

        if not selection:
            messagebox.showwarning("No Selection", "Select a bug from the list first.")
            return

        if not self._validate_corpus_ready():
            return

        selected_bug = self.bug_corpus[selection[0]]
        self._run_pipeline(single_bug=selected_bug)

    def _run_all_bugs(self):
        """Run analysis for the entire bug corpus."""
        if not self._validate_corpus_ready():
            return

        self._run_pipeline(single_bug=None)

    def _run_pipeline(self, single_bug: dict | None = None):
        """Run the analysis pipeline in a background thread."""
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
            self._toggle_controls(is_running=True)
            try:

                pipeline = AnalysisPipeline.from_config_files(
                    config_path=self.config_path,
                    skip_llm_fix=is_dry_run,
                    debug_on_failure=self.debug_mode_enabled.get(),
                    llm_provider=provider,
                    llm_model=self.llm_model.get(),
                )
                if single_bug:
                    pipeline.run_single_bug(
                        single_bug,
                        resume_event=self.resume_event,
                        stop_event=self.stop_event,
                    )
                else:
                    corpus = json.loads(self.corpus_path.read_text())
                    pipeline.run_corpus(
                        corpus,
                        resume_event=self.resume_event,
                        stop_event=self.stop_event,
                    )

            finally:
                self._toggle_controls(is_running=False)
                self._set_status("Idle")
                if not self.stop_event.is_set():
                    log(completion_message)

        threading.Thread(target=analysis_task, daemon=True).start()

    def _reset_pipeline_state(self):
        """Reset control events for a new run."""
        self.stop_event.clear()
        self.resume_event.set()
