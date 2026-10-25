## Why

Users testing the organizer MVP on resource-constrained devices need zero-cost cloud inference alternatives that do not consume local host RAM or disk space. Adding OpenRouter inference with support for the `openrouter/free` meta-router and structured JSON schema output provides accessible, free-tier AI file categorization across multiple open-source model providers.

## What Changes

- Add `OperationalMode.OPENROUTER = "openrouter"` and `OpenRouterSettings` schema to `src/organizer/config.py`.
- Implement `OpenRouterProviderAdapter` in `src/organizer/models/openrouter_adapter.py` supporting `OPENROUTER_API_KEY` discovery, connectivity smoke testing, and structured classification using `response_format` with `json_schema`.
- Extend `LocalModelLifecycleService` in `src/organizer/models/lifecycle.py` to support OpenRouter readiness checks, mode switching, and health diagnostics.
- Update `FirstRunSetupWizard` in `src/organizer/ui/setup.py` to offer OpenRouter as a first-class onboarding choice in setup menus, when Ollama is unavailable, and as a fallback option if local model execution fails.
- Update `organizer models status` and `organizer models doctor` in `src/organizer/cli.py` to inspect OpenRouter operational mode and credentials.
- Connect `OpenRouterProviderAdapter.classify_file()` into `organizer scan` in `src/organizer/cli.py` when in OpenRouter mode.

## Capabilities

### New Capabilities
- `openrouter-provider`: Cloud AI inference and file classification via OpenRouter's API using `openrouter/free` and structured JSON schemas.
- `openrouter-setup-flow`: OpenRouter onboarding, key discovery, smoke test verification, and CLI diagnostics.

### Modified Capabilities
<!-- None -->

## Impact

- `src/organizer/config.py`: Config settings schema and operational mode enum.
- `src/organizer/models/openrouter_adapter.py`: Provider adapter implementation.
- `src/organizer/models/lifecycle.py`: Lifecycle management and readiness verification.
- `src/organizer/ui/setup.py`: Setup wizard options and interactive prompts.
- `src/organizer/cli.py`: Models status, doctor, and scan commands.
- Test suite in `tests/test_config.py`, `tests/test_openrouter_adapter.py`, `tests/test_setup.py`, and `tests/test_cli.py`.
