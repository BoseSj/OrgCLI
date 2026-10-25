"""Unit tests for interactive plan session, state machine, and rendering."""

from pathlib import Path
from organizer.rules import ProposedMove
from organizer.ui.interactive_plan import (
    InteractivePlanSession,
    render_interactive_plan,
)


def _make_dummy_proposals():
    return [
        ProposedMove(
            source_path=Path("doc1.pdf"),
            source_rel="doc1.pdf",
            proposed_category="Documents",
            proposed_rel="Documents/doc1.pdf",
            confidence=1.0,
            reason="pdf",
        ),
        ProposedMove(
            source_path=Path("doc2.pdf"),
            source_rel="doc2.pdf",
            proposed_category="Documents",
            proposed_rel="Documents/doc2.pdf",
            confidence=1.0,
            reason="pdf",
        ),
        ProposedMove(
            source_path=Path("img1.png"),
            source_rel="img1.png",
            proposed_category="Images",
            proposed_rel="Images/img1.png",
            confidence=1.0,
            reason="png",
        ),
        ProposedMove(
            source_path=Path("other1.xyz"),
            source_rel="other1.xyz",
            proposed_category="Other",
            proposed_rel="Other/other1.xyz",
            confidence=0.5,
            reason="xyz",
        ),
    ]


def test_session_navigation():
    proposals = _make_dummy_proposals()
    session = InteractivePlanSession(proposals=proposals)

    assert session.cursor == 0
    # Down
    session.handle_key("down")
    assert session.cursor == 1
    session.handle_key("down")
    assert session.cursor == 2
    session.handle_key("down")
    assert session.cursor == 3
    # Clamping down
    session.handle_key("down")
    assert session.cursor == 3

    # Up
    session.handle_key("up")
    assert session.cursor == 2
    session.handle_key("up")
    assert session.cursor == 1
    session.handle_key("up")
    assert session.cursor == 0
    # Clamping up
    session.handle_key("up")
    assert session.cursor == 0


def test_session_single_and_multi_selection():
    proposals = _make_dummy_proposals()
    session = InteractivePlanSession(proposals=proposals)

    # Space toggles current
    session.handle_key("space")
    assert session.selected_indices == {0}

    # Space again untoggles
    session.handle_key("space")
    assert session.selected_indices == set()

    # Select 0, move to 2, multi-select
    session.handle_key("space")
    session.handle_key("down")
    session.handle_key("down")
    assert session.cursor == 2
    session.handle_key("shift_space")
    assert session.selected_indices == {0, 1, 2}

    # Deselect all
    session.handle_key("d")
    assert session.selected_indices == set()


def test_session_folder_suggestions():
    proposals = _make_dummy_proposals()
    session = InteractivePlanSession(proposals=proposals)

    # Default suggestions contain current and standard categories
    suggs = session.get_folder_suggestions()
    assert "Documents" in suggs
    assert "Images" in suggs
    assert "Other" in suggs

    # Filter with buffer
    session.input_buffer = "Doc"
    assert session.get_folder_suggestions() == ["Documents"]

    session.input_buffer = "nonexistent"
    assert session.get_folder_suggestions() == []


def test_session_move_single_item():
    proposals = _make_dummy_proposals()
    session = InteractivePlanSession(proposals=proposals)

    # Cursor at 0 (doc1.pdf)
    session.handle_key("m")
    assert session.mode == "move_prompt"

    # Type folder name
    for ch in "Finance":
        session.handle_key(ch)
    assert session.input_buffer == "Finance"

    session.handle_key("enter")
    assert session.mode == "browse"
    # doc1.pdf moved to Finance
    assert proposals[0].proposed_category == "Finance"
    assert proposals[0].proposed_rel == "Finance/doc1.pdf"


def test_session_move_multi_items():
    proposals = _make_dummy_proposals()
    session = InteractivePlanSession(proposals=proposals)

    # Select item 0 and 1
    session.cursor = 0
    session.handle_key("space")
    session.cursor = 1
    session.handle_key("space")
    assert session.selected_indices == {0, 1}

    # Move both to Archives
    session.handle_key("m")
    session.input_buffer = "Archives"
    session.handle_key("enter")

    assert proposals[0].proposed_category == "Archives"
    assert proposals[0].proposed_rel == "Archives/doc1.pdf"
    assert proposals[1].proposed_category == "Archives"
    assert proposals[1].proposed_rel == "Archives/doc2.pdf"
    assert session.selected_indices == set()


def test_session_tab_suggestion_cycle():
    proposals = _make_dummy_proposals()
    session = InteractivePlanSession(proposals=proposals)

    session.handle_key("m")
    session.handle_key("tab")
    assert session.input_buffer != ""

    # Escape cancels without applying
    session.handle_key("escape")
    assert session.mode == "browse"


def test_session_confirm_and_quit():
    proposals = _make_dummy_proposals()
    session = InteractivePlanSession(proposals=proposals)

    session.handle_key("enter")
    assert session.confirmed is True

    session2 = InteractivePlanSession(proposals=proposals)
    session2.handle_key("q")
    assert session2.cancelled is True


def test_render_interactive_plan():
    proposals = _make_dummy_proposals()
    session = InteractivePlanSession(proposals=proposals)
    renderable = render_interactive_plan(session)
    assert renderable is not None

    # In move prompt mode
    session.handle_key("m")
    renderable_prompt = render_interactive_plan(session)
    assert renderable_prompt is not None


def test_render_interactive_plan_with_ai_suggestions():
    import io
    from rich.console import Console

    p_ai = ProposedMove(
        source_path=Path("bill.pdf"),
        source_rel="bill.pdf",
        proposed_category="Invoices",
        proposed_rel="Invoices/bill.pdf",
        confidence=0.9,
        reason="AI",
        is_ai_suggested=True,
    )
    p_rule = ProposedMove(
        source_path=Path("notes.txt"),
        source_rel="notes.txt",
        proposed_category="Documents",
        proposed_rel="Documents/notes.txt",
        confidence=1.0,
        reason="Rule",
        is_ai_suggested=False,
    )
    session = InteractivePlanSession(proposals=[p_ai, p_rule])
    c = Console(file=io.StringIO(), color_system=None)
    c.print(render_interactive_plan(session))
    output = c.file.getvalue()
    assert "⭐ Invoices" in output
    assert "⭐ Documents" not in output

    # In move prompt mode
    session.handle_key("m")
    session.input_buffer = "Inv"
    c_prompt = Console(file=io.StringIO(), color_system=None)
    c_prompt.print(render_interactive_plan(session))
    output_prompt = c_prompt.file.getvalue()
    assert "⭐ Invoices" in output_prompt

