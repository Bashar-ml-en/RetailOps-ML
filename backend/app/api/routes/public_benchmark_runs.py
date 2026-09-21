"""Public-benchmark run API with no retailer connector or browser file access."""

from __future__ import annotations

from datetime import datetime
from hmac import compare_digest
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import settings
from app.copilot.client import CopilotUnavailable, OpenAIResponsesPlannerCopilot
from app.copilot.evidence import PublicBenchmarkEvidenceGateway
from app.runtime.contracts import PublicBenchmarkScope, PublicBenchmarkSubmission
from app.runtime.store import RuntimeStore


router = APIRouter()


class PublicBenchmarkScopeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_id: int = Field(ge=0)
    product_id: int = Field(ge=0)


class PublicBenchmarkRunInput(BaseModel):
    """Browser-safe request: source paths and connector settings are server-only."""

    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1, max_length=128)
    selection_id: str = Field(min_length=1, max_length=128)
    scopes: list[PublicBenchmarkScopeInput] = Field(min_length=20, max_length=50)
    as_of: datetime

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("as_of must include a timezone")
        return value


def _store() -> RuntimeStore:
    return RuntimeStore(settings.runtime_root)


@router.post(
    "/v1/public-benchmark-runs",
    status_code=status.HTTP_201_CREATED,
    tags=["public-benchmark-runtime"],
)
def create_public_benchmark_run(payload: PublicBenchmarkRunInput, response: Response) -> dict[str, object]:
    """Queue one labelled public benchmark run for an explicitly started worker."""

    try:
        submission = PublicBenchmarkSubmission(
            idempotency_key=payload.idempotency_key,
            selection_id=payload.selection_id,
            scopes=tuple(
                PublicBenchmarkScope(store_id=scope.store_id, product_id=scope.product_id)
                for scope in payload.scopes
            ),
            as_of=payload.as_of,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    run, created = _store().enqueue(submission)
    if not created:
        response.status_code = status.HTTP_200_OK
    return run.to_dict()


@router.get("/v1/public-benchmark-runs", tags=["public-benchmark-runtime"])
def list_public_benchmark_runs(limit: int = 20) -> dict[str, object]:
    try:
        runs = _store().list_runs(limit=limit)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"runs": [run.to_dict() for run in runs]}


@router.get("/v1/public-benchmark-runs/{run_id}", tags=["public-benchmark-runtime"])
def get_public_benchmark_run(run_id: str) -> dict[str, object]:
    run = _store().get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Public benchmark run not found")
    return run.to_dict()


@router.get("/v1/public-benchmark-runs/{run_id}/events", tags=["public-benchmark-runtime"])
def get_public_benchmark_events(run_id: str) -> dict[str, object]:
    if _store().get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Public benchmark run not found")
    return {"run_id": run_id, "events": [event.to_dict() for event in _store().list_events(run_id)]}


@router.get("/v1/public-benchmark-runs/{run_id}/planner-briefs", tags=["public-benchmark-runtime"])
def list_public_planner_briefs(run_id: str) -> dict[str, object]:
    if _store().get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Public benchmark run not found")
    return {"run_id": run_id, "briefs": _store().list_planner_briefs(run_id)}


@router.post("/v1/public-benchmark-runs/{run_id}/planner-briefs", tags=["public-benchmark-runtime"])
def create_public_planner_brief(
    run_id: str,
    operator_token: Annotated[str | None, Header(alias="X-RetailOps-Operator-Token")] = None,
) -> dict[str, object]:
    """Create a critic-gated explanation only when the optional copilot is enabled."""

    runtime_store = _store()
    if runtime_store.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Public benchmark run not found")
    expected_token = settings.planner_copilot_operator_token
    if expected_token and (
        operator_token is None or not compare_digest(operator_token, expected_token)
    ):
        raise HTTPException(status_code=403, detail="COPILOT_OPERATOR_TOKEN_INVALID")
    copilot = OpenAIResponsesPlannerCopilot(
        runtime_store=runtime_store,
        gateway=PublicBenchmarkEvidenceGateway(runtime_store, audit_root=settings.audit_root),
        config=settings,
    )
    try:
        result = copilot.create_brief(run_id)
    except CopilotUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    if result.payload is None:
        return {
            "status": result.status,
            "reason_code": result.reason_code,
            "trace_id": result.trace_id,
            "brief": None,
        }
    return {
        "status": result.status,
        "reason_code": result.reason_code,
        "trace_id": result.trace_id,
        "brief": result.payload,
    }
