"""Model catalog definitions, metadata, and hardware advisory checks."""

from dataclasses import dataclass, field
import shutil
from typing import Dict, List, Optional
import psutil
from pydantic import BaseModel, Field


class Modality:
    TEXT = "text"
    IMAGE = "image"


class HardwareRequirement(BaseModel):
    """Estimated hardware requirements based on verifiable local model benchmarks."""

    min_ram_gb: float = Field(description="Minimum RAM in gigabytes to run inference safely")
    recommended_ram_gb: float = Field(description="Recommended RAM in gigabytes")
    estimated_disk_gb: float = Field(description="Estimated disk space required in gigabytes")


class CatalogEntry(BaseModel):
    """Entry in the local model catalog."""

    model_id: str = Field(description="Exact Ollama model identifier and tag, e.g. 'gemma4:e2b'")
    display_name: str = Field(description="Human-readable display name")
    family: str = Field(description="Model family, e.g. 'gemma'")
    variant: str = Field(description="Model variant or parameter scale, e.g. 'e2b'")
    supported_modalities: List[str] = Field(default_factory=lambda: [Modality.TEXT])
    approx_download_bytes: Optional[int] = Field(
        default=None, description="Verified download size in bytes if known"
    )
    hardware: HardwareRequirement
    compatibility_constraints: List[str] = Field(default_factory=list)
    is_recommended: bool = Field(default=False)
    recommendation_reason: Optional[str] = None
    catalog_metadata_version: str = "1.0.0"
    source: str = "curated-local-v1"

    @property
    def supports_vision(self) -> bool:
        """Check if the model supports image/vision input."""
        return Modality.IMAGE in self.supported_modalities

    @property
    def download_size_str(self) -> str:
        """Human-readable download size matching download progress meters (decimal GB/MB)."""
        if not self.approx_download_bytes:
            return "Unknown"
        gb = self.approx_download_bytes / 1_000_000_000
        if gb >= 1.0:
            return f"{gb:.1f} GB"
        mb = self.approx_download_bytes / 1_000_000
        return f"{mb:.0f} MB"


# Pre-populated local catalog containing verified local models
DEFAULT_CATALOG: Dict[str, CatalogEntry] = {
    "gemma4:e2b": CatalogEntry(
        model_id="gemma4:e2b",
        display_name="Gemma 4 E2B (Multimodal)",
        family="gemma",
        variant="e2b",
        supported_modalities=[Modality.TEXT, Modality.IMAGE],
        approx_download_bytes=7_476_595_162,  # Verified Ollama pull size (~7.5 GB)
        hardware=HardwareRequirement(
            min_ram_gb=4.0,
            recommended_ram_gb=8.0,
            estimated_disk_gb=9.0,
        ),
        compatibility_constraints=[
            "macOS 12+ or Linux with Ollama >= 0.1.30",
            "Apple Silicon or AVX2 x86_64",
        ],
        is_recommended=True,
        recommendation_reason="Lightweight, fast multimodal model suited for 8 GB unified-memory Macs",
    ),
    "gemma2:2b": CatalogEntry(
        model_id="gemma2:2b",
        display_name="Gemma 2 2B (Text Only)",
        family="gemma",
        variant="2b",
        supported_modalities=[Modality.TEXT],
        approx_download_bytes=1_629_518_008,  # Verified Ollama pull size (~1.6 GB)
        hardware=HardwareRequirement(
            min_ram_gb=4.0,
            recommended_ram_gb=8.0,
            estimated_disk_gb=3.5,
        ),
        compatibility_constraints=["Ollama >= 0.1.30"],
        is_recommended=False,
        recommendation_reason="Text-only fallback for low-resource environments",
    ),
    "gemma2:9b": CatalogEntry(
        model_id="gemma2:9b",
        display_name="Gemma 2 9B (High Quality Text)",
        family="gemma",
        variant="9b",
        supported_modalities=[Modality.TEXT],
        approx_download_bytes=5_443_151_930,  # Verified Ollama pull size (~5.4 GB)
        hardware=HardwareRequirement(
            min_ram_gb=12.0,
            recommended_ram_gb=16.0,
            estimated_disk_gb=10.0,
        ),
        compatibility_constraints=["Requires 12+ GB available RAM"],
        is_recommended=False,
        recommendation_reason="High precision model; requires 16 GB+ unified memory",
    ),
}


