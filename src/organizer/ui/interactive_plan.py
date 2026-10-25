"""Interactive terminal UI for navigating, selecting, and reorganizing folder proposals."""

from dataclasses import dataclass, field
import os
from pathlib import Path
import sys
from typing import Dict, List, Optional, Set, Tuple
from rich import box
from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from organizer.rules import (
    EXTENSION_CATEGORY_MAP,
    FolderPlanGroup,
    ProposedMove,
    group_proposals_by_destination,
    reassign_proposal_destination,
)

# Suggested filename column is kept in code but hidden for now as filename editing is not currently active
SHOW_TARGET_FILENAME: bool = False


@dataclass
class InteractivePlanSession:
    """State machine for interactive proposal navigation, selection, and folder reassignment."""

    proposals: List[ProposedMove]
    target_dir: Optional[Path] = None
    cursor: int = 0
    selected_indices: Set[int] = field(default_factory=set)
    anchor_index: Optional[int] = None
    mode: str = "browse"  # "browse" | "move_prompt"
    input_buffer: str = ""
    suggestion_cursor: int = 0
    confirmed: bool = False
    cancelled: bool = False

    def get_ordered_proposals(self) -> List[Tuple[FolderPlanGroup, ProposedMove, int]]:
        """Return flattened list of (group, proposal, flat_index) matching current folder grouping."""
        groups = group_proposals_by_destination(self.proposals)
        flattened: List[Tuple[FolderPlanGroup, ProposedMove, int]] = []
        idx = 0
        for g in groups:
            for p in g.proposals:
                flattened.append((g, p, idx))
                idx += 1
        return flattened

    @property
    def total_items(self) -> int:
        return len(self.proposals)

    def move_cursor(self, delta: int) -> None:
        """Move cursor up or down in the proposal list."""
        if not self.proposals:
            self.cursor = 0
            return
        self.cursor = max(0, min(self.total_items - 1, self.cursor + delta))

    def toggle_select_current(self) -> None:
        """Toggle selection of the item at the current cursor."""
        if not self.proposals:
            return
        if self.cursor in self.selected_indices:
            self.selected_indices.remove(self.cursor)
        else:
            self.selected_indices.add(self.cursor)
        self.anchor_index = self.cursor

    def multi_select_to_current(self) -> None:
        """Select a range of items from anchor_index to current cursor."""
        if not self.proposals:
            return
        start = self.anchor_index if self.anchor_index is not None else self.cursor
        low = min(start, self.cursor)
        high = max(start, self.cursor)
        for i in range(low, high + 1):
            self.selected_indices.add(i)

    def deselect_all(self) -> None:
        """Clear all active selections."""
        self.selected_indices.clear()
        self.anchor_index = None

    def enter_move_mode(self) -> None:
        """Enter folder reassignment text input mode."""
        if not self.proposals:
            return
        self.mode = "move_prompt"
        self.input_buffer = ""
        self.suggestion_cursor = 0

    def exit_move_mode(self) -> None:
        """Exit move prompt back to browse mode without applying changes."""
        self.mode = "browse"
        self.input_buffer = ""
        self.suggestion_cursor = 0

    def get_folder_suggestions(self) -> List[str]:
        """Compute matching destination folder suggestions based on input buffer."""
        candidates: Set[str] = set()
        # 1. Existing categories in active proposals
        for p in self.proposals:
            cat = p.proposed_category or (Path(p.proposed_rel).parts[0] if p.proposed_rel else "Other")
            if cat:
                candidates.add(cat)
        # 2. Known extension categories
        candidates.update(EXTENSION_CATEGORY_MAP.values())
        # 3. Existing subfolders in target_dir if available
        if self.target_dir and self.target_dir.is_dir():
            try:
                for sub in self.target_dir.iterdir():
                    if sub.is_dir() and not sub.name.startswith("."):
                        candidates.add(sub.name)
            except OSError:
                pass

        query = self.input_buffer.strip().lower()
        if not query:
            return sorted(candidates, key=lambda s: (s.lower() == "other", s.lower()))

        # Prioritize prefix match over substring match
        prefix_matches = [c for c in sorted(candidates) if c.lower().startswith(query)]
        substring_matches = [
            c for c in sorted(candidates)
            if query in c.lower() and not c.lower().startswith(query)
        ]
        return prefix_matches + substring_matches

    def cycle_suggestion(self, delta: int = 1) -> None:
        """Cycle through the current suggestions."""
        suggs = self.get_folder_suggestions()
        if not suggs:
            return
        self.suggestion_cursor = (self.suggestion_cursor + delta) % len(suggs)
        self.input_buffer = suggs[self.suggestion_cursor]

    def apply_move(self, destination_folder: Optional[str] = None) -> None:
        """Apply destination reassignment to selected proposals (or current item)."""
        target_folder = destination_folder or self.input_buffer.strip()
        if not target_folder:
            suggs = self.get_folder_suggestions()
            if suggs and 0 <= self.suggestion_cursor < len(suggs):
                target_folder = suggs[self.suggestion_cursor]
            else:
                target_folder = "Other"

        flat = self.get_ordered_proposals()
        targets_to_update: List[ProposedMove] = []

        if self.selected_indices:
            for _, prop, idx in flat:
                if idx in self.selected_indices:
                    targets_to_update.append(prop)
        elif 0 <= self.cursor < len(flat):
            targets_to_update.append(flat[self.cursor][1])

        for p in targets_to_update:
            reassign_proposal_destination(p, target_folder)

        self.selected_indices.clear()
        self.mode = "browse"
        self.input_buffer = ""
        self.suggestion_cursor = 0

    def handle_key(self, key: str) -> None:
        """Process a single logical key event."""
        if self.mode == "browse":
            if key in ("up", "k"):
                self.move_cursor(-1)
            elif key in ("down", "j"):
                self.move_cursor(1)
            elif key == "space":
                self.toggle_select_current()
            elif key in ("shift_space", "shift_up", "shift_down"):
                if key == "shift_up":
                    self.move_cursor(-1)
                    self.multi_select_to_current()
                elif key == "shift_down":
                    self.move_cursor(1)
                    self.multi_select_to_current()
                else:
                    self.multi_select_to_current()
            elif key == "d":
                self.deselect_all()
            elif key == "m":
                self.enter_move_mode()
            elif key in ("enter", "\n", "\r"):
                self.confirmed = True
            elif key == "q":
                self.cancelled = True
            elif key == "escape":
                self.deselect_all()
        elif self.mode == "move_prompt":
            if key == "escape":
                self.exit_move_mode()
            elif key in ("enter", "\n", "\r"):
                self.apply_move()
            elif key == "tab":
                self.cycle_suggestion(1)
            elif key == "backspace":
                if self.input_buffer:
                    self.input_buffer = self.input_buffer[:-1]
                    self.suggestion_cursor = 0
            elif len(key) == 1 and key.isprintable():
                self.input_buffer += key
                self.suggestion_cursor = 0


