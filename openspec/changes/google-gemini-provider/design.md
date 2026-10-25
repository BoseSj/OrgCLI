## Context

The organizer CLI was designed with local Ollama inference (`OperationalMode.AI`) and fallback deterministic rules (`OperationalMode.RULE_ONLY`). However, local multimodal models such as Gemma 4 E2B require ~7.5 GB disk download and at least 4–8 GB of free host RAM. On memory-constrained hosts (e.g. system with only ~1.2 GB available memory), local inference engines fail to launch or fail smoke test health checks.

Google provides the Gemini API with a free tier supporting frontier multimodal models like `gemini-3.8-flash`. Integrating this cloud provider via the modern `google-genai` SDK allows users to leverage full AI-driven multimodal organization without requiring local GPU or RAM allocations.

## Goals / Non-Goals

**Goals:**
- Provide a clean, standalone `GeminiProviderAdapter` that interfaces with the Google Gemini API using `google-genai`.
- Support seamless environment authentication via `GEMINI_API_KEY` (with optional config file fallback).
- Add `OperationalMode.GEMINI` to `AppConfig` and `GeminiSettings`.
- Integrate an interactive onboarding flow in `organizer setup` when Ollama is unavailable, stopped, or memory-pressured.
- Provide fast, deterministic smoke testing and diagnostics in `organizer models status` and `organizer models doctor`.

**Non-Goals:**
- Supporting arbitrary third-party cloud LLM providers (e.g., Anthropic, OpenAI) in this change.
- Re-architecting local Ollama workflows; local models remain fully supported for users with sufficient hardware.
- Paid Gemini tier billing management or token usage analytics.

## Decisions

### 1. SDK Selection: `google-genai`
- **Choice**: Use the modern `google-genai>=2.30.1` SDK with `client.interactions.create` or `client.models.generate_content`.
- **Rationale**: `google-genai` is the official next-generation SDK for Gemini models. Legacy `google-generativeai` is deprecated.
- **Alternatives Considered**:
  - Direct HTTP calls via `httpx`: More boilerplate, manual payload construction for multimodal inputs, lack of typing.
  - Legacy `google-generativeai`: Outdated, incompatible with new models.

### 2. Default Model: `gemini-3.8-flash`
- **Choice**: Default to `gemini-3.8-flash`.
- **Rationale**: Fast, cost-efficient, high-throughput, natively multimodal (text and image inputs), and fully supported on the Google AI Studio free tier.
- **Alternatives Considered**:
  - `gemini-4-argon`: Slower for file categorization, lower rate limits on free tier.
  - `gemini-3.5-flash-lite`: Capable, but `3.8-flash` has superior multimodal reasoning for varied document layouts.

### 3. API Key Discovery
- **Choice**: Read `os.environ.get("GEMINI_API_KEY")` first. If present, use it automatically without storing plain-text secrets in `~/.config/organizer/config.json`. If user explicitly inputs a key in the interactive wizard, offer to store it or advise exporting `GEMINI_API_KEY`.
- **Rationale**: Storing API keys in plain text JSON config files is a security anti-pattern. Environment variable authentication conforms to standard CLI tooling.

### 4. Interactive Setup Integration
- **Choice**: Add option `[2] Use Google Gemini API (Online free tier — fast, multimodal, no local RAM needed)` to both the runtime-available menu and the runtime-unavailable/memory-pressured fallback menus.
- **Rationale**: When local Gemma fails a smoke test or Ollama is stopped, the wizard can immediately guide the user to activate Gemini rather than forcing them into non-AI rule mode.

## Risks / Trade-offs

- **[Privacy Trade-off]**: Unlike local Ollama where document bytes never leave the machine, cloud inference transmits file text/thumbnails to Google's API.
  - *Mitigation*: The setup wizard and CLI must explicitly label Gemini as "Online / Cloud API" so the user gives informed consent.
- **[Network Dependency]**: Requires an active internet connection.
  - *Mitigation*: If the network drops or API is unreachable, clear diagnostic messages point to network errors and suggest fallback to rule-only mode.
- **[Free Tier Rate Limits]**: Gemini free tier has RPM/TPM limits.
  - *Mitigation*: The adapter catches 429 Resource Exhausted errors with informative user messaging.
