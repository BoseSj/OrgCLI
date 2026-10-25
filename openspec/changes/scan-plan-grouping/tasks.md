## 1. Grouping Data Models and State Machine

- [x] 1.1 Implement `FolderPlanGroup` and `group_proposals_by_destination` in `src/organizer/rules.py` to partition proposals by target destination folder, compute item counts, and sort categories predictably, verified by unit tests in `tests/test_rules.py`.
- [x] 1.2 Implement `InteractivePlanSession` state machine in `src/organizer/ui/interactive_plan.py` to track cursor navigation (Up/Down), single selection (Space), multi-selection, and deselect all (`d`), verified by unit tests in `tests/test_interactive_plan.py`.
- [x] 1.3 Add destination reassignment methods to `InteractivePlanSession` (`enter_move_mode`, folder suggestion matching, and `apply_folder_reassignment`), updating proposal paths and recalculating folder groups and counts, verified by unit tests in `tests/test_interactive_plan.py`.

## 2. Terminal UI and Keyboard Interaction

- [x] 2.1 Implement Rich Live layout rendering in `src/organizer/ui/interactive_plan.py` displaying folder headers with counts (e.g. `📁 Documents (4 files)`), cursor and selection marks, and the dynamic contextual shortcut footer (`[↑/↓] Navigate  [Space] Select  [m] Move  [d] Deselect all  [Enter] Confirm  [q] Quit`), verified by layout rendering unit tests.
- [x] 2.2 Implement terminal raw keyboard event listener in `src/organizer/ui/interactive_plan.py` utilizing standard library `tty` and `termios` for arrow keys, Space, Shift+Space, `m`, `d`, Enter, and Esc, verified by simulated input tests.
- [x] 2.3 Implement the interactive textfield prompt for the `m` command with `Tab` autocomplete suggestions for existing/suggested folders and custom folder creation on submit, verified by interactive session tests.

## 3. CLI Integration and Verification

- [x] 3.1 Update `organizer scan` in `src/organizer/cli.py` to launch the interactive plan session when running in a TTY terminal, while falling back to a clean static grouped table in non-interactive or `--non-interactive` mode, verified by CLI tests in `tests/test_cli.py`.
- [x] 3.2 Update acceptance tests in `tests/test_acceptance_scenarios.py` covering folder grouping, count badges, interactive navigation/reassignment simulation, and empty directory handling, verified by running `pytest`.
