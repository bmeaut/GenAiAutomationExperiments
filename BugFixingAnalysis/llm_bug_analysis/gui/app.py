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

        self.threaded_mode = tk.StringVar(value="parallel")
        self.parallel_workers = tk.IntVar(value=5)

        self.show_logs = tk.BooleanVar(value=False)

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

        self.repository_listbox = tk.Listbox(repo_frame)
        self.repository_listbox.pack(side="left", fill="both", expand=True)

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
        ).pack(side="left")

        tk.Checkbutton(
            options,
            text="Pause on Failure (Debug)",
            variable=self.debug_mode_enabled,
        ).pack(side="left", padx=10)

        tk.Checkbutton(
            options,
            text="Show Logs",
            variable=self.show_logs,
            command=self._toggle_log_panel,
        ).pack(side="left", padx=10)

        tk.Button(options, text="Clear Log", command=self._clear_log).pack(side="right")

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

        tk.Label(llm_container, text="TODO: make GUI pretty!!").pack(
            side="left", padx=5
        )

        # init dropdown state
        self._on_llm_provider_changed(None)

    def _create_action_buttons(self, parent):
        self.action_buttons = tk.Frame(parent)
        self.action_buttons.pack(fill="x", expand=True)

        tk.Button(
            self.action_buttons,
            text="0. Build Bug Corpus",
            command=self._build_bug_corpus,
        ).pack(fill="x", padx=5)

        # threaded mode selection
        threaded_mode_frame = tk.Frame(self.action_buttons)
        threaded_mode_frame.pack(fill="x", pady=2)
        tk.Label(threaded_mode_frame, text="Threaded mode:").pack(side="left")
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

        tk.Button(
            stage_buttons_frame,
            text="Stage 2: Generate Patches",
            command=self._run_stage_2,
        ).pack(side="left", fill="x", expand=True, padx=1)

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
                "status": "Busy: Stage 1 - Building contexts...",
                "prereq_file": None,
                "prereq_message": None,
                "runner": lambda p: p.run_stage_1_build_contexts(
                    self.bug_corpus,
                    self.stop_event,
                ),
            },
            2: {
                "name": "Generate Patches",
                "status": f"Busy: Stage 2 - Generating patches ({self.threaded_mode.get()})...",
                "prereq_file": self.project_root
                / ".cache"
                / "pipeline_stages"
                / "stage1_contexts.json",
                "prereq_message": "No context found!\n\nRun Stage 1 to build contexts.",
                "runner": lambda p: p.run_stage_2_generate_patches(
                    None,  # load from cache
                    self.threaded_mode.get(),
                    self.stop_event,
                ),
            },
            3: {
                "name": "Test Patches",
                "status": "Busy: Stage 3 - Testing patches...",
                "prereq_file": self.project_root
                / ".cache"
                / "pipeline_stages"
                / "stage2_patches.json",
                "prereq_message": "No patches found!\n\nRun Stage 2 to generate patches.",
                "runner": lambda p: p.run_stage_3_test_patches(
                    None,  # load from cache
                    self.resume_event,
                    self.stop_event,
                ),
            },
        }

        config = stage_config[stage_num]

        if config["prereq_file"] and not config["prereq_file"].exists():
            messagebox.showerror("Error", config["prereq_message"])
            return

        self._reset_pipeline_state()
        self._save_configuration()
        self._set_status(config["status"])

        def stage_task():
            self._toggle_controls(is_running=True)
            try:
                pipeline = self._create_pipeline()
                config["runner"](pipeline)
                if not self.stop_event.is_set():
                    log(f">>> Stage {stage_num} complete!")
            except Exception as e:
                log(f"ERROR: Stage {stage_num} failed: {e}")
            finally:
                self._toggle_controls(is_running=False)
                self._set_status("Idle")

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
        self._set_status(f"Busy: Running full 3-stage pipeline ({mode})...")

        def pipeline_task():
            self._toggle_controls(is_running=True)
            try:
                pipeline = self._create_pipeline()
                pipeline.run_full_pipeline(
                    self.bug_corpus,
                    mode,
                    self.resume_event,
                    self.stop_event,
                )
                if not self.stop_event.is_set():
                    log(">>> Full pipeline complete!")
            except Exception as e:
                log(f"ERROR: Pipeline failed: {e}")
            finally:
                self._toggle_controls(is_running=False)
                self._set_status("Idle")

        threading.Thread(target=pipeline_task, daemon=True).start()

    def _create_pipeline(self):
        """Create pipeline with current settings."""
        config = json.loads(self.config_path.read_text())
        config["max_parallel_llm"] = self.parallel_workers.get()

        return AnalysisPipeline(
            config,
            self.project_root,
            skip_llm_fix=self.dry_run_enabled.get(),
            debug_on_failure=self.debug_mode_enabled.get(),
            llm_provider=self.llm_provider.get(),
            llm_model=self.llm_model.get(),
        )

    def _add_corpus_viewer(self, parent):
        """Create commit viewer and single commit runner."""
        corpus_frame = tk.LabelFrame(parent, text="Bug Corpus")
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

        tk.Button(
            controls,
            text="2. Patch",
            command=lambda: self._run_single_stage(2),
            bg="#FFF3E0",
        ).pack(fill="x", pady=1)

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

        # show bug details
        log(f"Bug details:")
        log(f"  Repo: {repo_name}")
        log(f"  SHA: {bug.get('bug_commit_sha')}")
        log(f"  Parent: {bug.get('parent_commit_sha')}")
        log(f"  Changed files: {bug.get('changed_files', [])}")
        log(f"  Issue title: {bug.get('issue_title', 'N/A')[:100]}")
        log(f"  Issue body length: {len(bug.get('issue_body', ''))} chars")

        # try to build context with detailed logging
        from core.project_handler import ProjectHandler
        from core.context_builder import ContextBuilder

        handler = ProjectHandler(repo_name)
        handler.setup()

        parent_sha = bug.get("parent_commit_sha")
        log(f"\nChecking out parent commit: {parent_sha}")
        handler.checkout(parent_sha)

        log(f"\nRepo path: {handler.repo_path}")
        log(f"Repo exists: {handler.repo_path.exists()}")

        log(f"\nChecking changed files:")
        for file_path in bug.get("changed_files", []):
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
            self._toggle_controls(is_running=True)
            try:
                pipeline = self._create_pipeline()

                log(f"\n{'='*70}")
                log(f"TESTING: {stage_names[stage]}")
                log(f"Bug: {repo_name}:{bug_sha}")
                log(f"{'='*70}\n")

                if stage == 1:
                    contexts = pipeline._build_contexts_for_repo(
                        repo_name, [bug], self.stop_event, None
                    )
                    self._save_test_result("context", contexts)

                elif stage == 2:
                    context = self._load_test_context(repo_name, bug_sha)
                    if not context:
                        return

                    bug_key = f"{repo_name}_{bug.get('bug_commit_sha', '')[:12]}"
                    contexts = {bug_key: context}

                    patches = pipeline._generate_patches_sequential(
                        contexts, self.stop_event, None
                    )
                    self._save_test_result("patch", patches)

                elif stage == 3:
                    patch = self._load_test_patch(repo_name, bug_sha)
                    if not patch:
                        return

                    from core.project_handler import ProjectHandler

                    handler = ProjectHandler(repo_name)
                    handler.setup()

                    if not handler.setup_virtual_environment():
                        log("ERROR: venv setup failed")
                        return

                    pipeline._test_single_patch(patch, handler)
                    handler.cleanup()

                elif stage == "full":
                    pipeline.run_full_pipeline(
                        [bug],  # single bug as list
                        self.threaded_mode.get(),
                        self.resume_event,
                        self.stop_event,
                    )

                if not self.stop_event.is_set():
                    log(f"\nSUCCESS: {stage_names[stage]} complete!")

            except Exception as e:
                log(f"\nERROR: {e}")
                import traceback

                log(traceback.format_exc())
            finally:
                self._toggle_controls(is_running=False)
                self._set_status("Idle")

        threading.Thread(target=test_task, daemon=True).start()

    def _save_test_result(self, result_type, data):
        """Save test result to file for inspection."""

        if not data:
            log(f"WARNING: No {result_type} data to save")
            return

        test_dir = self.project_root / "results" / "debug" / "test_single"
        test_dir.mkdir(parents=True, exist_ok=True)

        if isinstance(data, dict) and data:
            actual_data = list(data.values())[0]
        else:
            actual_data = data

        filename = f"{result_type}.json"
        filepath = test_dir / filename

        filepath.write_text(json.dumps(actual_data, indent=2, default=str))
        log(f"Saved to: {filepath}")

    def _load_test_context(self, repo_name, bug_sha):
        """Load context from test file or stage1 cache."""

        test_file = (
            self.project_root / "results" / "debug" / "test_single" / "context.json"
        )
        if test_file.exists():
            try:
                return json.loads(test_file.read_text())
            except:
                pass

        stage1_file = (
            self.project_root / ".cache" / "pipeline_stages" / "stage1_contexts.json"
        )
        if stage1_file.exists():
            try:
                all_contexts = json.loads(stage1_file.read_text())
                for key, ctx in all_contexts.items():
                    if repo_name in key and bug_sha in key:
                        return ctx
            except:
                pass

        messagebox.showerror(
            "Error",
            f"No context found for {repo_name}:{bug_sha}\n\n" "Run stage 1 first.",
        )
        return None

    def _load_test_patch(self, repo_name, bug_sha):
        """Load patch from test file or stage2 cache."""

        test_file = (
            self.project_root / "results" / "debug" / "test_single" / "patch.json"
        )
        if test_file.exists():
            try:
                return json.loads(test_file.read_text())
            except:
                pass

        stage2_file = (
            self.project_root / ".cache" / "pipeline_stages" / "stage2_patches.json"
        )
        if stage2_file.exists():
            try:
                all_patches = json.loads(stage2_file.read_text())
                for key, patch in all_patches.items():
                    if repo_name in key and bug_sha in key:
                        return patch
            except:
                pass

        messagebox.showerror(
            "Error",
            f"No patch found for {repo_name}:{bug_sha}\n\n" "Run stage 2 first.",
        )
        return None

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

            self.parallel_workers.set(config.get("max_parallel_llm", 5))

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
        config_data["max_parallel_llm"] = self.parallel_workers.get()

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

        bug = self.bug_corpus[selection[0]]
        repo_name = bug.get("repo_name", "unknown")
        bug_sha = bug.get("bug_commit_sha", "unknown")[:7]

        self._reset_pipeline_state()
        self._save_configuration()

        mode = self.threaded_mode.get()
        self._set_status(f"Busy: Running {repo_name}:{bug_sha} ({mode})...")

        def single_bug_task():
            self._toggle_controls(is_running=True)
            try:
                pipeline = self._create_pipeline()
                pipeline.run_full_pipeline(
                    [bug],
                    mode,
                    self.resume_event,
                    self.stop_event,
                )
                if not self.stop_event.is_set():
                    log(f">>> {repo_name}:{bug_sha} complete!")
            except Exception as e:
                log(f"ERROR: {e}")
            finally:
                self._toggle_controls(is_running=False)
                self._set_status("Idle")

        threading.Thread(target=single_bug_task, daemon=True).start()

    def _reset_pipeline_state(self):
        """Reset control events for a new run."""
        self.stop_event.clear()
        self.resume_event.set()
