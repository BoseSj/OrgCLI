## Context

See `proposal.md` for user motivation and problem context.

Currently, `ProposedMove` in `src/organizer/rules.py` does not store whether a suggestion originated from an AI model or a static rule. In addition, `FolderPlanGroup` titles and `InteractivePlanSession` render all folder names uniformly (`📁 <FolderName>`).

## Goals / Non-Goals

**Goals:**
- Provide clear visual differentiation between AI-recommended folder categories and rule-based categories in both static dry-run tables and interactive plan reviews.
- Track proposal origin on `ProposedMove` with an `is_ai_suggested` boolean.
- Enable `FolderPlanGroup` to expose `is_ai_suggested` dynamically.
- Allow `scan_command` to pass an AI classifier to `scan_and_propose_tree` when running in AI modes.
- Display a star emoji (`⭐`) in folder headers and move prompt suggestion chips.

**Non-Goals:**
- Modifying underlying file organization logic or disk operations.
- Introducing external iconography or graphical font dependencies.

## Decisions

### 1. Star Badge Format and Placement
- **Decision**: Prefix folder titles with `📁 ⭐ <FolderName>` (or `📁 <FolderName>` for rules). In interactive move prompt suggestion chips, display `⭐ <FolderName>` for AI-proposed categories.
- **Rationale**: The star emoji `⭐` (U+2B50) is cross-platform, natively supported in modern terminals and Rich, and directly matches the user's specification.
- **Alternatives Considered**: `✨` (Sparkles) or `✦` (Black Four Pointed Star). The star emoji is more legible and standard.

### 2. Proposal Origin Metadata
- **Decision**: Add `is_ai_suggested: bool = False` default field to `ProposedMove`.
- **Rationale**: Backwards-compatible dataclass field that defaults to `False` for rule classifications, while `GeminiProviderAdapter.classify_file()` sets `is_ai_suggested=True` upon successful API response.

### 3. Tree Scanner Classifier Injection
- **Decision**: Add `classifier: Optional[Callable[[Path, Path], ProposedMove]] = None` to `scan_and_propose_tree()`.
- **Rationale**: Keeps `rules.py` clean and free from direct dependencies on `gemini_adapter` or `OllamaProviderAdapter`, while allowing `scan_command` in `cli.py` to inject `service.gemini_adapter.classify_file` when in Gemini operational mode.

## Risks / Trade-offs

- **[Terminal Glyph Compatibility]** → Terminals with restricted ASCII may render standard emojis poorly. Rich console gracefully normalizes emojis on macOS and Unix terminals.
- **[Fallback Handling]** → If Gemini API encounters rate limits or errors, it falls back to extension rules with `is_ai_suggested=False`, ensuring no false AI stars are displayed.
