"""Interactive first-run setup wizard and onboarding UI."""

from pathlib import Path
import os
import threading
from typing import Callable, List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.table import Table

from organizer.config import OperationalMode
from organizer.models.adapter import PullProgress, RuntimeState
from organizer.models.catalog import CatalogEntry, Modality
from organizer.models.lifecycle import (
    LocalModelLifecycleService,
    ModelReadinessState,
)


class FirstRunSetupWizard:
    """Interactive setup wizard for first-run model selection and configuration."""

    def __init__(
        self,
        service: LocalModelLifecycleService,
        console: Optional[Console] = None,
        input_func: Optional[Callable[[str], str]] = None,
    ) -> None:
        self.service = service
        self.console = console or Console()
        self._input = input_func or input

    def prompt(self, message: str, default: Optional[str] = None) -> str:
        """Prompt user for input with an optional default."""
        prompt_text = f"{message} [{default}]: " if default else f"{message}: "
        self.console.print(prompt_text, end="")
        try:
            val = self._input("").strip()
            return val if val else (default or "")
        except (EOFError, KeyboardInterrupt):
            return "exit"

    def run(self) -> bool:
        """Run the interactive setup wizard. Returns True on success, False if aborted."""
        self.console.print()
        self.console.print(
            Panel.fit(
                "[bold cyan]Local Folder Organizer — First-Run Setup[/bold cyan]\n"
                "[dim]Private, on-device organization with local Gemma models or rule-based mode.[/dim]",
                border_style="cyan",
            )
        )

        runtime = self.service.check_runtime()

        if not runtime.is_available:
            return self._handle_runtime_unavailable(runtime)

        return self._handle_runtime_available()

    def _handle_runtime_unavailable(self, runtime) -> bool:
        """Guide user when Ollama is missing or stopped."""
        if runtime.state == RuntimeState.NOT_INSTALLED:
            self.console.print(
                Panel(
                    "[bold red]Prerequisite Missing: Ollama is not installed[/bold red]\n\n"
                    "The local folder organizer uses Ollama for local-only, private inference.\n"
                    "No files or document contents will ever leave your device.\n\n"
                    "[bold yellow]Installation Options:[/bold yellow]\n"
                    "  • Download installer from: [link=https://ollama.com]https://ollama.com[/link]\n"
                    "  • Or install via Homebrew: [bold]brew install ollama[/bold]\n\n"
                    "[dim]Privileged installers are never run automatically by this application.[/dim]",
                    title="Ollama Setup Required",
                    border_style="red",
                )
            )
        else:
            self.console.print(
                Panel(
                    "[bold yellow]Ollama Service Stopped[/bold yellow]\n\n"
                    f"Ollama binary is found at: [dim]{runtime.binary_path}[/dim]\n"
                    f"However, the local API on [dim]{runtime.endpoint}[/dim] is not responding.\n\n"
                    "[bold green]To start Ollama:[/bold green]\n"
                    "  • Launch the Ollama app from your Applications folder, OR\n"
                    "  • Run in another terminal: [bold]ollama serve[/bold]",
                    title="Runtime Stopped",
                    border_style="yellow",
                )
            )

        self.console.print("\n[bold]What would you like to do?[/bold]")
        self.console.print("  [1] Continue without AI (use deterministic extension rules only)")
        self.console.print("  [2] Use Google Gemini API (Online free tier — no local Ollama or RAM required)")
        self.console.print("  [3] Use OpenRouter (Online free inference — openrouter/free, zero host RAM required)")
        self.console.print("  [4] Exit setup and install/start Ollama first")

        choice = self.prompt("Select option", default="1")
        if choice == "1":
            self.service.enable_rule_only_mode()
            self.console.print(
                "\n[green]✓ Non-AI mode enabled.[/green] You can organize folders using deterministic rules.\n"
                "Run [bold]organizer setup[/bold] later when Ollama is ready."
            )
            return True

        if choice in ("2", "g", "G", "gemini"):
            return self._setup_gemini_mode()

        if choice in ("3", "o", "O", "openrouter"):
            return self._setup_openrouter_mode()

        self.console.print("\n[yellow]Setup exited.[/yellow] Run [bold]organizer setup[/bold] when ready.")
        return False

    def _handle_runtime_available(self) -> bool:
        """Present model selection options when Ollama is responding."""
        installed = self.service.discover_local_models()
        installed_names = [m.name for m in installed]

        rec = self.service.catalog.get_recommended()
        rec_id = rec.model_id if rec else "gemma4:e2b"
        rec_installed = rec_id in installed_names

        self.console.print("\n[bold]Select a setup option:[/bold]")

        rec_choice_idx = "1"
        if rec_installed:
            self.console.print(f"  [1] Use recommended installed model: [bold green]{rec.display_name}[/bold green]")
        else:
            self.console.print(
                f"  [1] Download recommended model: [bold green]{rec.display_name}[/bold green] "
                f"([cyan]{rec.download_size_str}[/cyan] — {rec.recommendation_reason})"
            )

        gemini_choice_idx = "2"
        gemini_has_key = bool(self.service.gemini_adapter.api_key or os.environ.get("GEMINI_API_KEY"))
        gemini_tag = "[bold green]Key Detected[/bold green]" if gemini_has_key else "[dim]Free Tier[/dim]"
        self.console.print(
            f"  [2] Use Google Gemini API ({gemini_tag} — fast multimodal cloud AI, zero host RAM required)"
        )

        openrouter_choice_idx = "3"
        openrouter_has_key = bool(self.service.openrouter_adapter.api_key or os.environ.get("OPENROUTER_API_KEY"))
        openrouter_tag = "[bold green]Key Detected[/bold green]" if openrouter_has_key else "[dim]Free Meta-Router[/dim]"
        self.console.print(
            f"  [3] Use OpenRouter ({openrouter_tag} — online free inference openrouter/free, zero host RAM required)"
        )

        option_idx = 4
        installed_choice_idx = None
        if installed:
            installed_choice_idx = str(option_idx)
            self.console.print(f"  [{installed_choice_idx}] Choose from already installed local models ({len(installed)} available)")
            option_idx += 1

        catalog_choice_idx = str(option_idx)
        self.console.print(f"  [{catalog_choice_idx}] Select another model from catalog")
        option_idx += 1

        rule_choice_idx = str(option_idx)
        self.console.print(f"  [{rule_choice_idx}] Continue without AI (deterministic rules only)")
        option_idx += 1

        exit_choice_idx = str(option_idx)
        self.console.print(f"  [{exit_choice_idx}] Exit setup")

        choice = self.prompt("Enter selection", default="1")

        if choice == gemini_choice_idx or choice.lower() in ("g", "gemini"):
            return self._setup_gemini_mode()

        if choice == openrouter_choice_idx or choice.lower() in ("o", "openrouter"):
            return self._setup_openrouter_mode()

        if choice == rec_choice_idx:
            if rec_installed:
                return self._activate_installed_model(rec_id)
            return self._download_and_activate_model(rec)

        if installed_choice_idx and choice == installed_choice_idx:
            return self._choose_installed_model(installed)

        if choice == catalog_choice_idx:
            return self._choose_catalog_model()

        if choice == rule_choice_idx:
            self.service.enable_rule_only_mode()
            self.console.print("\n[green]✓ Rule-only mode configured.[/green] All operations will run deterministically without AI.")
            return True

        self.console.print("\n[dim]Setup cancelled. No changes made.[/dim]")
        return False

    def _activate_installed_model(self, model_id: str) -> bool:
        """Verify readiness and activate an already installed model."""
        self.console.print(f"\n[cyan]Verifying readiness of '{model_id}'...[/cyan]")
        readiness = self.service.set_active_model(model_id, verify_first=True)
        if readiness.is_ready:
            self.console.print(f"[bold green]✓ Successfully set '{model_id}' as the active model![/bold green]")
            return True

        self.console.print(f"[bold red]Readiness check failed:[/bold red] {readiness.message}")
        self.console.print("\n[bold]Alternative options:[/bold]")
        self.console.print("  [1] Switch to Google Gemini API (Online free tier — zero host RAM required)")
        self.console.print("  [2] Switch to OpenRouter (Online free inference — openrouter/free)")
        self.console.print("  [3] Continue in rule-based mode (deterministic rules only)")
        self.console.print("  [4] Exit setup")

        alt = self.prompt("Select option", default="1")
        if alt in ("1", "g", "G", "gemini"):
            return self._setup_gemini_mode()
        elif alt in ("2", "o", "O", "openrouter"):
            return self._setup_openrouter_mode()
        elif alt == "3":
            self.service.enable_rule_only_mode()
            self.console.print("[green]✓ Rule-based mode enabled.[/green]")
            return True
        return False

    def _download_and_activate_model(self, entry: CatalogEntry) -> bool:
        """Download a catalog model with progress bar, verify, and activate."""
        self.console.print(f"\n[bold]Selected Model:[/bold] {entry.display_name} ([cyan]{entry.model_id}[/cyan])")
        self.console.print(f"  • Estimated download size: {entry.download_size_str}")
        self.console.print(f"  • Modalities supported: {', '.join(entry.supported_modalities)}")
        self.console.print("  • Note: An active internet connection is required for this one-time download.")

        # Check resource constraints
        res_eval = self.service.check_model_resources(entry.model_id)
        if res_eval.has_warnings:
            self.console.print("\n[bold yellow]Hardware Advisory Notice:[/bold yellow]")
            for w in res_eval.warnings:
                self.console.print(f"  [yellow]• {w}[/yellow]")

            if not res_eval.is_sufficient_disk:
                self.console.print("[bold red]Cannot proceed: Insufficient disk space.[/bold red]")
                return False

            override = self.prompt("Do you wish to acknowledge this advisory and proceed? (y/n)", default="y")
            if not override.lower().startswith("y"):
                self.console.print("[yellow]Download aborted by user.[/yellow]")
                return False

        confirm = self.prompt(f"Start downloading {entry.display_name}? (y/n)", default="y")
        if not confirm.lower().startswith("y"):
            self.console.print("[yellow]Setup aborted.[/yellow]")
            return False

        # Live streaming progress
        self.console.print()
        cancel_event = threading.Event()
        success = self._run_download_progress(entry.model_id, cancel_event)

        if not success:
            self.console.print(f"[bold red]Download failed or was cancelled.[/bold red]")
            return False

        # Verification and smoke test
        self.console.print("[cyan]Verifying installation and running smoke test...[/cyan]")
        readiness = self.service.set_active_model(entry.model_id, verify_first=True)
        if readiness.is_ready:
            self.console.print(f"\n[bold green]✓ Setup Complete! '{entry.model_id}' is ready for folder organization.[/bold green]")
            return True

        self.console.print(f"\n[bold red]Model readiness check failed:[/bold red] {readiness.message}")
        self.console.print("\n[yellow]Local hardware appears unable to execute this local model.[/yellow]")
        self.console.print("  [1] Switch to Google Gemini API (Online free tier — zero host RAM required)")
        self.console.print("  [2] Switch to OpenRouter (Online free inference — openrouter/free)")
        self.console.print("  [3] Continue in rule-based mode (deterministic rules only)")
        self.console.print("  [4] Exit setup")

        alt = self.prompt("Select option", default="1")
        if alt in ("1", "g", "G", "gemini"):
            return self._setup_gemini_mode()
        elif alt in ("2", "o", "O", "openrouter"):
            return self._setup_openrouter_mode()
        elif alt == "3":
            self.service.enable_rule_only_mode()
            self.console.print("[green]✓ Rule-based mode enabled.[/green]")
            return True
        return False

    def _setup_gemini_mode(self) -> bool:
        """Guide user through Google Gemini API onboarding and verification."""
        self.console.print("\n[bold cyan]=== Google Gemini API Setup ===[/bold cyan]")
        self.console.print(
            "Google Gemini API provides fast, frontier multimodal intelligence on a free tier,\n"
            "requiring zero host memory (RAM) or local disk space for model weights.\n"
        )

        detected_key = self.service.gemini_adapter.api_key or os.environ.get("GEMINI_API_KEY")
        if detected_key:
            masked = (
                detected_key[:6] + "..." + detected_key[-4:]
                if len(detected_key) > 10
                else "***"
            )
            self.console.print(
                f"[green]✓ Detected GEMINI_API_KEY in environment:[/green] [dim]{masked}[/dim]"
            )
            use_env = self.prompt("Use this detected key? (y/n)", default="y")
            if use_env.lower().startswith("y"):
                api_key = detected_key
            else:
                api_key = self.prompt("Enter your Gemini API key")
        else:
            self.console.print(
                "[yellow]GEMINI_API_KEY is not currently set in your environment.[/yellow]"
            )
            self.console.print(
                "[dim]You can obtain a free API key at https://aistudio.google.com/apikey[/dim]"
            )
            api_key = self.prompt("Enter your Gemini API key (or press Enter to cancel)")

        if not api_key:
            self.console.print("[yellow]Gemini setup cancelled.[/yellow]")
            return False

        model_name = self.service.config.gemini_settings.model_name or "gemini-2.5-flash"
        self.console.print(f"\n[cyan]Verifying Google Gemini API connectivity ({model_name})...[/cyan]")

        readiness = self.service.enable_gemini_mode(
            api_key=api_key, model_name=model_name, verify_first=True
        )
        if readiness.is_ready:
            self.console.print(
                f"\n[bold green]✓ Setup Complete! Google Gemini API ({model_name}) is ready for folder organization.[/bold green]"
            )
            return True

        self.console.print(f"\n[bold red]Gemini verification failed:[/bold red] {readiness.message}")
        retry = self.prompt("Would you like to retry? (y/n)", default="n")
        if retry.lower().startswith("y"):
            return self._setup_gemini_mode()
        return False

    def _setup_openrouter_mode(self) -> bool:
        """Guide user through OpenRouter API onboarding and verification."""
        self.console.print("\n[bold cyan]=== OpenRouter Setup ===[/bold cyan]")
        self.console.print(
            "OpenRouter provides access to frontier and open models, including the free\n"
            "meta-router 'openrouter/free' for testing and MVP file categorization without host RAM.\n"
        )

        detected_key = self.service.openrouter_adapter.api_key or os.environ.get("OPENROUTER_API_KEY")
        if detected_key:
            masked = (
                detected_key[:6] + "..." + detected_key[-4:]
                if len(detected_key) > 10
                else "***"
            )
            self.console.print(
                f"[green]✓ Detected OPENROUTER_API_KEY in environment:[/green] [dim]{masked}[/dim]"
            )
            use_env = self.prompt("Use this detected key? (y/n)", default="y")
            if use_env.lower().startswith("y"):
                api_key = detected_key
            else:
                api_key = self.prompt("Enter your OpenRouter API key")
        else:
            self.console.print(
                "[yellow]OPENROUTER_API_KEY is not currently set in your environment.[/yellow]"
            )
            self.console.print(
                "[dim]You can obtain a free API key at https://openrouter.ai/settings/keys[/dim]"
            )
            api_key = self.prompt("Enter your OpenRouter API key (or press Enter to cancel)")

        if not api_key:
            self.console.print("[yellow]OpenRouter setup cancelled.[/yellow]")
            return False

        model_name = self.service.config.openrouter_settings.model_name or "openrouter/free"
        self.console.print(f"\n[cyan]Verifying OpenRouter connectivity ({model_name})...[/cyan]")

        readiness = self.service.enable_openrouter_mode(
            api_key=api_key, model_name=model_name, verify_first=True
        )
        if readiness.is_ready:
            self.console.print(
                f"\n[bold green]✓ Setup Complete! OpenRouter ({model_name}) is ready for folder organization.[/bold green]"
            )
            return True

        self.console.print(f"\n[bold red]OpenRouter verification failed:[/bold red] {readiness.message}")
        retry = self.prompt("Would you like to retry? (y/n)", default="n")
        if retry.lower().startswith("y"):
            return self._setup_openrouter_mode()
        return False

    def _run_download_progress(self, model_id: str, cancel_event: threading.Event) -> bool:
        """Run progress display while downloading model."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=self.console,
        ) as progress:
            task = progress.add_task(f"Pulling {model_id}...", total=None)

            def on_progress(p: PullProgress) -> None:
                if p.total and p.completed:
                    progress.update(task, total=p.total, completed=p.completed, description=f"{p.status}")
                else:
                    progress.update(task, description=f"{p.status}")

            return self.service.pull_model(model_id, progress_callback=on_progress, cancel_event=cancel_event)

    def _choose_installed_model(self, installed: List) -> bool:
        """Prompt user to choose from discovered installed models."""
        self.console.print("\n[bold]Locally Installed Models:[/bold]")
        for i, m in enumerate(installed, 1):
            vision = " [cyan](Multimodal)[/cyan]" if m.catalog_entry and m.catalog_entry.supports_vision else ""
            self.console.print(f"  [{i}] {m.name} ({m.size_gb:.1f} GB){vision}")

        choice = self.prompt("Select model number", default="1")
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(installed):
                return self._activate_installed_model(installed[idx].name)
        except ValueError:
            pass

        self.console.print("[red]Invalid selection.[/red]")
        return False

    def _choose_catalog_model(self) -> bool:
        """Prompt user to choose from catalog models."""
        entries = self.service.catalog.list_entries()
        self.console.print("\n[bold]Available Models in Catalog:[/bold]")
        for i, e in enumerate(entries, 1):
            modalities = "/".join(e.supported_modalities)
            self.console.print(f"  [{i}] {e.display_name} ([cyan]{e.model_id}[/cyan]) — {e.download_size_str} [{modalities}]")

        choice = self.prompt("Select model number", default="1")
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(entries):
                return self._download_and_activate_model(entries[idx])
        except ValueError:
            pass

        self.console.print("[red]Invalid selection.[/red]")
        return False
