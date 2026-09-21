"""RetailOps ML runtime configuration."""

from dataclasses import dataclass, field
import os
from pathlib import Path


DEFAULT_AUDIT_ROOT = Path(__file__).resolve().parents[2] / "data" / "audit"
DEFAULT_RUNTIME_ROOT = Path(__file__).resolve().parents[2] / "data" / "runtime"


@dataclass(frozen=True)
class Settings:
    app_name: str = "RetailOps ML"
    app_version: str = "0.5.0"
    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )
    audit_root: Path = DEFAULT_AUDIT_ROOT
    runtime_root: Path = DEFAULT_RUNTIME_ROOT
    # The public benchmark input is configured only on the server.  The API
    # accepts a bounded selection, never a browser-supplied filesystem path.
    public_benchmark_source_path: Path | None = None
    # OpenAI stays fail-closed until the owner explicitly selects a model,
    # configures server-side credentials, and assigns both caps.  A credit
    # balance is not an authorisation to make uncapped requests.
    planner_copilot_enabled: bool = False
    openai_api_key: str | None = field(default=None, repr=False)
    planner_copilot_operator_token: str | None = field(default=None, repr=False)
    openai_model: str | None = None
    planner_copilot_per_run_budget_cents: int = 0
    planner_copilot_monthly_budget_cents: int = 0
    planner_copilot_max_output_tokens: int = 800
    planner_copilot_max_tool_calls: int = 3
    planner_copilot_no_provider_storage_approved: bool = False
    csv_ingestion_enabled: bool = False
    # This local release has no identity-provider adapter. It is intentionally
    # not environment-configurable: a flag is not tenant authentication.
    authenticated_tenant_runtime_implemented: bool = False
    max_csv_upload_bytes: int = 10_000_000

    @classmethod
    def from_environment(cls) -> "Settings":
        raw_origins = os.getenv("RETAILOPS_CORS_ORIGINS")
        origins = (
            tuple(origin.strip() for origin in raw_origins.split(",") if origin.strip())
            if raw_origins
            else cls().cors_origins
        )
        audit_root = Path(os.getenv("RETAILOPS_AUDIT_ROOT", str(cls().audit_root)))
        runtime_root = Path(os.getenv("RETAILOPS_RUNTIME_ROOT", str(cls().runtime_root)))
        raw_benchmark_source = os.getenv("RETAILOPS_PUBLIC_BENCHMARK_SOURCE_PATH")
        copilot_enabled = os.getenv("RETAILOPS_ENABLE_PLANNER_COPILOT", "false").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        per_run_budget = int(os.getenv("RETAILOPS_COPILOT_PER_RUN_BUDGET_CENTS", "0"))
        monthly_budget = int(os.getenv("RETAILOPS_COPILOT_MONTHLY_BUDGET_CENTS", "0"))
        max_output_tokens = int(os.getenv("RETAILOPS_COPILOT_MAX_OUTPUT_TOKENS", "800"))
        max_tool_calls = int(os.getenv("RETAILOPS_COPILOT_MAX_TOOL_CALLS", "3"))
        no_provider_storage_approved = os.getenv(
            "RETAILOPS_COPILOT_NO_PROVIDER_STORAGE_APPROVED", "false"
        ).strip().lower() in {"1", "true", "yes"}
        enabled = os.getenv("RETAILOPS_ENABLE_CSV_INGESTION", "false").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        max_upload = int(os.getenv("RETAILOPS_MAX_CSV_UPLOAD_BYTES", str(cls().max_csv_upload_bytes)))
        if max_upload <= 0:
            raise ValueError("RETAILOPS_MAX_CSV_UPLOAD_BYTES must be positive")
        if min(per_run_budget, monthly_budget) < 0:
            raise ValueError("planner copilot budget caps cannot be negative")
        if max_output_tokens <= 0 or max_tool_calls <= 0:
            raise ValueError("planner copilot output and tool caps must be positive")
        return cls(
            cors_origins=origins or cls().cors_origins,
            audit_root=audit_root,
            runtime_root=runtime_root,
            public_benchmark_source_path=(
                Path(raw_benchmark_source) if raw_benchmark_source else None
            ),
            planner_copilot_enabled=copilot_enabled,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            planner_copilot_operator_token=os.getenv("RETAILOPS_COPILOT_OPERATOR_TOKEN"),
            openai_model=os.getenv("RETAILOPS_OPENAI_MODEL"),
            planner_copilot_per_run_budget_cents=per_run_budget,
            planner_copilot_monthly_budget_cents=monthly_budget,
            planner_copilot_max_output_tokens=max_output_tokens,
            planner_copilot_max_tool_calls=max_tool_calls,
            planner_copilot_no_provider_storage_approved=no_provider_storage_approved,
            csv_ingestion_enabled=enabled,
            max_csv_upload_bytes=max_upload,
        )


settings = Settings.from_environment()
