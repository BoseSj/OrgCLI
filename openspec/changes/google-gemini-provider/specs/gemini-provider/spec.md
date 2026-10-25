## Purpose

Provides cloud-based multimodal AI intelligence via the Google Gemini API for classifying and organizing files when local hardware resources are limited.

## ADDED Requirements

### Requirement: Gemini API Client Authentication and Discovery
The system SHALL support configuring and authenticating Google Gemini API interactions using the `GEMINI_API_KEY` environment variable. When `GEMINI_API_KEY` is present, the system SHALL initialize the Gemini client without requiring local model execution.

#### Scenario: API key present in environment
- **WHEN** the system initializes in Gemini mode and `GEMINI_API_KEY` is set in the environment
- **THEN** the system authenticates the client using the key and marks the provider as configured.

#### Scenario: API key missing
- **WHEN** the system attempts to execute in Gemini mode without `GEMINI_API_KEY` in environment or settings
- **THEN** the system indicates that `GEMINI_API_KEY` is required and provides instructions for setting the environment variable.

### Requirement: Gemini Connectivity and Readiness Smoke Testing
The system SHALL provide a lightweight smoke test to verify that the Gemini API is reachable, the credentials are valid, and the model (defaulting to `gemini-3.8-flash`) is responsive before saving or running organizations.

#### Scenario: Successful connectivity verification
- **WHEN** the system runs a smoke test against the Gemini API with valid credentials
- **THEN** the smoke test receives a successful response from the model and marks the provider as ready.

#### Scenario: Invalid credentials or connectivity failure
- **WHEN** the smoke test encounters an authentication error (e.g. invalid API key) or network connection failure
- **THEN** the system catches the error, marks the provider as not ready, and reports a clear, human-readable error message.

### Requirement: Multimodal Classification via Gemini API
The system SHALL support submitting both textual document contents and visual image payloads to the Gemini API for category and destination folder classification.

#### Scenario: Classifying an image file
- **WHEN** an image file (e.g., PNG, JPEG) is evaluated in Gemini mode
- **THEN** the system transmits the image data to Gemini and extracts the structured folder classification proposal.

#### Scenario: Classifying text and code documents
- **WHEN** text or code files are evaluated in Gemini mode
- **THEN** the system transmits the document text or snippet to Gemini and extracts the structured folder classification proposal.
