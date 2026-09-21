# ADR 0001: local public-benchmark runtime

**Status:** accepted for public-benchmark development only  
**Date:** 2026-09-21

## Context

The approved product charter requires a durable, inspectable execution path
before the browser presents a run as real. The repository already has a
deterministic FreshRetailNet forecasting lifecycle, but it was invoked only by
local code and tests. No retailer tenant, identity provider, production queue,
cloud object store, or deployment provider has been approved.

## Decision

For P1 and P2, RetailOps uses a local-only runtime with these replaceable
adapters:

- SQLite stores public-run metadata, immutable events, idempotency keys,
  worker leases, and terminal outcomes.
- The existing immutable `SnapshotStore` stores benchmark snapshots and
  lifecycle artifacts beneath the configured local audit root.
- A separate command-line worker claims a lease and invokes the existing
  FreshRetailNet adapter, baseline runner, fixed-candidate lifecycle, and
  locked-final-test reporter.
- FastAPI exposes public-run submission and read-only event/report summaries.
  It does not start a hidden in-process worker.

The API accepts only a bounded FreshRetailNet selection and idempotency key.
The parquet file path is server configuration (`RETAILOPS_PUBLIC_BENCHMARK_SOURCE_PATH`),
so a browser cannot request arbitrary local files. A missing source ends the
persisted run as `INCONCLUSIVE`; it is never silently substituted with a demo.

## Consequences

This is a development runtime, not a production deployment or a cloud-vendor
decision. It handles the fixed `public-benchmark:freshretailnet-50k` namespace
only and cannot run inventory-risk, replenishment, action-drafting, customer
data, or external operations.

P5 must replace these local adapters with an approved identity boundary,
tenant-isolated metadata/object storage, managed worker/scheduler, secret
store, retention controls, and an authorised read-only connector. Those
decisions remain deliberately unresolved.
