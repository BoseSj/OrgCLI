## Why

Running local on-device models like Gemma 4 E2B requires substantial host memory and disk space (at least 4–8 GB available RAM). On resource-constrained host machines with low available RAM (e.g. ~1.2 GB available), local model runners fail to allocate sufficient memory or respond to smoke tests. 

To ensure users can still enjoy AI-assisted document and folder organization regardless of local hardware limitations, the organizer needs an online AI provider option. Google provides a generous free tier for the Gemini API supporting frontier multimodal reasoning (using models like `gemini-3.8-flash`), which offloads all compute and memory requirements from the user's host machine.

## What Changes

- Add Google Gemini API provider adapter (`GeminiProviderAdapter`) using the official `google-genai` SDK.
- Support `OperationalMode.GEMINI` in application configuration, including configurable model selection (defaulting to `gemini-3.8-flash`) and API key discovery via `GEMINI_API_KEY`.
- Update the first-run interactive setup wizard (`organizer setup`) to present Google Gemini API as an explicit onboarding path alongside local Ollama models and rule-only mode.
- In the setup wizard, detect `GEMINI_API_KEY` from the environment or prompt the user to provide it, and run a fast connectivity smoke test against Gemini API before saving.
- Update `organizer models status` and `organizer models doctor` to diagnose Gemini API connectivity, key validation, and model readiness when Gemini mode is active.
- Add `google-genai>=2.30.1` to project dependencies in `pyproject.toml`.

## Capabilities

### New Capabilities
- `gemini-provider`: Remote Google Gemini API adapter providing API authentication, connectivity verification, and multimodal file classification.
- `gemini-setup-flow`: First-run setup and CLI configuration workflows for selecting, validating, and testing Google Gemini API mode.

### Modified Capabilities
<!-- None: existing catalog and local Ollama lifecycle specs remain intact -->

## Impact

- `src/organizer/config.py`: Add `OperationalMode.GEMINI` enum and `GeminiSettings` model.
- `src/organizer/models/gemini_adapter.py`: New module encapsulating `google-genai` client communication and smoke test execution.
- `src/organizer/ui/setup.py`: Add interactive prompts and setup options for Gemini API mode.
- `src/organizer/cli.py`: Enhance `status` and `doctor` commands to support Gemini provider diagnostics.
- `pyproject.toml`: Add `google-genai>=2.30.1` to dependencies.
