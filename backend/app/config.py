"""RetailOps ML runtime configuration."""

from dataclasses import dataclass
import os
from pathlib import Path


DEFAULT_AUDIT_ROOT = Path(__file__).resolve().parents[2] / "data" / "audit"


@dataclass(frozen=True)
class Settings:
    app_name: str = "RetailOps ML"
    app_version: str = "0.4.0"
    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )
    audit_root: Path = DEFAULT_AUDIT_ROOT
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
        enabled = os.getenv("RETAILOPS_ENABLE_CSV_INGESTION", "false").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        max_upload = int(os.getenv("RETAILOPS_MAX_CSV_UPLOAD_BYTES", str(cls().max_csv_upload_bytes)))
        if max_upload <= 0:
            raise ValueError("RETAILOPS_MAX_CSV_UPLOAD_BYTES must be positive")
        return cls(
            cors_origins=origins or cls().cors_origins,
            audit_root=audit_root,
            csv_ingestion_enabled=enabled,
            max_csv_upload_bytes=max_upload,
        )


settings = Settings.from_environment()
