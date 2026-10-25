## Why

Users who want private, local-first folder organization currently face steep friction if they have to manually install, pull, and configure local models through external terminal utilities like `ollama pull`. Furthermore, users on resource-constrained devices (such as 8 GB unified-memory Macs) risk downloading models that freeze or exhaust memory, or attempting to use models that lack required capabilities (such as multimodal image understanding).

This change introduces an automated first-run model setup experience and a local model lifecycle management subsystem. It enables users to discover, select, download with real-time progress, verify, switch, and remove supported local Gemma models directly inside the application, while providing safe rule-only fallbacks and clear recovery guidance when Ollama is missing or stopped.

## What Changes

- **Model Catalog Abstraction**: Define a structured, versioned local model catalog specifying model IDs, tags, parameter sizes, download sizes, input modalities, compatibility constraints, and hardware recommendations.
- **Provider Adapter & Lifecycle Service**: Implement a dedicated `LocalModelLifecycleService` communicating over Ollama's local HTTP API, handling local discovery, capability inspection, streaming pull orchestration with cancellation, readiness checks, and smoke tests.
- **First-Run Setup Flow**: Present an interactive onboarding flow on startup when setup is incomplete. Users can select a recommended model (such as Gemma 4 E2B), select an already installed model, continue in rule-based non-AI mode, or exit.
- **Strict Local-Only & Privacy Guarantees**: Enforce that inference endpoints are strictly local (`localhost`/`127.0.0.1`), forbid cloud fallbacks, and clearly delineate network operations (model download) from offline document processing.
- **CLI Model Management Commands**: Add Typer CLI commands for manual model lifecycle management: `organizer setup`, `organizer models list`, `organizer models available`, `organizer models install <model>`, `organizer models use <model>`, `organizer models status`, `organizer models doctor`, and `organizer models remove <model>` (with explicit confirmation).
- **Graceful Failure Handling & Non-AI Mode**: Support running without any model installed (deterministic rules only) and provide clear diagnostic instructions when Ollama is uninstalled or unreachable.

## Capabilities

### New Capabilities
- `model-catalog`: Structured catalog for supported local models with capability, size, and hardware metadata.
- `model-lifecycle`: Local runtime integration owning discovery, download orchestration, progress reporting, cancellation, verification, smoke tests, and readiness.
- `first-run-setup`: Interactive startup setup flow guiding users through model selection, download, verification, or rule-based non-AI mode.
- `model-cli-commands`: CLI commands to inspect, install, switch, diagnose, and remove models.

### Modified Capabilities
<!-- None. Greenfield capabilities for OrgCLI. -->

## Impact

- **CLI / Architecture**: Introduces core configuration management (`~/.config/organizer/config.json` or local project config), runtime client adapter, model catalog, and setup orchestrator into the CLI package.
- **Dependencies**: Uses `typer`, `rich` (for terminal UI and progress displays), `httpx` (for streaming local Ollama HTTP API interactions), and `pydantic` (for schema validation).
- **Security & Privacy**: Enforces local loopback binding and prevents remote inference fallback.
