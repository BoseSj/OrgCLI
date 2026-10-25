"""Command-line interface for the organizer application."""

import os
from pathlib import Path
import sys
from typing import Optional
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import typer

from organizer.config import (
    AppConfig,
    OperationalMode,
    get_default_config_path,
    load_config,
)
from organizer.models.catalog import CatalogEntry, Modality, ModelCatalog
from organizer.models.lifecycle import (
    LocalModelLifecycleService,
    ModelReadinessState,
)
from organizer.rules import (
    ProposedMove,
    group_proposals_by_destination,
    scan_and_propose_tree,
)
from organizer.ui.interactive_plan import (
    SHOW_TARGET_FILENAME,
    run_interactive_plan_session,
)
from organizer.ui.setup import FirstRunSetupWizard

app = typer.Typer(
    help="Private, local-first macOS folder organizer with local Gemma model management.",
    no_args_is_help=False,
)
models_app = typer.Typer(help="Inspect, install, configure, and manage local models.")
app.add_typer(models_app, name="models")

console = Console()


def get_lifecycle_service(config_path: Optional[Path] = None) -> LocalModelLifecycleService:
    """Instantiate lifecycle service with configured options."""
    return LocalModelLifecycleService(config_path=config_path)


@app.command(name="setup")
def setup_command(
    config_path: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to configuration file."
    )
) -> None:
    """Launch the interactive first-run model setup wizard."""
    service = get_lifecycle_service(config_path)
    wizard = FirstRunSetupWizard(service=service, console=console)
    success = wizard.run()
    if not success:
        raise typer.Exit(code=1)


@models_app.command(name="list")
def models_list(
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path.")
) -> None:
    """List locally installed Ollama models."""
    service = get_lifecycle_service(config_path)
    runtime = service.check_runtime()
    if not runtime.is_available:
        console.print(f"[bold red]Cannot list models:[/bold red] {runtime.details}")
        raise typer.Exit(code=1)

    models = service.discover_local_models()
    if not models:
        console.print("[yellow]No models currently installed in local Ollama.[/yellow]")
        console.print("Run [bold]organizer models available[/bold] to see supported models.")
        return

    table = Table(title="Locally Installed Models", border_style="cyan")
    table.add_column("Active", justify="center", style="green")
    table.add_column("Model Identifier", style="bold", no_wrap=True)
    table.add_column("Disk Size", justify="right")
    table.add_column("Modalities")
    table.add_column("Display Name", style="dim")

    for m in models:
        active_mark = "✓" if m.is_active else ""
        modalities = (
            ", ".join(m.catalog_entry.supported_modalities)
            if m.catalog_entry
            else "text"
        )
        display_name = m.catalog_entry.display_name if m.catalog_entry else "Uncataloged"
        table.add_row(active_mark, m.name, f"{m.size_gb:.2f} GB", modalities, display_name)

    console.print(table)


@models_app.command(name="available")
def models_available(
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path.")
) -> None:
    """List supported models available in the catalog."""
    service = get_lifecycle_service(config_path)
    entries = service.catalog.list_entries()
    installed = {m.name for m in service.discover_local_models()}

    table = Table(title="Supported Models Catalog", border_style="cyan")
    table.add_column("Recommended", justify="center", style="yellow")
    table.add_column("Identifier", style="bold", no_wrap=True)
    table.add_column("Display Name")
    table.add_column("Modalities")
    table.add_column("Download Size", justify="right")
    table.add_column("Min RAM", justify="right")
    table.add_column("Installed", justify="center")

    for e in entries:
        rec_mark = "★" if e.is_recommended else ""
        installed_mark = "[green]Yes[/green]" if e.model_id in installed else "[dim]No[/dim]"
        modalities = ", ".join(e.supported_modalities)
        table.add_row(
            rec_mark,
            e.model_id,
            e.display_name,
            modalities,
            e.download_size_str,
            f"{e.hardware.min_ram_gb:.0f} GB",
            installed_mark,
        )

    console.print(table)
    console.print("[dim]★ Recommended for 8 GB unified-memory Macs.[/dim]")


