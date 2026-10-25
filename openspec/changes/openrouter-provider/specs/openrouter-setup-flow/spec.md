## Purpose

Integrates OpenRouter onboarding, key validation, and status diagnostics into the interactive setup wizard and CLI diagnostic commands.

## ADDED Requirements

### Requirement: Setup Wizard OpenRouter Option
The first-run setup wizard (`organizer setup`) SHALL provide a dedicated selection option for configuring OpenRouter mode, allowing users to choose online free inference without local host hardware requirements.

#### Scenario: User selects OpenRouter option with existing environment key
- **WHEN** the user runs `organizer setup`, selects OpenRouter mode, and `OPENROUTER_API_KEY` is present in the environment
- **THEN** the wizard detects the key, runs a smoke test, activates OpenRouter mode, and confirms successful setup.

#### Scenario: User selects OpenRouter option without environment key
- **WHEN** the user selects OpenRouter mode and `OPENROUTER_API_KEY` is not present in the environment
- **THEN** the wizard prompts the user to enter their OpenRouter API key, verifies connectivity via smoke test, and saves the configuration.

#### Scenario: OpenRouter smoke test fails during setup
- **WHEN** the user provides an invalid key or network connection fails during the smoke test
- **THEN** the wizard reports the specific error and offers options to retry entering the key or fallback to rule-only mode.

### Requirement: OpenRouter CLI Diagnostics
The CLI commands `organizer models status` and `organizer models doctor` SHALL support inspecting OpenRouter configuration and health when OpenRouter mode is active.

#### Scenario: Checking model status in OpenRouter mode
- **WHEN** the user runs `organizer models status` while in OpenRouter mode
- **THEN** the output displays operational mode as `OPENROUTER`, active model as `openrouter/free`, and key verification status.

#### Scenario: Running doctor diagnostics in OpenRouter mode
- **WHEN** the user runs `organizer models doctor` with OpenRouter mode active
- **THEN** the doctor command validates `OPENROUTER_API_KEY` presence and runs a live API ping to report health checks.
