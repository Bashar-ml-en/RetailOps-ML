"""FreshRetailNet-50K adapter for a bounded, explicitly public benchmark.

The adapter accepts a locally supplied source table. It never downloads data,
uses merchant credentials, or enables a customer connector. Its output is a
versioned benchmark snapshot that can enter the local forecasting lifecycle
only with the published source limitations attached.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from uuid import uuid4

import pandas as pd

from app.agents.data_quality import DataContractAgent
from app.schemas.benchmark import (
    FRESHRETAILNET_DATASET_ID,
    FRESHRETAILNET_LICENSE,
    FRESHRETAILNET_SOURCE_REVISION,
    FRESHRETAILNET_SOURCE_URL,
    FreshRetailNetBenchmarkRequest,
    FreshRetailNetBenchmarkRun,
)
from app.schemas.connector import ConnectorIssue, DataContractResult, RunEvent, SnapshotManifest
from app.services.storage import SnapshotStore
from app.services.validation import CsvBundle


BENCHMARK_DAILY_DEMAND_TABLE = "benchmark_daily_demand"
FRESHRETAILNET_REQUIRED_COLUMNS = frozenset(
    {
        "city_id",
        "store_id",
        "management_group_id",
        "first_category_id",
        "second_category_id",
        "third_category_id",
        "product_id",
        "dt",
        "sale_amount",
        "hours_sale",
        "stock_hour6_22_cnt",
        "hours_stock_status",
        "discount",
        "holiday_flag",
        "activity_flag",
        "precpt",
        "avg_temperature",
        "avg_humidity",
        "avg_wind_level",
    }
)
FRESHRETAILNET_MAPPING_COLUMNS = (
    "city_id",
    "store_id",
    "management_group_id",
    "first_category_id",
    "second_category_id",
    "third_category_id",
    "product_id",
    "dt",
    "sale_amount",
    "stock_hour6_22_cnt",
    "discount",
    "holiday_flag",
    "activity_flag",
)
BENCHMARK_LIMITATIONS = (
    "PUBLIC_BENCHMARK_NOT_RETAILER_DATA",
    "NORMALIZED_SALES_AMOUNT_NOT_PHYSICAL_QUANTITY",
    "CENSORED_SALES_DURING_STOCKOUT_NOT_RECOVERED",
    "STOCKOUT_STATUS_IS_NOT_ON_HAND_INVENTORY",
    "NO_INBOUND_SUPPLY_OR_LEAD_TIME_EVIDENCE",
    "NO_INVENTORY_OR_REPLENISHMENT_ACTIONS",
)


class FreshRetailNetMappingError(ValueError):
    """Raised when a selected public series cannot be mapped without guessing."""


@dataclass(frozen=True)
class FreshRetailNetMaterialization:
    """The persisted public run and its server-side canonical source tables."""

    run: FreshRetailNetBenchmarkRun
    bundle: CsvBundle


class FreshRetailNetAdapter:
    """Map explicitly selected source series into benchmark-only canonical tables."""

    def materialize(
        self, request: FreshRetailNetBenchmarkRequest, source: pd.DataFrame
    ) -> CsvBundle:
        prepared = self._prepare_source(request, source)
        selected = self._select_scopes(request, prepared)
        products = self._products(selected)
        locations = self._locations(selected)
        daily_demand = self._daily_demand(selected)
        return CsvBundle.from_text(
            {
                "products": products.to_csv(index=False, lineterminator="\n"),
                "locations": locations.to_csv(index=False, lineterminator="\n"),
                BENCHMARK_DAILY_DEMAND_TABLE: daily_demand.to_csv(
                    index=False, lineterminator="\n"
                ),
            }
        )

    def _prepare_source(
        self, request: FreshRetailNetBenchmarkRequest, source: pd.DataFrame
    ) -> pd.DataFrame:
        missing = sorted(set(FRESHRETAILNET_MAPPING_COLUMNS) - set(source.columns))
        if missing:
            raise FreshRetailNetMappingError(
                f"FRESHRETAILNET_MAPPING_SCHEMA_MISMATCH: missing {', '.join(missing)}"
            )
        prepared = source.loc[:, FRESHRETAILNET_MAPPING_COLUMNS].copy()
        if prepared.empty:
            raise FreshRetailNetMappingError("FRESHRETAILNET_SOURCE_EMPTY")
        for column in (
            "city_id",
            "store_id",
            "management_group_id",
            "first_category_id",
            "second_category_id",
            "third_category_id",
            "product_id",
        ):
            values = pd.to_numeric(prepared[column], errors="coerce")
            if values.isna().any() or not (values % 1 == 0).all():
                raise FreshRetailNetMappingError(f"INVALID_FRESHRETAILNET_{column.upper()}")
            prepared[column] = values.astype("int64")

        dates = pd.to_datetime(prepared["dt"], format="%Y-%m-%d", errors="coerce")
        if dates.isna().any():
            raise FreshRetailNetMappingError("INVALID_FRESHRETAILNET_DATE")
        prepared["source_date"] = dates.dt.date
        as_of_date = request.as_of.astimezone(timezone.utc).date()
        if (prepared["source_date"] > as_of_date).any():
            raise FreshRetailNetMappingError("FUTURE_PUBLIC_BENCHMARK_OBSERVATION")

        for column in ("sale_amount", "stock_hour6_22_cnt"):
            values = pd.to_numeric(prepared[column], errors="coerce")
            if values.isna().any() or not values.map(isfinite).all() or (values < 0).any():
                raise FreshRetailNetMappingError(f"INVALID_FRESHRETAILNET_{column.upper()}")
            prepared[column] = values.astype(float)
        return prepared

    @staticmethod
    def _select_scopes(
        request: FreshRetailNetBenchmarkRequest, prepared: pd.DataFrame
    ) -> pd.DataFrame:
        selected_keys = {(scope.store_id, scope.product_id) for scope in request.scopes}
        selected_scope_frame = pd.DataFrame(
            sorted(selected_keys), columns=["store_id", "product_id"]
        )
        rows = prepared.merge(
            selected_scope_frame,
            on=["store_id", "product_id"],
            how="inner",
            validate="many_to_one",
        )
        found_keys = set(zip(rows["store_id"], rows["product_id"], strict=True))
        missing_scopes = sorted(selected_keys - found_keys)
        if missing_scopes:
            rendered = ", ".join(f"{store_id}:{product_id}" for store_id, product_id in missing_scopes)
            raise FreshRetailNetMappingError(f"UNMAPPED_FRESHRETAILNET_SCOPE:{rendered}")
        if rows.duplicated(["store_id", "product_id", "source_date"]).any():
            raise FreshRetailNetMappingError("DUPLICATE_FRESHRETAILNET_DAILY_OBSERVATION")

        for store_id, product_id in sorted(selected_keys):
            scope_rows = rows[(rows["store_id"] == store_id) & (rows["product_id"] == product_id)]
            dates = tuple(sorted(scope_rows["source_date"]))
            expected = tuple(pd.date_range(dates[0], dates[-1], freq="D").date)
            if dates != expected:
                raise FreshRetailNetMappingError("GAPPED_FRESHRETAILNET_DAILY_OBSERVATION")
        return rows.sort_values(["store_id", "product_id", "source_date"])

    @staticmethod
    def _products(selected: pd.DataFrame) -> pd.DataFrame:
        hierarchy_columns = (
            "management_group_id",
            "first_category_id",
            "second_category_id",
            "third_category_id",
        )
        rows: list[dict[str, str]] = []
        for product_id, product_rows in selected.groupby("product_id", sort=True):
            hierarchies = product_rows.loc[:, hierarchy_columns].drop_duplicates()
            if len(hierarchies) != 1:
                raise FreshRetailNetMappingError("INCONSISTENT_FRESHRETAILNET_PRODUCT_HIERARCHY")
            hierarchy = hierarchies.iloc[0]
            rows.append(
                {
                    "product_id": f"frn-product-{int(product_id)}",
                    "sku": f"frn-sku-{int(product_id)}",
                    "name": f"FreshRetailNet product {int(product_id)}",
                    "quantity_unit": "normalized_sales_amount",
                    "category": "/".join(str(int(hierarchy[column])) for column in hierarchy_columns),
                }
            )
        return pd.DataFrame(rows)

    @staticmethod
    def _locations(selected: pd.DataFrame) -> pd.DataFrame:
        rows: list[dict[str, str]] = []
        for store_id, store_rows in selected.groupby("store_id", sort=True):
            city_ids = store_rows["city_id"].drop_duplicates()
            if len(city_ids) != 1:
                raise FreshRetailNetMappingError("INCONSISTENT_FRESHRETAILNET_STORE_CITY")
            city_id = int(city_ids.iloc[0])
            rows.append(
                {
                    "location_id": f"frn-store-{int(store_id)}",
                    "name": f"FreshRetailNet store {int(store_id)} (city {city_id})",
                    "type": "store",
                }
            )
        return pd.DataFrame(rows)

    @staticmethod
    def _daily_demand(selected: pd.DataFrame) -> pd.DataFrame:
        output = pd.DataFrame(
            {
                "sku": selected["product_id"].map(lambda item: f"frn-sku-{int(item)}"),
                "location_id": selected["store_id"].map(lambda item: f"frn-store-{int(item)}"),
                "observed_on": selected["source_date"].map(lambda item: item.isoformat()),
                "quantity": selected["sale_amount"],
                "stockout_hours": selected["stock_hour6_22_cnt"],
                "discount": selected["discount"],
                "holiday_flag": selected["holiday_flag"],
                "activity_flag": selected["activity_flag"],
            }
        )
        return output.sort_values(["location_id", "sku", "observed_on"])


class FreshRetailNetBenchmarkRunner:
    """Persist one public benchmark snapshot and its limited data-contract decision."""

    def __init__(
        self,
        store: SnapshotStore,
        adapter: FreshRetailNetAdapter | None = None,
        agent: DataContractAgent | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.adapter = adapter or FreshRetailNetAdapter()
        self.agent = agent or DataContractAgent()
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @classmethod
    def for_root(cls, root: Path) -> "FreshRetailNetBenchmarkRunner":
        return cls(store=SnapshotStore(root))

    def run(
        self, request: FreshRetailNetBenchmarkRequest, source: pd.DataFrame
    ) -> FreshRetailNetMaterialization:
        run_id = str(uuid4())
        events: list[RunEvent] = []

        def record(name: str, detail: str, *evidence_refs: str) -> None:
            events.append(
                RunEvent(
                    sequence=len(events) + 1,
                    name=name,  # type: ignore[arg-type]
                    occurred_at=self.clock(),
                    detail=detail,
                    evidence_refs=tuple(evidence_refs),
                )
            )

        record("QUEUED", "FreshRetailNet public benchmark subset queued.")
        record("FETCHING", "Locally supplied public benchmark table received for explicit mapping.")
        record("VALIDATING", "Validating published schema, selected scopes, daily coverage, and source limits.")
        bundle = self.adapter.materialize(request, source)
        manifest = self._manifest(request, bundle)
        snapshot_path = self.store.persist_snapshot(manifest, bundle.tables)
        record(
            "SNAPSHOT_STORED",
            "Immutable public benchmark snapshot stored.",
            f"snapshot:{manifest.snapshot_id}",
            f"snapshot_path:{snapshot_path.name}",
        )
        result = DataContractResult(
            status="PASS_WITH_LIMITATIONS",
            approved_uses=("demand_forecast",),
            blocked_uses=("inventory_risk", "replenishment_draft", "production_scoring"),
            limitations=BENCHMARK_LIMITATIONS,
            next_action="evaluate_public_benchmark_baseline",
        )
        decision = self.agent.decide(run_id=run_id, manifest=manifest, result=result)
        agent_decision = {
            "agent": decision.agent,
            "status": decision.status,
            "findings": [
                {"statement": finding.statement, "evidence_refs": list(finding.evidence_refs)}
                for finding in decision.findings
            ],
            "limitations": list(decision.limitations),
            "next_action": decision.next_action,
        }
        record(
            "DATA_CONTRACT_LIMITED",
            "Public benchmark Data Contract returned PASS_WITH_LIMITATIONS.",
            f"snapshot:{manifest.snapshot_id}",
        )
        run = FreshRetailNetBenchmarkRun(
            run_id=run_id,
            request=request,
            manifest=manifest,
            result=result,
            agent_decision=agent_decision,
            events=tuple(events),
        )
        self.store.persist_public_benchmark_run(run)
        return FreshRetailNetMaterialization(run=run, bundle=bundle)

    def run_from_parquet(
        self, request: FreshRetailNetBenchmarkRequest, source_path: Path
    ) -> FreshRetailNetMaterialization:
        """Read only mapping columns after checking the full published schema."""

        if not source_path.is_file():
            raise FreshRetailNetMappingError("FRESHRETAILNET_SOURCE_FILE_NOT_FOUND")
        source_file_sha256 = self._file_hash(source_path)
        if (
            request.source_file_sha256 is not None
            and request.source_file_sha256.lower() != source_file_sha256
        ):
            raise FreshRetailNetMappingError("FRESHRETAILNET_SOURCE_FILE_HASH_MISMATCH")
        try:
            import pyarrow.parquet as parquet
        except ImportError as error:
            raise FreshRetailNetMappingError("PYARROW_REQUIRED_FOR_FRESHRETAILNET_PARQUET") from error
        schema_columns = set(parquet.ParquetFile(source_path).schema_arrow.names)
        missing = sorted(FRESHRETAILNET_REQUIRED_COLUMNS - schema_columns)
        if missing:
            raise FreshRetailNetMappingError(
                f"FRESHRETAILNET_SCHEMA_MISMATCH: missing {', '.join(missing)}"
            )
        try:
            source_file = parquet.ParquetFile(source_path)
            selected_stores = {scope.store_id for scope in request.scopes}
            selected_products = {scope.product_id for scope in request.scopes}
            selected_batches: list[pd.DataFrame] = []
            for batch in source_file.iter_batches(
                batch_size=100_000, columns=list(FRESHRETAILNET_MAPPING_COLUMNS)
            ):
                frame = batch.to_pandas()
                selected = frame[
                    frame["store_id"].isin(selected_stores)
                    & frame["product_id"].isin(selected_products)
                ]
                if not selected.empty:
                    selected_batches.append(selected)
            source = (
                pd.concat(selected_batches, ignore_index=True)
                if selected_batches
                else pd.DataFrame(columns=FRESHRETAILNET_MAPPING_COLUMNS)
            )
        except (OSError, ValueError, ImportError) as error:
            raise FreshRetailNetMappingError("FRESHRETAILNET_PARQUET_UNREADABLE") from error
        materialized_request = replace(
            request,
            source_file_name=source_path.name,
            source_file_sha256=source_file_sha256,
        )
        return self.run(materialized_request, source)

    @staticmethod
    def _manifest(
        request: FreshRetailNetBenchmarkRequest, bundle: CsvBundle
    ) -> SnapshotManifest:
        table_hashes = {
            table: hashlib.sha256(payload).hexdigest() for table, payload in sorted(bundle.tables.items())
        }
        source_hash = FreshRetailNetBenchmarkRunner._combined_hash(bundle.tables)
        headers = {
            table: payload.decode("utf-8").splitlines()[0].split(",")
            for table, payload in sorted(bundle.tables.items())
        }
        schema_hash = hashlib.sha256(
            json.dumps(headers, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return SnapshotManifest(
            snapshot_id=str(uuid4()),
            tenant_id=request.tenant_id,
            source_type="PUBLIC_BENCHMARK",
            source_name=FRESHRETAILNET_DATASET_ID,
            authorization_reference="NOT_APPLICABLE_PUBLIC_BENCHMARK",
            mapping_version=request.mapping_version,
            retrieved_at=request.as_of,
            source_hash=source_hash,
            schema_hash=schema_hash,
            table_hashes=table_hashes,
            row_counts={table: FreshRetailNetBenchmarkRunner._row_count(payload) for table, payload in bundle.tables.items()},
            excluded_counts={},
            data_classification="PUBLIC_BENCHMARK",
            source_reference=(
                f"{FRESHRETAILNET_SOURCE_URL}/resolve/{FRESHRETAILNET_SOURCE_REVISION}/"
                f"data/{request.source_file_name or 'locally-supplied-source'}"
            ),
            license_reference=FRESHRETAILNET_LICENSE,
            issues=tuple(
                ConnectorIssue("LIMITATION", limitation, "public_benchmark", None, limitation)
                for limitation in BENCHMARK_LIMITATIONS
            ),
        )

    @staticmethod
    def _combined_hash(tables: dict[str, bytes] | object) -> str:
        digest = hashlib.sha256()
        for table, payload in sorted(tables.items()):  # type: ignore[union-attr]
            digest.update(table.encode("utf-8"))
            digest.update(b"\0")
            digest.update(payload)
        return digest.hexdigest()

    @staticmethod
    def _row_count(payload: bytes) -> int:
        return max(0, len(payload.decode("utf-8").splitlines()) - 1)

    @staticmethod
    def _file_hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1_048_576), b""):
                digest.update(chunk)
        return digest.hexdigest()