@models_app.command(name="install")
def models_install(
    model_id: str = typer.Argument(..., help="Model identifier to install (e.g. 'gemma4:e2b')"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
    use: bool = typer.Option(True, "--use/--no-use", help="Set as active model after installation."),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path."),
) -> None:
    """Download, verify, and optionally activate a local model."""
    service = get_lifecycle_service(config_path)
    entry = service.catalog.get_entry(model_id)

    name = entry.display_name if entry else model_id
    size_str = entry.download_size_str if entry else "unknown"

    console.print(f"[bold]Preparing to install model:[/bold] {name} ([cyan]{model_id}[/cyan])")
    console.print(f"Estimated download size: [cyan]{size_str}[/cyan]")
    console.print("An active internet connection is required for this one-time download.")

    # Check resources
    res_eval = service.check_model_resources(model_id)
    if res_eval.has_warnings:
        console.print("\n[bold yellow]Hardware Advisory:[/bold yellow]")
        for w in res_eval.warnings:
            console.print(f"  [yellow]• {w}[/yellow]")
        if not res_eval.is_sufficient_disk and not yes:
            console.print("[bold red]Cannot proceed: Insufficient disk space.[/bold red]")
            raise typer.Exit(code=1)

    if not yes:
        confirm = typer.confirm(f"Proceed with downloading '{model_id}'?", default=True)
        if not confirm:
            console.print("[yellow]Installation cancelled.[/yellow]")
            raise typer.Exit(code=0)

    wizard = FirstRunSetupWizard(service, console=console)
    success = wizard._run_download_progress(model_id, cancel_event=None)
    if not success:
        console.print(f"[bold red]Failed to download model '{model_id}'.[/bold red]")
        raise typer.Exit(code=1)

    console.print("[cyan]Verifying installation readiness...[/cyan]")
    readiness = service.verify_readiness(model_id)
    if not readiness.is_ready:
        console.print(f"[bold red]Readiness check failed:[/bold red] {readiness.message}")
        raise typer.Exit(code=1)

    console.print(f"[bold green]✓ Model '{model_id}' successfully installed and verified![/bold green]")

    if use:
        service.set_active_model(model_id, verify_first=False)
        console.print(f"[green]✓ '{model_id}' is now configured as the active model.[/green]")


@models_app.command(name="use")
def models_use(
    model_id: str = typer.Argument(..., help="Model identifier to set as active"),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path."),
) -> None:
    """Switch the active model for file organization."""
    service = get_lifecycle_service(config_path)
    readiness = service.set_active_model(model_id, verify_first=True)

    if not readiness.is_ready:
        console.print(f"[bold red]Cannot activate model '{model_id}':[/bold red] {readiness.message}")
        raise typer.Exit(code=1)

    console.print(f"[bold green]✓ Active model switched to '{model_id}'.[/bold green]")


@models_app.command(name="status")
def models_status(
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path.")
) -> None:
    """Display current model and runtime status."""
    service = get_lifecycle_service(config_path)
    cfg = service.config

    table = Table(title="Model & Runtime Status", show_header=False, border_style="cyan")
    table.add_column("Property", style="bold")
    table.add_column("Value")

    table.add_row("Operational Mode", cfg.operational_mode.value.upper())

    if cfg.operational_mode == OperationalMode.GEMINI:
        active_model = cfg.gemini_settings.model_name or cfg.active_model or "gemini-2.5-flash"
        table.add_row("Active Model", active_model)
        key_status = (
            "[green]Configured (Environment)[/green]"
            if os.environ.get("GEMINI_API_KEY")
            else (
                "[green]Configured (Settings)[/green]"
                if cfg.gemini_settings.api_key
                else "[red]Missing[/red]"
            )
        )
        table.add_row("Gemini API Key", key_status)
        readiness = service.verify_readiness()
        readiness_val = (
            "[green]Ready[/green]" if readiness.is_ready else f"[red]{readiness.message}[/red]"
        )
        table.add_row("Gemini API Readiness", readiness_val)
    elif cfg.operational_mode == OperationalMode.OPENROUTER:
        active_model = cfg.openrouter_settings.model_name or cfg.active_model or "openrouter/free"
        table.add_row("Active Model", active_model)
        key_status = (
            "[green]Configured (Environment)[/green]"
            if os.environ.get("OPENROUTER_API_KEY")
            else (
                "[green]Configured (Settings)[/green]"
                if cfg.openrouter_settings.api_key
                else "[red]Missing[/red]"
            )
        )
        table.add_row("OpenRouter API Key", key_status)
        readiness = service.verify_readiness()
        readiness_val = (
            "[green]Ready[/green]" if readiness.is_ready else f"[red]{readiness.message}[/red]"
        )
        table.add_row("OpenRouter API Readiness", readiness_val)
    elif cfg.operational_mode == OperationalMode.RULE_ONLY:
        table.add_row("Active Model", "[dim]None (Rule-only mode)[/dim]")
    else:
        table.add_row("Active Model", cfg.active_model or "[dim]None[/dim]")
        table.add_row("Runtime Endpoint", cfg.model_settings.endpoint)

        runtime = service.check_runtime()
        runtime_val = (
            "[green]Running[/green]" if runtime.is_available else f"[red]{runtime.state.value}[/red]"
        )
        table.add_row("Ollama Status", runtime_val)

        if cfg.active_model and runtime.is_available:
            readiness = service.verify_readiness()
            readiness_val = (
                "[green]Ready[/green]" if readiness.is_ready else f"[red]{readiness.message}[/red]"
            )
            table.add_row("Model Readiness", readiness_val)

    console.print(table)


@models_app.command(name="doctor")
def models_doctor(
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path.")
) -> None:
    """Run full diagnostic check on local runtime, loopback safety, and model readiness."""
    service = get_lifecycle_service(config_path)
    report = service.run_diagnostics()

    console.print("\n[bold cyan]=== Local Folder Organizer Doctor ===[/bold cyan]\n")

    # Diagnostic checks table
    table = Table(border_style="dim")
    table.add_column("Component", style="bold")
    table.add_column("Status")
    table.add_column("Details")

    if report.operational_mode == OperationalMode.GEMINI:
        cred_check = service.gemini_adapter.check_credentials()
        table.add_row(
            "Gemini API Key",
            "[green]PASSED[/green]" if cred_check.api_key_configured else "[red]FAILED[/red]",
            cred_check.message,
        )
        table.add_row(
            "Gemini API Readiness",
            "[green]PASSED[/green]" if report.readiness.is_ready else "[red]FAILED[/red]",
            report.readiness.message,
        )
    elif report.operational_mode == OperationalMode.OPENROUTER:
        cred_check = service.openrouter_adapter.check_credentials()
        table.add_row(
            "OpenRouter API Key",
            "[green]PASSED[/green]" if cred_check.api_key_configured else "[red]FAILED[/red]",
            cred_check.message,
        )
        table.add_row(
            "OpenRouter API Readiness",
            "[green]PASSED[/green]" if report.readiness.is_ready else "[red]FAILED[/red]",
            report.readiness.message,
        )
    else:
        # Ollama Binary
        table.add_row(
            "Ollama Binary",
            "[green]PASSED[/green]" if report.runtime_check.binary_path else "[red]FAILED[/red]",
            report.runtime_check.binary_path or "Not found in system PATH",
        )

        # API Endpoint
        table.add_row(
            "Local Loopback API",
            "[green]PASSED[/green]" if report.runtime_check.is_available else "[red]FAILED[/red]",
            report.runtime_check.endpoint,
        )

    # Memory Check
    mem = report.host_resources
    table.add_row(
        "Host RAM",
        "[green]PASSED[/green]",
        f"Total: {mem.total_ram_gb:.1f} GB, Available: {mem.available_ram_gb:.1f} GB",
    )

    # Disk Check
    table.add_row(
        "Free Disk Space",
        "[green]PASSED[/green]" if mem.free_disk_gb >= 3.0 else "[yellow]WARNING[/yellow]",
        f"{mem.free_disk_gb:.1f} GB free",
    )

    # Active Model / Mode
    if report.operational_mode == OperationalMode.RULE_ONLY:
        table.add_row("Operational Mode", "[green]PASSED[/green]", "Rule-only (Non-AI)")
    elif report.operational_mode == OperationalMode.GEMINI:
        table.add_row(
            "Operational Mode",
            "[green]PASSED[/green]",
            f"Google Gemini API ({service.config.gemini_settings.model_name or 'gemini-2.5-flash'})",
        )
    elif report.operational_mode == OperationalMode.OPENROUTER:
        table.add_row(
            "Operational Mode",
            "[green]PASSED[/green]",
            f"OpenRouter API ({service.config.openrouter_settings.model_name or 'openrouter/free'})",
        )
    else:
        table.add_row(
            "Active Model Readiness",
            "[green]PASSED[/green]" if report.readiness.is_ready else "[red]FAILED[/red]",
            report.readiness.message,
        )

    console.print(table)

    if report.warnings:
        console.print("\n[bold yellow]Warnings / Diagnostics:[/bold yellow]")
        for w in report.warnings:
            console.print(f"  [yellow]• {w}[/yellow]")

    if report.diagnostics_passed:
        console.print("\n[bold green]✓ All critical diagnostic checks passed![/bold green]\n")
    else:
        console.print("\n[bold red]✗ Some diagnostic checks failed.[/bold red]\n")
        raise typer.Exit(code=1)


@models_app.command(name="remove")
def models_remove(
    model_id: str = typer.Argument(..., help="Model identifier to delete from Ollama"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Confirm deletion without interactive prompt"),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path."),
) -> None:
    """Remove a local model from Ollama with explicit confirmation."""
    service = get_lifecycle_service(config_path)

    console.print(
        f"[bold yellow]WARNING:[/bold yellow] This will permanently delete the local model files "
        f"for '[bold]{model_id}[/bold]' through Ollama."
    )

    if not yes:
        confirm = typer.confirm(f"Are you sure you want to delete '{model_id}'?", default=False)
        if not confirm:
            console.print("[yellow]Removal cancelled.[/yellow]")
            return

    try:
        deleted = service.remove_model(model_id)
        if deleted:
            console.print(f"[bold green]✓ Model '{model_id}' was removed successfully.[/bold green]")
        else:
            console.print(f"[bold red]Failed to remove model '{model_id}'.[/bold red]")
            raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[bold red]Error deleting model:[/bold red] {exc}")
        raise typer.Exit(code=1)


def print_static_grouped_plan(proposals: List[ProposedMove], console_out: Console) -> None:
    """Print the folder-grouped dry-run organization plan."""
    groups = group_proposals_by_destination(proposals)
    total_files = len(proposals)
    total_folders = len(groups)

    console_out.print(
        Panel(
            f"[bold cyan]Proposed Organization Plan (Dry-Run)[/bold cyan]\n"
            f"[dim]Organizing {total_files} files across {total_folders} folders[/dim]",
            border_style="cyan",
        )
    )

    for g in groups:
        star_badge = "⭐ " if g.is_ai_suggested else ""
        table = Table(
            title=f"📁 {star_badge}{g.folder_name} ({g.count_label})",
            title_justify="left",
            box=box.SIMPLE_HEAD,
            show_header=True,
            header_style="bold dim",
            expand=True,
        )
        table.add_column("Current Path", style="dim", ratio=4)
        if SHOW_TARGET_FILENAME:
            table.add_column("Target File Name", style="bold green", ratio=3)
        table.add_column("Confidence", justify="right", width=12)
        table.add_column("Reason", style="dim", ratio=4)

        for p in g.proposals:
            conf_str = f"{p.confidence * 100:.0f}%"
            target_name = Path(p.proposed_rel).name
            row = [p.source_rel]
            if SHOW_TARGET_FILENAME:
                row.append(target_name)
            row.extend([conf_str, p.reason])
            table.add_row(*row)

        console_out.print(table)

    console_out.print(
        f"\n[bold green]Summary:[/bold green] {total_files} files to organize across {total_folders} destination folders."
    )
    console_out.print("[dim]Dry-run only: no files were moved.[/dim]\n")


@app.command(name="scan")
def scan_command(
    path: Path = typer.Argument(Path("."), help="Target folder to scan and organize"),
    interactive: bool = typer.Option(
        True, "--interactive/--non-interactive", help="Enable interactive plan review session."
    ),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path."),
) -> None:
    """Scan target folder and propose an editable organization plan."""
    service = get_lifecycle_service(config_path)
    cfg = service.config

    # Startup setup hook: Check if setup is completed or model is ready
    if not cfg.setup_completed:
        console.print("[bold yellow]Organizer has not been configured yet.[/bold yellow]")
        start_setup = typer.confirm("Would you like to run the first-run model setup now?", default=True)
        if start_setup:
            wizard = FirstRunSetupWizard(service, console=console)
            success = wizard.run()
            if not success:
                console.print("[yellow]Exited setup. Scan aborted.[/yellow]")
                raise typer.Exit(code=1)
            cfg = service.reload_config()
        else:
            console.print("[yellow]Using rule-only mode for this scan.[/yellow]")

    target_dir = path.resolve()
    if not target_dir.is_dir():
        console.print(f"[bold red]Error:[/bold red] '{target_dir}' is not a directory.")
        raise typer.Exit(code=1)

    classifier = None
    if cfg.operational_mode == OperationalMode.GEMINI:
        cred = service.gemini_adapter.check_credentials()
        if cred.api_key_configured:
            classifier = service.gemini_adapter.classify_file
    elif cfg.operational_mode == OperationalMode.OPENROUTER:
        cred = service.openrouter_adapter.check_credentials()
        if cred.api_key_configured:
            classifier = service.openrouter_adapter.classify_file

    console.print(f"\n[bold cyan]Scanning directory:[/bold cyan] {target_dir}")
    proposals = scan_and_propose_tree(target_dir, classifier=classifier)

    if not proposals:
        console.print("[yellow]No eligible files found to organize.[/yellow]")
        return

    force_interactive = os.environ.get("ORGANIZER_FORCE_INTERACTIVE") == "1"
    is_tty = force_interactive or (sys.stdin.isatty() and sys.stdout.isatty())
    if interactive and is_tty:
        confirmed, final_proposals = run_interactive_plan_session(
            proposals, target_dir=target_dir, console=console
        )
        if confirmed:
            console.print("\n[bold green]✓ Organization plan confirmed![/bold green]")
            print_static_grouped_plan(final_proposals, console)
        else:
            console.print("\n[yellow]Organization review cancelled. No files were modified.[/yellow]\n")
    else:
        print_static_grouped_plan(proposals, console)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="Display version"),
) -> None:
    """Organizer CLI entrypoint."""
    if version:
        console.print("organizer version 0.1.0")
        raise typer.Exit(0)
    if ctx.invoked_subcommand is None:
        console.print("Run [bold]organizer --help[/bold] to see available commands, or [bold]organizer scan .[/bold] to organize a folder.")
