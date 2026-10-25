"""Tests for organizer.config module."""

from pathlib import Path
import pytest

from organizer.config import (
    AppConfig,
    GeminiSettings,
    ModelSettings,
    NonLoopbackEndpointError,
    OpenRouterSettings,
    OperationalMode,
    is_loopback_host,
    load_config,
    save_config,
    validate_loopback_endpoint,
)


def test_is_loopback_host():
    assert is_loopback_host("localhost")
    assert is_loopback_host("127.0.0.1")
    assert is_loopback_host("127.0.1.1")
    assert is_loopback_host("::1")
    assert is_loopback_host("[::1]")
    assert not is_loopback_host("example.com")
    assert not is_loopback_host("192.168.1.1")
    assert not is_loopback_host("8.8.8.8")
    assert not is_loopback_host("")


def test_validate_loopback_endpoint_valid():
    assert validate_loopback_endpoint("http://localhost:11434") == "http://localhost:11434"
    assert validate_loopback_endpoint("http://127.0.0.1:11434") == "http://127.0.0.1:11434"
    assert validate_loopback_endpoint("http://[::1]:11434") == "http://[::1]:11434"


def test_validate_loopback_endpoint_rejected():
    with pytest.raises(NonLoopbackEndpointError):
        validate_loopback_endpoint("http://api.openai.com/v1")

    with pytest.raises(NonLoopbackEndpointError):
        validate_loopback_endpoint("http://192.168.1.50:11434")

    with pytest.raises(ValueError, match="Invalid URL scheme"):
        validate_loopback_endpoint("ftp://localhost:11434")


def test_config_save_and_load(tmp_path: Path):
    cfg_file = tmp_path / "organizer" / "config.json"
    cfg = AppConfig(
        setup_completed=True,
        operational_mode=OperationalMode.RULE_ONLY,
        active_model="gemma4:e2b",
        model_settings=ModelSettings(
            endpoint="http://127.0.0.1:11434",
            context_length=4096,
        ),
    )

    saved_path = save_config(cfg, cfg_file)
    assert saved_path == cfg_file
    assert cfg_file.exists()

    loaded = load_config(cfg_file)
    assert loaded.setup_completed is True
    assert loaded.operational_mode == OperationalMode.RULE_ONLY
    assert loaded.active_model == "gemma4:e2b"
    assert loaded.model_settings.endpoint == "http://127.0.0.1:11434"
    assert loaded.model_settings.context_length == 4096


def test_load_nonexistent_or_corrupt_config(tmp_path: Path):
    nonexistent = tmp_path / "missing.json"
    cfg = load_config(nonexistent)
    assert cfg.setup_completed is False
    assert cfg.operational_mode == OperationalMode.AI

    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{not valid json", encoding="utf-8")
    cfg2 = load_config(corrupt)
    assert cfg2.setup_completed is False


def test_config_gemini_settings(tmp_path: Path):
    cfg_file = tmp_path / "organizer" / "gemini_config.json"
    cfg = AppConfig(
        setup_completed=True,
        operational_mode=OperationalMode.GEMINI,
        active_model="gemini-3.8-flash",
        gemini_settings=GeminiSettings(
            model_name="gemini-3.8-flash",
            api_key="test-api-key",
            timeout_seconds=45.0,
        ),
    )
    save_config(cfg, cfg_file)
    loaded = load_config(cfg_file)
    assert loaded.setup_completed is True
    assert loaded.operational_mode == OperationalMode.GEMINI
    assert loaded.active_model == "gemini-3.8-flash"
    assert loaded.gemini_settings.model_name == "gemini-3.8-flash"
    assert loaded.gemini_settings.api_key == "test-api-key"
    assert loaded.gemini_settings.timeout_seconds == 45.0


def test_config_openrouter_settings(tmp_path: Path):
    cfg_file = tmp_path / "organizer" / "openrouter_config.json"
    cfg = AppConfig(
        setup_completed=True,
        operational_mode=OperationalMode.OPENROUTER,
        active_model="openrouter/free",
        openrouter_settings=OpenRouterSettings(
            model_name="openrouter/free",
            api_key="sk-or-test-key",
            timeout_seconds=25.0,
        ),
    )
    save_config(cfg, cfg_file)
    loaded = load_config(cfg_file)
    assert loaded.setup_completed is True
    assert loaded.operational_mode == OperationalMode.OPENROUTER
    assert loaded.active_model == "openrouter/free"
    assert loaded.openrouter_settings.model_name == "openrouter/free"
    assert loaded.openrouter_settings.api_key == "sk-or-test-key"
    assert loaded.openrouter_settings.timeout_seconds == 25.0


