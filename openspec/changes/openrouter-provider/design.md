## Context

See `proposal.md` for user motivation and problem context.

The application currently supports `OperationalMode.AI` (local Ollama), `OperationalMode.GEMINI` (Google Gemini), and `OperationalMode.RULE_ONLY`. This design introduces `OperationalMode.OPENROUTER` backed by an HTTP adapter calling `https://openrouter.ai/api/v1/chat/completions`.

## Goals / Non-Goals

**Goals:**
- Provide zero-cost cloud inference using the OpenRouter `openrouter/free` meta-router.
- Leverage the existing `httpx` dependency without requiring new third-party packages.
- Enforce structured JSON schema outputs for consistent category and reason parsing.
- Offer automated `OPENROUTER_API_KEY` discovery with interactive manual input fallback.
- Integrate into the setup wizard and CLI diagnostics (`models status`, `models doctor`, `scan`).

**Non-Goals:**
- Account balance tracking, billing management, or paid model routing.
- Re-architecting existing Ollama or Gemini provider adapters.

## Decisions

### 1. HTTP Client Strategy
- **Decision**: Use `httpx.Client` to interact with OpenRouter's REST endpoint (`https://openrouter.ai/api/v1/chat/completions`).
- **Rationale**: `httpx>=0.28.1` is already installed in the environment and used by `OllamaProviderAdapter`. Avoiding the heavy `openai` package maintains a minimal dependency footprint.

### 2. Structured JSON Schema
- **Decision**: Include `response_format` with `type: "json_schema"` in chat completion payloads:
  ```json
  {
    "type": "json_schema",
    "json_schema": {
      "name": "category",
      "strict": true,
      "schema": {
        "type": "object",
        "properties": {
          "category": { "type": "string" },
          "reason": { "type": "string" }
        },
        "required": ["category"],
        "additionalProperties": false
      }
    }
  }
  ```
- **Rationale**: Enforces deterministic JSON parsing across disparate models selected by the `openrouter/free` meta-router.

### 3. Graceful Error Handling and Star Badge Integration
- **Decision**: When OpenRouter returns a valid JSON classification, return `ProposedMove(..., is_ai_suggested=True)`. If a rate limit or network error occurs, fall back to `classify_file_by_rules()` with `is_ai_suggested=False` and detail the failure in `reason`.

## Risks / Trade-offs

- **[Free Route Availability]** → OpenRouter free models can occasionally experience high demand or 429 rate limits.
  - *Mitigation*: The adapter implements a 30s timeout and catches all request errors, falling back safely to deterministic rules so file organization is never blocked.
- **[JSON Schema Strictness]** → Some free models may return slight formatting deviations.
  - *Mitigation*: The adapter parses the response JSON and tolerates both raw JSON strings and markdown-fenced ```json blocks.
