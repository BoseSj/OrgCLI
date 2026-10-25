"""Tests for organizer.models.catalog module."""

import pytest
from organizer.models.catalog import (
    DEFAULT_CATALOG,
    CatalogEntry,
    HardwareRequirement,
    HostResources,
    ModelCatalog,
    Modality,
    evaluate_model_resources,
    inspect_host_resources,
)


def test_default_catalog_contains_gemma4_e2b():
    catalog = ModelCatalog()
    entry = catalog.get_entry("gemma4:e2b")
    assert entry is not None
    assert entry.display_name == "Gemma 4 E2B (Multimodal)"
    assert entry.family == "gemma"
    assert entry.variant == "e2b"
    assert entry.is_recommended is True
    assert entry.supports_vision is True
    assert Modality.IMAGE in entry.supported_modalities
    assert entry.download_size_str == "7.5 GB"


def test_catalog_distinguishes_vision_and_text_only():
    catalog = ModelCatalog()
    gemma4 = catalog.get_entry("gemma4:e2b")
    assert gemma4.supports_vision is True

    gemma2 = catalog.get_entry("gemma2:2b")
    assert gemma2.supports_vision is False


def test_catalog_custom_registration():
    catalog = ModelCatalog()
    custom = CatalogEntry(
        model_id="custom:1b",
        display_name="Custom 1B",
        family="custom",
        variant="1b",
        supported_modalities=[Modality.TEXT],
        approx_download_bytes=800_000_000,
        hardware=HardwareRequirement(
            min_ram_gb=2.0,
            recommended_ram_gb=4.0,
            estimated_disk_gb=1.5,
        ),
        is_recommended=False,
    )
    catalog.register_entry(custom)
    assert catalog.get_entry("custom:1b") == custom
    assert custom.download_size_str == "800 MB"


def test_inspect_host_resources():
    resources = inspect_host_resources()
    assert resources.total_ram_gb > 0
    assert resources.available_ram_gb > 0
    assert resources.free_disk_gb > 0


def test_evaluate_model_resources_suitable():
    entry = DEFAULT_CATALOG["gemma4:e2b"]
    resources = HostResources(
        total_ram_gb=8.0,
        available_ram_gb=5.0,
        free_disk_gb=20.0,
    )
    eval_res = evaluate_model_resources(entry, resources)
    assert eval_res.is_sufficient_disk is True
    assert eval_res.is_sufficient_ram is True
    assert len(eval_res.warnings) == 0


def test_evaluate_model_resources_low_disk():
    entry = DEFAULT_CATALOG["gemma4:e2b"]
    resources = HostResources(
        total_ram_gb=8.0,
        available_ram_gb=5.0,
        free_disk_gb=2.0,  # entry needs 3.5 + 1.0 = 4.5 GB
    )
    eval_res = evaluate_model_resources(entry, resources)
    assert eval_res.is_sufficient_disk is False
    assert eval_res.advisory_only is False
    assert any("Low disk space" in w for w in eval_res.warnings)


def test_evaluate_model_resources_high_ram_warning():
    entry = DEFAULT_CATALOG["gemma2:9b"]  # requires min 12 GB RAM
    resources = HostResources(
        total_ram_gb=8.0,
        available_ram_gb=4.0,
        free_disk_gb=50.0,
    )
    eval_res = evaluate_model_resources(entry, resources)
    assert eval_res.is_sufficient_ram is False
    assert any("Insufficient total RAM" in w for w in eval_res.warnings)
