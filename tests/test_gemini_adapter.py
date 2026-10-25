"""Unit tests for GeminiProviderAdapter."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from organizer.models.gemini_adapter import GeminiProviderAdapter, GeminiCheckResult


def test_check_credentials_missing_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    adapter = GeminiProviderAdapter(api_key=None)
    result = adapter.check_credentials()
    assert result.is_available is False
    assert result.api_key_configured is False
    assert "not set" in result.message


def test_check_credentials_explicit_or_env(monkeypatch):
    # Test explicit key
    adapter1 = GeminiProviderAdapter(api_key="explicit-key")
    res1 = adapter1.check_credentials()
    assert res1.is_available is True
    assert res1.api_key_configured is True

    # Test env var
    monkeypatch.setenv("GEMINI_API_KEY", "env-key")
    adapter2 = GeminiProviderAdapter(api_key=None)
    res2 = adapter2.check_credentials()
    assert res2.is_available is True
    assert res2.api_key_configured is True


def test_get_client_missing_key_raises(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    adapter = GeminiProviderAdapter(api_key=None)
    with pytest.raises(ValueError, match="GEMINI_API_KEY is not set"):
        adapter.get_client()


def test_run_smoke_test_success():
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = "OK"
    mock_client.models.generate_content.return_value = mock_resp

    adapter = GeminiProviderAdapter(api_key="dummy", client=mock_client)
    success, msg = adapter.run_smoke_test()
    assert success is True
    assert "responded successfully" in msg
    mock_client.models.generate_content.assert_called_once()


def test_run_smoke_test_failure():
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("Quota exceeded")

    adapter = GeminiProviderAdapter(api_key="dummy", client=mock_client)
    success, msg = adapter.run_smoke_test()
    assert success is False
    assert "Quota exceeded" in msg


def test_classify_file_text_success(tmp_path: Path):
    doc = tmp_path / "invoice.txt"
    doc.write_text("Invoice: $250 for design services", encoding="utf-8")

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = "CATEGORY: Invoices | REASON: Document references invoiced design services"
    mock_client.models.generate_content.return_value = mock_resp

    adapter = GeminiProviderAdapter(api_key="dummy", client=mock_client)
    proposal = adapter.classify_file(doc, tmp_path)

    assert proposal.proposed_category == "Invoices"
    assert proposal.proposed_rel == "Invoices/invoice.txt"
    assert "invoiced design services" in proposal.reason
    assert proposal.confidence == 0.9
    assert proposal.is_ai_suggested is True


def test_classify_file_image_multimodal(tmp_path: Path):
    img = tmp_path / "photo.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = "CATEGORY: Photographs | REASON: Visual landscape capture"
    mock_client.models.generate_content.return_value = mock_resp

    adapter = GeminiProviderAdapter(api_key="dummy", client=mock_client)
    proposal = adapter.classify_file(img, tmp_path)

    assert proposal.proposed_category == "Photographs"
    assert proposal.proposed_rel == "Photographs/photo.png"
    assert "Visual landscape capture" in proposal.reason
    assert proposal.is_ai_suggested is True
    mock_client.models.generate_content.assert_called_once()


def test_classify_file_fallback_on_error(tmp_path: Path):
    doc = tmp_path / "data.csv"
    doc.write_text("a,b,c\n1,2,3", encoding="utf-8")

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = ConnectionError("Network unreachable")

    adapter = GeminiProviderAdapter(api_key="dummy", client=mock_client)
    proposal = adapter.classify_file(doc, tmp_path)

    assert proposal.source_path == doc
    assert "Rule fallback" in proposal.reason
    assert proposal.is_ai_suggested is False

