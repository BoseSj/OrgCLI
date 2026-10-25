## Purpose

Manages the lifecycle, discovery, installation, streaming download, cancellation, smoke testing, and readiness verification of local Ollama models.

## ADDED Requirements

### Requirement: Runtime Availability and Health Diagnostics
The system SHALL check whether Ollama is installed on the local system and whether its local HTTP API is responsive. If Ollama is not installed, the system MUST explain the prerequisite with manual installation instructions without executing privileged installers. If Ollama is installed but not running, the system MUST provide instructions to start the service.

#### Scenario: Missing Ollama runtime
- **WHEN** the system attempts to connect to Ollama and neither binary nor API is present
- **THEN** the system reports a missing runtime status and displays standard instructions to install Ollama manually.

#### Scenario: Ollama installed but API unreachable
- **WHEN** Ollama is installed on the machine but the local API port does not respond
- **THEN** the system reports that Ollama service is stopped and directs the user to start Ollama.

### Requirement: Strict Local-Only Endpoint Validation
The system SHALL validate that all runtime and inference requests are directed exclusively to local loopback endpoints (`127.0.0.1`, `localhost`, `[::1]`). Any attempt to configure a remote or cloud-hosted endpoint MUST be rejected.

#### Scenario: Rejection of non-local endpoint
- **WHEN** an endpoint configuration is provided pointing to an external domain or non-loopback IP
- **THEN** the system rejects the endpoint and raises a configuration validation error.

#### Scenario: Valid local endpoint accepted
- **WHEN** the runtime endpoint is set to `http://localhost:11434` or `http://127.0.0.1:11434`
- **THEN** the system accepts the endpoint and connects locally.

### Requirement: Model Discovery and Inspection
The system SHALL query the local Ollama API to list installed models and inspect their details and capabilities. The system MUST treat runtime responses as untrusted data and validate JSON structures gracefully.

#### Scenario: Discover locally installed models
- **WHEN** local models are queried from a running Ollama runtime
- **THEN** the system returns a list of installed model names, tags, sizes, and capability details.

#### Scenario: Malformed runtime response
- **WHEN** the Ollama API returns malformed or incomplete JSON
- **THEN** the system catches the parsing error, reports a diagnostic failure, and avoids crashing.

### Requirement: Resumable Streaming Model Pull and Progress Reporting
The system SHALL orchestrate model downloads using the Ollama pull API, streaming real-time progress events. The progress events MUST handle messages with completed and total byte counts as well as status-only messages lacking byte counts. The system SHALL allow the user to safely cancel an ongoing download.

#### Scenario: Successful model pull with byte progress
- **WHEN** a user initiates a download for an available model and the stream emits progress with bytes
- **THEN** the system updates the display with downloaded bytes, total bytes, and status until completion.

#### Scenario: Progress stream without byte counts
- **WHEN** the pull progress event contains status text but no total or completed bytes
- **THEN** the system displays the status text without crashing or displaying invalid percentage bars.

#### Scenario: Cancelled model pull
- **WHEN** a user cancels an active model download
- **THEN** the system aborts the HTTP pull stream safely and leaves the local state clean.

#### Scenario: Network interruption during pull
- **WHEN** the network connection fails while streaming a model download
- **THEN** the system reports a clear network failure message and preserves resumability for future pull attempts.

### Requirement: Verification, Smoke Testing, and Readiness
The system SHALL verify that a model is present in Ollama's local tags and perform a minimal deterministic smoke test before marking the model ready. The active model selection MUST only be persisted after verification succeeds.

#### Scenario: Successful smoke test and readiness
- **WHEN** a model finishes downloading and successfully completes a prompt smoke test
- **THEN** the system marks the model as ready and records it as the active model in the configuration.

#### Scenario: Smoke test failure
- **WHEN** a model is present in tags but fails to execute a smoke test prompt
- **THEN** the system marks the model as unready, reports a readiness diagnostic error, and does not set it as the active model.

### Requirement: Safe Model Removal
The system SHALL support removing a local model from Ollama only upon receiving explicit user confirmation.

#### Scenario: Model removal with confirmation
- **WHEN** a user invokes model removal and explicitly confirms the prompt
- **THEN** the system sends a delete request to Ollama, reports successful removal, and updates active configuration if the deleted model was active.

#### Scenario: Model removal aborted on denial
- **WHEN** a user declines confirmation for model removal
- **THEN** the system cancels the removal operation and makes no changes to the local model.