def render_interactive_plan(session: InteractivePlanSession) -> RenderableType:
    """Render the full interactive view with grouped tables and contextual shortcuts."""
    groups = group_proposals_by_destination(session.proposals)
    flat = session.get_ordered_proposals()

    elements = []

    # Title Banner
    total_files = len(session.proposals)
    total_folders = len(groups)
    selected_count = len(session.selected_indices)

    header_text = Text()
    header_text.append("📁 Proposed Organization Plan (Dry-Run)\n", style="bold cyan")
    header_text.append(f"Organizing {total_files} files across {total_folders} folders", style="dim")
    if selected_count > 0:
        header_text.append(f"  •  [bold green]{selected_count} selected[/bold green]")
    elements.append(Panel(header_text, border_style="cyan"))

    # Render each group
    global_idx = 0
    for g in groups:
        # Group Header
        group_title = Text()
        star_badge = "⭐ " if g.is_ai_suggested else ""
        group_title.append(f"📁 {star_badge}{g.folder_name} ", style="bold green")
        group_title.append(f"({g.count_label})", style="yellow")

        table = Table(
            title=group_title,
            title_justify="left",
            box=box.SIMPLE_HEAD,
            show_header=True,
            header_style="bold dim",
            expand=True,
        )
        table.add_column("Sel", width=3, justify="center")
        table.add_column("Cur", width=3, justify="center")
        table.add_column("Current Path", style="dim", ratio=4)
        if SHOW_TARGET_FILENAME:
            table.add_column("Target File Name", style="bold green", ratio=3)
        table.add_column("Confidence", justify="right", width=12)
        table.add_column("Reason", style="dim", ratio=4)

        for p in g.proposals:
            is_selected = global_idx in session.selected_indices
            is_cursor = (global_idx == session.cursor)

            sel_mark = Text("[x]", style="bold #38bdf8") if is_selected else Text("[ ]", style="dim")
            cur_mark = Text(">", style="bold #60a5fa") if is_cursor else Text(" ")

            # Transparent bluish styling for active cursor and selection
            if is_cursor and session.mode == "browse":
                if is_selected:
                    row_style = "bold white on #1e3a5f"
                else:
                    row_style = "bold #bfdbfe on #172554"
            elif is_selected:
                row_style = "#93c5fd on #0f172a"
            else:
                row_style = None

            conf_str = f"{p.confidence * 100:.0f}%"
            target_name = Path(p.proposed_rel).name

            row = [sel_mark, cur_mark, p.source_rel]
            if SHOW_TARGET_FILENAME:
                row.append(target_name)
            row.extend([conf_str, p.reason])

            table.add_row(*row, style=row_style)
            global_idx += 1

        elements.append(table)

    # Footer / Contextual Help Box
    footer_text = Text()
    if session.mode == "browse":
        footer_text.append("Shortcuts: ", style="bold")
        footer_text.append("[↑/↓] ", style="bold cyan").append("Navigate  ")
        footer_text.append("[Space] ", style="bold cyan").append("Select  ")
        footer_text.append("[Shift+Space] ", style="bold cyan").append("Multi-select  ")
        footer_text.append("[m] ", style="bold cyan").append("Move to folder  ")
        footer_text.append("[d] ", style="bold cyan").append("Deselect all  ")
        footer_text.append("[Enter] ", style="bold green").append("Confirm Plan  ")
        footer_text.append("[q] ", style="bold red").append("Quit")
    elif session.mode == "move_prompt":
        count_target = len(session.selected_indices) if session.selected_indices else 1
        footer_text.append(f"Move {count_target} file(s) to folder: ", style="bold yellow")
        footer_text.append(f"{session.input_buffer}_", style="bold white on blue")
        footer_text.append("\nSuggestions: ", style="dim")

        ai_categories = {
            (p.proposed_category or (Path(p.proposed_rel).parts[0] if p.proposed_rel else "Other"))
            for p in session.proposals
            if p.is_ai_suggested
        }

        suggs = session.get_folder_suggestions()
        if suggs:
            for idx, s in enumerate(suggs[:6]):
                star = "⭐ " if s in ai_categories else ""
                chip = f"{star}{s}"
                if idx == session.suggestion_cursor:
                    footer_text.append(f" [{chip}] ", style="bold black on cyan")
                else:
                    footer_text.append(f" {chip} ", style="cyan")
        else:
            footer_text.append("(New folder will be created)", style="italic green")

        footer_text.append("\n[Enter] Apply  [Tab] Suggestion  [Esc] Cancel", style="bold dim")

    elements.append(Panel(footer_text, border_style="yellow" if session.mode == "move_prompt" else "blue"))

    return Group(*elements)


