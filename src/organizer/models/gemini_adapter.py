"""Google Gemini API provider adapter for cloud-based multimodal categorization."""

import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from organizer.rules import ProposedMove, classify_file_by_rules

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None  # type: ignore
    types = None  # type: ignore


class GeminiCheckResult(BaseModel):
    """Result of checking Gemini credentials and environment configuration."""

    is_available: bool
    api_key_configured: bool
    model_name: str
    message: str


class GeminiProviderAdapter:
    """Adapter for communicating with Google Gemini API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash",
        timeout_seconds: float = 30.0,
        client: Optional[Any] = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self._client = client

    def get_client(self) -> Any:
        """Resolve and initialize Google GenAI client."""
        if self._client is not None:
            return self._client

        key = self.api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Please export GEMINI_API_KEY or configure an API key."
            )
        if genai is None:
            raise RuntimeError(
                "google-genai package is not installed. Install it via 'pip install google-genai'."
            )

        self._client = genai.Client(api_key=key)
        return self._client

    def check_credentials(self) -> GeminiCheckResult:
        """Check whether Gemini API key is configured in settings or environment."""
        key = self.api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            return GeminiCheckResult(
                is_available=False,
                api_key_configured=False,
                model_name=self.model_name,
                message="GEMINI_API_KEY is not set in environment or configuration.",
            )
        return GeminiCheckResult(
            is_available=True,
            api_key_configured=True,
            model_name=self.model_name,
            message=f"Gemini API key configured for model '{self.model_name}'.",
        )

    def run_smoke_test(self, timeout: Optional[float] = None) -> Tuple[bool, str]:
        """Perform a minimal smoke test against the Gemini API to verify credentials and connectivity."""
        try:
            client = self.get_client()
            resp = client.models.generate_content(
                model=self.model_name,
                contents="Reply with the single word 'OK'.",
            )
            if resp and resp.text:
                return True, f"Gemini API responded successfully ({self.model_name})."
            return False, "Gemini API returned an empty response."
        except Exception as exc:
            return False, f"Gemini API smoke test failed: {exc}"

    def classify_file(self, path: Path, root: Path) -> ProposedMove:
        """Classify a file using Gemini multimodal model, falling back to rules on failure."""
        rel_path = path.relative_to(root).as_posix()
        mime, _ = mimetypes.guess_type(str(path))

        prompt = (
            f"You are an intelligent file organizer. Propose a single concise folder category name "
            f"(e.g., Invoices, Receipts, Photographs, Screenshots, Documentation, Source Code, Spreadsheets, Design) "
            f"for this file named '{path.name}'. "
            f"Respond strictly in the format: CATEGORY: <CategoryName> | REASON: <ShortReason>"
        )

        try:
            client = self.get_client()
            contents: List[Any] = []

            # Multimodal image handling
            if mime and mime.startswith("image/") and types is not None:
                image_bytes = path.read_bytes()
                # Limit thumbnail to 10MB
                if len(image_bytes) <= 10 * 1024 * 1024:
                    image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime)
                    contents.append(image_part)

            # Text content snippet
            if not contents:
                try:
                    text_sample = path.read_text(encoding="utf-8", errors="ignore")[:3000]
                    if text_sample.strip():
                        prompt += f"\nFile preview:\n```\n{text_sample}\n```"
                except Exception:
                    pass

            contents.append(prompt)
            resp = client.models.generate_content(
                model=self.model_name,
                contents=contents,
            )

            text = resp.text.strip() if resp and resp.text else ""
            category = "Other"
            reason = f"Gemini ({self.model_name}) analysis"

            if "CATEGORY:" in text:
                parts = text.split("CATEGORY:", 1)[1]
                if "| REASON:" in parts:
                    cat_part, reason_part = parts.split("| REASON:", 1)
                    category = cat_part.strip().strip('"').strip("'")
                    reason = reason_part.strip()
                else:
                    category = parts.split("\n")[0].strip().strip('"').strip("'")
            elif text:
                category = text.split()[0].strip().strip('"').strip("'")

            # Clean category name
            category = category.replace("/", "-").strip()
            if not category:
                category = "Other"

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
            # Graceful fallback to deterministic extension rules on network error
            move = classify_file_by_rules(path, root)
            move.reason = f"Rule fallback (Gemini unavailable: {exc})"
            move.is_ai_suggested = False
            return move
