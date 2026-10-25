## Purpose

Orchestrates startup readiness evaluation, first-run onboarding, model selection, and fallback to rule-based operation without AI.

## ADDED Requirements

### Requirement: Startup Setup Evaluation
The system SHALL evaluate configuration and model readiness on application startup. If the active model is configured and ready, the application proceeds to regular operation. If setup is incomplete or no active model is ready, the system MUST initiate the first-run setup flow unless rule-based mode was explicitly chosen.

#### Scenario: First run on fresh installation
- **WHEN** the user launches the application with no prior configuration or active model
- **THEN** the system triggers the first-run model setup interface.

#### Scenario: Startup with valid configured model
- **WHEN** the application starts and finds a configured active model that passes readiness verification
- **THEN** the system bypasses the setup wizard and loads the organizer CLI ready for operation.

#### Scenario: Startup with missing configured model
- **WHEN** the configured model is missing from local Ollama tags on startup
- **THEN** the system notifies the user of the missing model and offers to run setup or continue in rule-based mode.

### Requirement: Interactive First-Run Model Setup Experience
The setup flow SHALL present users with options to: (1) select and download a recommended local model (e.g., Gemma 4 E2B), (2) choose an already installed local model, (3) continue in rule-based mode without AI, or (4) exit.

#### Scenario: Setup flow with download of recommended model
- **WHEN** the user selects the recommended model in the setup wizard
- **THEN** the system confirms download requirements, streams the pull progress, runs the smoke test, and saves the configuration.

#### Scenario: Setup flow using already installed model
- **WHEN** the user selects an already installed model from the discovered list
- **THEN** the system validates model capabilities, runs a smoke test, marks it active, and skips downloading.

### Requirement: Non-AI and Rule-Based Operation
The system SHALL allow users to explicitly choose to operate without AI. In non-AI mode, file scanning, deterministic rule categorization, and tree preview operations MUST function normally without requiring Ollama or any model installation.

#### Scenario: User chooses to continue without AI
- **WHEN** the user selects "Continue without AI" during first-run setup
- **THEN** the system configures rule-only mode, persists this preference, and enables deterministic file organization without downloading any models.

#### Scenario: Rule-based file scan in non-AI mode
- **WHEN** an organizer scan command is executed in non-AI mode
- **THEN** the system classifies files using deterministic extension and metadata rules without making any runtime inference calls.

### Requirement: Graceful Exit During Setup
The system SHALL allow users to exit the setup flow at any interactive prompt without leaving incomplete or corrupt configuration files.

#### Scenario: User cancels first-run setup
- **WHEN** the user selects "Exit" or sends an interrupt signal during setup
- **THEN** the system exits cleanly and prompts the user that setup can be rerun later with `organizer setup`.
