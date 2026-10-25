"""Tests for FirstRunSetupWizard and deterministic rule-based organization."""

import io
from pathlib import Path
from rich.console import Console
import pytest

from organizer.config import OperationalMode, load_config
from organizer.models.adapter import OllamaProviderAdapter
from organizer.models.gemini_adapter import GeminiProviderAdapter
from organizer.models.openrouter_adapter import OpenRouterProviderAdapter
from organizer.models.lifecycle import LocalModelLifecycleService
from organizer.rules import classify_file_by_rules, scan_and_propose_tree
from organizer.testing.fake_ollama import FakeOllamaServer
from organizer.ui.setup import FirstRunSetupWizard


def test_deterministic_rules_classification(tmp_path: Path):
    root = tmp_path / "target_folder"
    root.mkdir()
    (root / "doc1.pdf").write_text("dummy")
    (root / "photo.png").write_text("dummy")
    (root / "archive.zip").write_text("dummy")
    (root / "script.py").write_text("dummy")
    (root / "unknown.xyz").write_text("dummy")

    proposals = scan_and_propose_tree(root)
    assert len(proposals) == 5

    cat_map = {p.source_path.name: p.proposed_category for p in proposals}
    assert cat_map["doc1.pdf"] == "Documents"
    assert cat_map["photo.png"] == "Images"
    assert cat_map["archive.zip"] == "Archives"
    assert cat_map["script.py"] == "Development"
    assert cat_map["unknown.xyz"] == "Other"


