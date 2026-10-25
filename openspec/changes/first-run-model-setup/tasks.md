## 1. Project Scaffolding and Configuration Management

- [x] 1.1 Create project structure with `pyproject.toml`, package modules, and verify installation in the virtual environment.
- [x] 1.2 Implement `organizer.config` with `AppConfig`, `ModelConfig`, `OperationalMode`, loopback endpoint validation, and config file persistence, verified by config unit tests.

## 2. Model Catalog Abstraction

- [x] 2.1 Implement `organizer.models.catalog` with `CatalogEntry`, modality requirements, download sizes, and Gemma 4 E2B defaults, verified by catalog unit tests.
- [x] 2.2 Implement host resource inspection (memory, disk) and advisory check utilities, verified by resource check unit tests.

## 3. Ollama Provider Adapter and Test Harness

- [x] 3.1 Implement `organizer.models.adapter` loopback HTTP client with typed streaming pull, tag listing, capability inspection, smoke test generation, and delete operations, verified by adapter unit tests.
- [x] 3.2 Implement `organizer.testing.fake_ollama` deterministic fake server simulating pull progress with/without bytes, interruptions, cancellation, malformed JSON, and smoke tests, verified by test harness tests.

## 4. Local Model Lifecycle Service

- [x] 4.1 Implement `organizer.models.lifecycle` service managing discovery, capability verification, readiness checks, active model selection, and prompt smoke tests, verified by lifecycle service tests.
- [x] 4.2 Implement streaming pull orchestration with progress events, cancellation tokens, failure recovery, and readiness gates, verified by pull orchestration unit tests.

## 5. First-Run Setup Flow and Non-AI Mode

- [x] 5.1 Implement `organizer.ui.setup` interactive Rich/Typer wizard for first-run model selection, live progress reporting, cancellation, and exit handling, verified by simulated interactive setup tests.
- [x] 5.2 Implement rule-based non-AI mode and persistence, verifying scanner and organization commands execute deterministically without Ollama.

## 6. CLI Management Commands

- [x] 6.1 Implement `organizer setup` and `organizer models` command group (`list`, `available`, `install`, `use`, `status`, `doctor`, `remove` with confirmation), verified by Typer CLI runner tests.
- [x] 6.2 Implement startup hook checking model readiness before CLI commands, gracefully offering setup or non-AI operation when unconfigured, verified by CLI runner tests.

## 7. Verification and Acceptance Testing

- [x] 7.1 Execute test suite covering all 16 specified acceptance scenarios: missing runtime, unreachable runtime, installed model, uninstalled model, pull success, pull failure, pull cancellation, progress without bytes, malformed responses, capability mismatch, readiness failure, configuration persistence, model switching, removal confirmation, strict local-only validation, and non-AI operation.
- [x] 7.2 Run end-to-end integration verification demonstrating complete CLI workflows and verify all engineering graph gates pass.
