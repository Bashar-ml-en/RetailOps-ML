# RetailOps ML demand-baseline contract

## Why this gate exists

An ML candidate cannot be trusted merely because it produces a forecast. The
system first needs a simple, reproducible baseline that can be evaluated
without future data and retained as the fallback comparison.

## What exists locally

The `naive-last-observation-v1` evaluator consumes an accepted connector
snapshot and produces a typed baseline artifact per compatible SKU, location,
and quantity unit. It records validation MAE and RMSE, split boundaries, a
feature hash, the source snapshot ID, and a Forecast Evaluation Agent decision.
The baseline artifact itself does not make a promotion decision or production
score. A separate fixed-candidate lifecycle may compare this recorded artifact
only when the same accepted snapshot, feature hash, and split boundaries match;
it still has no customer-data run or claim of retail impact.

## Required input boundary

- The Data Contract result must approve `demand_forecast` for the same tenant
  and immutable snapshot ID.
- The retailer operating timezone must be declared using an IANA timezone.
- Only completed, fulfilled, or paid order lines contribute to daily demand.
- An observation after the snapshot retrieval time is rejected before any
  evaluation. Missing days are represented as zero demand only within the
  observed date range.

## Chronological policy

The default fixture policy uses 14 minimum training days, 7 validation days,
and 7 locked final-test days. The naïve baseline predicts each validation day
from the last demand observation available before that day, then updates only
with the now-observed historical validation actual. It never evaluates the
locked final-test period during this gate.

Insufficient history returns `INCONCLUSIVE`; an invalid snapshot scope or
future order observation returns `REJECT`. A successful local fixture proves
only code behavior. A successful public benchmark run proves only the declared
benchmark result and inherits all source limitations. An authorised retailer
run is required before RetailOps reports a retailer baseline metric or makes a
production model claim.
