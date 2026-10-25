"""Tests for organizer CLI commands."""

from pathlib import Path
from typer.testing import CliRunner
import pytest

from organizer.cli import app
from organizer.config import AppConfig, OperationalMode, save_config
from organizer.testing.fake_ollama import FakeOllamaServer

runner = CliRunner(env={"COLUMNS": "120"})


def test_cli_models_available(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    result = runner.invoke(app, ["models", "available", "--config", str(cfg_file)])
    assert result.exit_code == 0
    assert "gemma4:e2b" in result.stdout
    assert "Gemma 4 E2B" in result.stdout
    assert "gemma2:2b" in result.stdout


def test_cli_models_list(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    with FakeOllamaServer() as server:
        server.installed_models = [{"name": "gemma4:e2b", "size": 1600000000}]
        cfg = AppConfig(
            setup_completed=True,
            active_model="gemma4:e2b",
            model_settings={"endpoint": server.endpoint},
        )
        save_config(cfg, cfg_file)

        result = runner.invoke(app, ["models", "list", "--config", str(cfg_file)])
        assert result.exit_code == 0
        assert "gemma4:e2b" in result.stdout
        assert "1.49 GB" in result.stdout


def test_cli_models_install_and_use(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    with FakeOllamaServer() as server:
        cfg = AppConfig(model_settings={"endpoint": server.endpoint})
        save_config(cfg, cfg_file)

        # Install gemma4:e2b with --yes
        res_install = runner.invoke(
            app,
            ["models", "install", "gemma4:e2b", "--yes", "--config", str(cfg_file)],
        )
        assert res_install.exit_code == 0
        assert "successfully installed and verified" in res_install.stdout

        # Use command
        res_use = runner.invoke(
            app,
            ["models", "use", "gemma4:e2b", "--config", str(cfg_file)],
        )
        assert res_use.exit_code == 0
        assert "switched to 'gemma4:e2b'" in res_use.stdout


def test_cli_models_status_and_doctor(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    with FakeOllamaServer() as server:
        server.installed_models = [{"name": "gemma4:e2b", "size": 1600000000}]
        cfg = AppConfig(
            setup_completed=True,
            active_model="gemma4:e2b",
            model_settings={"endpoint": server.endpoint},
        )
        save_config(cfg, cfg_file)

        # Status
        res_status = runner.invoke(app, ["models", "status", "--config", str(cfg_file)])
        assert res_status.exit_code == 0
        assert "AI" in res_status.stdout
        assert "gemma4:e2b" in res_status.stdout

        # Doctor
        res_doc = runner.invoke(app, ["models", "doctor", "--config", str(cfg_file)])
        assert res_doc.exit_code == 0
        assert "Local Loopback API" in res_doc.stdout
        assert "Host RAM" in res_doc.stdout


def test_cli_models_remove_with_confirmation(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    with FakeOllamaServer() as server:
        server.installed_models = [{"name": "gemma4:e2b", "size": 1600000000}]
        cfg = AppConfig(
            setup_completed=True,
            active_model="gemma4:e2b",
            model_settings={"endpoint": server.endpoint},
        )
        save_config(cfg, cfg_file)

        # Remove with decline 'n'
        res_abort = runner.invoke(
            app,
            ["models", "remove", "gemma4:e2b", "--config", str(cfg_file)],
            input="n\n",
        )
        assert res_abort.exit_code == 0
        assert "Removal cancelled" in res_abort.stdout
        assert len(server.installed_models) == 1

        # Remove with confirm 'y'
        res_confirm = runner.invoke(
            app,
            ["models", "remove", "gemma4:e2b", "--config", str(cfg_file)],
            input="y\n",
        )
        assert res_confirm.exit_code == 0
        assert "removed successfully" in res_confirm.stdout
        assert len(server.installed_models) == 0


def test_cli_scan_dry_run_rule_mode(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    folder = tmp_path / "my_docs"
    folder.mkdir()
    (folder / "notes.txt").write_text("hello")
    (folder / "chart.png").write_text("img")

    # Set up config as rule-only
    cfg = AppConfig(
        setup_completed=True,
        operational_mode=OperationalMode.RULE_ONLY,
    )
    save_config(cfg, cfg_file)

    res = runner.invoke(app, ["scan", str(folder), "--config", str(cfg_file)])
    assert res.exit_code == 0
    assert "Proposed Organization Plan (Dry-Run)" in res.stdout
    assert "Documents (1 file)" in res.stdout
    assert "Images (1 file)" in res.stdout
    assert "Summary: 2 files to organize across 2 destination folders" in res.stdout
    assert "Dry-run only: no files were moved" in res.stdout


def test_cli_scan_empty_directory(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    folder = tmp_path / "empty_dir"
    folder.mkdir()

    cfg = AppConfig(
        setup_completed=True,
        operational_mode=OperationalMode.RULE_ONLY,
    )
    save_config(cfg, cfg_file)

    res = runner.invoke(app, ["scan", str(folder), "--config", str(cfg_file)])
    assert res.exit_code == 0
    assert "No eligible files found to organize" in res.stdout


def test_cli_scan_interactive_mock_confirm(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    folder = tmp_path / "my_docs"
    folder.mkdir()
    (folder / "notes.txt").write_text("hello")

    cfg = AppConfig(
        setup_completed=True,
        operational_mode=OperationalMode.RULE_ONLY,
    )
    save_config(cfg, cfg_file)

    monkeypatch.setenv("ORGANIZER_FORCE_INTERACTIVE", "1")

    def mock_run_session(proposals, target_dir=None, console=None):
        return True, proposals

    monkeypatch.setattr("organizer.cli.run_interactive_plan_session", mock_run_session)

    res = runner.invoke(app, ["scan", str(folder), "--config", str(cfg_file)])
    assert res.exit_code == 0
    assert "Organization plan confirmed" in res.stdout


def test_cli_scan_interactive_mock_cancel(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    folder = tmp_path / "my_docs"
    folder.mkdir()
    (folder / "notes.txt").write_text("hello")

    cfg = AppConfig(
        setup_completed=True,
        operational_mode=OperationalMode.RULE_ONLY,
    )
    save_config(cfg, cfg_file)

    monkeypatch.setenv("ORGANIZER_FORCE_INTERACTIVE", "1")

    def mock_run_session(proposals, target_dir=None, console=None):
        return False, proposals

    monkeypatch.setattr("organizer.cli.run_interactive_plan_session", mock_run_session)

    res = runner.invoke(app, ["scan", str(folder), "--config", str(cfg_file)])
    assert res.exit_code == 0
    assert "Organization review cancelled" in res.stdout


def test_cli_models_status_and_doctor_gemini_mode(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-12345")

    cfg = AppConfig(
        setup_completed=True,
        operational_mode=OperationalMode.GEMINI,
        gemini_settings={"api_key": None, "model_name": "gemini-2.5-flash"},
    )
    save_config(cfg, cfg_file)

    from organizer.models.gemini_adapter import GeminiProviderAdapter
    monkeypatch.setattr(GeminiProviderAdapter, "run_smoke_test", lambda self: (True, "Gemini API test passed"))

    # Status
    res_status = runner.invoke(app, ["models", "status", "--config", str(cfg_file)])
    assert res_status.exit_code == 0
    assert "GEMINI" in res_status.stdout
    assert "gemini-2.5-flash" in res_status.stdout
    assert "Configured (Environment)" in res_status.stdout
    assert "Ready" in res_status.stdout

    # Doctor
    res_doc = runner.invoke(app, ["models", "doctor", "--config", str(cfg_file)])
    assert res_doc.exit_code == 0
    assert "Gemini API Key" in res_doc.stdout
    assert "PASSED" in res_doc.stdout


def test_cli_scan_non_interactive_renders_ai_star_indicator(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    folder = tmp_path / "my_docs"
    folder.mkdir()
    (folder / "bill.pdf").write_text("dummy")

    cfg = AppConfig(
        setup_completed=True,
        operational_mode=OperationalMode.GEMINI,
        gemini_settings={"api_key": "dummy-key", "model_name": "gemini-2.5-flash"},
    )
    save_config(cfg, cfg_file)

    from organizer.models.gemini_adapter import GeminiProviderAdapter
    from organizer.rules import ProposedMove

    def mock_classify(self, path, root):
        return ProposedMove(
            source_path=path,
            source_rel=path.name,
            proposed_category="Invoices",
            proposed_rel=f"Invoices/{path.name}",
            confidence=0.9,
            reason="AI detected invoice",
            is_ai_suggested=True,
        )

    monkeypatch.setattr(GeminiProviderAdapter, "classify_file", mock_classify)

    res = runner.invoke(app, ["scan", str(folder), "--non-interactive", "--config", str(cfg_file)])
    assert res.exit_code == 0
    assert "⭐" in res.stdout
    assert "Invoices" in res.stdout


def test_cli_models_status_and_doctor_openrouter_mode(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-testkey123")

    cfg = AppConfig(
        setup_completed=True,
        operational_mode=OperationalMode.OPENROUTER,
        openrouter_settings={"api_key": None, "model_name": "openrouter/free"},
    )
    save_config(cfg, cfg_file)

    from organizer.models.openrouter_adapter import OpenRouterProviderAdapter
    monkeypatch.setattr(OpenRouterProviderAdapter, "run_smoke_test", lambda self: (True, "OpenRouter test passed"))

    # Status
    res_status = runner.invoke(app, ["models", "status", "--config", str(cfg_file)])
    assert res_status.exit_code == 0
    assert "OPENROUTER" in res_status.stdout
    assert "openrouter/free" in res_status.stdout
    assert "Configured (Environment)" in res_status.stdout
    assert "Ready" in res_status.stdout

    # Doctor
    res_doc = runner.invoke(app, ["models", "doctor", "--config", str(cfg_file)])
    assert res_doc.exit_code == 0
    assert "OpenRouter API Key" in res_doc.stdout
    assert "PASSED" in res_doc.stdout


def test_cli_scan_openrouter_mode(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    folder = tmp_path / "my_docs"
    folder.mkdir()
    (folder / "statement.csv").write_text("dummy")

    cfg = AppConfig(
        setup_completed=True,
        operational_mode=OperationalMode.OPENROUTER,
        openrouter_settings={"api_key": "dummy-openrouter-key", "model_name": "openrouter/free"},
    )
    save_config(cfg, cfg_file)

    from organizer.models.openrouter_adapter import OpenRouterProviderAdapter
    from organizer.rules import ProposedMove

    def mock_classify(self, path, root):
        return ProposedMove(
            source_path=path,
            source_rel=path.name,
            proposed_category="Banking",
            proposed_rel=f"Banking/{path.name}",
            confidence=0.95,
            reason="OpenRouter parsed bank statement",
            is_ai_suggested=True,
        )

    monkeypatch.setattr(OpenRouterProviderAdapter, "classify_file", mock_classify)

    res = runner.invoke(app, ["scan", str(folder), "--non-interactive", "--config", str(cfg_file)])
    assert res.exit_code == 0
    assert "⭐" in res.stdout
    assert "Banking" in res.stdout


