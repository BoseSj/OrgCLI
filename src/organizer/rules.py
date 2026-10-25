"""Deterministic rule-based classification and file scanning without AI."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional


@dataclass
class ProposedMove:
    """Proposed file reorganization item."""

    source_path: Path
    source_rel: str
    proposed_category: str
    proposed_rel: str
    confidence: float
    reason: str
    is_ai_suggested: bool = False


@dataclass
class FolderPlanGroup:
    """Group of proposed moves belonging to a destination folder."""

    folder_name: str
    proposals: List[ProposedMove]

    @property
    def count(self) -> int:
        """Total count of proposed files in this folder group."""
        return len(self.proposals)

    @property
    def count_label(self) -> str:
        """Formatted file count string with singular/plural support."""
        c = len(self.proposals)
        return f"{c} file" if c == 1 else f"{c} files"

    @property
    def is_ai_suggested(self) -> bool:
        """Whether this folder contains any AI-suggested file moves."""
        return any(p.is_ai_suggested for p in self.proposals)


def reassign_proposal_destination(proposal: ProposedMove, new_folder: str) -> ProposedMove:
    """Update proposed destination folder and relative path."""
    dest_name = Path(proposal.proposed_rel).name if proposal.proposed_rel else proposal.source_path.name
    clean_folder = new_folder.strip().strip("/")
    if not clean_folder:
        clean_folder = "Other"
    proposal.proposed_category = clean_folder
    proposal.proposed_rel = f"{clean_folder}/{dest_name}"
    return proposal


def group_proposals_by_destination(proposals: List[ProposedMove]) -> List[FolderPlanGroup]:
    """Partition proposals by target destination folder, sorted predictably.

    Standard categories are sorted alphabetically first, custom folders alphabetically,
    and 'Other' placed at the end. Files within each folder are sorted alphabetically.
    """
    groups_map: Dict[str, List[ProposedMove]] = {}
    for p in proposals:
        folder = p.proposed_category or (Path(p.proposed_rel).parts[0] if p.proposed_rel else "Other")
        if folder not in groups_map:
            groups_map[folder] = []
        groups_map[folder].append(p)

    def folder_sort_key(folder: str) -> tuple:
        if folder.lower() == "other":
            return (2, folder.lower())
        return (0, folder.lower())

    result: List[FolderPlanGroup] = []
    for folder in sorted(groups_map.keys(), key=folder_sort_key):
        sorted_proposals = sorted(groups_map[folder], key=lambda x: x.source_path.name.lower())
        result.append(FolderPlanGroup(folder_name=folder, proposals=sorted_proposals))

    return result


EXTENSION_CATEGORY_MAP: Dict[str, str] = {
    # Documents
    ".pdf": "Documents",
    ".docx": "Documents",
    ".doc": "Documents",
    ".txt": "Documents",
    ".md": "Documents",
    ".rtf": "Documents",
    # Images
    ".png": "Images",
    ".jpg": "Images",
    ".jpeg": "Images",
    ".gif": "Images",
    ".webp": "Images",
    ".svg": "Images",
    # Archives
    ".zip": "Archives",
    ".tar": "Archives",
    ".gz": "Archives",
    ".7z": "Archives",
    # Development
    ".py": "Development",
    ".js": "Development",
    ".ts": "Development",
    ".json": "Development",
    ".html": "Development",
    ".css": "Development",
    # Audio/Video
    ".mp3": "Media",
    ".wav": "Media",
    ".mp4": "Media",
    ".mov": "Media",
}


def classify_file_by_rules(path: Path, root: Path) -> ProposedMove:
    """Classify a single file based solely on deterministic extension and metadata rules."""
    rel_path = path.relative_to(root).as_posix()
    ext = path.suffix.lower()

    category = EXTENSION_CATEGORY_MAP.get(ext, "Other")
    dest_rel = f"{category}/{path.name}"

    return ProposedMove(
        source_path=path,
        source_rel=rel_path,
        proposed_category=category,
        proposed_rel=dest_rel,
        confidence=1.0 if category != "Other" else 0.5,
        reason=f"Deterministic rule for extension '{ext}'" if ext else "No extension found",
    )


def scan_and_propose_tree(
    root_folder: Path,
    include_hidden: bool = False,
    classifier: Optional[Callable[[Path, Path], ProposedMove]] = None,
) -> List[ProposedMove]:
    """Scan root folder recursively for regular files and generate classification proposals."""
    root = root_folder.resolve()
    if not root.is_dir():
        raise ValueError(f"Root path '{root}' is not a valid directory.")

    classify_fn = classifier or classify_file_by_rules
    proposals: List[ProposedMove] = []
    for item in sorted(root.rglob("*")):
        if item.is_file():
            # Skip hidden files unless requested
            if not include_hidden and (item.name.startswith(".") or any(p.startswith(".") for p in item.relative_to(root).parts)):
                continue
            # Skip symlinks
            if item.is_symlink():
                continue
            proposals.append(classify_fn(item, root))

    return proposals
