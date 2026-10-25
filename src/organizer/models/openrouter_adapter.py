"""Adapter for OpenRouter cloud inference API supporting free models and structured outputs."""

from dataclasses import dataclass
import json
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import httpx

from organizer.rules import ProposedMove, classify_file_by_rules


@dataclass
class OpenRouterCheckResult:
    """Result of checking OpenRouter credentials."""

    is_available: bool
    api_key_configured: bool
    model_name: str
    message: str


class OpenRouterProviderAdapter:
    """Adapter communicating with OpenRouter via OpenAI-compatible REST API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "openrouter/free",
        base_url: str = "https://openrouter.ai/api/v1",
        timeout_seconds: float = 30.0,
        app_referer: str = "https://github.com/local-folder-organizer",
        app_title: str = "Local Folder Organizer",
        client: Optional[httpx.Client] = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.app_referer = app_referer
        self.app_title = app_title
        self._custom_client = client

    def _get_client(self, timeout: Optional[float] = None) -> Any:
        if self._custom_client is not None:
            class _NoopContext:
                def __init__(self, inner):
                    self.inner = inner

                def __enter__(self):
                    return self.inner

                def __exit__(self, *args):
                    pass

            return _NoopContext(self._custom_client)
        return httpx.Client(timeout=timeout or self.timeout_seconds)

    def _get_headers(self) -> Dict[str, str]:
        key = self.api_key or os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise ValueError(
                "OPENROUTER_API_KEY is not set. Please export OPENROUTER_API_KEY or configure an API key."
            )
        return {
            "Authorization": f"Bearer {key}",
            "HTTP-Referer": self.app_referer,
            "X-Title": self.app_title,
            "Content-Type": "application/json",
        }

    def check_credentials(self) -> OpenRouterCheckResult:
        """Check whether OpenRouter API key is configured in settings or environment."""
        key = self.api_key or os.environ.get("OPENROUTER_API_KEY")
        if not key:
            return OpenRouterCheckResult(
                is_available=False,
                api_key_configured=False,
                model_name=self.model_name,
                message="OPENROUTER_API_KEY is not set in environment or configuration.",
            )
        return OpenRouterCheckResult(
            is_available=True,
            api_key_configured=True,
            model_name=self.model_name,
            message=f"OpenRouter API key configured for model '{self.model_name}'.",
        )

    def run_smoke_test(self, timeout: Optional[float] = None) -> Tuple[bool, str]:
        """Perform a minimal smoke test against OpenRouter to verify credentials and connectivity."""
        try:
            headers = self._get_headers()
            url = f"{self.base_url}/chat/completions"
            payload = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": "Reply with 'OK'."}],
                "max_tokens": 10,
            }

            with self._get_client(timeout=timeout) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices and choices[0].get("message", {}).get("content"):
                        return True, f"OpenRouter API responded successfully ({self.model_name})."
                    return False, "OpenRouter returned an empty choices list."
                return False, f"OpenRouter API returned HTTP {resp.status_code}: {resp.text}"
        except Exception as exc:
            return False, f"OpenRouter API smoke test failed: {exc}"

    def classify_file(self, path: Path, root: Path) -> ProposedMove:
        """Classify a file using OpenRouter structured JSON schema outputs, falling back to rules on error."""
        rel_path = path.relative_to(root).as_posix()
        mime, _ = mimetypes.guess_type(str(path))

        prompt = (
            f"You are an intelligent file organizer. Propose a single concise folder category name "
            f"(e.g., Invoices, Receipts, Photographs, Screenshots, Documentation, Source Code, Spreadsheets, Design) "
            f"for this file named '{path.name}'."
        )

        try:
            # Add text preview if text-based file
            try:
                text_sample = path.read_text(encoding="utf-8", errors="ignore")[:3000]
                if text_sample.strip():
                    prompt += f"\nFile preview:\n```\n{text_sample}\n```"
            except Exception:
                pass

            headers = self._get_headers()
            url = f"{self.base_url}/chat/completions"

            payload = {
                "model": self.model_name,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "category",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "category": {"type": "string"},
                                "reason": {"type": "string"},
                            },
                            "required": ["category"],
                            "additionalProperties": False,
                        },
                    },
                },
            }

            with self._get_client() as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")

                data = resp.json()
                raw_content = data["choices"][0]["message"]["content"].strip()

                # Handle markdown code blocks if present
                if raw_content.startswith("```"):
                    lines = raw_content.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].startswith("```"):
                        lines = lines[:-1]
                    raw_content = "\n".join(lines).strip()

                parsed = json.loads(raw_content)
                category = parsed.get("category", "Other").replace("/", "-").strip()
                if not category:
                    category = "Other"
                reason = parsed.get("reason", f"OpenRouter ({self.model_name}) analysis")

                dest_rel = f"{category}/{path.name}"
                return ProposedMove(
                    source_path=path,
                    source_rel=rel_path,
                    proposed_category=category,
                    proposed_rel=dest_rel,
                    confidence=0.9,
                    reason=reason,
                    is_ai_suggested=True,
                )

        except Exception as exc:
            # Graceful fallback to deterministic rules on error
            move = classify_file_by_rules(path, root)
            move.reason = f"Rule fallback (OpenRouter unavailable: {exc})"
            move.is_ai_suggested = False
            return move
