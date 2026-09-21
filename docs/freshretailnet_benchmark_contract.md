# FreshRetailNet-50K public benchmark contract

## Decision

**PROCEED — benchmark build only.** RetailOps can use FreshRetailNet-50K to
exercise its demand-forecasting lifecycle without a retailer sponsor or
customer data. It cannot turn the source into a retailer pilot, production
model, inventory-cover calculation, replenishment recommendation, or impact
claim.

## Why

The project needs a reproducible multi-store, multi-SKU demand corpus to test
source mapping, chronological evaluation, and evidence artifacts before an
authorised retailer engages. FreshRetailNet-50K provides published
store-product sales histories and stockout annotations suitable for that
engineering exercise.

## Source and attribution

- Dataset: `FreshRetailNet-50K`, version `1.0`, published by Dingdong-Inc.
- Source: <https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K>
- Licence: CC BY 4.0. Retain this attribution in every derived benchmark
  artifact or presentation.
- Baseline code: <https://github.com/Dingdong-Inc/frn-50k-baseline>

The source publishes date-level, globally normalised `sale_amount` values and
stockout-status annotations. It does **not** supply physical quantity units,
on-hand inventory, inbound supply, supplier lead times, a retailer operating
timezone, or any RetailOps customer approval.

## What is implemented

`FreshRetailNetBenchmarkRunner.run_from_parquet` accepts a locally supplied
published parquet file and an explicit selection of 20–50 `(store_id,
product_id)` scopes across one to three stores. It checks the full published
schema and streams only the mapping columns required for the subset. It validates
selected scope coverage, unique daily observations, continuous dates,
non-negative sales/stockout values, and the absence of future observations. It
then stores an immutable local snapshot with these facts:

- `source_type: PUBLIC_BENCHMARK`
- `data_classification: PUBLIC_BENCHMARK`
- fixed virtual namespace: `public-benchmark:freshretailnet-50k`
- pinned source revision, local raw-file SHA-256, source URL, licence, mapping
  version, schema/table/source hashes, and row counts
- `PUBLIC_BENCHMARK` provenance and a Data Contract Agent decision

The adapter maps `product_id` to a benchmark SKU, `store_id` to a benchmark
location, and `sale_amount` to `quantity_unit: normalized_sales_amount`. It
preserves zero-sales days in `benchmark_daily_demand`; it never invents order
lines or physical units.

## Approved and blocked uses

| Use | Decision | Reason |
| --- | --- | --- |
| Chronological observed-sales baseline/candidate evaluation | `PASS_WITH_LIMITATIONS` | The source has continuous store-product daily sales observations. |
| Stockout-aware benchmark analysis | `PASS_WITH_LIMITATIONS` | Stockout-hour annotations are available, but latent demand recovery is not implemented. |
| Inventory-risk scoring | Blocked | Stockout status is not an on-hand inventory snapshot. |
| Replenishment draft | Blocked | No on-hand, inbound-supply, or lead-time evidence exists. |
| Production scoring or retailer performance claim | Blocked | The data is public benchmark material, not an authorised retailer source. |

Every baseline and candidate artifact inherits the public-source limitations;
the UI/API must label any metric as a **public benchmark result**, never as a
customer, pilot, or business-impact result.

## Local execution boundary

No dataset is bundled with this repository and the app does not download it.
Download the published data directly, preserve the source licence/attribution,
and load a local table only in a trusted development environment. A developer
declares the exact store-product scopes before calling the adapter; automatic
scope discovery, credential use, and customer-data ingestion are out of scope.

The resulting `CsvBundle` can be passed to the existing baseline and
fixed-candidate runners using its snapshot ID, fixed benchmark namespace, and
`UTC` operating timezone. `UTC` is required because the published `dt` field
is a date without a declared store timezone.

## Measured impact and unknowns

The permitted measurements are validation MAE/RMSE and one post-selection
final-test report on a declared, locked public benchmark split. The final-test
report must be immutable, identify the source revision, snapshot, baseline,
selected model, and split dates, and state that it did not alter selection.
For the recorded run, `final-test-a4c2a81f-92f4-4e65-a3fa-289d033f796c`
reports macro MAE `0.6368571429` and macro RMSE `0.8062199696` across 20
seven-day scopes for the retained `naive-last-observation-v1` model.

These demonstrate code and lifecycle behavior, not sales accuracy for another
retailer, stockout reduction, profit, availability, or replenishment impact.
