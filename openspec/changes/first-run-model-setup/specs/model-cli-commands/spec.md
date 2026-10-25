## Purpose

Provides command-line commands for inspecting, downloading, switching, diagnosing, and removing local models within the organizer CLI.

## ADDED Requirements

### Requirement: Standalone Setup Command
The CLI SHALL provide an `organizer setup` command allowing users to rerun the interactive setup wizard at any time to reconfigure the active model or toggle rule-based non-AI mode.

#### Scenario: Re-running setup command
- **WHEN** the user executes `organizer setup`
- **THEN** the system launches the interactive setup wizard and allows updating the active model or operational mode.

### Requirement: Model Listing Commands
The CLI SHALL distinguish between locally installed models and models available in the remote catalog through separate commands: `organizer models list` for locally installed models, and `organizer models available` for catalog models.

#### Scenario: Listing locally installed models
- **WHEN** the user runs `organizer models list`
- **THEN** the system displays a table of locally installed models with their tags, disk sizes, and an indicator for the currently active model.

#### Scenario: Listing available catalog models
- **WHEN** the user runs `organizer models available`
- **THEN** the system displays all catalog models with their recommended hardware, input modalities, estimated download sizes, and installation status.

### Requirement: Model Installation and Switching Commands
The CLI SHALL provide `organizer models install <model>` to download and verify a model, and `organizer models use <model>` to set an installed model as the active model.

#### Scenario: Installing a model via CLI
- **WHEN** the user runs `organizer models install gemma4:e2b`
- **THEN** the system checks disk space and prerequisites, asks for confirmation, streams download progress, verifies readiness, and prompts whether to set it as active.

#### Scenario: Switching active model
- **WHEN** the user runs `organizer models use gemma4:e2b`
- **THEN** the system verifies the model is installed, performs a readiness check, and updates the active configuration.

#### Scenario: Switching to an uninstalled model
- **WHEN** the user runs `organizer models use <model>` for a model that is not installed
- **THEN** the system informs the user that the model is not installed and suggests installing it first.

### Requirement: Model Status and Diagnostics
The CLI SHALL provide `organizer models status` to show the current operational mode and active model, and `organizer models doctor` to run comprehensive diagnostic checks on Ollama connectivity, loopback safety, disk space, and active model readiness.

#### Scenario: Checking model status
- **WHEN** the user runs `organizer models status`
- **THEN** the system prints the current mode (e.g., Local AI or Rule-only), active model tag, runtime API endpoint, and readiness state.

#### Scenario: Running model doctor diagnostics
- **WHEN** the user runs `organizer models doctor`
- **THEN** the system validates Ollama installation, local loopback endpoint binding, API responsiveness, active model existence, and host memory suitability.

### Requirement: Model Removal with Confirmation
The CLI SHALL provide `organizer models remove <model>` to delete a local model via Ollama. The command MUST require explicit confirmation and MUST warn the user that local model files will be deleted.

#### Scenario: Removing model with user confirmation
- **WHEN** the user runs `organizer models remove gemma4:e2b` and enters `y` at the confirmation prompt
- **THEN** the system calls the Ollama delete endpoint, deletes the model, and prints confirmation of deletion.

#### Scenario: Cancelling model removal
- **WHEN** the user runs `organizer models remove gemma4:e2b` and enters `n` at the confirmation prompt
- **THEN** the system aborts removal and leaves the model intact.
