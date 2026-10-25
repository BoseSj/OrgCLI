"""Local model lifecycle service orchestrating discovery, downloads, verification, and diagnostics."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import threading
from typing import Any, Callable, Dict, List, Optional

from organizer.config import (
    AppConfig,
    OperationalMode,
    load_config,
    save_config,
)
from organizer.models.adapter import (
    InstalledModel,
    OllamaProviderAdapter,
    PullProgress,
    RuntimeCheckResult,
    RuntimeState,
)
from organizer.models.gemini_adapter import GeminiProviderAdapter
from organizer.models.openrouter_adapter import OpenRouterProviderAdapter
from organizer.models.catalog import (
    CatalogEntry,
    HostResources,
    ModelCatalog,
    Modality,
    ResourceEvaluation,
    evaluate_model_resources,
    inspect_host_resources,
)


class ModelReadinessState(str, Enum):
    READY = "ready"
    NOT_INSTALLED = "not_installed"
    SMOKE_TEST_FAILED = "smoke_test_failed"
    CAPABILITY_MISMATCH = "capability_mismatch"
    RUNTIME_UNAVAILABLE = "runtime_unavailable"


@dataclass
class DiscoveredModel:
    """Discovered local model with catalog enrichment if known."""

    name: str
    size_bytes: int
    size_gb: float
    is_active: bool
    catalog_entry: Optional[CatalogEntry] = None
    is_ready: bool = False


@dataclass
class ReadinessResult:
    """Detailed result of checking whether a model is ready for inference."""

    state: ModelReadinessState
    is_ready: bool
    message: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class DiagnosticReport:
    """Health report for runtime, catalog, and active model."""

    runtime_check: RuntimeCheckResult
    operational_mode: OperationalMode
    active_model: Optional[str]
    readiness: ReadinessResult
    host_resources: HostResources
    installed_models_count: int
    diagnostics_passed: bool
    warnings: List[str]


class LocalModelLifecycleService:
    """High-level service managing local models independently of document categorization."""

    def __init__(
        self,
        adapter: Optional[OllamaProviderAdapter] = None,
        catalog: Optional[ModelCatalog] = None,
        config_path: Optional[Path] = None,
        gemini_adapter: Optional[GeminiProviderAdapter] = None,
        openrouter_adapter: Optional[OpenRouterProviderAdapter] = None,
    ) -> None:
        self.config_path = config_path
        self.config: AppConfig = load_config(config_path)
        self.adapter = adapter or OllamaProviderAdapter(
            endpoint=self.config.model_settings.endpoint,
            timeout_seconds=self.config.model_settings.timeout_seconds,
        )
        self.catalog = catalog or ModelCatalog()
        self.gemini_adapter = gemini_adapter or GeminiProviderAdapter(
            api_key=self.config.gemini_settings.api_key,
            model_name=self.config.gemini_settings.model_name,
            timeout_seconds=self.config.gemini_settings.timeout_seconds,
        )
        self.openrouter_adapter = openrouter_adapter or OpenRouterProviderAdapter(
            api_key=self.config.openrouter_settings.api_key,
            model_name=self.config.openrouter_settings.model_name,
            base_url=self.config.openrouter_settings.base_url,
            timeout_seconds=self.config.openrouter_settings.timeout_seconds,
            app_referer=self.config.openrouter_settings.app_referer,
            app_title=self.config.openrouter_settings.app_title,
        )

    def reload_config(self) -> AppConfig:
        """Reload configuration from disk."""
        self.config = load_config(self.config_path)
        return self.config

    def check_runtime(self) -> RuntimeCheckResult:
        """Check whether Ollama runtime is installed and responsive."""
        return self.adapter.check_runtime()

    def discover_local_models(self) -> List[DiscoveredModel]:
        """Discover all installed local models and annotate with catalog metadata and active status."""
        runtime = self.check_runtime()
        if not runtime.is_available:
            return []

        installed = self.adapter.list_installed_models()
        active = self.config.active_model
        results: List[DiscoveredModel] = []

        for m in installed:
            entry = self.catalog.get_entry(m.name)
            is_active = (m.name == active)
            results.append(
                DiscoveredModel(
                    name=m.name,
                    size_bytes=m.size,
                    size_gb=m.size_gb,
                    is_active=is_active,
                    catalog_entry=entry,
                    is_ready=True,
                )
            )
        return results

    def verify_capabilities(
        self, model_id: str, required_modalities: Optional[List[str]] = None
    ) -> bool:
        """Verify if a model satisfies required modalities (e.g. vision support)."""
        required = required_modalities or [Modality.TEXT]
        entry = self.catalog.get_entry(model_id)
        if not entry:
            # If not in catalog, assume text only
            return Modality.IMAGE not in required

        for req in required:
            if req not in entry.supported_modalities:
                return False
        return True

    def verify_readiness(self, model_id: Optional[str] = None) -> ReadinessResult:
        """Verify model readiness: runtime up -> model in tags -> smoke test succeeds."""
        if self.config.operational_mode == OperationalMode.GEMINI:
            cred = self.gemini_adapter.check_credentials()
            if not cred.is_available:
                return ReadinessResult(
                    state=ModelReadinessState.NOT_INSTALLED,
                    is_ready=False,
                    message=cred.message,
                )
            smoke_ok, smoke_msg = self.gemini_adapter.run_smoke_test()
            if not smoke_ok:
                return ReadinessResult(
                    state=ModelReadinessState.SMOKE_TEST_FAILED,
                    is_ready=False,
                    message=smoke_msg,
                )
            return ReadinessResult(
                state=ModelReadinessState.READY,
                is_ready=True,
                message=f"Gemini API model '{self.gemini_adapter.model_name}' is connected and ready.",
            )

        if self.config.operational_mode == OperationalMode.OPENROUTER:
            cred = self.openrouter_adapter.check_credentials()
            if not cred.is_available:
                return ReadinessResult(
                    state=ModelReadinessState.NOT_INSTALLED,
                    is_ready=False,
                    message=cred.message,
                )
            smoke_ok, smoke_msg = self.openrouter_adapter.run_smoke_test()
            if not smoke_ok:
                return ReadinessResult(
                    state=ModelReadinessState.SMOKE_TEST_FAILED,
                    is_ready=False,
                    message=smoke_msg,
                )
            return ReadinessResult(
                state=ModelReadinessState.READY,
                is_ready=True,
                message=f"OpenRouter model '{self.openrouter_adapter.model_name}' is connected and ready.",
            )

        target_model = model_id or self.config.active_model
        if not target_model:
            return ReadinessResult(
                state=ModelReadinessState.NOT_INSTALLED,
                is_ready=False,
                message="No active model configured.",
            )

        runtime = self.check_runtime()
        if not runtime.is_available:
            return ReadinessResult(
                state=ModelReadinessState.RUNTIME_UNAVAILABLE,
                is_ready=False,
                message=f"Runtime unavailable: {runtime.details}",
            )

        # Check installed models
        try:
            installed = self.adapter.list_installed_models()
        except Exception as exc:
            return ReadinessResult(
                state=ModelReadinessState.RUNTIME_UNAVAILABLE,
                is_ready=False,
                message=f"Failed to query local models: {exc}",
            )

        installed_names = [m.name for m in installed]
        if target_model not in installed_names:
            return ReadinessResult(
                state=ModelReadinessState.NOT_INSTALLED,
                is_ready=False,
                message=f"Model '{target_model}' is not installed locally in Ollama.",
            )

        # Smoke test execution
        smoke_ok = self.adapter.run_smoke_test(target_model)
        if not smoke_ok:
            return ReadinessResult(
                state=ModelReadinessState.SMOKE_TEST_FAILED,
                is_ready=False,
                message=f"Smoke test failed for model '{target_model}'. The model runner did not respond.",
            )

        return ReadinessResult(
            state=ModelReadinessState.READY,
            is_ready=True,
            message=f"Model '{target_model}' is installed, responsive, and ready.",
        )

    def pull_model(
        self,
        model_id: str,
        progress_callback: Optional[Callable[[PullProgress], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> bool:
        """Orchestrate streaming model download, reporting events to callback."""
        runtime = self.check_runtime()
        if not runtime.is_available:
            raise RuntimeError(f"Cannot pull model: {runtime.details}")

        last_status = "unknown"
        success = False

        for progress in self.adapter.pull_model_stream(model_id, cancel_event=cancel_event):
            last_status = progress.status
            if progress_callback:
                progress_callback(progress)

            if progress.status == "success":
                success = True
            elif progress.status in ("error", "cancelled"):
                return False

        return success

    def set_active_model(self, model_id: str, verify_first: bool = True) -> ReadinessResult:
        """Verify readiness and persist model as active in application config."""
        if verify_first:
            readiness = self.verify_readiness(model_id)
            if not readiness.is_ready:
                return readiness
        else:
            readiness = ReadinessResult(
                state=ModelReadinessState.READY,
                is_ready=True,
                message=f"Model '{model_id}' set as active (unverified).",
            )

        self.config.active_model = model_id
        self.config.setup_completed = True
        self.config.operational_mode = OperationalMode.AI
        save_config(self.config, self.config_path)
        return readiness

    def enable_gemini_mode(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        verify_first: bool = True,
    ) -> ReadinessResult:
        """Configure and persist Google Gemini cloud API mode."""
        if api_key:
            self.config.gemini_settings.api_key = api_key
            self.gemini_adapter.api_key = api_key
        if model_name:
            self.config.gemini_settings.model_name = model_name
            self.gemini_adapter.model_name = model_name
        elif getattr(self.gemini_adapter, "model_name", None):
            self.config.gemini_settings.model_name = self.gemini_adapter.model_name

        if verify_first:
            smoke_ok, smoke_msg = self.gemini_adapter.run_smoke_test()
            if not smoke_ok:
                return ReadinessResult(
                    state=ModelReadinessState.SMOKE_TEST_FAILED,
                    is_ready=False,
                    message=smoke_msg,
                )

        self.config.operational_mode = OperationalMode.GEMINI
        self.config.active_model = self.config.gemini_settings.model_name
        self.config.setup_completed = True
        save_config(self.config, self.config_path)
        return ReadinessResult(
            state=ModelReadinessState.READY,
            is_ready=True,
            message=f"Google Gemini mode enabled with '{self.config.gemini_settings.model_name}'.",
        )

    def enable_openrouter_mode(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        verify_first: bool = True,
    ) -> ReadinessResult:
        """Configure and persist OpenRouter cloud API mode."""
        if api_key:
            self.config.openrouter_settings.api_key = api_key
            self.openrouter_adapter.api_key = api_key
        if model_name:
            self.config.openrouter_settings.model_name = model_name
            self.openrouter_adapter.model_name = model_name
        elif getattr(self.openrouter_adapter, "model_name", None):
            self.config.openrouter_settings.model_name = self.openrouter_adapter.model_name

        if verify_first:
            smoke_ok, smoke_msg = self.openrouter_adapter.run_smoke_test()
            if not smoke_ok:
                return ReadinessResult(
                    state=ModelReadinessState.SMOKE_TEST_FAILED,
                    is_ready=False,
                    message=smoke_msg,
                )

        self.config.operational_mode = OperationalMode.OPENROUTER
        self.config.active_model = self.config.openrouter_settings.model_name
        self.config.setup_completed = True
        save_config(self.config, self.config_path)
        return ReadinessResult(
            state=ModelReadinessState.READY,
            is_ready=True,
            message=f"OpenRouter mode enabled with '{self.config.openrouter_settings.model_name}'.",
        )

    def enable_rule_only_mode(self) -> None:
        """Configure and persist rule-based operation without AI."""
        self.config.operational_mode = OperationalMode.RULE_ONLY
        self.config.setup_completed = True
        save_config(self.config, self.config_path)

    def remove_model(self, model_id: str) -> bool:
        """Delete local model via Ollama and update active config if needed."""
        deleted = self.adapter.delete_model(model_id)
        if deleted and self.config.active_model == model_id:
            self.config.active_model = None
            save_config(self.config, self.config_path)
        return deleted

    def check_model_resources(self, model_id: str) -> ResourceEvaluation:
        """Evaluate resource requirements for a catalog model against current host."""
        entry = self.catalog.get_entry(model_id)
        resources = inspect_host_resources()
        if not entry:
            # Default fallback for uncataloged model
            return ResourceEvaluation(
                is_sufficient_disk=resources.free_disk_gb >= 5.0,
                is_sufficient_ram=resources.total_ram_gb >= 4.0,
                warnings=[],
            )
        return evaluate_model_resources(entry, resources)

    def run_diagnostics(self) -> DiagnosticReport:
        """Run full diagnostic health check for doctor command."""
        runtime = self.check_runtime()
        resources = inspect_host_resources()
        warnings: List[str] = []

        installed_count = 0
        if runtime.is_available:
            try:
                installed_count = len(self.adapter.list_installed_models())
            except Exception as e:
                warnings.append(f"Failed to query installed models: {e}")

        readiness = self.verify_readiness()

        if self.config.operational_mode == OperationalMode.AI:
            if not runtime.is_available:
                warnings.append(runtime.details or "Runtime is not available.")
            if not readiness.is_ready:
                warnings.append(readiness.message)
        elif self.config.operational_mode in (OperationalMode.GEMINI, OperationalMode.OPENROUTER):
            if not readiness.is_ready:
                warnings.append(readiness.message)

        if resources.free_disk_gb < 3.0:
            warnings.append(f"Low disk space: {resources.free_disk_gb:.1f} GB available.")

        if self.config.operational_mode in (OperationalMode.GEMINI, OperationalMode.OPENROUTER):
            passed = readiness.is_ready
        elif self.config.operational_mode == OperationalMode.RULE_ONLY:
            passed = True
        else:
            passed = runtime.is_available and readiness.is_ready

        return DiagnosticReport(
            runtime_check=runtime,
            operational_mode=self.config.operational_mode,
            active_model=self.config.active_model,
            readiness=readiness,
            host_resources=resources,
            installed_models_count=installed_count,
            diagnostics_passed=passed,
            warnings=warnings,
        )
