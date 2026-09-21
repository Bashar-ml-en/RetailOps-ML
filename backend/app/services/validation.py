"""Deterministic validation for an authorised RetailOps CSV connector."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Iterable, Literal, Mapping
from uuid import uuid4

from app.schemas.connector import (
    ConnectorIssue,
    ConnectorRunRequest,
    DataContractResult,
    SnapshotManifest,
)


REQUIRED_TABLES: dict[str, tuple[str, ...]] = {
    "products": ("product_id", "sku", "name", "quantity_unit"),
    "locations": ("location_id", "name", "type"),
    "order_lines": ("order_id", "sku", "location_id", "occurred_at", "quantity", "status"),
    "inventory_snapshots": ("snapshot_at", "sku", "location_id", "on_hand"),
}
OPTIONAL_TABLES: dict[str, tuple[str, ...]] = {
    "inbound_supply": (
        "supply_id",
        "sku",
        "location_id",
        "expected_at",
        "quantity",
        "status",
    ),
    "supplier_terms": ("supplier_id", "sku", "lead_time_days"),
}
ALL_TABLES = tuple((*REQUIRED_TABLES, *OPTIONAL_TABLES))
DEMAND_STATUSES = frozenset({"completed", "fulfilled", "paid"})
EXCLUDED_ORDER_STATUSES = frozenset({"cancelled", "canceled", "refunded", "voided"})


@dataclass(frozen=True)
class CsvBundle:
    """Raw connector files keyed by canonical table name.

    Raw bytes are retained only by the server-side snapshot store. This class
    deliberately does not transform or repair input values.
    """

    tables: Mapping[str, bytes]

    @classmethod
    def from_text(cls, tables: Mapping[str, str]) -> "CsvBundle":
        return cls({name: content.encode("utf-8") for name, content in tables.items()})


@dataclass(frozen=True)
class ValidationOutcome:
    manifest: SnapshotManifest
    result: DataContractResult


class CsvConnectorValidator:
    """Validate a CSV bundle without estimating demand or operational actions."""

    def validate(self, request: ConnectorRunRequest, bundle: CsvBundle) -> ValidationOutcome:
        issues: list[ConnectorIssue] = []
        excluded_counts: defaultdict[str, int] = defaultdict(int)
        headers: dict[str, tuple[str, ...]] = {}
        rows_by_table: dict[str, list[dict[str, str]]] = {}

        for table in ALL_TABLES:
            required_columns = REQUIRED_TABLES.get(table) or OPTIONAL_TABLES[table]
            is_required = table in REQUIRED_TABLES
            payload = bundle.tables.get(table)
            if payload is None:
                if is_required:
                    issues.append(
                        ConnectorIssue("ERROR", "MISSING_TABLE", table, None, "Required table is absent.")
                    )
                else:
                    issues.append(
                        ConnectorIssue(
                            "LIMITATION",
                            f"MISSING_{table.upper()}",
                            table,
                            None,
                            "Optional table is absent; affected uses are blocked.",
                        )
                    )
                headers[table] = ()
                rows_by_table[table] = []
                continue

            parsed_headers, parsed_rows = self._read_table(table, payload, issues)
            headers[table] = parsed_headers
            rows_by_table[table] = parsed_rows
            missing_columns = [column for column in required_columns if column not in parsed_headers]
            if missing_columns:
                issues.append(
                    ConnectorIssue(
                        "ERROR",
                        "MISSING_COLUMNS",
                        table,
                        None,
                        f"Missing required columns: {', '.join(missing_columns)}.",
                    )
                )
            if is_required and not parsed_rows:
                issues.append(
                    ConnectorIssue("ERROR", "EMPTY_TABLE", table, None, "Required table has no data rows."))

        known_skus = self._validate_products(rows_by_table["products"], issues)
        known_locations = self._validate_locations(rows_by_table["locations"], issues)
        accepted_order_rows = self._validate_order_lines(
            rows_by_table["order_lines"], known_skus, known_locations, issues, excluded_counts
        )
        freshest_inventory = self._validate_inventory(
            rows_by_table["inventory_snapshots"], known_skus, known_locations, issues
        )
        valid_inbound = self._validate_inbound_supply(
            rows_by_table["inbound_supply"], known_skus, known_locations, issues
        )
        valid_supplier_terms = self._validate_supplier_terms(
            rows_by_table["supplier_terms"], known_skus, issues
        )

        as_of = request.as_of or datetime.now(timezone.utc)
        if freshest_inventory is not None:
            age = as_of - freshest_inventory
            if age > timedelta(hours=request.max_inventory_age_hours):
                issues.append(
                    ConnectorIssue(
                        "LIMITATION",
                        "STALE_INVENTORY",
                        "inventory_snapshots",
                        None,
                        "Latest inventory is older than the declared freshness window.",
                    )
                )
            elif age < timedelta(minutes=-5):
                issues.append(
                    ConnectorIssue(
                        "LIMITATION",
                        "FUTURE_DATED_INVENTORY",
                        "inventory_snapshots",
                        None,
                        "Latest inventory timestamp is after the connector run time.",
                    )
                )

        if not accepted_order_rows:
            issues.append(
                ConnectorIssue(
                    "LIMITATION",
                    "NO_ELIGIBLE_ORDER_LINES",
                    "order_lines",
                    None,
                    "No completed, fulfilled, or paid order lines are eligible for demand history.",
                )
            )

        table_hashes = {
            table: hashlib.sha256(payload).hexdigest()
            for table, payload in sorted(bundle.tables.items())
            if table in ALL_TABLES
        }
        source_hash = self._source_hash(bundle.tables)
        schema_hash = self._schema_hash(headers)
        manifest = SnapshotManifest(
            snapshot_id=str(uuid4()),
            tenant_id=request.tenant_id,
            source_type="CSV",
            source_name=request.source_name,
            authorization_reference=request.authorization_reference,
            mapping_version=request.mapping_version,
            retrieved_at=as_of,
            source_hash=source_hash,
            schema_hash=schema_hash,
            table_hashes=table_hashes,
            row_counts={table: len(rows_by_table[table]) for table in ALL_TABLES},
            excluded_counts=dict(excluded_counts),
            issues=tuple(issues),
        )
        result = self._result_for(
            issues,
            accepted_order_rows=accepted_order_rows,
            freshest_inventory=freshest_inventory,
            valid_inbound=valid_inbound,
            valid_supplier_terms=valid_supplier_terms,
        )
        return ValidationOutcome(manifest=manifest, result=result)

    @staticmethod
    def _read_table(
        table: str, payload: bytes, issues: list[ConnectorIssue]
    ) -> tuple[tuple[str, ...], list[dict[str, str]]]:
        try:
            text = payload.decode("utf-8-sig")
        except UnicodeDecodeError:
            issues.append(
                ConnectorIssue("ERROR", "INVALID_ENCODING", table, None, "CSV must be UTF-8 encoded.")
            )
            return (), []

        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            issues.append(ConnectorIssue("ERROR", "MISSING_HEADER", table, None, "CSV header is absent."))
            return (), []
        headers = tuple((header or "").strip() for header in reader.fieldnames)
        if not all(headers) or len(set(headers)) != len(headers):
            issues.append(
                ConnectorIssue(
                    "ERROR", "INVALID_HEADER", table, None, "CSV headers must be non-empty and unique."
                )
            )
        rows: list[dict[str, str]] = []
        for row_number, raw_row in enumerate(reader, start=2):
            if raw_row.get(None):
                issues.append(
                    ConnectorIssue(
                        "ERROR",
                        "MALFORMED_ROW",
                        table,
                        row_number,
                        "CSV row contains more values than declared headers.",
                    )
                )
                continue
            row = {str(key).strip(): (value or "").strip() for key, value in raw_row.items() if key is not None}
            if any(row.values()):
                rows.append(row)
        return headers, rows

    @staticmethod
    def _validate_products(
        rows: Iterable[dict[str, str]], issues: list[ConnectorIssue]
    ) -> set[str]:
        skus: set[str] = set()
        product_ids: set[str] = set()
        for row_number, row in enumerate(rows, start=2):
            product_id = row.get("product_id", "")
            sku = row.get("sku", "")
            unit = row.get("quantity_unit", "")
            if not product_id or not sku or not unit:
                issues.append(
                    ConnectorIssue("ERROR", "INVALID_PRODUCT_IDENTITY", "products", row_number, "Product ID, SKU, and unit are required.")
                )
                continue
            if product_id in product_ids or sku in skus:
                issues.append(
                    ConnectorIssue("ERROR", "DUPLICATE_PRODUCT_IDENTITY", "products", row_number, "Product ID and SKU must be unique.")
                )
                continue
            product_ids.add(product_id)
            skus.add(sku)
        return skus

    @staticmethod
    def _validate_locations(
        rows: Iterable[dict[str, str]], issues: list[ConnectorIssue]
    ) -> set[str]:
        locations: set[str] = set()
        for row_number, row in enumerate(rows, start=2):
            location_id = row.get("location_id", "")
            if not location_id or not row.get("name", "") or not row.get("type", ""):
                issues.append(
                    ConnectorIssue("ERROR", "INVALID_LOCATION", "locations", row_number, "Location ID, name, and type are required.")
                )
                continue
            if location_id in locations:
                issues.append(
                    ConnectorIssue("ERROR", "DUPLICATE_LOCATION", "locations", row_number, "Location ID must be unique.")
                )
                continue
            locations.add(location_id)
        return locations

    def _validate_order_lines(
        self,
        rows: Iterable[dict[str, str]],
        known_skus: set[str],
        known_locations: set[str],
        issues: list[ConnectorIssue],
        excluded_counts: defaultdict[str, int],
    ) -> int:
        seen: set[tuple[str, ...]] = set()
        accepted = 0
        for row_number, row in enumerate(rows, start=2):
            status = row.get("status", "").lower()
            if status in EXCLUDED_ORDER_STATUSES:
                excluded_counts["order_lines"] += 1
                continue
            if status not in DEMAND_STATUSES:
                issues.append(
                    ConnectorIssue("LIMITATION", "UNMAPPED_ORDER_STATUS", "order_lines", row_number, "Order status is not approved for demand history.")
                )
                excluded_counts["order_lines"] += 1
                continue
            if not row.get("order_id", ""):
                issues.append(ConnectorIssue("ERROR", "MISSING_ORDER_ID", "order_lines", row_number, "Order ID is required."))
                continue
            if row.get("sku", "") not in known_skus:
                issues.append(ConnectorIssue("ERROR", "UNKNOWN_SKU", "order_lines", row_number, "Order line SKU is not mapped."))
                continue
            if row.get("location_id", "") not in known_locations:
                issues.append(ConnectorIssue("ERROR", "UNKNOWN_LOCATION", "order_lines", row_number, "Order line location is not mapped."))
                continue
            if self._parse_datetime(row.get("occurred_at", "")) is None:
                issues.append(ConnectorIssue("ERROR", "INVALID_TIMESTAMP", "order_lines", row_number, "Order timestamp must be ISO-8601 with timezone."))
                continue
            if not self._positive_decimal(row.get("quantity", "")):
                issues.append(ConnectorIssue("ERROR", "INVALID_QUANTITY", "order_lines", row_number, "Order quantity must be positive."))
                continue
            identity = tuple(row.get(field, "") for field in ("order_id", "sku", "location_id", "occurred_at", "quantity", "status"))
            if identity in seen:
                issues.append(ConnectorIssue("ERROR", "DUPLICATE_ORDER_LINE", "order_lines", row_number, "Exact duplicate order line is not accepted."))
                continue
            seen.add(identity)
            accepted += 1
        return accepted

    def _validate_inventory(
        self,
        rows: Iterable[dict[str, str]],
        known_skus: set[str],
        known_locations: set[str],
        issues: list[ConnectorIssue],
    ) -> datetime | None:
        newest: datetime | None = None
        for row_number, row in enumerate(rows, start=2):
            snapshot_at = self._parse_datetime(row.get("snapshot_at", ""))
            if snapshot_at is None:
                issues.append(ConnectorIssue("ERROR", "INVALID_TIMESTAMP", "inventory_snapshots", row_number, "Inventory timestamp must be ISO-8601 with timezone."))
                continue
            if row.get("sku", "") not in known_skus:
                issues.append(ConnectorIssue("ERROR", "UNKNOWN_SKU", "inventory_snapshots", row_number, "Inventory SKU is not mapped."))
                continue
            if row.get("location_id", "") not in known_locations:
                issues.append(ConnectorIssue("ERROR", "UNKNOWN_LOCATION", "inventory_snapshots", row_number, "Inventory location is not mapped."))
                continue
            if not self._non_negative_decimal(row.get("on_hand", "")):
                issues.append(ConnectorIssue("ERROR", "INVALID_ON_HAND", "inventory_snapshots", row_number, "On-hand quantity must be zero or positive."))
                continue
            newest = max(newest, snapshot_at) if newest else snapshot_at
        return newest

    def _validate_inbound_supply(
        self,
        rows: Iterable[dict[str, str]],
        known_skus: set[str],
        known_locations: set[str],
        issues: list[ConnectorIssue],
    ) -> int:
        valid = 0
        for row_number, row in enumerate(rows, start=2):
            if not row.get("supply_id", ""):
                issues.append(ConnectorIssue("ERROR", "MISSING_SUPPLY_ID", "inbound_supply", row_number, "Supply ID is required."))
                continue
            if row.get("sku", "") not in known_skus or row.get("location_id", "") not in known_locations:
                issues.append(ConnectorIssue("ERROR", "UNKNOWN_SUPPLY_SCOPE", "inbound_supply", row_number, "Supply SKU and location must be mapped."))
                continue
            if self._parse_datetime(row.get("expected_at", "")) is None or not self._positive_decimal(row.get("quantity", "")):
                issues.append(ConnectorIssue("ERROR", "INVALID_INBOUND_SUPPLY", "inbound_supply", row_number, "Expected timestamp and positive quantity are required."))
                continue
            valid += 1
        return valid

    def _validate_supplier_terms(
        self, rows: Iterable[dict[str, str]], known_skus: set[str], issues: list[ConnectorIssue]
    ) -> int:
        valid = 0
        for row_number, row in enumerate(rows, start=2):
            if not row.get("supplier_id", "") or row.get("sku", "") not in known_skus:
                issues.append(ConnectorIssue("ERROR", "INVALID_SUPPLIER_SCOPE", "supplier_terms", row_number, "Supplier ID and mapped SKU are required."))
                continue
            if not self._positive_decimal(row.get("lead_time_days", "")):
                issues.append(ConnectorIssue("ERROR", "INVALID_LEAD_TIME", "supplier_terms", row_number, "Lead time must be positive."))
                continue
            valid += 1
        return valid

    @staticmethod
    def _parse_datetime(value: str) -> datetime | None:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else None

    @staticmethod
    def _positive_decimal(value: str) -> bool:
        try:
            return Decimal(value) > 0
        except (InvalidOperation, ValueError):
            return False

    @staticmethod
    def _non_negative_decimal(value: str) -> bool:
        try:
            return Decimal(value) >= 0
        except (InvalidOperation, ValueError):
            return False

    @staticmethod
    def _source_hash(tables: Mapping[str, bytes]) -> str:
        digest = hashlib.sha256()
        for table, payload in sorted(tables.items()):
            if table in ALL_TABLES:
                digest.update(table.encode("utf-8"))
                digest.update(b"\0")
                digest.update(payload)
        return digest.hexdigest()

    @staticmethod
    def _schema_hash(headers: Mapping[str, tuple[str, ...]]) -> str:
        payload = json.dumps({table: list(headers[table]) for table in sorted(headers)}, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _result_for(
        issues: Iterable[ConnectorIssue],
        *,
        accepted_order_rows: int,
        freshest_inventory: datetime | None,
        valid_inbound: int,
        valid_supplier_terms: int,
    ) -> DataContractResult:
        issue_list = tuple(issues)
        errors = tuple(issue for issue in issue_list if issue.severity == "ERROR")
        limitations = tuple(issue.code for issue in issue_list if issue.severity == "LIMITATION")
        if errors:
            return DataContractResult(
                status="REJECT",
                approved_uses=(),
                blocked_uses=("demand_forecast", "inventory_risk", "replenishment_draft"),
                limitations=tuple(issue.code for issue in errors) + limitations,
                next_action="correct_connector_mapping",
            )

        approved_uses: list[str] = []
        if accepted_order_rows:
            approved_uses.append("demand_forecast")
        inventory_is_usable = freshest_inventory is not None and not any(
            code in {"STALE_INVENTORY", "FUTURE_DATED_INVENTORY"} for code in limitations
        )
        if inventory_is_usable:
            approved_uses.append("inventory_risk")
        if inventory_is_usable and valid_inbound and valid_supplier_terms:
            approved_uses.append("replenishment_draft")

        blocked_uses = tuple(
            use
            for use in ("demand_forecast", "inventory_risk", "replenishment_draft")
            if use not in approved_uses
        )
        if not approved_uses:
            return DataContractResult(
                status="INCONCLUSIVE",
                approved_uses=(),
                blocked_uses=blocked_uses,
                limitations=limitations,
                next_action="request_eligible_coverage",
            )
        status: Literal["PASS", "PASS_WITH_LIMITATIONS"] = "PASS_WITH_LIMITATIONS" if limitations else "PASS"
        return DataContractResult(
            status=status,
            approved_uses=tuple(approved_uses),
            blocked_uses=blocked_uses,
            limitations=limitations,
            next_action="build_demand_series" if "demand_forecast" in approved_uses else "request_demand_history",
        )
