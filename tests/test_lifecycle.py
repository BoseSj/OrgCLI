"""Tests for organizer.models.lifecycle module."""

from pathlib import Path
import threading
import pytest

from organizer.config import OperationalMode, load_config
from organizer.models.adapter import OllamaProviderAdapter
from organizer.models.catalog import Modality, ModelCatalog
from organizer.models.lifecycle import (
    LocalModelLifecycleService,
    ModelReadinessState,
)
from organizer.testing.fake_ollama import FakeOllamaServer


def test_lifecycle_discovery(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    with FakeOllamaServer() as server:
        server.installed_models = [
            {"name": "gemma4:e2b", "size": 1600000000, "details": {"family": "gemma"}}
        ]
        adapter = OllamaProviderAdapter(server.endpoint)
        service = LocalModelLifecycleService(adapter=adapter, config_path=cfg_file)

        discovered = service.discover_local_models()
        assert len(discovered) == 1
        assert discovered[0].name == "gemma4:e2b"
        assert discovered[0].catalog_entry is not None
        assert discovered[0].catalog_entry.display_name == "Gemma 4 E2B (Multimodal)"


def test_lifecycle_verify_capabilities(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    with FakeOllamaServer() as server:
        adapter = OllamaProviderAdapter(server.endpoint)
        service = LocalModelLifecycleService(adapter=adapter, config_path=cfg_file)

        # Gemma 4 E2B supports vision
        assert service.verify_capabilities("gemma4:e2b", [Modality.TEXT, Modality.IMAGE]) is True
        # Gemma 2 2B does not support vision
        assert service.verify_capabilities("gemma2:2b", [Modality.TEXT, Modality.IMAGE]) is False
        assert service.verify_capabilities("gemma2:2b", [Modality.TEXT]) is True


def test_lifecycle_readiness_checks(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    with FakeOllamaServer() as server:
        adapter = OllamaProviderAdapter(server.endpoint)
        service = LocalModelLifecycleService(adapter=adapter, config_path=cfg_file)

        # Model not in installed tags
        r1 = service.verify_readiness("gemma4:e2b")
        assert r1.is_ready is False
        assert r1.state == ModelReadinessState.NOT_INSTALLED

        # Model installed, but smoke test fails
        server.installed_models = [{"name": "gemma4:e2b", "size": 1600000000}]
        server.fail_smoke_test = True
        r2 = service.verify_readiness("gemma4:e2b")
        assert r2.is_ready is False
        assert r2.state == ModelReadinessState.SMOKE_TEST_FAILED

        # Model installed, smoke test passes
        server.fail_smoke_test = False
        r3 = service.verify_readiness("gemma4:e2b")
        assert r3.is_ready is True
        assert r3.state == ModelReadinessState.READY


def test_lifecycle_pull_orchestration(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    with FakeOllamaServer() as server:
        adapter = OllamaProviderAdapter(server.endpoint)
        service = LocalModelLifecycleService(adapter=adapter, config_path=cfg_file)

        progress_reports = []
        success = service.pull_model(
            "gemma4:e2b",
            progress_callback=lambda p: progress_reports.append(p.status),
        )
        assert success is True
        assert "success" in progress_reports
        # After pull, model is in installed_models
        assert any(m["name"] == "gemma4:e2b" for m in server.installed_models)


def test_lifecycle_pull_cancellation(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    with FakeOllamaServer() as server:
        server.slow_pull_delay = 0.05
        adapter = OllamaProviderAdapter(server.endpoint)
        service = LocalModelLifecycleService(adapter=adapter, config_path=cfg_file)

        cancel_event = threading.Event()
        cancel_event.set()  # Cancel immediately

        success = service.pull_model("gemma4:e2b", cancel_event=cancel_event)
        assert success is False


def test_lifecycle_set_active_model_and_persistence(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    with FakeOllamaServer() as server:
        server.installed_models = [{"name": "gemma4:e2b", "size": 1600000000}]
        adapter = OllamaProviderAdapter(server.endpoint)
        service = LocalModelLifecycleService(adapter=adapter, config_path=cfg_file)

        res = service.set_active_model("gemma4:e2b")
        assert res.is_ready is True

        # Check saved configuration
        saved = load_config(cfg_file)
        assert saved.setup_completed is True
        assert saved.active_model == "gemma4:e2b"
        assert saved.operational_mode == OperationalMode.AI


def test_lifecycle_enable_rule_only_mode(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    with FakeOllamaServer() as server:
        adapter = OllamaProviderAdapter(server.endpoint)
        service = LocalModelLifecycleService(adapter=adapter, config_path=cfg_file)

        service.enable_rule_only_mode()
        saved = load_config(cfg_file)
        assert saved.setup_completed is True
        assert saved.operational_mode == OperationalMode.RULE_ONLY


def test_lifecycle_remove_model(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    with FakeOllamaServer() as server:
        server.installed_models = [{"name": "gemma4:e2b", "size": 1600000000}]
        adapter = OllamaProviderAdapter(server.endpoint)
        service = LocalModelLifecycleService(adapter=adapter, config_path=cfg_file)
        service.set_active_model("gemma4:e2b")

        # Removing active model deletes it and resets active_model in config
        removed = service.remove_model("gemma4:e2b")
        assert removed is True
        saved = load_config(cfg_file)
        assert saved.active_model is None


def test_lifecycle_diagnostics(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    with FakeOllamaServer() as server:
        server.installed_models = [{"name": "gemma4:e2b", "size": 1600000000}]
        adapter = OllamaProviderAdapter(server.endpoint)
        service = LocalModelLifecycleService(adapter=adapter, config_path=cfg_file)
        service.set_active_model("gemma4:e2b")

        report = service.run_diagnostics()
        assert report.diagnostics_passed is True
        assert report.installed_models_count == 1
        assert report.active_model == "gemma4:e2b"


def test_lifecycle_gemini_mode(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    from unittest.mock import MagicMock
    from organizer.models.gemini_adapter import GeminiProviderAdapter

    mock_gemini = MagicMock(spec=GeminiProviderAdapter)
    mock_gemini.model_name = "gemini-2.5-flash"
    mock_gemini.run_smoke_test.return_value = (True, "Gemini OK")
    mock_gemini.check_credentials.return_value = MagicMock(is_available=True, message="OK")

    service = LocalModelLifecycleService(
        config_path=cfg_file,
        gemini_adapter=mock_gemini,
    )

    result = service.enable_gemini_mode(api_key="custom-key")
    assert result.is_ready is True
    assert service.config.operational_mode == OperationalMode.GEMINI
    assert service.config.active_model == "gemini-2.5-flash"
    assert service.config.gemini_settings.api_key == "custom-key"

    readiness = service.verify_readiness()
    assert readiness.is_ready is True
    assert readiness.state == ModelReadinessState.READY

    report = service.run_diagnostics()
    assert report.diagnostics_passed is True


def test_lifecycle_openrouter_mode(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    from unittest.mock import MagicMock
    from organizer.models.openrouter_adapter import OpenRouterProviderAdapter

    mock_openrouter = MagicMock(spec=OpenRouterProviderAdapter)
    mock_openrouter.model_name = "openrouter/free"
    mock_openrouter.run_smoke_test.return_value = (True, "OpenRouter OK")
    mock_openrouter.check_credentials.return_value = MagicMock(is_available=True, message="OK")

    service = LocalModelLifecycleService(
        config_path=cfg_file,
        openrouter_adapter=mock_openrouter,
    )

    result = service.enable_openrouter_mode(api_key="sk-or-v1-test")
    assert result.is_ready is True
    assert service.config.operational_mode == OperationalMode.OPENROUTER
    assert service.config.active_model == "openrouter/free"
    assert service.config.openrouter_settings.api_key == "sk-or-v1-test"

    readiness = service.verify_readiness()
    assert readiness.is_ready is True
    assert readiness.state == ModelReadinessState.READY

    report = service.run_diagnostics()
    assert report.diagnostics_passed is True

