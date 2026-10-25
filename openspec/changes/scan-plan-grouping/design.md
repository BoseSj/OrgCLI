## Context

See `proposal.md` for motivation. In the current implementation, `organizer scan` prints a flat static table with no interactive inspection or modification capabilities. To give users complete confidence before executing file moves, the tool needs an interactive terminal user interface (TUI) allowing users to navigate through grouped proposals, select files, reassign target folders with autocomplete, and see live folder count updates.

## Goals / Non-Goals

**Goals:**
- Present file proposals grouped by destination folder with item counts (e.g. `📁 Documents (4 files)`).
- Provide responsive keyboard navigation (Up/Down arrows, Space selection, multi-selection, and `d` to deselect all).
- Provide an inline folder reassignment prompt (`m`) with suggestion autocomplete for existing and tool-suggested folders, or new folder creation on submit.
- Maintain an always-visible contextual shortcut help bar adapting to the active mode.
- Support non-interactive fallback (CI, piping, or `--non-interactive` flag) rendering static grouped tables.
- Keep the session state machine decoupled from terminal I/O for comprehensive unit testing.

**Non-Goals:**
- Performing the physical file move disk I/O in this change (file movement is executed in the apply execution command).
- Mouse click handling in the terminal.

## Decisions

### 1. Separation of State Machine and Terminal I/O
Implement an `InteractivePlanSession` state machine in `src/organizer/ui/interactive_plan.py` containing:
- `proposals: List[ProposedMove]`
- `cursor: int` (index in the flattened proposal list)
- `selected_indices: Set[int]`
- `mode: Literal["browse", "move_prompt"]`
- `input_buffer: str` and `suggestion_index: int`
- Methods: `move_cursor(delta)`, `toggle_selection()`, `deselect_all()`, `enter_move_mode()`, `apply_folder_reassignment(folder_name)`, `cancel_move_mode()`.

*Rationale*: A pure state machine can be tested deterministically with simulated keystroke sequences without requiring mock terminal TTYs.

### 2. Live Rendering with Rich
Use `rich.live.Live` with `screen=True` (or auto-clearing layout) to render the plan:
- **Grouped Section Layout**: Each destination directory is rendered with an icon and count header: `📁 Documents (4 files)`.
- **Item Rows**: Each item displays selection status `[ ]` or `[x]`, cursor indicator `>` when active, filename, confidence, and rule reason.
- **Contextual Footer**: Adapts dynamically:
  - In `browse` mode: `[↑/↓] Navigate  [Space] Select  [m] Move to folder  [d] Deselect all  [Enter] Confirm  [q] Quit`
  - In `move_prompt` mode: `Move selected (N files) to folder: <input>_  [Tab] Suggestion  [Enter] Confirm  [Esc] Cancel`

*Rationale*: Rich is already a core project dependency. `rich.live.Live` provides flicker-free terminal updates.

### 3. Folder Autocomplete & Reassignment
When `m` is pressed:
- Suggestions are populated from:
  1. All target folders currently proposed in the plan (e.g. `Documents`, `Images`, `Media`, `Development`, `Other`).
  2. Any existing directories present in the root scanning target.
  3. Standard catalog category names.
- If the user types a new folder name, submitting creates a new destination group for that name and moves the selected file(s) into it.
- Folder counts and groups update immediately in the live plan.

### 4. Raw Keyboard Input via Standard Library `tty` / `termios`
Use Python's built-in `termios` and `tty` modules (supported on macOS/Unix) with `sys.stdin.fileno()` in cbreak mode to read arrow keys (`\x1b[A`, `\x1b[B`), Space, Shift+Space, Enter, and single-character commands without external C-extensions.

### 5. Graceful Fallback for Non-Interactive Environments
If `sys.stdout.isatty()` is False or if `--non-interactive` is passed, `scan_command` skips the event loop and prints the static Rich grouped table and summary banner.

## Risks / Trade-offs

- **[Risk] Terminal resizing during interactive session**
  *Mitigation*: `rich.live.Live` handles terminal resize signals gracefully by reflowing table rows and clipping overflow.
- **[Risk] Large numbers of files scrolling past terminal height**
  *Mitigation*: Implement scroll-windowing in the view renderer so that the cursor stays centered within the visible terminal height.
