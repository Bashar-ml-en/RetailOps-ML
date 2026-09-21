"""Typed artifacts for the explicitly limited FreshRetailNet public benchmark."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from app.schemas.connector import DataContractResult, RunEvent, SnapshotManifest


FRESHRETAILNET_DATASET_ID = "FreshRetailNet-50K"
FRESHRETAILNET_DATASET_VERSION = "1.0"
FRESHRETAILNET_BENCHMARK_TENANT_ID = "public-benchmark:freshretailnet-50k"
FRESHRETAILNET_SOURCE_URL = "https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K"
FRESHRETAILNET_SOURCE_REVISION = "08c1fab7f9257bc73679d415d65d644165d351d4"
FRESHRETAILNET_LICENSE = "CC-BY-4.0"


@dataclass(frozen=True, order=True)
class FreshRetailNetScope:
    """One explicitly selected published store-product series."""

    store_id: int
    product_id: int

    def __post_init__(self) -> None:
        if self.store_id < 0 or self.product_id < 0:
            raise ValueError("FreshRetailNet store_id and product_id must be non-negative")


@dataclass(frozen=True)
class FreshRetailNetBenchmarkRequest:
    """A reproducible, public-data-only benchmark subset declaration.

    ``tenant_id`` is a fixed virtual namespace, never a retailer tenant. The
    source publishes date-only daily observations, so the benchmark uses UTC
    only rather than inventing a store operating timezone.
    """

    selection_id: str
    scopes: tuple[FreshRetailNetScope, ...]
    as_of: datetime
    mapping_version: str = "freshretailnet-50k-v1"
    dataset_version: str = FRESHRETAILNET_DATASET_VERSION
    tenant_id: str = FRESHRETAILNET_BENCHMARK_TENANT_ID
    operating_timezone: str = "UTC"
    source_revision: str = FRESHRETAILNET_SOURCE_REVISION
    source_file_name: str | None = None
    source_file_sha256: str | None = None

    def __post_init__(self) -> None:
        if not self.selection_id.strip():
            raise ValueError("selection_id is required")
        if self.as_of.tzinfo is None:
            raise ValueError("as_of must include a timezone")
        if self.tenant_id != FRESHRETAILNET_BENCHMARK_TENANT_ID:
            raise ValueError("FreshRetailNet must use its fixed public benchmark namespace")
        if self.dataset_version != FRESHRETAILNET_DATASET_VERSION:
            raise ValueError("FreshRetailNet dataset_version must be 1.0")
        if self.source_revision != FRESHRETAILNET_SOURCE_REVISION:
            raise ValueError("FreshRetailNet source_revision must be the approved pinned revision")
        if self.source_file_sha256 is not None and (
            len(self.source_file_sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.source_file_sha256.lower())
        ):
            raise ValueError("source_file_sha256 must be a SHA-256 hex digest when declared")
        if self.operating_timezone != "UTC":
            raise ValueError("FreshRetailNet date-only observations require operating_timezone UTC")
        if not 20 <= len(self.scopes) <= 50:
            raise ValueError("FreshRetailNet selection must contain 20 to 50 store-product scopes")
        if len(set(self.scopes)) != len(self.scopes):
            raise ValueError("FreshRetailNet selection contains duplicate store-product scopes")
        if not 1 <= len({scope.store_id for scope in self.scopes}) <= 3:
            raise ValueError("FreshRetailNet selection must contain one to three stores")


@dataclass(frozen=True)
class FreshRetailNetBenchmarkRun:
    """Immutable provenance and decision record for a public benchmark subset."""

    run_id: str
    request: FreshRetailNetBenchmarkRequest
    manifest: SnapshotManifest
    result: DataContractResult
    agent_decision: dict[str, object] | None = None
    events: tuple[RunEvent, ...] = field(default_factory=tuple)
    run_schema_version: Literal["freshretailnet-benchmark-run-v1"] = (
        "freshretailnet-benchmark-run-v1"
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "run_schema_version": self.run_schema_version,
            "run_id": self.run_id,
            "source_type": "PUBLIC_BENCHMARK",
            "data_classification": "PUBLIC_BENCHMARK",
            "customer_data_ingestion_permitted": False,
            "tenant_id": self.request.tenant_id,
            "selection_id": self.request.selection_id,
            "dataset": {
                "id": FRESHRETAILNET_DATASET_ID,
                "version": self.request.dataset_version,
                "source_url": FRESHRETAILNET_SOURCE_URL,
                "source_revision": self.request.source_revision,
                "source_file_name": self.request.source_file_name,
                "source_file_sha256": self.request.source_file_sha256,
                "license": FRESHRETAILNET_LICENSE,
                "attribution": "FreshRetailNet-50K, Dingdong-Inc",
            },
            "operating_timezone": self.request.operating_timezone,
            "snapshot": self.manifest.to_dict(),
            "data_contract": self.result.to_dict(),
            "agent_decision": self.agent_decision,
            "events": [event.to_dict() for event in self.events],
        }


@dataclass(frozen=True)
class FinalTestScopeEvaluation:
    """One post-selection, locked-test result for a public benchmark scope."""

    sku: str
    location_id: str
    quantity_unit: str
    locked_test_start: str
    locked_test_end: str
    locked_test_days: int
    selected_model_mae: float
    selected_model_rmse: float

    @property
    def scope_ref(self) -> str:
        return f"sku:{self.sku}|location:{self.location_id}|unit:{self.quantity_unit}"

    def to_dict(self) -> dict[str, object]:
        return {
            "sku": self.sku,
            "location_id": self.location_id,
            "quantity_unit": self.quantity_unit,
            "locked_test_start": self.locked_test_start,
            "locked_test_end": self.locked_test_end,
            "locked_test_days": self.locked_test_days,
            "selected_model_mae": self.selected_model_mae,
            "selected_model_rmse": self.selected_model_rmse,
        }


@dataclass(frozen=True)
class FreshRetailNetFinalTestReport:
    """An immutable, labelled final-test report that cannot alter selection."""

    report_id: str
    evaluated_at: datetime
    benchmark_run_id: str
    baseline_run_id: str
    model_run_id: str
    snapshot_id: str
    tenant_id: str
    source_revision: str
    source_file_sha256: str | None
    selected_model_version: str
    selection: Literal["PROMOTED_CANDIDATE", "RETAINED_BASELINE"]
    selection_rationale: str
    status: Literal["PASS", "PASS_WITH_LIMITATIONS"]
    evaluations: tuple[FinalTestScopeEvaluation, ...]
    macro_average_mae: float
    macro_average_rmse: float
    limitations: tuple[str, ...] = field(default_factory=tuple)
    agent_decision: dict[str, object] | None = None
    report_schema_version: Literal["freshretailnet-final-test-report-v1"] = (
        "freshretailnet-final-test-report-v1"
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "report_schema_version": self.report_schema_version,
            "report_id": self.report_id,
            "evaluated_at": self.evaluated_at.isoformat(),
            "source_type": "PUBLIC_BENCHMARK",
            "data_classification": "PUBLIC_BENCHMARK",
            "customer_data_ingestion_permitted": False,
            "tenant_id": self.tenant_id,
            "benchmark_run_id": self.benchmark_run_id,
            "baseline_run_id": self.baseline_run_id,
            "model_run_id": self.model_run_id,
            "snapshot_id": self.snapshot_id,
            "dataset": {
                "id": FRESHRETAILNET_DATASET_ID,
                "version": FRESHRETAILNET_DATASET_VERSION,
                "source_url": FRESHRETAILNET_SOURCE_URL,
                "source_revision": self.source_revision,
                "source_file_sha256": self.source_file_sha256,
                "license": FRESHRETAILNET_LICENSE,
                "attribution": "FreshRetailNet-50K, Dingdong-Inc",
            },
            "selection": {
                "selection": self.selection,
                "selected_model_version": self.selected_model_version,
                "selection_rationale": self.selection_rationale,
                "selection_inputs": "chronological_validation_only",
                "selection_changed_by_final_test": False,
            },
            "final_test": {
                "evaluation_timing": "post_selection_once",
                "metrics": {
                    "macro_average_mae": self.macro_average_mae,
                    "macro_average_rmse": self.macro_average_rmse,
                },
                "evaluations": [evaluation.to_dict() for evaluation in self.evaluations],
            },
            "limitations": list(self.limitations),
            "prohibited_claims": [
                "customer_forecast_accuracy",
                "retailer_business_impact",
                "inventory_risk",
                "replenishment_action",
                "production_model",
            ],
            "agent_decision": self.agent_decision,
        }
