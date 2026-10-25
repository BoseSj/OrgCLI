"""Unit tests for deterministic rules, grouping logic, and proposal management."""

from pathlib import Path
from organizer.rules import (
    FolderPlanGroup,
    ProposedMove,
    classify_file_by_rules,
    group_proposals_by_destination,
    reassign_proposal_destination,
    scan_and_propose_tree,
)


def test_folder_plan_group_count_and_label():
    p1 = ProposedMove(
        source_path=Path("doc1.pdf"),
        source_rel="doc1.pdf",
        proposed_category="Documents",
        proposed_rel="Documents/doc1.pdf",
        confidence=1.0,
        reason="test",
    )
    group_single = FolderPlanGroup(folder_name="Documents", proposals=[p1])
    assert group_single.count == 1
    assert group_single.count_label == "1 file"

    p2 = ProposedMove(
        source_path=Path("doc2.pdf"),
        source_rel="doc2.pdf",
        proposed_category="Documents",
        proposed_rel="Documents/doc2.pdf",
        confidence=1.0,
        reason="test",
    )
    group_multiple = FolderPlanGroup(folder_name="Documents", proposals=[p1, p2])
    assert group_multiple.count == 2
    assert group_multiple.count_label == "2 files"


def test_group_proposals_by_destination_empty():
    groups = group_proposals_by_destination([])
    assert groups == []


def test_group_proposals_by_destination_sorting():
    p_other = ProposedMove(
        source_path=Path("unknown.xyz"),
        source_rel="unknown.xyz",
        proposed_category="Other",
        proposed_rel="Other/unknown.xyz",
        confidence=0.5,
        reason="test",
    )
    p_doc = ProposedMove(
        source_path=Path("report.pdf"),
        source_rel="report.pdf",
        proposed_category="Documents",
        proposed_rel="Documents/report.pdf",
        confidence=1.0,
        reason="test",
    )
    p_img = ProposedMove(
        source_path=Path("photo.png"),
        source_rel="photo.png",
        proposed_category="Images",
        proposed_rel="Images/photo.png",
        confidence=1.0,
        reason="test",
    )
    p_custom = ProposedMove(
        source_path=Path("fin.xlsx"),
        source_rel="fin.xlsx",
        proposed_category="Finance",
        proposed_rel="Finance/fin.xlsx",
        confidence=1.0,
        reason="test",
    )

    groups = group_proposals_by_destination([p_other, p_doc, p_img, p_custom])
    folder_names = [g.folder_name for g in groups]

    # Documents, Finance, Images sorted alphabetically first; Other sorted last
    assert folder_names == ["Documents", "Finance", "Images", "Other"]
    assert groups[3].folder_name == "Other"
    assert groups[0].count == 1
    assert groups[0].proposals[0].source_rel == "report.pdf"


def test_reassign_proposal_destination():
    p = ProposedMove(
        source_path=Path("receipt.pdf"),
        source_rel="receipt.pdf",
        proposed_category="Documents",
        proposed_rel="Documents/receipt.pdf",
        confidence=1.0,
        reason="test",
    )
    updated = reassign_proposal_destination(p, "Taxes 2026")
    assert updated.proposed_category == "Taxes 2026"
    assert updated.proposed_rel == "Taxes 2026/receipt.pdf"

    # Blank destination falls back to "Other"
    reassign_proposal_destination(p, "   ")
    assert p.proposed_category == "Other"
    assert p.proposed_rel == "Other/receipt.pdf"


def test_folder_plan_group_is_ai_suggested():
    p_rule = ProposedMove(
        source_path=Path("doc.pdf"),
        source_rel="doc.pdf",
        proposed_category="Documents",
        proposed_rel="Documents/doc.pdf",
        confidence=1.0,
        reason="test",
        is_ai_suggested=False,
    )
    group_rule = FolderPlanGroup(folder_name="Documents", proposals=[p_rule])
    assert group_rule.is_ai_suggested is False

    p_ai = ProposedMove(
        source_path=Path("receipt.jpg"),
        source_rel="receipt.jpg",
        proposed_category="Invoices",
        proposed_rel="Invoices/receipt.jpg",
        confidence=0.9,
        reason="AI classification",
        is_ai_suggested=True,
    )
    group_ai = FolderPlanGroup(folder_name="Invoices", proposals=[p_ai])
    assert group_ai.is_ai_suggested is True

    # Mixed group
    group_mixed = FolderPlanGroup(folder_name="Mixed", proposals=[p_rule, p_ai])
    assert group_mixed.is_ai_suggested is True


def test_scan_and_propose_tree_with_custom_classifier(tmp_path: Path):
    folder = tmp_path / "files"
    folder.mkdir()
    (folder / "file1.txt").write_text("content")

    def mock_ai_classifier(path: Path, root: Path) -> ProposedMove:
        return ProposedMove(
            source_path=path,
            source_rel=path.name,
            proposed_category="AI-Category",
            proposed_rel=f"AI-Category/{path.name}",
            confidence=0.95,
            reason="Mocked AI",
            is_ai_suggested=True,
        )

    proposals = scan_and_propose_tree(folder, classifier=mock_ai_classifier)
    assert len(proposals) == 1
    assert proposals[0].proposed_category == "AI-Category"
    assert proposals[0].is_ai_suggested is True