class ModelCatalog:
    """Catalog abstraction managing supported local models."""

    def __init__(self, entries: Optional[Dict[str, CatalogEntry]] = None) -> None:
        self._entries: Dict[str, CatalogEntry] = dict(entries or DEFAULT_CATALOG)

    def get_entry(self, model_id: str) -> Optional[CatalogEntry]:
        """Fetch catalog entry by exact model identifier."""
        return self._entries.get(model_id)

    def list_entries(self) -> List[CatalogEntry]:
        """Return all catalog entries."""
        return list(self._entries.values())

    def get_recommended(self) -> Optional[CatalogEntry]:
        """Return the default recommended model."""
        for entry in self._entries.values():
            if entry.is_recommended:
                return entry
        return None

    def register_entry(self, entry: CatalogEntry) -> None:
        """Register or update an entry in the catalog."""
        self._entries[entry.model_id] = entry


@dataclass
class HostResources:
    """Host machine hardware resource snapshot."""

    total_ram_gb: float
    available_ram_gb: float
    free_disk_gb: float


def inspect_host_resources(target_path: Optional[str] = None) -> HostResources:
    """Inspect current host RAM and disk space."""
    vmem = psutil.virtual_memory()
    total_ram_gb = vmem.total / (1024**3)
    available_ram_gb = vmem.available / (1024**3)

    disk = shutil.disk_usage(target_path or "/")
    free_disk_gb = disk.free / (1024**3)

    return HostResources(
        total_ram_gb=round(total_ram_gb, 1),
        available_ram_gb=round(available_ram_gb, 1),
        free_disk_gb=round(free_disk_gb, 1),
    )


@dataclass
class ResourceEvaluation:
    """Evaluation of model suitability on the host machine."""

    is_sufficient_disk: bool
    is_sufficient_ram: bool
    warnings: List[str] = field(default_factory=list)
    advisory_only: bool = True

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0


def evaluate_model_resources(
    entry: CatalogEntry, resources: HostResources
) -> ResourceEvaluation:
    """Check if the selected catalog entry satisfies host resource constraints."""
    warnings: List[str] = []
    is_sufficient_disk = True
    is_sufficient_ram = True

    # Disk space check: Require estimated disk space + 1 GB safety margin
    needed_disk = entry.hardware.estimated_disk_gb + 1.0
    if resources.free_disk_gb < needed_disk:
        is_sufficient_disk = False
        warnings.append(
            f"Low disk space: {resources.free_disk_gb:.1f} GB free, but {entry.display_name} "
            f"requires ~{entry.hardware.estimated_disk_gb:.1f} GB (plus margin)."
        )

    # RAM check: Check against total and available RAM
    if resources.total_ram_gb < entry.hardware.min_ram_gb:
        is_sufficient_ram = False
        warnings.append(
            f"Insufficient total RAM: System has {resources.total_ram_gb:.1f} GB RAM, "
            f"but {entry.display_name} requires at least {entry.hardware.min_ram_gb:.1f} GB."
        )
    elif resources.available_ram_gb < entry.hardware.min_ram_gb:
        warnings.append(
            f"Memory pressure: System currently has {resources.available_ram_gb:.1f} GB available RAM. "
            f"Inference may experience paging or performance slowdowns."
        )

    return ResourceEvaluation(
        is_sufficient_disk=is_sufficient_disk,
        is_sufficient_ram=is_sufficient_ram,
        warnings=warnings,
        advisory_only=is_sufficient_disk,  # Only disk insufficiency is non-advisory
    )
