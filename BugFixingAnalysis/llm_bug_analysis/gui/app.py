import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog, ttk
import json
import threading
from pathlib import Path

from ..core import logger
from ..core.pipeline import AnalysisPipeline
from ..core.logger import log
from ..core.corpus_builder import CorpusBuilder


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
        self.show_terminals = tk.BooleanVar(value=True)

        self.llm_provider = tk.StringVar(value="manual")
        self.llm_model = tk.StringVar(value="gemini-2.5-flash")
        self.test_context_level = tk.StringVar(value="assertions")
        self.oracle_level = tk.StringVar(value="none")

        self.threaded_mode = tk.StringVar(value="parallel")
        self.parallel_workers = tk.IntVar(value=5)

        self.max_commits_per_repo = tk.IntVar(value=3)
        self.commit_search_depth = tk.IntVar(value=300)

        self.show_logs = tk.BooleanVar(value=False)

        self.resume_event = threading.Event()
        self.resume_event.set()
        self.stop_event = threading.Event()

        self.status_message = tk.StringVar(value="Idle")

        self.spinner_active = False
        self.spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.spinner_index = 0
        self.spinner_base_message = ""

        self.pack(pady=20, padx=20, fill="both", expand=True)
        self._create_widgets()
        self._configure_log_colors()
        self._load_configuration()
        self._update_model_dropdown_state()
        self._load_bug_corpus()
        self._on_skip_llm_changed()

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

        self.main_container = tk.Frame(self)
        self.main_container.pack(fill="both", expand=True)

        self.left_panel = tk.Frame(self.main_container, width=800)
        self.left_panel.pack(side="left", fill="y", expand=False)
        self.left_panel.pack_propagate(False)

        self._build_repository_section(self.left_panel)
        self._setup_controls(self.left_panel)
        self._add_corpus_viewer(self.left_panel)

        self.right_panel = tk.Frame(self.main_container)
        self._create_log_viewer(self.right_panel)

        self._add_status_bar()

    def _build_repository_section(self, parent):
        repo_frame = tk.LabelFrame(parent, text="Target Repositories")
        repo_frame.pack(fill="x", expand=False, pady=5)

        list_frame = tk.Frame(repo_frame)
        list_frame.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(list_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        self.repository_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        self.repository_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.repository_listbox.yview)

        button_container = tk.Frame(repo_frame)
        tk.Button(button_container, text="Add", command=self._add_repository).pack(
            fill="x", padx=5, pady=1
        )
        tk.Button(
            button_container, text="Remove", command=self._remove_repository
        ).pack(fill="x", padx=5, pady=1)
        button_container.pack(side="right", fill="y")

    def _setup_controls(self, parent):
        controls = tk.LabelFrame(parent, text="Controls")
        controls.pack(fill="x", expand=False, pady=10)

        self._add_pause_stop(controls)
        self._create_analysis_options(controls)
        self._add_llm_dropdown(controls)
        self._create_action_buttons(controls)

    def _add_pause_stop(self, parent):
        """Pause/resume/stop pipeline controls."""
        controls = tk.Frame(parent)
        controls.pack(fill="x", padx=3, pady=5)

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
            command=self._on_skip_llm_changed,
        ).pack(side="left")

        tk.Checkbutton(
            options,
            text="Pause on Failure (Debug)",
            variable=self.debug_mode_enabled,
        ).pack(side="left", padx=10)

        tk.Checkbutton(
            options,
            text="Show Terminals",
            variable=self.show_terminals,
        ).pack(side="left", padx=10)

        tk.Checkbutton(
            options,
            text="Show Logs",
            variable=self.show_logs,
            command=self._toggle_log_panel,
        ).pack(side="left", padx=10)

        tk.Button(options, text="Clear Log", command=self._clear_log).pack(side="right")

    def _on_skip_llm_changed(self):
        """Enable/disable patch generation buttons with skip flag."""
        if self.dry_run_enabled.get():
            self.stage2_btn.config(state="disabled", bg="lightgray")
            self.single_patch_btn.config(state="disabled", bg="lightgray")
        else:
            self.stage2_btn.config(state="normal")
            self.single_patch_btn.config(state="normal", bg="#FFF3E0")

    def _toggle_log_panel(self):
        """Show/hide log viewer and resize window."""

        window = self.winfo_toplevel()
        if self.show_logs.get():

            self.right_panel.pack(side="right", fill="both", expand=True)

            # expand window width (double it)
            window.update_idletasks()
            current_width = window.winfo_width()
            current_height = window.winfo_height()

            if current_width < 1200:
                new_width = current_width * 2
                window.geometry(f"{new_width}x{current_height}")
        else:
            # hide logs and shrink window back
            self.right_panel.pack_forget()
            window.update_idletasks()
            current_width = window.winfo_width()
            current_height = window.winfo_height()

            if current_width > 1000:
                new_width = current_width // 2
                window.geometry(f"{new_width}x{current_height}")

    def _add_llm_dropdown(self, parent):
        """Dropdown for models and manual mode."""
        llm_container = tk.Frame(parent)
        llm_container.pack(fill="x", padx=5, pady=5)

        tk.Label(llm_container, text="LLM Provider:").pack(side="left", padx=1)

        provider_selector = ttk.Combobox(
            llm_container,
            textvariable=self.llm_provider,
            values=["manual", "gemini"],
            state="readonly",
            width=8,
        )
        provider_selector.pack(side="left", padx=1)
        provider_selector.bind("<<ComboboxSelected>>", self._on_llm_provider_changed)

        tk.Label(llm_container, text="Model:").pack(side="left", padx=1)

        self.model_dropdown = ttk.Combobox(
            llm_container,
            textvariable=self.llm_model,
            values=["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"],
            state="readonly",
            width=15,
        )
        self.model_dropdown.pack(side="left", padx=1)

        tk.Label(llm_container, text="Test Context:").pack(side="left", padx=1)

        test_context_selector = ttk.Combobox(
            llm_container,
            textvariable=self.test_context_level,
            values=["none", "names", "docstrings", "assertions"],
            state="readonly",
            width=12,
        )
        test_context_selector.pack(side="left", padx=1)

        tk.Label(llm_container, text="Oracle:").pack(side="left", padx=1)

        oracle_level_selector = ttk.Combobox(
            llm_container,
            textvariable=self.oracle_level,
            values=["none", "function"],
            state="readonly",
            width=10,
        )
        oracle_level_selector.pack(side="left", padx=1)

        # init dropdown state
        self._on_llm_provider_changed(None)

    def _create_action_buttons(self, parent):
        self.action_buttons = tk.Frame(parent)
        self.action_buttons.pack(fill="x", expand=True)

        corpus_settings = tk.Frame(self.action_buttons)
        corpus_settings.pack(fill="x", pady=2)

        corpus_settings = tk.Frame(self.action_buttons)
        corpus_settings.pack(fill="x", pady=2)

        tk.Button(
            corpus_settings,
            text="0. Build Bug Corpus",
            command=self._build_bug_corpus,
        ).pack(side="left", padx=5)

        tk.Label(corpus_settings, text="Max commits/repo:").pack(
            side="left", padx=(15, 0)
        )
        tk.Spinbox(
            corpus_settings,
            from_=1,
            to=50,
            textvariable=self.max_commits_per_repo,
            width=5,
        ).pack(side="left", padx=2)

        tk.Label(corpus_settings, text="Search depth:").pack(side="left", padx=(10, 0))
        tk.Spinbox(
            corpus_settings,
            from_=50,
            to=1000,
            increment=50,
            textvariable=self.commit_search_depth,
            width=6,
        ).pack(side="left", padx=2)

        # threaded mode selection
        threaded_mode_frame = tk.Frame(self.action_buttons)
        threaded_mode_frame.pack(fill="x", pady=2, padx=5)
        tk.Label(threaded_mode_frame, text="Threaded mode:").pack(side="left", padx=5)
        tk.Radiobutton(
            threaded_mode_frame,
            text="Sequential",
            variable=self.threaded_mode,
            value="sequential",
        ).pack(side="left", padx=5)
        tk.Radiobutton(
            threaded_mode_frame,
            text="Parallel",
            variable=self.threaded_mode,
            value="parallel",
        ).pack(side="left", padx=5)
        tk.Label(threaded_mode_frame, text="Workers:").pack(side="left", padx=(10, 0))
        tk.Spinbox(
            threaded_mode_frame,
            from_=1,
            to=10,
            textvariable=self.parallel_workers,
            width=5,
        ).pack(side="left")

        # stage buttons
        stage_buttons_frame = tk.Frame(self.action_buttons)
        stage_buttons_frame.pack(fill="x", pady=2)

        tk.Button(
            stage_buttons_frame,
            text="Stage 1: Build Contexts",
            command=self._run_stage_1,
        ).pack(side="left", fill="x", expand=True, padx=(5, 1))

        self.stage2_btn = tk.Button(
            stage_buttons_frame,
            text="Stage 2: Generate Patches",
            command=self._run_stage_2,
        )
        self.stage2_btn.pack(side="left", fill="x", expand=True, padx=1)

        tk.Button(
            stage_buttons_frame,
            text="Stage 3: Test Patches",
            command=self._run_stage_3,
        ).pack(side="left", fill="x", expand=True, padx=(1, 0))

        tk.Button(
            stage_buttons_frame,
            text="Run Full Pipeline",
            command=self._run_full_pipeline,
            bg="#4CAF50",
            fg="white",
        ).pack(fill="x", padx=(1, 5))

    def _run_stage(self, stage_num: int):
        """Run a single pipeline stage."""
        if not self._validate_corpus_ready():
            return

        stage_config = {
            1: {
                "name": "Build Contexts",
                "status": "Building contexts...",
                "prereq_file": None,
                "prereq_message": None,
                "runner": lambda p: p.run_stage_1_build_contexts(
                    self.bug_corpus,
                    self.stop_event,
                    self.resume_event,
                    self._create_progress_updater(),
                ),
            },
            2: {
                "name": "Generate Patches",
                "status": f"Generating patches ({self.threaded_mode.get()})...",
                "prereq_file": self.project_root
                / ".cache"
                / "pipeline_stages"
                / "stage1_contexts.json",
                "prereq_message": "No context found!\n\nRun Stage 1 to build contexts.",
                "runner": lambda p: p.run_stage_2_generate_patches(
                    None,  # load from cache
                    self.threaded_mode.get(),
                    self.stop_event,
                    self._create_progress_updater(),
                ),
            },
            3: {
                "name": "Test Patches",
                "status": "Testing patches...",
                "prereq_file": (
                    self.project_root
                    / ".cache"
                    / "pipeline_stages"
                    / "stage1_contexts.json"
                    if self.dry_run_enabled.get()
                    else self.project_root
                    / ".cache"
                    / "pipeline_stages"
                    / "stage2_patches.json"
                ),
                "prereq_message": (
                    "No contexts found!\n\nRun Stage 1 to build contexts."
                    if self.dry_run_enabled.get()
                    else "No patches found!\n\nRun Stage 2 to generate patches."
                ),
                "runner": lambda p: p.run_stage_3_test_patches(
                    None,  # load from cache
                    self.resume_event,
                    self.stop_event,
                    self._create_progress_updater(),
                ),
            },
        }

        config = stage_config[stage_num]

        if config["prereq_file"] and not config["prereq_file"].exists():
            messagebox.showerror("Error", config["prereq_message"])
            return

        self._reset_pipeline_state()
        self._save_configuration()

        def stage_task():
            self._toggle_controls(is_running=True)
            self._start_spinner(config["status"])

            try:
                pipeline = self._create_pipeline()
                config["runner"](pipeline)
                if self.stop_event.is_set():
                    final_status = f"Stage {stage_num} stopped by user"
                    log(f">>> Stage {stage_num} stopped by user")
                else:
                    final_status = f"Stage {stage_num} complete!"
                    log(f">>> Stage {stage_num} complete!")
            except Exception as e:
                final_status = f"ERROR: Stage {stage_num} failed: {str(e)[:50]}"
                log(f"ERROR: Stage {stage_num} failed: {e}")
            finally:
                self._stop_spinner()
                self._toggle_controls(is_running=False)
                self._set_status(final_status)

        threading.Thread(target=stage_task, daemon=True).start()

    def _run_stage_1(self):
        """Run stage 1: Build contexts."""
        self._run_stage(1)

    def _run_stage_2(self):
        """Run stage 2: Generate patches."""
        self._run_stage(2)

    def _run_stage_3(self):
        """Run stage 3: Test patches."""
        self._run_stage(3)

    def _run_full_pipeline(self):
        """Run all 3 stages automatically."""
        if not self._validate_corpus_ready():
            return

        self._reset_pipeline_state()
        self._save_configuration()
        mode = self.threaded_mode.get()

        def pipeline_task():
            final_status = "Pipeline failed"
            self._toggle_controls(is_running=True)
            self._start_spinner(f"Running full pipeline ({mode})...")
            try:
                pipeline = self._create_pipeline()

                if pipeline.terminal_manager:
                    with pipeline.terminal_manager:
                        pipeline.run_full_pipeline(
                            self.bug_corpus,
                            mode,
                            self.resume_event,
                            self.stop_event,
                            self._create_progress_updater(),
                        )
                else:
                    pipeline.run_full_pipeline(
                        self.bug_corpus,
                        mode,
                        self.resume_event,
                        self.stop_event,
                        self._create_progress_updater(),
                    )

                if self.stop_event.is_set():
                    final_status = "Full pipeline stopped by user"
                    log(">>> Full pipeline stopped by user")
                else:
                    final_status = "Full pipeline complete!"
                    log(">>> Full pipeline complete!")

            except Exception as e:
                final_status = f"ERROR: Pipeline failed: {str(e)[:50]}"
                log(f"ERROR: Pipeline failed: {e}")
            finally:
                self._stop_spinner()
                self._toggle_controls(is_running=False)
                self._set_status(final_status)

        threading.Thread(target=pipeline_task, daemon=True).start()

    def _create_pipeline(self):
        """Create pipeline with current settings."""
        config = json.loads(self.config_path.read_text())
        config["max_parallel_llm"] = self.parallel_workers.get()

        return AnalysisPipeline(
            config=config,
            project_root=self.project_root,
            skip_llm_fix=self.dry_run_enabled.get(),
            debug_on_failure=self.debug_mode_enabled.get(),
            llm_provider=self.llm_provider.get(),
            llm_model=self.llm_model.get(),
            show_terminals=self.show_terminals.get(),
        )

    def _create_progress_updater(self):
        """Create progress callback that updates spinner message."""

        def update_progress(current: int, total: int, message: str):
            if total > 0:
                percentage = int((current / total) * 100)
                enhanced_message = f"{message} [{current}/{total} - {percentage}%]"
            else:
                enhanced_message = message
            self._update_spinner_message(enhanced_message)

        return update_progress

    def _add_corpus_viewer(self, parent):
        """Create commit viewer and single commit runner."""
        corpus_frame = tk.LabelFrame(parent, text="Bug Corpus")
        corpus_frame.pack(fill="both", expand=True, pady=5)

        list_frame = tk.Frame(corpus_frame)
        list_frame.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(list_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        self.corpus_listbox = tk.Listbox(
            list_frame, height=8, yscrollcommand=scrollbar.set
        )
        self.corpus_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.corpus_listbox.yview)

        controls = tk.Frame(corpus_frame)
        tk.Button(
            controls,
            text="Run Selected",
            command=lambda: self._run_single_stage("full"),
            bg="#4CAF50",
            fg="white",
        ).pack(fill="x", pady=2)
        controls.pack(side="right", fill="y", padx=5)

        tk.Label(controls, text="─" * 20).pack(fill="x", pady=5)
        tk.Label(controls, text="Test Stages:", font=("TkDefaultFont", 9, "bold")).pack(
            fill="x"
        )

        tk.Button(
            controls,
            text="1. Context",
            command=lambda: self._run_single_stage(1),
            bg="#E3F2FD",
        ).pack(fill="x", pady=1)

        self.single_patch_btn = tk.Button(
            controls,
            text="2. Patch",
            command=lambda: self._run_single_stage(2),
            bg="#FFF3E0",
        )
        self.single_patch_btn.pack(fill="x", pady=1)

        tk.Button(
            controls,
            text="3. Test",
            command=lambda: self._run_single_stage(3),
            bg="#F3E5F5",
        ).pack(fill="x", pady=1)

        controls.pack(side="right", fill="y", padx=5)

        tk.Button(
            controls,
            text="Debug Context",
            command=self._debug_context,
            bg="#FFECB3",
        ).pack(fill="x", pady=1)

        tk.Button(
            controls,
            text="Clear Cache",
            command=self._clear_context_cache,
            bg="#FFCDD2",
        ).pack(fill="x", pady=1)

    def _clear_context_cache(self):
        """Clear all cached contexts."""
        import shutil

        cache_root = self.project_root / ".cache"

        cleared = []

        # clear contexts
        context_cache = cache_root / "contexts"
        if context_cache.exists():
            shutil.rmtree(context_cache)
            context_cache.mkdir(parents=True)
            cleared.append("contexts")

        # clear llm responses
        llm_cache = cache_root / "llm_responses"
        if llm_cache.exists():
            shutil.rmtree(llm_cache)
            llm_cache.mkdir(parents=True)
            cleared.append("llm_responses")

        # clear pipeline stages
        stages_cache = cache_root / "pipeline_stages"
        if stages_cache.exists():
            shutil.rmtree(stages_cache)
            stages_cache.mkdir(parents=True)
            cleared.append("pipeline_stages")

        if cleared:
            msg = f"Cleared: {', '.join(cleared)}"
            log(msg)
            messagebox.showinfo("Success", msg)
        else:
            messagebox.showinfo("Info", "No cache to clear")

    def _debug_context(self):
        """Debug of context building for selected bug."""
        selection = self.corpus_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Select a bug first.")
            return

        bug = self.bug_corpus[selection[0]]
        repo_name = bug.get("repo_name", "unknown")
        bug_sha = bug.get("bug_commit_sha", "unknown")[:7]

        log(f"\n{'='*60}")
        log(f"DEBUG: Context Building")
        log(f"Bug: {repo_name}:{bug_sha}")
        log(f"{'='*60}\n")

        log(f"Bug details:")
        log(f"  Repo: {repo_name}")
        log(f"  SHA: {bug.get('bug_commit_sha')}")
        log(f"  Parent: {bug.get('parent_commit_sha')}")
        log(f"  Source files: {bug.get('changed_source_files', [])}")
        log(f"  Test files: {bug.get('changed_test_files', [])}")
        log(f"  Issue title: {bug.get('issue_title', 'N/A')[:100]}")
        log(f"  Issue body length: {len(bug.get('issue_body', ''))} chars")

        # try to build context with detailed logging
        from ..core.project_handler import ProjectHandler
        from ..core.context_builder import ContextBuilder

        handler = ProjectHandler(repo_name)  # no terminal
        handler.setup()

        parent_sha = bug.get("parent_commit_sha")
        log(f"\nChecking out parent commit: {parent_sha}")
        handler.checkout(parent_sha)

        log(f"\nRepo path: {handler.repo_path}")
        log(f"Repo exists: {handler.repo_path.exists()}")

        log(f"\nChecking changed files:")
        source_files = bug.get("changed_source_files", [])
        test_files = bug.get("changed_test_files", [])
        for file_path in source_files + test_files:
            full_path = handler.repo_path / file_path
            log(f"  {file_path}:")
            log(f"    Full path: {full_path}")
            log(f"    Exists: {full_path.exists()}")
            if full_path.exists():
                try:
                    content = full_path.read_text()
                    log(f"    Size: {len(content)} bytes")
                    log(f"    Lines: {len(content.splitlines())}")
                    lines = content.splitlines()[:5]
                    log(f"    First lines:")
                    for line in lines:
                        log(f"      {line[:80]}")
                except Exception as e:
                    log(f"    ERROR reading: {e}")

        log(f"\nBuilding context...")
        builder = ContextBuilder(
            repo_path=handler.repo_path,
            max_snippets=5,
            debug=True,
            cache_dir=self.project_root / ".cache" / "contexts",
        )

        context, formatted = builder.build_and_format(bug)

        log(f"\n{'='*60}")
        log(f"Context Results:")
        log(f"  Classes: {len(context['aag']['classes'])}")
        log(f"  Functions: {len(context['aag']['functions'])}")
        log(f"  Snippets: {len(context['rag']['snippets'])}")
        log(f"  Formatted length: {len(formatted)} chars")
        log(f"{'='*60}\n")

        if len(formatted) < 500:
            log("Full formatted context:")
            log(formatted)
        else:
            log("Formatted context preview:")
            log(formatted[:500] + "...")

        handler.cleanup()

        log(f"\n{'='*60}")
        log("Debug complete")
        log(f"{'='*60}\n")

    def _run_single_stage(self, stage):
        """Test a single stage on selected bug."""
        selection = self.corpus_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Select a bug from the list first.")
            return

        if not self._validate_corpus_ready():
            return

        bug = self.bug_corpus[selection[0]]
        repo_name = bug.get("repo_name", "unknown")
        bug_sha = bug.get("bug_commit_sha", "unknown")[:7]

        stage_names = {
            1: "Build Context",
            2: "Generate Patch",
            3: "Test Patch",
            "full": "Full Pipeline (3 stages)",
        }

        self._set_status(f"Testing: {stage_names[stage]} - {repo_name}:{bug_sha}")

        def test_task():
            final_status = "Task failed"
            self._toggle_controls(is_running=True)
            self._start_spinner(f"{stage_names[stage]}: {repo_name}:{bug_sha}")

            try:
                pipeline = self._create_pipeline()

                log(f"\n{'='*60}")
                log(f"TESTING: {stage_names[stage]}")
                log(f"Bug: {repo_name}:{bug_sha}")
                log(f"{'='*60}\n")

                if stage == 1:
                    self._update_spinner_message(
                        f"Building context for {repo_name}:{bug_sha}"
                    )
                    pipeline.run_stage_1_build_contexts(
                        [bug],  # single bug
                        self.stop_event,
                        self.resume_event,
                        self._create_progress_updater(),
                    )

                elif stage == 2:
                    self._update_spinner_message(
                        f"Generating patch for {repo_name}:{bug_sha}"
                    )
                    pipeline.run_stage_2_generate_patches(
                        None,  # load contexts from cache
                        self.threaded_mode.get(),
                        self.stop_event,
                        self._create_progress_updater(),
                    )

                elif stage == 3:
                    self._update_spinner_message(
                        f"Testing patch for {repo_name}:{bug_sha}"
                    )
                    pipeline.run_stage_3_test_patches(
                        None,  # load patches from cache
                        self.resume_event,
                        self.stop_event,
                        self._create_progress_updater(),
                    )

                elif stage == "full":
                    pipeline.run_full_pipeline(
                        [bug],  # single bug as list
                        self.threaded_mode.get(),
                        self.resume_event,
                        self.stop_event,
                    )

                if self.stop_event.is_set():
                    final_status = (
                        f"{stage_names[stage]} stopped: {repo_name}:{bug_sha}"
                    )
                    log(f"\nSTOPPED: {stage_names[stage]}")
                else:
                    final_status = (
                        f"{stage_names[stage]} complete: {repo_name}:{bug_sha}"
                    )
                    log(f"\nSUCCESS: {stage_names[stage]} complete!")

            except Exception as e:
                final_status = (
                    f"ERROR: {stage_names[stage]} failed: {repo_name}:{bug_sha}"
                )
                log(f"\nERROR: {e}")
                import traceback

                log(traceback.format_exc())

            finally:
                self._stop_spinner()
                self._toggle_controls(is_running=False)
                self._set_status(final_status)

        threading.Thread(target=test_task, daemon=True).start()

    def _create_log_viewer(self, parent):
        """Create scrollable log viewer."""
        log_frame = tk.LabelFrame(parent, text="Logs")
        log_frame.pack(fill="both", expand=True, pady=5)

        self.log_viewer = scrolledtext.ScrolledText(
            log_frame, state="disabled", height=15, width=60
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
            self.test_context_level.set(config.get("test_context_level", "assertions"))
            self.oracle_level.set(config.get("oracle_level", "none"))
            self.parallel_workers.set(config.get("max_parallel_llm", 5))
            self.max_commits_per_repo.set(config.get("max_commits_per_repo", 3))
            self.commit_search_depth.set(config.get("commit_search_depth", 300))

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
        config_data["test_context_level"] = self.test_context_level.get()
        config_data["oracle_level"] = self.oracle_level.get()
        config_data["max_parallel_llm"] = self.parallel_workers.get()
        config_data["max_commits_per_repo"] = self.max_commits_per_repo.get()
        config_data["commit_search_depth"] = self.commit_search_depth.get()

        self.config_path.write_text(json.dumps(config_data, indent=2))

    def _set_status(self, message):
        """Update status bar text and force GUI refresh."""

        def update():
            self.status_message.set(message)
            self.master.update_idletasks()

        # after() is needed, so the GUI update happens on the main thread
        self.master.after(0, update)

    def _start_spinner(self, base_message: str):
        """Start animated spinner in status bar."""

        def start_on_main_thread():
            self.spinner_active = True
            self.spinner_base_message = base_message
            self.spinner_index = 0
            self._update_spinner()

        self.master.after(0, start_on_main_thread)

    def _update_spinner(self):
        """Update spinner animation frame."""
        if not self.spinner_active:
            return

        char = self.spinner_chars[self.spinner_index]
        self.status_message.set(f"{char} {self.spinner_base_message}")

        # next frame
        self.spinner_index = (self.spinner_index + 1) % len(self.spinner_chars)

        # 100ms = 10 FPS
        self.master.after(100, self._update_spinner)

    def _stop_spinner(self):
        """Stop spinner animation."""

        def stop_on_main_thread():
            self.spinner_active = False

        self.master.after(0, stop_on_main_thread)

    def _update_spinner_message(self, message: str):
        """Update spinner message without restarting animation."""

        def update_on_main_thread():
            if self.spinner_active:
                self.spinner_base_message = message

        self.master.after(0, update_on_main_thread)

    def _log_message(self, message):
        """Log message with color coding to GUI and console."""
        log_tag, console_color = self._color_log_message(message)

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
            keyword in stripped  # TODO: only look for .lower versions?
            for keyword in [
                "Tests PASSED",
                "Success",
                "SUCCESS",
                "Found FUNCTIONAL fix",
            ]
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
        self._save_configuration()
        self._reset_pipeline_state()

        def build_task():
            self._toggle_controls(is_running=True)
            self.pause_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.NORMAL)
            self._start_spinner("Building bug corpus...")

            try:
                builder = CorpusBuilder()
                builder.build(
                    self._create_progress_updater(), self.stop_event, self.resume_event
                )

                self._load_bug_corpus()

                if self.stop_event.is_set():
                    final_status = "Corpus building stopped by user"
                    log(">>> Corpus building stopped by user")
                else:
                    final_status = "Bug corpus built successfully!"
                    log(">>> Bug corpus building complete!")

            except Exception as e:
                final_status = f"ERROR: Corpus building failed: {str(e)[:50]}"
                log(f"ERROR: Corpus building failed: {e}")

            finally:
                self._stop_spinner()
                self._toggle_controls(is_running=False)
                self._set_status(final_status)

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

    def _reset_pipeline_state(self):
        """Reset control events for a new run."""
        self.stop_event.clear()
        self.resume_event.set()
