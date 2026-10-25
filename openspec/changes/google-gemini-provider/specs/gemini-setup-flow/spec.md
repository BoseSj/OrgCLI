## Purpose

Integrates Google Gemini API onboarding, key validation, and status diagnostics into the interactive setup wizard and CLI diagnostic commands.

## ADDED Requirements

### Requirement: Setup Wizard Gemini Option
The first-run setup wizard (`organizer setup`) SHALL provide a dedicated selection option for configuring Google Gemini API mode, allowing users to choose online AI organization when host resources cannot run local models.

#### Scenario: User selects Gemini API option with existing environment key
- **WHEN** the user runs `organizer setup`, selects the Google Gemini API option, and `GEMINI_API_KEY` is already present in the environment
- **THEN** the wizard detects the key, runs a smoke test against Gemini, sets the active operational mode to Gemini, and confirms successful setup.

#### Scenario: User selects Gemini API option without environment key
- **WHEN** the user selects the Gemini API option and `GEMINI_API_KEY` is not detected in the environment
- **THEN** the wizard prompts the user to enter their Gemini API key, verifies it with a smoke test, saves the configuration, and advises exporting `GEMINI_API_KEY`.

#### Scenario: Gemini smoke test fails during setup
- **WHEN** the user provides an invalid key or network connection fails during the setup smoke test
- **THEN** the wizard reports the specific error and offers options to retry entering the key, fallback to rule-only mode, or cancel.

### Requirement: Gemini CLI Diagnostics
The CLI commands `organizer models status` and `organizer models doctor` SHALL support inspecting Google Gemini API configuration when Gemini mode is enabled.

#### Scenario: Checking model status in Gemini mode
- **WHEN** the user runs `organizer models status` while in Gemini mode
- **THEN** the output displays operational mode as `GEMINI`, active model as `gemini-3.8-flash` (or configured model), and verification status of the API key.

#### Scenario: Running doctor diagnostics in Gemini mode
- **WHEN** the user runs `organizer models doctor` with Gemini mode active
- **THEN** the doctor command validates internet connectivity, verifies `GEMINI_API_KEY` validity, runs a live API ping, and reports health checks.
