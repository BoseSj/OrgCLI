## Why

When scanning directories with many files (such as `~/Downloads`), the current `organizer scan` command outputs a flat, static table with repetitive paths. Users cannot easily see folder-level aggregation counts, nor can they adjust or customize destination suggestions before committing to an organization action.

Providing a clean folder-grouped overview with item counts, coupled with an interactive keyboard-driven review interface, allows users to navigate proposed moves, select files, reassign destinations with autocomplete assistance, and inspect changes intuitively.

## What Changes

- **Folder-Grouped Plan with Item Counts**: Group proposed moves by target destination folder with prominent count badges (e.g., `📁 Documents (4 files)`).
- **Interactive Keyboard Navigation**: Allow users to scroll through proposals using Up (`↑`) and Down (`↓`) arrow keys with an active cursor indicator.
- **Single & Multi-File Selection**: Enable selecting/deselecting individual files with `Space` and toggling multi-selection across files. Provide a quick deselect-all shortcut (`d`).
- **Interactive Folder Reassignment (`m`)**: Pressing `m` opens an inline prompt to reassign selected file(s) to a different folder. It offers autocomplete/suggestions from existing folders and catalog suggestions, or creates a new custom folder on submit.
- **Contextual Key Shortcut Legend**: Display an always-visible contextual shortcut bar at the bottom of the interface (`[↑/↓] Navigate  [Space] Select  [m] Move  [d] Deselect all  [Enter] Confirm  [q] Quit`) so users never have to memorize commands.
- **Non-Interactive / TTY Fallback**: When stdout is not a TTY (or when passed `--non-interactive`), render a clean static grouped table and summary banner.

## Capabilities

### New Capabilities
- `scan-plan-grouping`: Folder-grouped plan representation, item counts, interactive keyboard navigation, file selection, interactive destination reassignment (`m`), and contextual shortcut guidance.

### Modified Capabilities
<!-- None: No existing main specs are being modified. -->

## Impact

- CLI `organizer scan` (`src/organizer/cli.py`): Updated to support both interactive plan review mode and static non-interactive rendering.
- UI layer (`src/organizer/ui/interactive_plan.py`): New interactive plan session handling keystrokes, selection state, folder reassignment input, and Rich Live UI rendering.
- Grouping & Plan logic (`src/organizer/rules.py`): Helpers to group proposals, update destination folders on selected items, and recalculate folder metrics.
- Test suite: Unit and component tests for state machine, keyboard events, folder reassignment, and CLI invocations.