def test_setup_flow_continue_without_ai_when_runtime_missing(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    # Adapter pointing to unreachable port
    adapter = OllamaProviderAdapter("http://127.0.0.1:59999")
    service = LocalModelLifecycleService(adapter=adapter, config_path=cfg_file)

    # Input "1" means continue without AI
    wizard = FirstRunSetupWizard(
        service=service,
        console=Console(file=io.StringIO()),
        input_func=lambda prompt: "1",
    )
    result = wizard.run()
    assert result is True

    cfg = load_config(cfg_file)
    assert cfg.setup_completed is True
    assert cfg.operational_mode == OperationalMode.RULE_ONLY


def test_setup_flow_download_recommended_model(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    with FakeOllamaServer() as server:
        adapter = OllamaProviderAdapter(server.endpoint)
        service = LocalModelLifecycleService(adapter=adapter, config_path=cfg_file)

        # Responses:
        # Option 1 (recommended model)
        # Advisory override (if triggered by machine RAM): "y"
        # Confirm download: "y"
        inputs = iter(["1", "y", "y", "y"])
        wizard = FirstRunSetupWizard(
            service=service,
            console=Console(file=io.StringIO()),
            input_func=lambda prompt: next(inputs),
        )
        result = wizard.run()
        assert result is True

        cfg = load_config(cfg_file)
        assert cfg.setup_completed is True
        assert cfg.active_model == "gemma4:e2b"
        assert cfg.operational_mode == OperationalMode.AI


def test_setup_flow_use_already_installed_model(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    with FakeOllamaServer() as server:
        # Pre-install recommended model
        server.installed_models = [{"name": "gemma4:e2b", "size": 1600000000}]
        adapter = OllamaProviderAdapter(server.endpoint)
        service = LocalModelLifecycleService(adapter=adapter, config_path=cfg_file)

        # Input 1 selects the installed model directly
        wizard = FirstRunSetupWizard(
            service=service,
            console=Console(file=io.StringIO()),
            input_func=lambda prompt: "1",
        )
        result = wizard.run()
        assert result is True

        cfg = load_config(cfg_file)
        assert cfg.setup_completed is True
        assert cfg.active_model == "gemma4:e2b"


def test_setup_flow_exit_without_saving(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    with FakeOllamaServer() as server:
        adapter = OllamaProviderAdapter(server.endpoint)
        service = LocalModelLifecycleService(adapter=adapter, config_path=cfg_file)

        # Option "exit"
        wizard = FirstRunSetupWizard(
            service=service,
            console=Console(file=io.StringIO()),
            input_func=lambda prompt: "exit",
        )
        result = wizard.run()
        assert result is False

        # Config should still show setup incomplete
        cfg = load_config(cfg_file)
        assert cfg.setup_completed is False


def test_setup_flow_gemini_when_runtime_missing_with_env_key(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    adapter = OllamaProviderAdapter("http://127.0.0.1:59999")
    monkeypatch.setenv("GEMINI_API_KEY", "env-secret-key-12345")

    class MockGeminiAdapter(GeminiProviderAdapter):
        def run_smoke_test(self, timeout=None):
            return True, "Gemini OK"

    gemini_adapter = MockGeminiAdapter()
    service = LocalModelLifecycleService(
        adapter=adapter,
        gemini_adapter=gemini_adapter,
        config_path=cfg_file,
    )

    # Option "2": Use Google Gemini API
    # "y": Use detected key
    inputs = iter(["2", "y"])
    out = io.StringIO()
    wizard = FirstRunSetupWizard(
        service=service,
        console=Console(file=out),
        input_func=lambda prompt: next(inputs),
    )
    result = wizard.run()
    assert result is True

    cfg = load_config(cfg_file)
    assert cfg.setup_completed is True
    assert cfg.operational_mode == OperationalMode.GEMINI


def test_setup_flow_gemini_manual_key_entry(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    adapter = OllamaProviderAdapter("http://127.0.0.1:59999")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    class MockGeminiAdapter(GeminiProviderAdapter):
        def run_smoke_test(self, timeout=None):
            return True, "Gemini OK"

    gemini_adapter = MockGeminiAdapter()
    service = LocalModelLifecycleService(
        adapter=adapter,
        gemini_adapter=gemini_adapter,
        config_path=cfg_file,
    )

    # Option "2": Use Google Gemini API
    # "my-manual-key-999": API key
    inputs = iter(["2", "my-manual-key-999"])
    out = io.StringIO()
    wizard = FirstRunSetupWizard(
        service=service,
        console=Console(file=out),
        input_func=lambda prompt: next(inputs),
    )
    result = wizard.run()
    assert result is True

    cfg = load_config(cfg_file)
    assert cfg.setup_completed is True
    assert cfg.operational_mode == OperationalMode.GEMINI
    assert cfg.gemini_settings.api_key == "my-manual-key-999"


def test_setup_flow_gemini_selection_from_available_runtime_menu(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    monkeypatch.setenv("GEMINI_API_KEY", "env-key-abc")

    class MockGeminiAdapter(GeminiProviderAdapter):
        def run_smoke_test(self, timeout=None):
            return True, "Gemini OK"

    gemini_adapter = MockGeminiAdapter()

    with FakeOllamaServer() as server:
        adapter = OllamaProviderAdapter(server.endpoint)
        service = LocalModelLifecycleService(
            adapter=adapter,
            gemini_adapter=gemini_adapter,
            config_path=cfg_file,
        )

        # "g": Use Google Gemini API
        # "y": Confirm detected key
        inputs = iter(["g", "y"])
        out = io.StringIO()
        wizard = FirstRunSetupWizard(
            service=service,
            console=Console(file=out),
            input_func=lambda prompt: next(inputs),
        )
        result = wizard.run()
        assert result is True

        cfg = load_config(cfg_file)
        assert cfg.setup_completed is True
        assert cfg.operational_mode == OperationalMode.GEMINI


def test_setup_flow_select_gemini_by_number_when_runtime_available(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    monkeypatch.setenv("GEMINI_API_KEY", "env-key-number-2")

    class MockGeminiAdapter(GeminiProviderAdapter):
        def run_smoke_test(self, timeout=None):
            return True, "Gemini OK"

    gemini_adapter = MockGeminiAdapter()

    with FakeOllamaServer() as server:
        adapter = OllamaProviderAdapter(server.endpoint)
        service = LocalModelLifecycleService(
            adapter=adapter,
            gemini_adapter=gemini_adapter,
            config_path=cfg_file,
        )

        # "2": Use Google Gemini API
        # "y": Confirm detected key
        inputs = iter(["2", "y"])
        out = io.StringIO()
        wizard = FirstRunSetupWizard(
            service=service,
            console=Console(file=out),
            input_func=lambda prompt: next(inputs),
        )
        result = wizard.run()
        assert result is True

        cfg = load_config(cfg_file)
        assert cfg.setup_completed is True
        assert cfg.operational_mode == OperationalMode.GEMINI



def test_setup_flow_fallback_to_gemini_on_local_readiness_failure(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    monkeypatch.setenv("GEMINI_API_KEY", "env-key-xyz")

    class MockGeminiAdapter(GeminiProviderAdapter):
        def run_smoke_test(self, timeout=None):
            return True, "Gemini OK"

    gemini_adapter = MockGeminiAdapter()

    with FakeOllamaServer() as server:
        server.installed_models = [{"name": "gemma4:e2b", "size": 1600000000}]
        adapter = OllamaProviderAdapter(server.endpoint)
        adapter.run_smoke_test = lambda model_id, timeout=15.0: False

        service = LocalModelLifecycleService(
            adapter=adapter,
            gemini_adapter=gemini_adapter,
            config_path=cfg_file,
        )

        # "1": Choose installed model (readiness check will fail)
        # "1": Alternative option: Switch to Google Gemini API
        # "y": Confirm detected key
        inputs = iter(["1", "1", "y"])
        out = io.StringIO()
        wizard = FirstRunSetupWizard(
            service=service,
            console=Console(file=out),
            input_func=lambda prompt: next(inputs),
        )
        result = wizard.run()
        assert result is True

        cfg = load_config(cfg_file)
        assert cfg.setup_completed is True
        assert cfg.operational_mode == OperationalMode.GEMINI


def test_setup_flow_gemini_smoke_test_failure_and_cancel(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    adapter = OllamaProviderAdapter("http://127.0.0.1:59999")
    monkeypatch.setenv("GEMINI_API_KEY", "invalid-key")

    class MockFailingGeminiAdapter(GeminiProviderAdapter):
        def run_smoke_test(self, timeout=None):
            return False, "400 INVALID_ARGUMENT: API key not valid"

    gemini_adapter = MockFailingGeminiAdapter()
    service = LocalModelLifecycleService(
        adapter=adapter,
        gemini_adapter=gemini_adapter,
        config_path=cfg_file,
    )

    # "2": Use Gemini API
    # "y": Use detected key
    # "n": Retry prompt -> Decline retry
    inputs = iter(["2", "y", "n"])
    out = io.StringIO()
    wizard = FirstRunSetupWizard(
        service=service,
        console=Console(file=out),
        input_func=lambda prompt: next(inputs),
    )
    result = wizard.run()
    assert result is False

    cfg = load_config(cfg_file)
    assert cfg.setup_completed is False


def test_setup_flow_openrouter_when_runtime_missing_with_env_key(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    adapter = OllamaProviderAdapter("http://127.0.0.1:59999")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-env-123456789")

    class MockOpenRouterAdapter(OpenRouterProviderAdapter):
        def run_smoke_test(self, timeout=None):
            return True, "OpenRouter OK"

    openrouter_adapter = MockOpenRouterAdapter()
    service = LocalModelLifecycleService(
        adapter=adapter,
        openrouter_adapter=openrouter_adapter,
        config_path=cfg_file,
    )

    # "3": Use OpenRouter
    # "y": Confirm detected env key
    inputs = iter(["3", "y"])
    out = io.StringIO()
    wizard = FirstRunSetupWizard(
        service=service,
        console=Console(file=out),
        input_func=lambda prompt: next(inputs),
    )
    result = wizard.run()
    assert result is True

    cfg = load_config(cfg_file)
    assert cfg.setup_completed is True
    assert cfg.operational_mode == OperationalMode.OPENROUTER
    assert cfg.active_model == "openrouter/free"


def test_setup_flow_openrouter_when_runtime_available_with_manual_key(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    class MockOpenRouterAdapter(OpenRouterProviderAdapter):
        def run_smoke_test(self, timeout=None):
            return True, "OpenRouter OK"

    openrouter_adapter = MockOpenRouterAdapter()

    with FakeOllamaServer() as server:
        adapter = OllamaProviderAdapter(server.endpoint)
        service = LocalModelLifecycleService(
            adapter=adapter,
            openrouter_adapter=openrouter_adapter,
            config_path=cfg_file,
        )

        # "o": Use OpenRouter
        # manual key: "sk-or-v1-my-manual-key"
        inputs = iter(["o", "sk-or-v1-my-manual-key"])
        out = io.StringIO()
        wizard = FirstRunSetupWizard(
            service=service,
            console=Console(file=out),
            input_func=lambda prompt: next(inputs),
        )
        result = wizard.run()
        assert result is True

        cfg = load_config(cfg_file)
        assert cfg.setup_completed is True
        assert cfg.operational_mode == OperationalMode.OPENROUTER
        assert cfg.openrouter_settings.api_key == "sk-or-v1-my-manual-key"


def test_setup_flow_fallback_to_openrouter_on_local_readiness_failure(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    monkeypatch.setenv("OPENROUTER_API_KEY", "env-openrouter-key")

    class MockOpenRouterAdapter(OpenRouterProviderAdapter):
        def run_smoke_test(self, timeout=None):
            return True, "OpenRouter OK"

    openrouter_adapter = MockOpenRouterAdapter()

    with FakeOllamaServer() as server:
        server.installed_models = [{"name": "gemma4:e2b", "size": 1600000000}]
        adapter = OllamaProviderAdapter(server.endpoint)
        adapter.run_smoke_test = lambda model_id, timeout=15.0: False

        service = LocalModelLifecycleService(
            adapter=adapter,
            openrouter_adapter=openrouter_adapter,
            config_path=cfg_file,
        )

        # "1": Choose installed model (readiness check fails)
        # "2": Alternative option: Switch to OpenRouter
        # "y": Confirm detected key
        inputs = iter(["1", "2", "y"])
        out = io.StringIO()
        wizard = FirstRunSetupWizard(
            service=service,
            console=Console(file=out),
            input_func=lambda prompt: next(inputs),
        )
        result = wizard.run()
        assert result is True

        cfg = load_config(cfg_file)
        assert cfg.setup_completed is True
        assert cfg.operational_mode == OperationalMode.OPENROUTER


def test_setup_flow_openrouter_smoke_test_failure_and_cancel(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    adapter = OllamaProviderAdapter("http://127.0.0.1:59999")
    monkeypatch.setenv("OPENROUTER_API_KEY", "invalid-openrouter-key")

    class MockFailingOpenRouterAdapter(OpenRouterProviderAdapter):
        def run_smoke_test(self, timeout=None):
            return False, "401 Unauthorized: Invalid OpenRouter API key"

    openrouter_adapter = MockFailingOpenRouterAdapter()
    service = LocalModelLifecycleService(
        adapter=adapter,
        openrouter_adapter=openrouter_adapter,
        config_path=cfg_file,
    )

    # "3": Use OpenRouter
    # "y": Use detected key
    # "n": Retry prompt -> Decline retry
    inputs = iter(["3", "y", "n"])
    out = io.StringIO()
    wizard = FirstRunSetupWizard(
        service=service,
        console=Console(file=out),
        input_func=lambda prompt: next(inputs),
    )
    result = wizard.run()
    assert result is False

    cfg = load_config(cfg_file)
    assert cfg.setup_completed is False


def test_setup_flow_select_openrouter_by_number_when_runtime_available(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    monkeypatch.setenv("OPENROUTER_API_KEY", "env-key-number-3")

    class MockOpenRouterAdapter(OpenRouterProviderAdapter):
        def run_smoke_test(self, timeout=None):
            return True, "OpenRouter OK"

    openrouter_adapter = MockOpenRouterAdapter()

    with FakeOllamaServer() as server:
        adapter = OllamaProviderAdapter(server.endpoint)
        service = LocalModelLifecycleService(
            adapter=adapter,
            openrouter_adapter=openrouter_adapter,
            config_path=cfg_file,
        )

        # "3": Use OpenRouter
        # "y": Confirm detected key
        inputs = iter(["3", "y"])
        out = io.StringIO()
        wizard = FirstRunSetupWizard(
            service=service,
            console=Console(file=out),
            input_func=lambda prompt: next(inputs),
        )
        result = wizard.run()
        assert result is True

        cfg = load_config(cfg_file)
        assert cfg.setup_completed is True
        assert cfg.operational_mode == OperationalMode.OPENROUTER
        assert cfg.active_model == "openrouter/free"


