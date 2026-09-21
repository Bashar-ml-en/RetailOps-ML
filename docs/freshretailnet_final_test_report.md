# FreshRetailNet-50K Final-Test Benchmark Report

## Label and decision

**Public benchmark result — not retailer, pilot, production, inventory, or
business-impact evidence.** The selected local model was evaluated once after
validation-only selection. The result did not change model selection.

| Field | Value |
| --- | --- |
| Dataset | FreshRetailNet-50K v1.0, Dingdong-Inc, CC BY 4.0 |
| Source revision | `08c1fab7f9257bc73679d415d65d644165d351d4` |
| Source file SHA-256 | `6706832db892bbae4969c19d87e07975d2543d2ba7d7d4756360654785de5a3d` |
| Benchmark run | `3439b1a7-2073-4dd1-939b-2d1c91a8309c` |
| Snapshot | `ff8577dd-8a9d-41b0-8c58-2acfa3f73054` |
| Baseline run | `3fc5c0c7-fea2-43f6-8494-dc6dfc996023` |
| Model registry record | `a4c2a81f-92f4-4e65-a3fa-289d033f796c` |
| Final-test report | `final-test-a4c2a81f-92f4-4e65-a3fa-289d033f796c` |
| Selection | `RETAINED_BASELINE` — `naive-last-observation-v1` |

## Measurement

The report evaluates 20 selected store-product scopes at one published store.
Each scope contains a seven-day final-test interval from 2024-06-19 through
2024-06-25. It reports a macro average across scope-level metrics, using the
published `normalized_sales_amount` unit.

| Metric | Result |
| --- | ---: |
| Macro average MAE | 0.6368571429 |
| Macro average RMSE | 0.8062199696 |

The underlying immutable JSON artifact is
`data/audit/public-benchmark-final-test-reports/final-test-a4c2a81f-92f4-4e65-a3fa-289d033f796c.json`.
It verifies persisted snapshot table hashes, feature hash, scope boundaries,
and the baseline/model-registry chain before calculating the test metrics.

## What this proves and does not prove

It proves that the local forecasting lifecycle can preserve a benchmark
snapshot, choose the baseline by chronological validation, and subsequently
measure that already-selected model once on a locked public test split. It does
not prove accuracy for a retailer or authorise inventory-risk scoring,
replenishment, production scoring, purchasing, transfers, pricing, supplier
contact, stockout reduction, profit, availability, or business impact.

The report inherits these source limitations: the source is not retailer data;
sales are globally normalised rather than physical units; stockout censorship
is not recovered; stockout status is not an on-hand inventory record; and
inbound supply and supplier lead-time evidence are absent.
