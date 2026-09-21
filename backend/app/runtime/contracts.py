"""Versioned contracts for the public benchmark execution runtime."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


PUBLIC_BENCHMARK_SOURCE_MODE = "PUBLIC_BENCHMARK"
RUNTIME_SCHEMA_VERSION = "public-benchmark-runtime-v1"


class RuntimeStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    REPORT_READY = "REPORT_READY"
    INCONCLUSIVE = "INCONCLUSIVE"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


TERMINAL_STATUSES = frozenset(
    {
        RuntimeStatus.REPORT_READY,
        RuntimeStatus.INCONCLUSIVE,
        RuntimeStatus.REJECTED,
        RuntimeStatus.FAILED,
    }
)


class RuntimeEventName(StrEnum):
    QUEUED = "QUEUED"
    CLAIMED = "CLAIMED"
    REQUEUED = "REQUEUED"
    VALIDATING = "VALIDATING"
    SNAPSHOT_STORED = "SNAPSHOT_STORED"
    BASELINE_EVALUATED = "BASELINE_EVALUATED"
    MODEL_SELECTED = "MODEL_SELECTED"
    FINAL_TEST_REPORTED = "FINAL_TEST_REPORTED"
    REPORT_READY = "REPORT_READY"
    INCONCLUSIVE = "INCONCLUSIVE"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


@dataclass(frozen=True, order=True)
class PublicBenchmarkScope:
    """A bounded published store-product scope, never a merchant SKU scope."""

    store_id: int
    product_id: int

    def __post_init__(self) -> None:
        if self.store_id < 0 or self.product_id < 0:
            raise ValueError("store_id and product_id must be non-negative")

    def to_dict(self) -> dict[str, int]:
        return {"store_id": self.store_id, "product_id": self.product_id}


@dataclass(frozen=True)
class PublicBenchmarkSubmission:
    """The browser-safe execution request stored with an idempotency key."""

    idempotency_key: str
    selection_id: str
    scopes: tuple[PublicBenchmarkScope, ...]
    as_of: datetime

    def __post_init__(self) -> None:
        if not self.idempotency_key.strip() or len(self.idempotency_key) > 128:
            raise ValueError("idempotency_key must be between 1 and 128 characters")
        if not self.selection_id.strip() or len(self.selection_id) > 128:
            raise ValueError("selection_id must be between 1 and 128 characters")
        if self.as_of.tzinfo is None:
            raise ValueError("as_of must include a timezone")
        if not 20 <= len(self.scopes) <= 50:
            raise ValueError("FreshRetailNet selection must contain 20 to 50 scopes")
        if len(set(self.scopes)) != len(self.scopes):
            raise ValueError("FreshRetailNet selection contains duplicate scopes")
        if not 1 <= len({scope.store_id for scope in self.scopes}) <= 3:
            raise ValueError("FreshRetailNet selection must contain one to three stores")

    def to_dict(self) -> dict[str, object]:
        return {
            "idempotency_key": self.idempotency_key,
            "selection_id": self.selection_id,
            "scopes": [scope.to_dict() for scope in sorted(self.scopes)],
            "as_of": self.as_of.isoformat(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PublicBenchmarkSubmission":
        raw_scopes = payload.get("scopes")
        if not isinstance(raw_scopes, list):
            raise ValueError("runtime payload scopes must be a list")
        try:
            scopes = tuple(
                PublicBenchmarkScope(
                    store_id=int(item["store_id"]), product_id=int(item["product_id"])
                )
                for item in raw_scopes
                if isinstance(item, dict)
            )
            as_of = datetime.fromisoformat(str(payload["as_of"]))
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("runtime payload is malformed") from error
        return cls(
            idempotency_key=str(payload["idempotency_key"]),
            selection_id=str(payload["selection_id"]),
            scopes=scopes,
            as_of=as_of,
        )


@dataclass(frozen=True)
class RuntimeEvent:
    sequence: int
    name: RuntimeEventName
    occurred_at: datetime
    detail: str
    evidence_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "name": self.name.value,
            "occurred_at": self.occurred_at.isoformat(),
            "detail": self.detail,
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True)
class RuntimeRun:
    run_id: str
    submission: PublicBenchmarkSubmission
    status: RuntimeStatus
    created_at: datetime
    updated_at: datetime
    attempt_count: int
    outcome: dict[str, object] | None = None
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "runtime_schema_version": RUNTIME_SCHEMA_VERSION,
            "run_id": self.run_id,
            "source_mode": PUBLIC_BENCHMARK_SOURCE_MODE,
            "data_classification": PUBLIC_BENCHMARK_SOURCE_MODE,
            "customer_data_ingestion_permitted": False,
            "status": self.status.value,
            "selection_id": self.submission.selection_id,
            "scopes": [scope.to_dict() for scope in sorted(self.submission.scopes)],
            "as_of": self.submission.as_of.isoformat(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "attempt_count": self.attempt_count,
            "outcome": self.outcome,
            "limitations": (
                list(self.outcome.get("limitations", ())) if self.outcome else []
            ),
            "prohibited_operations": [
                "customer_data_access",
                "inventory_risk",
                "replenishment_action",
                "external_execution",
            ],
        }
