"""Historical-only daily demand series for compatible retail scopes."""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable
from zoneinfo import ZoneInfo

import pandas as pd

from app.services.validation import CsvBundle, DEMAND_STATUSES


class DemandSeriesError(ValueError):
    """Raised when an approved snapshot cannot safely form a demand series."""


@dataclass(frozen=True)
class DailyDemandSeries:
    sku: str
    location_id: str
    quantity_unit: str
    dates: tuple[date, ...]
    quantities: tuple[float, ...]

    @property
    def scope_ref(self) -> str:
        return f"sku:{self.sku}|location:{self.location_id}|unit:{self.quantity_unit}"


@dataclass(frozen=True)
class DemandSeriesBuild:
    series: tuple[DailyDemandSeries, ...]
    feature_hash: str


def build_daily_demand_series(
    bundle: CsvBundle, *, operating_timezone: str, as_of: datetime
) -> DemandSeriesBuild:
    """Aggregate eligible orders by the retailer's declared local calendar day.

    The function accepts a previously validated source bundle but still rejects
    observations later than its immutable snapshot time. This is the final
    no-leakage check before chronological evaluation.
    """

    if "benchmark_daily_demand" in bundle.tables:
        return _build_public_benchmark_daily_demand_series(bundle, as_of=as_of)

    try:
        products = pd.read_csv(io.BytesIO(bundle.tables["products"]), dtype=str, keep_default_na=False)
        orders = pd.read_csv(io.BytesIO(bundle.tables["order_lines"]), dtype=str, keep_default_na=False)
    except KeyError as error:
        raise DemandSeriesError(f"Missing source table: {error.args[0]}") from error
    except (UnicodeDecodeError, pd.errors.ParserError) as error:
        raise DemandSeriesError("Validated source tables could not be read as CSV") from error

    try:
        orders["occurred_at"] = pd.to_datetime(orders["occurred_at"], utc=True, errors="raise")
        orders["quantity"] = pd.to_numeric(orders["quantity"], errors="raise")
    except (KeyError, TypeError, ValueError) as error:
        raise DemandSeriesError("Order timestamps and quantities must remain parseable") from error

    as_of_utc = pd.Timestamp(as_of).tz_convert("UTC")
    if (orders["occurred_at"] > as_of_utc).any():
        raise DemandSeriesError("FUTURE_ORDER_OBSERVATION")

    eligible = orders[orders["status"].str.lower().isin(DEMAND_STATUSES)].copy()
    if eligible.empty:
        return DemandSeriesBuild(series=(), feature_hash=_feature_hash(()))

    try:
        timezone = ZoneInfo(operating_timezone)
    except Exception as error:  # BaselineRunRequest validates the name; keep this boundary defensive.
        raise DemandSeriesError("operating_timezone must be an IANA timezone") from error
    eligible["demand_date"] = eligible["occurred_at"].dt.tz_convert(timezone).dt.date
    product_units = products[["sku", "quantity_unit"]]
    eligible = eligible.merge(product_units, on="sku", how="left", validate="many_to_one")
    if eligible["quantity_unit"].isna().any():
        raise DemandSeriesError("UNMAPPED_DEMAND_UNIT")

    grouped = (
        eligible.groupby(["sku", "location_id", "quantity_unit", "demand_date"], as_index=False)["quantity"]
        .sum()
        .sort_values(["sku", "location_id", "quantity_unit", "demand_date"])
    )
    output: list[DailyDemandSeries] = []
    for (sku, location_id, quantity_unit), scope in grouped.groupby(
        ["sku", "location_id", "quantity_unit"], sort=True
    ):
        start = scope["demand_date"].min()
        end = scope["demand_date"].max()
        dates = tuple(day.date() for day in pd.date_range(start, end, freq="D"))
        quantities_by_day = dict(zip(scope["demand_date"], scope["quantity"], strict=True))
        quantities = tuple(float(quantities_by_day.get(day, 0.0)) for day in dates)
        output.append(
            DailyDemandSeries(
                sku=str(sku),
                location_id=str(location_id),
                quantity_unit=str(quantity_unit),
                dates=dates,
                quantities=quantities,
            )
        )
    immutable_series = tuple(output)
    return DemandSeriesBuild(series=immutable_series, feature_hash=_feature_hash(immutable_series))


def _build_public_benchmark_daily_demand_series(
    bundle: CsvBundle, *, as_of: datetime
) -> DemandSeriesBuild:
    """Build an explicit daily series without relabelling it as an order feed.

    FreshRetailNet publishes date-level sales amounts, including zero-sales
    days. Those rows must remain visible: unlike order lines, zero values are
    valid observations and cannot be silently discarded or inferred.
    """

    try:
        products = pd.read_csv(io.BytesIO(bundle.tables["products"]), dtype=str, keep_default_na=False)
        observations = pd.read_csv(
            io.BytesIO(bundle.tables["benchmark_daily_demand"]), dtype=str, keep_default_na=False
        )
    except KeyError as error:
        raise DemandSeriesError(f"Missing source table: {error.args[0]}") from error
    except (UnicodeDecodeError, pd.errors.ParserError) as error:
        raise DemandSeriesError("Validated public benchmark tables could not be read as CSV") from error

    try:
        observations["observed_on"] = pd.to_datetime(
            observations["observed_on"], format="%Y-%m-%d", errors="raise"
        ).dt.date
        observations["quantity"] = pd.to_numeric(observations["quantity"], errors="raise")
    except (KeyError, TypeError, ValueError) as error:
        raise DemandSeriesError("Public benchmark dates and quantities must remain parseable") from error
    if (observations["quantity"] < 0).any():
        raise DemandSeriesError("NEGATIVE_PUBLIC_BENCHMARK_QUANTITY")
    if observations.duplicated(["sku", "location_id", "observed_on"]).any():
        raise DemandSeriesError("DUPLICATE_PUBLIC_BENCHMARK_DAILY_OBSERVATION")
    if (observations["observed_on"] > as_of.astimezone(ZoneInfo("UTC")).date()).any():
        raise DemandSeriesError("FUTURE_ORDER_OBSERVATION")

    product_units = products[["sku", "quantity_unit"]]
    observations = observations.merge(product_units, on="sku", how="left", validate="many_to_one")
    if observations["quantity_unit"].isna().any():
        raise DemandSeriesError("UNMAPPED_DEMAND_UNIT")

    output: list[DailyDemandSeries] = []
    for (sku, location_id, quantity_unit), scope in observations.groupby(
        ["sku", "location_id", "quantity_unit"], sort=True
    ):
        ordered = scope.sort_values("observed_on")
        dates = tuple(ordered["observed_on"])
        expected_dates = tuple(day.date() for day in pd.date_range(dates[0], dates[-1], freq="D"))
        if dates != expected_dates:
            raise DemandSeriesError("GAPPED_PUBLIC_BENCHMARK_DAILY_OBSERVATION")
        output.append(
            DailyDemandSeries(
                sku=str(sku),
                location_id=str(location_id),
                quantity_unit=str(quantity_unit),
                dates=dates,
                quantities=tuple(float(item) for item in ordered["quantity"]),
            )
        )
    immutable_series = tuple(output)
    return DemandSeriesBuild(series=immutable_series, feature_hash=_feature_hash(immutable_series))


def _feature_hash(series: Iterable[DailyDemandSeries]) -> str:
    payload = [
        {
            "scope": item.scope_ref,
            "dates": [day.isoformat() for day in item.dates],
            "quantities": list(item.quantities),
        }
        for item in series
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
