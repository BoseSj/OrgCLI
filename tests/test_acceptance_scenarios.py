"""Comprehensive Acceptance Scenarios Test Suite.

Verifies all 16 required acceptance scenarios:
1. Runtime missing
2. Runtime unreachable
3. Model already installed
4. Model not installed
5. Pull success
6. Pull failure
7. Pull cancellation
8. Progress messages without byte counts
9. Malformed responses
10. Model capability mismatch
11. Model readiness failure (smoke test failure)
12. Configuration persistence
13. Switching active model
14. Removal confirmation
15. Strict local-only endpoint validation
16. Operation without AI
"""

from pathlib import Path
import threading
from typing import List
from typer.testing import CliRunner
import pytest

from organizer.cli import app
from organizer.config import (
    AppConfig,
    ModelSettings,
    NonLoopbackEndpointError,
    OperationalMode,
    load_config,
    save_config,
    validate_loopback_endpoint,
)
from organizer.models.adapter import (
    OllamaProviderAdapter,
    PullProgress,
    RuntimeState,
)
from organizer.models.catalog import Modality, ModelCatalog
from organizer.models.lifecycle import (
    LocalModelLifecycleService,
    ModelReadinessState,
)
from organizer.rules import scan_and_propose_tree
from organizer.testing.fake_ollama import FakeOllamaServer

runner = CliRunner(env={"COLUMNS": "120"})


