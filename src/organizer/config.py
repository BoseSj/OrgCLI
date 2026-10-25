"""Configuration management for the organizer application."""

from enum import Enum
import ipaddress
import json
import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


class OperationalMode(str, Enum):
    """Operational mode of the organizer."""

    AI = "ai"
    GEMINI = "gemini"
    OPENROUTER = "openrouter"
    RULE_ONLY = "rule-only"


class NonLoopbackEndpointError(ValueError):
    """Raised when an inference endpoint is not on the local loopback."""

    pass


def is_loopback_host(hostname: str) -> bool:
    """Check if a hostname or IP string represents a local loopback address."""
    if not hostname:
        return False
    lower_host = hostname.lower()
    if lower_host in ("localhost", "127.0.0.1", "::1", "[::1]"):
        return True
    try:
        ip = ipaddress.ip_address(lower_host.strip("[]"))
        return ip.is_loopback
    except ValueError:
        return False


def validate_loopback_endpoint(url: str) -> str:
    """Validate that the given URL points strictly to a local loopback address.

    Raises:
        NonLoopbackEndpointError: If the URL points to a non-loopback address.
        ValueError: If the URL is invalid.
    """
    if not url:
        raise ValueError("Endpoint URL cannot be empty.")

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme '{parsed.scheme}'. Must be 'http' or 'https'.")

    host = parsed.hostname
    if not host or not is_loopback_host(host):
        raise NonLoopbackEndpointError(
            f"Strict local-only policy violation: Endpoint '{url}' does not resolve to a local loopback address. "
            "Only 'localhost' or '127.0.0.1' is permitted for privacy."
        )

    return url


class ModelSettings(BaseModel):
    """Configuration for local model runtime integration."""

    endpoint: str = Field(default="http://localhost:11434")
    context_length: int = Field(default=2048, ge=512, le=32768)
    timeout_seconds: float = Field(default=30.0, ge=1.0, le=600.0)

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, v: str) -> str:
        return validate_loopback_endpoint(v)


class GeminiSettings(BaseModel):
    """Configuration for Google Gemini cloud API integration."""

    model_name: str = Field(default="gemini-3.8-flash")
    api_key: Optional[str] = Field(
        default=None,
        description="Explicit API key override; defaults to GEMINI_API_KEY environment variable",
    )
    timeout_seconds: float = Field(default=30.0, ge=1.0, le=600.0)


class OpenRouterSettings(BaseModel):
    """Configuration for OpenRouter cloud API integration."""

    model_name: str = Field(default="openrouter/free")
    api_key: Optional[str] = Field(
        default=None,
        description="Explicit API key override; defaults to OPENROUTER_API_KEY environment variable",
    )
    base_url: str = Field(default="https://openrouter.ai/api/v1")
    timeout_seconds: float = Field(default=30.0, ge=1.0, le=600.0)
    app_referer: str = Field(default="https://github.com/local-folder-organizer")
    app_title: str = Field(default="Local Folder Organizer")


class AppConfig(BaseModel):
    """Application-wide configuration."""

    config_version: int = 1
    setup_completed: bool = False
    operational_mode: OperationalMode = OperationalMode.AI
    active_model: Optional[str] = None
    model_settings: ModelSettings = Field(default_factory=ModelSettings)
    gemini_settings: GeminiSettings = Field(default_factory=GeminiSettings)
    openrouter_settings: OpenRouterSettings = Field(default_factory=OpenRouterSettings)


def get_default_config_path() -> Path:
    """Resolve the default configuration file location."""
    override = os.environ.get("ORGANIZER_CONFIG_PATH")
    if override:
        return Path(override).expanduser().resolve()
    base_dir = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()
    return (base_dir / "organizer" / "config.json").resolve()


def load_config(config_path: Optional[Path] = None) -> AppConfig:
    """Load application configuration from file, or return default if absent."""
    path = config_path or get_default_config_path()
    if not path.exists():
        return AppConfig()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return AppConfig.model_validate(data)
    except Exception:
        # If config is corrupt or invalid, return default config
        return AppConfig()


def save_config(config: AppConfig, config_path: Optional[Path] = None) -> Path:
    """Save application configuration to disk atomically."""
    path = config_path or get_default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = path.with_suffix(".tmp")
    data = config.model_dump(mode="json")
    temp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temp_path.replace(path)
    return path
