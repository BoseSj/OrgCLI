"""Unit tests for OpenRouterProviderAdapter."""

import json
from pathlib import Path
from unittest.mock import MagicMock
import httpx
import pytest

from organizer.models.openrouter_adapter import OpenRouterProviderAdapter


def test_openrouter_credentials_from_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-abc123456789")
    adapter = OpenRouterProviderAdapter()
    cred = adapter.check_credentials()
    assert cred.is_available is True
    assert cred.api_key_configured is True
    assert cred.model_name == "openrouter/free"


def test_openrouter_credentials_missing(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    adapter = OpenRouterProviderAdapter(api_key=None)
    cred = adapter.check_credentials()
    assert cred.is_available is False
    assert cred.api_key_configured is False
    assert "not set" in cred.message


def test_openrouter_credentials_from_init():
    adapter = OpenRouterProviderAdapter(api_key="sk-explicit-key", model_name="custom/model")
    cred = adapter.check_credentials()
    assert cred.is_available is True
    assert cred.api_key_configured is True
    assert cred.model_name == "custom/model"


def test_openrouter_smoke_test_success():
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "OK"}}]
    }
    mock_client.post.return_value = mock_resp

    adapter = OpenRouterProviderAdapter(api_key="test-key", client=mock_client)
    ok, msg = adapter.run_smoke_test()
    assert ok is True
    assert "responded successfully" in msg
    mock_client.post.assert_called_once()


def test_openrouter_smoke_test_failure_status():
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = '{"error": {"message": "Invalid API key"}}'
    mock_client.post.return_value = mock_resp

    adapter = OpenRouterProviderAdapter(api_key="test-key", client=mock_client)
    ok, msg = adapter.run_smoke_test()
    assert ok is False
    assert "HTTP 401" in msg


def test_openrouter_smoke_test_exception():
    mock_client = MagicMock()
    mock_client.post.side_effect = httpx.ConnectError("Connection refused")

    adapter = OpenRouterProviderAdapter(api_key="test-key", client=mock_client)
    ok, msg = adapter.run_smoke_test()
    assert ok is False
    assert "Connection refused" in msg


def test_openrouter_classify_file_success(tmp_path: Path):
    doc = tmp_path / "invoice_101.pdf"
    doc.write_text("Invoice: $450 due next month", encoding="utf-8")

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "category": "Invoices",
                        "reason": "Document is a billing invoice"
                    })
                }
            }
        ]
    }
    mock_client.post.return_value = mock_resp

    adapter = OpenRouterProviderAdapter(api_key="test-key", client=mock_client)
    proposal = adapter.classify_file(doc, tmp_path)

    assert proposal.proposed_category == "Invoices"
    assert proposal.proposed_rel == "Invoices/invoice_101.pdf"
    assert "billing invoice" in proposal.reason
    assert proposal.is_ai_suggested is True


def test_openrouter_classify_file_markdown_fenced_json(tmp_path: Path):
    doc = tmp_path / "script.py"
    doc.write_text("print('hello')", encoding="utf-8")

    fenced_content = "```json\n{\"category\": \"Source Code\", \"reason\": \"Python script\"}\n```"
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": fenced_content}}]
    }
    mock_client.post.return_value = mock_resp

    adapter = OpenRouterProviderAdapter(api_key="test-key", client=mock_client)
    proposal = adapter.classify_file(doc, tmp_path)

    assert proposal.proposed_category == "Source Code"
    assert proposal.is_ai_suggested is True


def test_openrouter_classify_file_fallback_on_error(tmp_path: Path):
    doc = tmp_path / "doc.unknown"
    doc.write_text("misc content", encoding="utf-8")

    mock_client = MagicMock()
    mock_client.post.side_effect = httpx.TimeoutException("Request timed out")

    adapter = OpenRouterProviderAdapter(api_key="test-key", client=mock_client)
    proposal = adapter.classify_file(doc, tmp_path)

    assert proposal.source_path == doc
    assert "Rule fallback" in proposal.reason
    assert proposal.is_ai_suggested is False