# 1. Scenario: Runtime missing
def test_scenario_01_runtime_missing(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    adapter = OllamaProviderAdapter("http://127.0.0.1:54999")
    service = LocalModelLifecycleService(adapter=adapter, config_path=cfg_file)

    check = service.check_runtime()
    assert check.is_available is False
    assert check.state in (RuntimeState.STOPPED, RuntimeState.NOT_INSTALLED)
    assert "Ollama" in (check.details or "")


# 2. Scenario: Runtime unreachable
def test_scenario_02_runtime_unreachable(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    adapter = OllamaProviderAdapter("http://127.0.0.1:54999")
    service = LocalModelLifecycleService(adapter=adapter, config_path=cfg_file)

    readiness = service.verify_readiness("gemma4:e2b")
    assert readiness.is_ready is False
    assert readiness.state == ModelReadinessState.RUNTIME_UNAVAILABLE


# 3. Scenario: Model already installed
def test_scenario_03_model_already_installed(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    with FakeOllamaServer() as server:
        server.installed_models = [{"name": "gemma4:e2b", "size": 1600000000}]
        adapter = OllamaProviderAdapter(server.endpoint)
        service = LocalModelLifecycleService(adapter=adapter, config_path=cfg_file)

        models = service.discover_local_models()
        assert len(models) == 1
        assert models[0].name == "gemma4:e2b"
        assert models[0].is_ready is True

        readiness = service.verify_readiness("gemma4:e2b")
        assert readiness.is_ready is True
        assert readiness.state == ModelReadinessState.READY


# 4. Scenario: Model not installed
def test_scenario_04_model_not_installed(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    with FakeOllamaServer() as server:
        server.installed_models = []
        adapter = OllamaProviderAdapter(server.endpoint)
        service = LocalModelLifecycleService(adapter=adapter, config_path=cfg_file)

        readiness = service.verify_readiness("gemma4:e2b")
        assert readiness.is_ready is False
        assert readiness.state == ModelReadinessState.NOT_INSTALLED


# 5. Scenario: Pull success
def test_scenario_05_pull_success(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    with FakeOllamaServer() as server:
        adapter = OllamaProviderAdapter(server.endpoint)
        service = LocalModelLifecycleService(adapter=adapter, config_path=cfg_file)

        events: List[PullProgress] = []
        success = service.pull_model(
            "gemma4:e2b",
            progress_callback=lambda p: events.append(p),
        )
        assert success is True
        assert any(e.status == "success" for e in events)
        assert any(e.has_bytes for e in events)


# 6. Scenario: Pull failure
def test_scenario_06_pull_failure(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    with FakeOllamaServer() as server:
        server.fail_pull = True
        adapter = OllamaProviderAdapter(server.endpoint)
        service = LocalModelLifecycleService(adapter=adapter, config_path=cfg_file)

        events: List[PullProgress] = []
        success = service.pull_model(
            "nonexistent_model",
            progress_callback=lambda p: events.append(p),
        )
        assert success is False
        assert any(e.status == "error" for e in events)


# 7. Scenario: Cancellation
def test_scenario_07_cancellation(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    with FakeOllamaServer() as server:
        server.slow_pull_delay = 0.05
        adapter = OllamaProviderAdapter(server.endpoint)
        service = LocalModelLifecycleService(adapter=adapter, config_path=cfg_file)

        cancel_event = threading.Event()
        cancel_event.set()

        events: List[PullProgress] = []
        success = service.pull_model(
            "gemma4:e2b",
            progress_callback=lambda p: events.append(p),
            cancel_event=cancel_event,
        )
        assert success is False
        assert any(e.status == "cancelled" for e in events)


# 8. Scenario: Progress messages without byte counts
def test_scenario_08_progress_messages_without_byte_counts(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    with FakeOllamaServer() as server:
        server.progress_without_bytes = True
        adapter = OllamaProviderAdapter(server.endpoint)
        service = LocalModelLifecycleService(adapter=adapter, config_path=cfg_file)

        events: List[PullProgress] = []
        success = service.pull_model(
            "gemma4:e2b",
            progress_callback=lambda p: events.append(p),
        )
        assert success is True
        assert len(events) > 0
        assert all(e.has_bytes is False for e in events)


# 9. Scenario: Malformed responses
def test_scenario_09_malformed_responses(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    with FakeOllamaServer() as server:
        server.malformed_tags_response = True
        adapter = OllamaProviderAdapter(server.endpoint)
        service = LocalModelLifecycleService(adapter=adapter, config_path=cfg_file)

        with pytest.raises(RuntimeError, match="malformed response"):
            service.discover_local_models()


# 10. Scenario: Model capability mismatch
def test_scenario_10_model_capability_mismatch(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    catalog = ModelCatalog()
    service = LocalModelLifecycleService(catalog=catalog, config_path=cfg_file)

    # Gemma 4 E2B satisfies vision requirements
    assert service.verify_capabilities("gemma4:e2b", [Modality.TEXT, Modality.IMAGE]) is True

    # Gemma 2 2B does not satisfy vision requirement
    assert service.verify_capabilities("gemma2:2b", [Modality.TEXT, Modality.IMAGE]) is False


# 11. Scenario: Model readiness failure (smoke test failure)
def test_scenario_11_readiness_smoke_test_failure(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    with FakeOllamaServer() as server:
        server.installed_models = [{"name": "gemma4:e2b", "size": 1600000000}]
        server.fail_smoke_test = True
        adapter = OllamaProviderAdapter(server.endpoint)
        service = LocalModelLifecycleService(adapter=adapter, config_path=cfg_file)

        readiness = service.verify_readiness("gemma4:e2b")
        assert readiness.is_ready is False
        assert readiness.state == ModelReadinessState.SMOKE_TEST_FAILED


# 12. Scenario: Configuration persistence
def test_scenario_12_configuration_persistence(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    cfg = AppConfig(
        setup_completed=True,
        operational_mode=OperationalMode.AI,
        active_model="gemma4:e2b",
        model_settings=ModelSettings(
            endpoint="http://127.0.0.1:11434",
            context_length=4096,
        ),
    )
    save_config(cfg, cfg_file)

    loaded = load_config(cfg_file)
    assert loaded.setup_completed is True
    assert loaded.active_model == "gemma4:e2b"
    assert loaded.model_settings.context_length == 4096


# 13. Scenario: Switching active model
def test_scenario_13_switching_active_model(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    with FakeOllamaServer() as server:
        server.installed_models = [
            {"name": "gemma4:e2b", "size": 1600000000},
            {"name": "gemma2:2b", "size": 1700000000},
        ]
        adapter = OllamaProviderAdapter(server.endpoint)
        service = LocalModelLifecycleService(adapter=adapter, config_path=cfg_file)

        # Set first model
        service.set_active_model("gemma4:e2b")
        assert load_config(cfg_file).active_model == "gemma4:e2b"

        # Switch to second model
        service.set_active_model("gemma2:2b")
        assert load_config(cfg_file).active_model == "gemma2:2b"


# 14. Scenario: Removal confirmation
def test_scenario_14_removal_confirmation(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    with FakeOllamaServer() as server:
        server.installed_models = [{"name": "gemma4:e2b", "size": 1600000000}]
        cfg = AppConfig(
            setup_completed=True,
            active_model="gemma4:e2b",
            model_settings={"endpoint": server.endpoint},
        )
        save_config(cfg, cfg_file)

        # Abort on 'n'
        res_abort = runner.invoke(app, ["models", "remove", "gemma4:e2b", "--config", str(cfg_file)], input="n\n")
        assert "Removal cancelled" in res_abort.stdout
        assert len(server.installed_models) == 1

        # Delete on 'y'
        res_del = runner.invoke(app, ["models", "remove", "gemma4:e2b", "--config", str(cfg_file)], input="y\n")
        assert "removed successfully" in res_del.stdout
        assert len(server.installed_models) == 0


# 15. Scenario: Strict local-only validation
def test_scenario_15_strict_local_only_validation():
    # Valid loopback
    assert validate_loopback_endpoint("http://localhost:11434") == "http://localhost:11434"
    assert validate_loopback_endpoint("http://127.0.0.1:11434") == "http://127.0.0.1:11434"

    # Cloud or non-loopback endpoints strictly rejected
    with pytest.raises(NonLoopbackEndpointError):
        validate_loopback_endpoint("https://api.openai.com/v1")

    with pytest.raises(NonLoopbackEndpointError):
        validate_loopback_endpoint("http://cloud-inference.org:8080")

    with pytest.raises(NonLoopbackEndpointError):
        validate_loopback_endpoint("http://192.168.1.100:11434")


# 16. Scenario: Operation without AI (Rule-only)
def test_scenario_16_operation_without_ai(tmp_path: Path):
    folder = tmp_path / "test_folder"
    folder.mkdir()
    (folder / "file.pdf").write_text("dummy")
    (folder / "image.png").write_text("dummy")

    proposals = scan_and_propose_tree(folder)
    assert len(proposals) == 2
    assert proposals[0].proposed_category in ("Documents", "Images")
    assert proposals[1].proposed_category in ("Documents", "Images")


# 17. Scenario: Folder-Grouped Presentation with Item Counts
def test_scenario_17_grouped_scan_plan_with_counts(tmp_path: Path):
    from organizer.rules import group_proposals_by_destination

    folder = tmp_path / "downloads"
    folder.mkdir()
    (folder / "resume.pdf").write_text("cv")
    (folder / "letter.docx").write_text("doc")
    (folder / "photo.jpg").write_text("img")

    cfg_file = tmp_path / "config.json"
    cfg = AppConfig(setup_completed=True, operational_mode=OperationalMode.RULE_ONLY)
    save_config(cfg, cfg_file)

    res = runner.invoke(app, ["scan", str(folder), "--config", str(cfg_file)])
    assert res.exit_code == 0
    assert "Documents (2 files)" in res.stdout
    assert "Images (1 file)" in res.stdout
    assert "Summary: 3 files to organize across 2 destination folders" in res.stdout


# 18. Scenario: Interactive Plan Navigation, Selection, and Reassignment
def test_scenario_18_interactive_plan_navigation_and_reassignment(tmp_path: Path):
    from organizer.ui.interactive_plan import InteractivePlanSession

    folder = tmp_path / "items"
    folder.mkdir()
    (folder / "doc1.pdf").write_text("1")
    (folder / "doc2.pdf").write_text("2")
    (folder / "img1.png").write_text("3")

    proposals = scan_and_propose_tree(folder)
    session = InteractivePlanSession(proposals=proposals, target_dir=folder)

    # 1. Navigate down
    assert session.cursor == 0
    session.handle_key("down")
    assert session.cursor == 1

    # 2. Select file
    session.handle_key("space")
    assert session.selected_indices == {1}

    # 3. Reassign selected file using 'm' to a new folder
    session.handle_key("m")
    assert session.mode == "move_prompt"
    for ch in "Portfolio":
        session.handle_key(ch)
    session.handle_key("enter")
    assert session.mode == "browse"

    # Verify item moved to new category and folder counts updated
    from organizer.rules import group_proposals_by_destination
    groups = group_proposals_by_destination(session.proposals)
    folder_names = [g.folder_name for g in groups]
    assert "Portfolio" in folder_names

    # 4. Deselect all
    session.handle_key("space")
    assert len(session.selected_indices) > 0
    session.handle_key("d")
    assert len(session.selected_indices) == 0


# 19. Scenario: Empty Directory Handling
def test_scenario_19_empty_scan_handling(tmp_path: Path):
    folder = tmp_path / "empty"
    folder.mkdir()

    cfg_file = tmp_path / "config.json"
    cfg = AppConfig(setup_completed=True, operational_mode=OperationalMode.RULE_ONLY)
    save_config(cfg, cfg_file)

    res = runner.invoke(app, ["scan", str(folder), "--config", str(cfg_file)])
    assert res.exit_code == 0
    assert "No eligible files found to organize." in res.stdout

