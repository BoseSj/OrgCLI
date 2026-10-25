"""Adapter for Ollama local HTTP API with strict loopback validation and streaming support."""

from dataclasses import dataclass
from enum import Enum
import json
import shutil
import threading
from typing import Any, Callable, Dict, Generator, List, Optional
import httpx
from pydantic import BaseModel, Field

from organizer.config import validate_loopback_endpoint


class RuntimeState(str, Enum):
    """Local runtime availability states."""

    READY = "ready"
    STOPPED = "stopped"
    NOT_INSTALLED = "not_installed"


@dataclass
class RuntimeCheckResult:
    """Result of checking local Ollama availability."""

    state: RuntimeState
    binary_path: Optional[str] = None
    endpoint: str = "http://localhost:11434"
    details: Optional[str] = None

    @property
    def is_available(self) -> bool:
        return self.state == RuntimeState.READY


class PullProgress(BaseModel):
    """Progress event emitted during model streaming pull."""

    status: str
    digest: Optional[str] = None
    total: Optional[int] = None
    completed: Optional[int] = None
    error: Optional[str] = None

    @property
    def has_bytes(self) -> bool:
        return self.total is not None and self.completed is not None and self.total > 0

    @property
    def percentage(self) -> Optional[float]:
        if self.has_bytes and self.total:
            return min(100.0, (self.completed / self.total) * 100.0)
        return None


class InstalledModel(BaseModel):
    """Information about a locally installed model."""

    name: str
    size: int = Field(default=0, description="Size on disk in bytes")
    modified_at: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    capabilities: List[str] = Field(default_factory=list)

    @property
    def size_gb(self) -> float:
        return round(self.size / (1024**3), 2)


class OllamaProviderAdapter:
    """Adapter communicating with Ollama via local loopback HTTP API."""

    def __init__(
        self,
        endpoint: str = "http://localhost:11434",
        timeout_seconds: float = 30.0,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self.endpoint = validate_loopback_endpoint(endpoint.rstrip("/"))
        self.timeout_seconds = timeout_seconds
        self._custom_client = client

    def _get_client(self, timeout: Optional[float] = None) -> httpx.Client:
        if self._custom_client:
            return self._custom_client
        return httpx.Client(timeout=timeout or self.timeout_seconds)

    def check_runtime(self) -> RuntimeCheckResult:
        """Inspect whether Ollama is installed on system and if API is responsive."""
        binary = shutil.which("ollama")

        # Try pinging loopback endpoint
        try:
            with self._get_client(timeout=3.0) as client:
                resp = client.get(f"{self.endpoint}/api/tags")
                if resp.status_code == 200:
                    return RuntimeCheckResult(
                        state=RuntimeState.READY,
                        binary_path=binary,
                        endpoint=self.endpoint,
                        details="Ollama is running and responding to local requests.",
                    )
        except Exception as exc:
            pass

        if binary:
            return RuntimeCheckResult(
                state=RuntimeState.STOPPED,
                binary_path=binary,
                endpoint=self.endpoint,
                details=(
                    f"Ollama binary found at '{binary}', but service is not running on {self.endpoint}. "
                    "Start it via 'ollama serve' or launch the Ollama macOS application."
                ),
            )

        return RuntimeCheckResult(
            state=RuntimeState.NOT_INSTALLED,
            binary_path=None,
            endpoint=self.endpoint,
            details=(
                "Ollama is not installed. Download and install it from https://ollama.com "
                "or via Homebrew ('brew install ollama')."
            ),
        )

    def list_installed_models(self) -> List[InstalledModel]:
        """Fetch all installed models from local Ollama runtime."""
        try:
            with self._get_client() as client:
                resp = client.get(f"{self.endpoint}/api/tags")
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Failed to communicate with Ollama at {self.endpoint}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Received malformed response from Ollama: {exc}") from exc

        models_raw = data.get("models", [])
        result: List[InstalledModel] = []
        for m in models_raw:
            try:
                result.append(
                    InstalledModel(
                        name=m.get("name") or m.get("model", "unknown"),
                        size=m.get("size", 0),
                        modified_at=m.get("modified_at"),
                        details=m.get("details", {}),
                        capabilities=m.get("capabilities", []),
                    )
                )
            except Exception:
                continue
        return result

    def inspect_model(self, model_id: str) -> Dict[str, Any]:
        """Query model details from local Ollama."""
        try:
            with self._get_client() as client:
                resp = client.post(
                    f"{self.endpoint}/api/show",
                    json={"model": model_id},
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Failed to inspect model '{model_id}': {exc}") from exc

    def pull_model_stream(
        self,
        model_id: str,
        cancel_event: Optional[threading.Event] = None,
    ) -> Generator[PullProgress, None, None]:
        """Stream model download progress from Ollama pull API with cancellation support."""
        url = f"{self.endpoint}/api/pull"
        payload = {"model": model_id, "stream": True}

        # Long timeout for model download streaming
        timeout = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)

        try:
            with httpx.stream("POST", url, json=payload, timeout=timeout) as response:
                if response.status_code != 200:
                    err_body = response.read().decode("utf-8", errors="replace")
                    yield PullProgress(
                        status="error",
                        error=f"HTTP {response.status_code}: {err_body}",
                    )
                    return

                for line in response.iter_lines():
                    if cancel_event and cancel_event.is_set():
                        yield PullProgress(status="cancelled", error="Download cancelled by user.")
                        return

                    if not line or not line.strip():
                        continue

                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        # Skip or report malformed line
                        continue

                    if "error" in chunk:
                        yield PullProgress(status="error", error=chunk["error"])
                        return

                    yield PullProgress(
                        status=chunk.get("status", "downloading"),
                        digest=chunk.get("digest"),
                        total=chunk.get("total"),
                        completed=chunk.get("completed"),
                    )

        except (httpx.RequestError, httpx.TimeoutException) as exc:
            if cancel_event and cancel_event.is_set():
                yield PullProgress(status="cancelled", error="Download cancelled by user.")
            else:
                yield PullProgress(status="error", error=f"Network error during pull: {exc}")

    def run_smoke_test(self, model_id: str, timeout: float = 15.0) -> bool:
        """Execute a minimal deterministic smoke test query to verify model readiness."""
        url = f"{self.endpoint}/api/generate"
        payload = {
            "model": model_id,
            "prompt": "Hello",
            "stream": False,
            "options": {"num_predict": 2},
        }

        try:
            with self._get_client(timeout=timeout) as client:
                resp = client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("done", False) is True or "response" in data
                return False
        except Exception:
            return False

    def delete_model(self, model_id: str) -> bool:
        """Request deletion of a local model via Ollama."""
        url = f"{self.endpoint}/api/delete"
        payload = {"model": model_id}

        try:
            with self._get_client() as client:
                # Ollama delete endpoint accepts DELETE request with json payload
                req = client.build_request("DELETE", url, json=payload)
                resp = client.send(req)
                return resp.status_code == 200
        except Exception as exc:
            raise RuntimeError(f"Failed to delete model '{model_id}': {exc}") from exc
