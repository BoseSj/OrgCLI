"""Tests for organizer.models.adapter and fake_ollama test server."""

import threading
import time
import pytest

from organizer.config import NonLoopbackEndpointError
from organizer.models.adapter import (
    OllamaProviderAdapter,
    PullProgress,
    RuntimeState,
)
from organizer.testing.fake_ollama import FakeOllamaServer


def test_adapter_rejects_non_loopback():
    with pytest.raises(NonLoopbackEndpointError):
        OllamaProviderAdapter("http://remote-server.com:11434")


def test_adapter_runtime_check_ready():
    with FakeOllamaServer() as server:
        adapter = OllamaProviderAdapter(server.endpoint)
        check = adapter.check_runtime()
        assert check.is_available is True
        assert check.state == RuntimeState.READY


def test_adapter_list_installed_models():
    with FakeOllamaServer() as server:
        server.installed_models = [
            {"name": "gemma4:e2b", "size": 1600000000, "details": {"family": "gemma"}}
        ]
        adapter = OllamaProviderAdapter(server.endpoint)
        models = adapter.list_installed_models()
        assert len(models) == 1
        assert models[0].name == "gemma4:e2b"
        assert models[0].size_gb == 1.49


def test_adapter_pull_stream_with_byte_progress():
    with FakeOllamaServer() as server:
        adapter = OllamaProviderAdapter(server.endpoint)
        events = list(adapter.pull_model_stream("gemma4:e2b"))
        assert len(events) >= 3
        # Check that byte progress was captured
        byte_events = [e for e in events if e.has_bytes]
        assert len(byte_events) >= 2
        assert byte_events[0].completed == 250_000
        assert byte_events[0].percentage == 25.0
        assert byte_events[-1].percentage == 100.0


def test_adapter_pull_stream_without_byte_counts():
    with FakeOllamaServer() as server:
        server.progress_without_bytes = True
        adapter = OllamaProviderAdapter(server.endpoint)
        events = list(adapter.pull_model_stream("gemma4:e2b"))
        assert len(events) > 0
        for e in events:
            assert e.has_bytes is False
            assert e.percentage is None
            assert e.status is not None


def test_adapter_pull_stream_cancellation():
    with FakeOllamaServer() as server:
        server.slow_pull_delay = 0.05
        adapter = OllamaProviderAdapter(server.endpoint)

        cancel_event = threading.Event()

        # Trigger cancellation after brief delay
        def trigger_cancel():
            time.sleep(0.06)
            cancel_event.set()

        t = threading.Thread(target=trigger_cancel)
        t.start()

        events = list(adapter.pull_model_stream("gemma4:e2b", cancel_event=cancel_event))
        t.join()

        assert any(e.status == "cancelled" for e in events)


def test_adapter_pull_stream_failure():
    with FakeOllamaServer() as server:
        server.fail_pull = True
        adapter = OllamaProviderAdapter(server.endpoint)
        events = list(adapter.pull_model_stream("missing_model"))
        assert len(events) == 1
        assert events[0].status == "error"
        assert "HTTP 404" in (events[0].error or "")


def test_adapter_smoke_test():
    with FakeOllamaServer() as server:
        adapter = OllamaProviderAdapter(server.endpoint)
        assert adapter.run_smoke_test("gemma4:e2b") is True

        server.fail_smoke_test = True
        assert adapter.run_smoke_test("gemma4:e2b") is False


def test_adapter_delete_model():
    with FakeOllamaServer() as server:
        server.installed_models = [{"name": "gemma4:e2b", "size": 1000}]
        adapter = OllamaProviderAdapter(server.endpoint)
        assert len(adapter.list_installed_models()) == 1

        deleted = adapter.delete_model("gemma4:e2b")
        assert deleted is True
        assert len(adapter.list_installed_models()) == 0


def test_adapter_malformed_response():
    with FakeOllamaServer() as server:
        server.malformed_tags_response = True
        adapter = OllamaProviderAdapter(server.endpoint)
        with pytest.raises(RuntimeError, match="malformed response"):
            adapter.list_installed_models()
