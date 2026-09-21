# RetailOps ML fixed-candidate lifecycle contract

## Why this gate exists

A candidate forecast method must earn selection against the recorded naïve
baseline; a more attractive chart, a locked-test result, or a manually chosen
configuration is not evidence of improvement. This local gate makes that
comparison reproducible before any authorised pilot or production claim.

## What exists locally

The lifecycle evaluates exactly one predeclared candidate:
`trailing-mean-7-v1`. It predicts a validation day from the prior seven
observed daily demands and adds that day's actual only after making the
prediction. It has no fitted parameters, tuning loop, production score,
deployment, or authorised retailer run.

The local filesystem registry records an immutable JSON artifact for each
attempt. It includes the input snapshot and baseline references, feature hash
and version, candidate configuration, per-scope validation MAE/RMSE, selection
rationale, selected local model version, and the naïve baseline rollback
reference.

## Required input boundary

- The connector result for the same tenant and snapshot must be `PASS` or
  `PASS_WITH_LIMITATIONS` and approve `demand_forecast`.
- The recorded baseline run ID, tenant, snapshot ID, feature version, and
  feature hash must match the rebuilt historical demand series.
- The baseline must itself be `PASS` or `PASS_WITH_LIMITATIONS` and use the
  declared `naive-last-observation-v1` baseline contract.
- A future order observation, unmatched scope, altered baseline split, or
  altered baseline metric returns `REJECT`; insufficient accepted evidence
  returns `INCONCLUSIVE`.

## Chronological selection policy

The candidate uses the baseline's recorded training and validation boundaries.
It makes predictions only for validation days. The final test partition remains
recorded as `LOCKED_UNEVALUATED` in every scope and registry artifact and is
never used for prediction, metric calculation, threshold selection, or model
selection.

The candidate is selected only when it strictly improves validation MAE for
every eligible SKU-location-unit scope. A tie or regression for any eligible
scope retains `naive-last-observation-v1` as the selected local baseline. RMSE
is retained as a diagnostic metric, but it is not a second, undeclared
promotion route.

After selection, a public benchmark may evaluate the selected local model once
on the locked final test in a new immutable final-test report. That report
rechecks the stored snapshot table hashes, feature hash, scope splits, and
registry chain. It records metrics only; it does not mutate the model-registry
record, change selection, select a new candidate, or authorise a production
claim.

## Registry and rollback boundary

`SnapshotStore.persist_model_run` writes a non-overwriting record below the
local `model-registry/` directory. Every record carries the baseline model
version and baseline run ID as its rollback reference, including a candidate
selection. This is a local-pilot audit adapter, not a production registry or
an automatic promotion mechanism.

A future production lifecycle still requires an authorised tenant-scoped
snapshot, durable storage, a human-reviewed release gate, realised-error and
drift monitoring, and an explicit rollback decision. No registry record causes
RetailOps to score demand, change a champion in production, or take an
operational action.