def read_terminal_key() -> str:
    """Read a single keypress or ANSI escape sequence from stdin in raw/cbreak mode."""
    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        data = os.read(fd, 32)
        if not data:
            return ""

        # Arrow keys and standard ANSI sequences
        if data in (b"\x1b[A", b"\x1bOA"):
            return "up"
        elif data in (b"\x1b[B", b"\x1bOB"):
            return "down"
        elif data in (b"\x1b[C", b"\x1bOC"):
            return "right"
        elif data in (b"\x1b[D", b"\x1bOD"):
            return "left"
        elif data in (b"\x1b[1;2A", b"\x1b[a"):
            return "shift_up"
        elif data in (b"\x1b[1;2B", b"\x1b[b"):
            return "shift_down"
        elif data in (b"\x1b[Z",):
            return "shift_tab"
        elif data == b" ":
            return "space"
        elif data in (b"\r", b"\n"):
            return "enter"
        elif data in (b"\x7f", b"\x08"):
            return "backspace"
        elif data == b"\t":
            return "tab"
        elif data == b"\x03":  # Ctrl+C
            return "q"
        elif data == b"\x1b":  # Standalone Escape
            return "escape"

        if data.startswith(b"\x1b"):
            return "unknown_escape"

        try:
            return data.decode("utf-8", errors="ignore")
        except Exception:
            return ""
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def run_interactive_plan_session(
    proposals: List[ProposedMove],
    target_dir: Optional[Path] = None,
    console: Optional[Console] = None,
) -> Tuple[bool, List[ProposedMove]]:
    """Run interactive plan loop using Rich Live and raw keyboard events.

    Returns:
        (confirmed: bool, proposals: List[ProposedMove])
    """
    if console is None:
        console = Console()

    session = InteractivePlanSession(proposals=proposals, target_dir=target_dir)

    from rich.live import Live

    with Live(render_interactive_plan(session), console=console, refresh_per_second=20, screen=True) as live:
        while not session.confirmed and not session.cancelled:
            try:
                key = read_terminal_key()
                session.handle_key(key)
                live.update(render_interactive_plan(session))
            except (KeyboardInterrupt, EOFError):
                session.cancelled = True
                break

    return session.confirmed, session.proposals
