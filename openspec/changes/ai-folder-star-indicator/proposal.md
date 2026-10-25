## Why

When scanning folders with `organizer scan`, destination folders recommended by AI intelligence (e.g. Google Gemini or local Gemma) appear visually identical to deterministic extension-based rules. Users cannot easily see which folder groupings were derived from multimodal AI understanding versus static rules. Adding a prominent star emoji/icon (`⭐`) beside AI-suggested folders gives users immediate clarity and transparency over AI suggestions during organization review.

## What Changes

- Extend `ProposedMove` dataclass with `is_ai_suggested: bool = False` attribute.
- Extend `FolderPlanGroup` dataclass with an `is_ai_suggested: bool` property that detects when proposals in the folder group originate from AI.
- Ensure `GeminiProviderAdapter.classify_file()` marks `is_ai_suggested=True` for successful AI classifications, and `False` when falling back to rules.
- Support AI-aware tree scanning in `scan_and_propose_tree()` / `scan_command` using the configured operational mode.
- Update `print_static_grouped_plan()` in `src/organizer/cli.py` to render the star icon (e.g., `📁 ⭐ <FolderName>`) in table titles for AI-suggested folders.
- Update `render_interactive_plan()` in `src/organizer/ui/interactive_plan.py` to render the star icon on folder headers and in the folder reassignment suggestion chips.

## Capabilities

### New Capabilities
- `ai-folder-indicator`: Star icon indicator distinguishing AI-suggested folders from rule-based folders across static CLI tables and interactive review sessions.

### Modified Capabilities
<!-- None -->

## Impact

- `src/organizer/rules.py`: `ProposedMove`, `FolderPlanGroup`, and `scan_and_propose_tree`.
- `src/organizer/models/gemini_adapter.py`: `classify_file` sets `is_ai_suggested=True`.
- `src/organizer/cli.py`: Group table headers in `print_static_grouped_plan` and classification pipeline in `scan_command`.
- `src/organizer/ui/interactive_plan.py`: Folder title rendering and suggestion list badges in `render_interactive_plan`.
- Unit and CLI tests in `tests/test_rules.py`, `tests/test_interactive_plan.py`, and `tests/test_cli.py`.
