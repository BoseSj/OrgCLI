## Purpose

Provides folder-grouped dry-run plan display with item counts and interactive keyboard navigation, selection, and destination reassignment.

## ADDED Requirements

### Requirement: Folder-Grouped Presentation with Item Counts
The CLI scan command SHALL group proposed file moves under their suggested destination folders, displaying the item count beside each folder header.

#### Scenario: Displaying folder groups with counts
- **WHEN** `organizer scan <path>` runs on a directory containing files destined for various folders
- **THEN** the output groups items by target folder and displays headers with formatted file counts (e.g., `📁 Documents (4 files)`).

### Requirement: Interactive Keyboard Navigation
When executed in an interactive terminal, the scan command SHALL allow navigating through proposed files using the Up (`↑`) and Down (`↓`) arrow keys, highlighting the active item.

#### Scenario: Navigating items with arrow keys
- **WHEN** the user presses Up or Down arrow keys during plan inspection
- **THEN** the active row cursor moves to the corresponding previous or next file item across folder boundaries.

### Requirement: Single and Multi-File Selection
The interactive plan view SHALL allow selecting or deselecting individual files with the Space bar, multi-selecting files, and clearing all selections with the `d` key.

#### Scenario: Selecting and toggling individual files
- **WHEN** the user highlights a file item and presses the Space bar
- **THEN** that file's selection state toggles between selected and unselected, indicated by a selection checkbox mark.

#### Scenario: Deselecting all selected items
- **WHEN** one or more files are selected and the user presses `d`
- **THEN** all selected items are cleared back to unselected state.

### Requirement: Interactive Destination Reassignment
The interactive plan view SHALL allow pressing `m` to reassign the target folder for currently selected file(s) or the currently highlighted file, prompting with autocomplete suggestions from existing folders and categories or accepting a new folder name.

#### Scenario: Reassigning destination to an existing or suggested folder
- **WHEN** the user presses `m` with one or more files selected and chooses a suggested folder
- **THEN** the destination path and category of the selected file(s) are updated, moving them into the corresponding folder group and updating group counts.

#### Scenario: Reassigning destination to a new custom folder
- **WHEN** the user presses `m`, types a custom folder name not present in the suggestion list, and presses Enter
- **THEN** the selected file(s) are moved into a new destination folder group named after the custom input, ready to be created upon application.

### Requirement: Contextual Shortcut Help Legend
The interactive plan view SHALL render a contextual shortcut legend at the bottom of the interface displaying available key combinations for the current state.

#### Scenario: Viewing navigation mode shortcuts
- **WHEN** the interactive plan is in normal browsing mode
- **THEN** the legend displays available controls: `[↑/↓] Navigate  [Space] Select  [m] Move  [d] Deselect all  [Enter] Confirm  [q] Quit`.

#### Scenario: Viewing input prompt shortcuts
- **WHEN** the destination folder input prompt is active following an `m` keystroke
- **THEN** the legend switches to display input controls: `[Enter] Submit  [Tab] Autocomplete  [Esc] Cancel`.

### Requirement: Non-Interactive Terminal Fallback
When standard output is not an interactive terminal or when `--non-interactive` is passed, the CLI SHALL render a static grouped table and summary banner without launching interactive key listeners.

#### Scenario: Running scan in piped or headless environment
- **WHEN** `organizer scan` is executed in a non-interactive pipe or script
- **THEN** the tool prints the folder-grouped table and summary to stdout and exits with code 0.
