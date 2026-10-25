## 1. Configuration Model

- [x] 1.1 Extend `OperationalMode` with `OPENROUTER = "openrouter"` and add `OpenRouterSettings` schema to `src/organizer/config.py`, verified with unit tests in `tests/test_config.py`.

## 2. OpenRouter Adapter Implementation

- [x] 2.1 Implement `OpenRouterProviderAdapter` in `src/organizer/models/openrouter_adapter.py` supporting `OPENROUTER_API_KEY` credential discovery, connectivity smoke test, and structured JSON schema classification (`openrouter/free`).
- [x] 2.2 Add unit tests in `tests/test_openrouter_adapter.py` verifying credential resolution, smoke testing, structured classification parsing, and fallback error handling.

## 3. Lifecycle Integration and CLI Commands

- [x] 3.1 Extend `LocalModelLifecycleService` in `src/organizer/models/lifecycle.py` to support OpenRouter mode activation, readiness verification, and diagnostics, verified with unit tests in `tests/test_lifecycle.py`.
- [x] 3.2 Update `organizer models status`, `organizer models doctor`, and `organizer scan` in `src/organizer/cli.py` to support OpenRouter mode, verified with tests in `tests/test_cli.py`.

## 4. Setup Wizard Integration

- [x] 4.1 Update `FirstRunSetupWizard` in `src/organizer/ui/setup.py` to offer OpenRouter as an onboarding choice in initial setup menus, when Ollama is unavailable, and on local readiness failure.
- [x] 4.2 Add end-to-end setup wizard tests in `tests/test_setup.py` verifying successful onboarding into OpenRouter mode.
