## 1. Dependencies and Configuration Model

- [x] 1.1 Add `google-genai>=2.30.1` dependency to `pyproject.toml` and verify package installation in virtual environment.
- [x] 1.2 Extend `OperationalMode` with `GEMINI = "gemini"` and add `GeminiSettings` schema in `src/organizer/config.py`, verifying with updated unit tests in `tests/test_config.py`.

## 2. Gemini Provider Adapter and Diagnostics

- [x] 2.1 Implement `GeminiProviderAdapter` in `src/organizer/models/gemini_adapter.py` supporting API key discovery (`GEMINI_API_KEY`), `google-genai` client initialization, smoke test verification, and structured classification.
- [x] 2.2 Add unit tests in `tests/test_gemini_adapter.py` verifying client initialization, smoke test passing/failing states, and error handling for missing keys.

## 3. Lifecycle Integration and Multimodal Classification

- [x] 3.1 Extend `LocalModelLifecycleService` in `src/organizer/models/lifecycle.py` to support Gemini readiness checks, diagnostics, and mode switching.
- [x] 3.2 Implement multimodal file classification method in `GeminiProviderAdapter` that reads image/text file content and returns category proposals, verified by unit tests.

## 4. Setup Wizard and CLI Commands Integration

- [x] 4.1 Update `FirstRunSetupWizard` in `src/organizer/ui/setup.py` to include Google Gemini API as an onboarding option with automated `GEMINI_API_KEY` detection, interactive prompt fallback, and smoke test verification.
- [x] 4.2 Update `organizer models status` and `organizer models doctor` in `src/organizer/cli.py` to display Gemini operational mode and health checks.
- [x] 4.3 Add end-to-end setup wizard tests in `tests/test_setup.py` verifying successful onboarding into Gemini mode.
