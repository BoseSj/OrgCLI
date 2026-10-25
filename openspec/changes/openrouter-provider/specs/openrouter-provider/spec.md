## Purpose

Provides cloud-based AI classification via OpenRouter using free-tier routing (`openrouter/free`) and structured JSON schema output without local host memory overhead.

## ADDED Requirements

### Requirement: OpenRouter API Authentication and Client Resolution
The system SHALL support configuring and authenticating OpenRouter interactions using the `OPENROUTER_API_KEY` environment variable or configuration settings.

#### Scenario: API key present in environment or settings
- **WHEN** the system executes in OpenRouter mode and `OPENROUTER_API_KEY` is present
- **THEN** the system authenticates API requests to OpenRouter with the bearer token.

#### Scenario: API key missing
- **WHEN** the system attempts to execute in OpenRouter mode without an API key
- **THEN** the system marks the provider as unconfigured and reports that `OPENROUTER_API_KEY` is required.

### Requirement: OpenRouter Free Tier Model Routing
The system SHALL default the model identifier to `openrouter/free` to route requests to available zero-cost free models while allowing user overrides.

#### Scenario: Defaulting to openrouter/free
- **WHEN** no custom OpenRouter model is specified in configuration
- **THEN** requests use model `openrouter/free`.

### Requirement: Structured JSON Schema Output for Categorization
The system SHALL request structured classification responses using OpenRouter's `response_format` with `json_schema` specifying `category` and `reason`.

#### Scenario: Successful structured classification
- **WHEN** file excerpt is submitted with JSON schema response formatting
- **THEN** the system parses the JSON object from the response and extracts the proposed folder category.

#### Scenario: OpenRouter API failure fallback
- **WHEN** the OpenRouter API encounters a rate limit, network failure, or provider outage
- **THEN** the system falls back gracefully to deterministic rule classification with `is_ai_suggested = False`.
