## 1. Proposal and Grouping Models

- [x] 1.1 Add `is_ai_suggested: bool = False` to `ProposedMove` and implement `is_ai_suggested` property on `FolderPlanGroup` in `src/organizer/rules.py`, verifying with unit tests in `tests/test_rules.py`.
- [x] 1.2 Update `GeminiProviderAdapter.classify_file()` in `src/organizer/models/gemini_adapter.py` to set `is_ai_suggested=True` on successful AI responses and `is_ai_suggested=False` on fallback, verifying with tests in `tests/test_gemini_adapter.py`.

## 2. Tree Scanner and CLI Classification Pipeline

- [x] 2.1 Update `scan_and_propose_tree()` in `src/organizer/rules.py` to accept an optional file classifier callable and update `scan_command` in `src/organizer/cli.py` to pass the active AI provider classifier when operational mode is Gemini, verified with unit tests.
- [x] 2.2 Update `print_static_grouped_plan()` in `src/organizer/cli.py` to render the star badge `📁 ⭐ <FolderName>` for AI-suggested folder tables, verified with CLI tests in `tests/test_cli.py`.

## 3. Interactive Review UI

- [x] 3.1 Update `render_interactive_plan()` in `src/organizer/ui/interactive_plan.py` to display the star emoji `📁 ⭐ <FolderName>` in group headers and annotate AI-suggested candidates in the move suggestions footer, verified with tests in `tests/test_interactive_plan.py`.
