"""Deterministic Fake Ollama HTTP Server for testing."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time
from typing import Any, Dict, List, Optional


class FakeOllamaHandler(BaseHTTPRequestHandler):
    """HTTP request handler simulating Ollama endpoints."""

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress standard logging to keep test output clean
        pass

    @property
    def server_state(self) -> "FakeOllamaServer":
        return self.server  # type: ignore

    def do_GET(self) -> None:
        if self.path == "/api/tags":
            if self.server_state.malformed_tags_response:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b"this is not valid json")
                return

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = {"models": self.server_state.installed_models}
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {}

        if self.path == "/api/show":
            model = payload.get("model", "")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {
                "modelfile": f"FROM {model}",
                "details": {"format": "gguf", "family": "gemma", "parameter_size": "2B"},
                "model_info": {"general.architecture": "gemma"},
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        if self.path == "/api/pull":
            model = payload.get("model", "")
            if self.server_state.fail_pull:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"model not found")
                return

            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.end_headers()

            chunks = self.server_state.custom_pull_chunks
            if chunks is None:
                if self.server_state.progress_without_bytes:
                    chunks = [
                        {"status": "pulling manifest"},
                        {"status": "verifying sha256 digest"},
                        {"status": "writing manifest"},
                        {"status": "success"},
                    ]
                else:
                    total = 1_000_000
                    chunks = [
                        {"status": "pulling manifest"},
                        {"status": "downloading", "total": total, "completed": 250_000},
                        {"status": "downloading", "total": total, "completed": 750_000},
                        {"status": "downloading", "total": total, "completed": total},
                        {"status": "success"},
                    ]

            for chunk in chunks:
                if self.server_state.slow_pull_delay > 0:
                    time.sleep(self.server_state.slow_pull_delay)
                line = json.dumps(chunk) + "\n"
                try:
                    self.wfile.write(line.encode("utf-8"))
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    # Client aborted/cancelled
                    return

            # If pull succeeds, add model to installed_models
            if not any("error" in c for c in chunks):
                self.server_state.installed_models.append(
                    {
                        "name": model,
                        "model": model,
                        "size": 1_600_000_000,
                        "details": {"family": "gemma"},
                    }
                )
            return

        if self.path == "/api/generate":
            if self.server_state.fail_smoke_test:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b'{"error": "smoke test failed"}')
                return

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"response": "Hello world", "done": true}')
            return

        self.send_response(404)
        self.end_headers()

    def do_DELETE(self) -> None:
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {}

        if self.path == "/api/delete":
            model = payload.get("model", "")
            self.server_state.installed_models = [
                m for m in self.server_state.installed_models if m.get("name") != model
            ]
            self.send_response(200)
            self.end_headers()
            return

        self.send_response(404)
        self.end_headers()


class FakeOllamaServer(ThreadingHTTPServer):
    """Threading HTTP Server that runs a simulated Ollama instance on local loopback."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        super().__init__((host, port), FakeOllamaHandler)
        self.installed_models: List[Dict[str, Any]] = []
        self.fail_pull: bool = False
        self.fail_smoke_test: bool = False
        self.progress_without_bytes: bool = False
        self.malformed_tags_response: bool = False
        self.slow_pull_delay: float = 0.0
        self.custom_pull_chunks: Optional[List[Dict[str, Any]]] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def endpoint(self) -> str:
        host, port = self.server_address
        return f"http://{host}:{port}"

    def start(self) -> "FakeOllamaServer":
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self.shutdown()
        self.server_close()
        if self._thread:
            self._thread.join(timeout=2.0)

    def __enter__(self) -> "FakeOllamaServer":
        return self.start()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()
