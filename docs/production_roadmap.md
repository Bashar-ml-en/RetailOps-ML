# RetailOps ML Production Roadmap

## Decision statement

RetailOps must progress from an architecture explorer to a read-only,
evidence-first pilot. It may not claim a live model, agent run, or operational
result until a result identifies its authorised source snapshot, model version,
typed agent decisions, and human reviewer outcome.

## Current assessment

| Area | Current state | Production implication |
| --- | --- | --- |
| Governance | Root AGENTS.md and the RetailOps lifecycle documents now describe the same evidence-first, human-approved product boundary; a local pilot-readiness gate records the missing charter/source evidence without treating it as authorisation. | Keep this alignment under version control as connector and model contracts are added. |
| Data | No authorised customer dataset is loaded. A FreshRetailNet-50K public benchmark run is locally recorded against pinned revision `08c1fab7f9257bc73679d415d65d644165d351d4` (run `3439b1a7-2073-4dd1-939b-2d1c91a8309c`); its selected subset is versioned as a hashed benchmark snapshot. | A public benchmark may produce only labelled benchmark metrics; it cannot support a customer, risk, replenishment, or business-impact claim. |
| ML | CSV ingestion, deterministic validation, a local naïve baseline evaluator, one fixed-candidate comparison/registry gate, and a limited FreshRetailNet public-benchmark adapter are implemented. The recorded public run retains the naïve baseline; immutable final-test report `final-test-a4c2a81f-92f4-4e65-a3fa-289d033f796c` records public macro MAE 0.6368571429 and RMSE 0.8062199696 without altering selection. There is no authorised evaluation, production registry, trained customer model, or customer metrics claim. | Use an authorised accepted snapshot and a human-reviewed release decision before any production model claim. |
| Agents | Data Contract, Forecast Evaluation, Inventory Risk, Impact Ranking, Policy Critic, and Action Drafting have deterministic local contracts. A synchronous fixture-only workflow persists real specialist transitions to a critic-approved local queue case or a terminal safety outcome; the local queue persists append-only approve/decline/defer decisions. There is no shared worker, authenticated reviewer identity, SSE, customer case, or external action capability. | Agent movement must be driven by persisted job events, not animation. |
| Deployment | Vercel deploys the static React interface. The CSV API is hard-disabled locally. A P0 non-secret provisioning contract records required identity, secret-store, audit-store, object-store, worker, scheduler, and RBAC references. A local SQLite adapter proves fixture-only audit migrations, tenant partition queries, and blocked job/schedule records; it is not an external service or authenticated API. | Provision and security-review an authenticated API/worker separately with durable audit/object storage before customer data. |
| CI/CD | Backend tests and frontend build run locally; no complete code, data, and model release pipeline exists. | Keep code deployment, data ingestion, and model promotion as separate gates. |

## Priority queue

P0 blocks all customer-data and production claims. Work moves forward only when
the current item has its acceptance evidence.

| Priority | Queue item | Alignment reason | Dependency | Acceptance evidence |
| --- | --- | --- | --- | --- |
| Complete | Governance alignment | One product constitution now governs data, models, and agents. | None. | Root instructions, README, and deployment documentation name RetailOps and its evidence boundary. |
| Complete locally | Pilot-readiness gate | Pilot metadata must be complete and read-only before source mapping is prepared. | Named retailer approval before activation. | Immutable readiness assessment rejects write/non-CSV boundaries, blocks missing charter evidence, and never grants ingestion access. |
| P0 | Name one pilot retailer and use case | A model cannot be trained against an unspecified problem. | Retailer agreement. | Named planner, SKU/location cohort, horizon, current comparison process, and impact measures. |
| P0 | Select the source mode | Authorisation and data availability determine all later work. | Pilot retailer decision. | An authorised CSV export, Shopify read-only access, or Square read-only access is recorded. |
| Complete locally (contract) | Define production foundations | Customer data must be durable, isolated, and auditable. | Hosting and security decision before provisioning. | Immutable non-secret resource declaration, required role declaration, fixture tenant-scope checks, SQLite migration/partition tests, atomic blocked job/event records, and failure-closed activation tests. |
| P0 | Provision and verify production foundations | Local contracts do not create or verify external controls. | Hosting, security, and identity-provider decision. | Server-side secret store, relational audit database, immutable object storage, worker queue, scheduler, role-based access, security review, and durable migrations. |
| Complete locally | Implement canonical CSV connector contract | Later artifacts need compatible SKU, location, unit, time, and quantity identities. | Authorised source and production storage before activation. | Versioned mappings for products, locations, orders, inventory, inbound supply, and supplier terms; invalid identities fail closed. |
| Complete locally | Snapshot and validate data | Inputs must be reproducible before modelling. | Connector contract. | Immutable snapshot ID, schema hash, row counts, exclusions, freshness result, Data Contract Agent decision, and persisted event timeline. |
| Complete locally | Run a transparent demand baseline | Forecast quality must be measured before ML complexity. | Authorised accepted demand history before a metrics claim. | Per-SKU/location/unit chronological split, baseline, validation MAE/RMSE, insufficient-history path, future-observation rejection, and locked final test period. |
| Complete locally | Add fixed-candidate lifecycle | A candidate must earn local selection against the baseline without touching final test days. | Accepted fixture snapshot and sufficient history. | Feature version/hash, fixed configuration, validation comparison, immutable local registry record, strict-promotion rationale, retained-baseline path, and rollback target. |
| Complete locally (fixture) | Persist specialist workflow events | Agent motion must represent actual persisted work. | Labelled fixture evidence, deterministic specialists, local audit store, and queue. | Immutable local timeline records queued, validation, named evidence checks, specialist decisions, and review-ready or terminal rejected/inconclusive/failed outcomes. |
| Complete locally (fixture) | Add reviewer queue | RetailOps supports human decisions; it does not execute actions. | Critic-approved typed fixture case. | Fixture planner role can approve, decline, or defer a draft through append-only local audit events; the decision cannot execute an external action. |
| P3 | Connect incremental feeds | Freshness is useful only after snapshot correctness is proven. | Proven source-contract pilot. | Read-only webhook/poll reconciliation, retrieval metadata, idempotency, and stale-feed alerts. |
| P3 | Activate monitoring and controlled retraining | Champion quality must remain measurable after release. | Registered champion and realised demand. | Drift, coverage, freshness, realised-error events, retrain proposal, and rollback procedure. |

## Dataset policy

### First production dataset: authorised retailer data

The first production model uses a named retailer's authorised data, not a public
dataset. Required canonical tables are:

| Table | Required fields | Used for |
| --- | --- | --- |
| Products | product_id, sku, name, quantity_unit | Identity and unit compatibility. |
| Locations | location_id, name, type | Store or warehouse scope. |
| Order lines | order_id, sku, location_id, occurred_at, quantity, status | Historical demand and actuals. |
| Inventory snapshots | snapshot_at, sku, location_id, on_hand | Stock-risk eligibility. |
| Inbound supply | supply_id, sku, location_id, expected_at, quantity, status | Expected replenishment. |
| Supplier terms | supplier_id, sku, lead_time_days | Lead-time eligibility. |

Missing current inventory or lead time blocks an inventory/replenishment case;
it does not produce a guessed recommendation.

### Benchmark dataset: M5

M5 may be used in a separate, visibly labelled benchmark environment to build
and test forecasting mechanics. It is not a live retailer connector and must
never be shown as a customer result or used to claim inventory-risk
performance.

## API inventory

### External, read-only source APIs

Use only one commerce source for the first pilot. Do not request write,
price-change, purchasing, or supplier-contact permissions.

| Source | Needed reads | Supplies | Separate gap |
| --- | --- | --- | --- |
| CSV export | No external API; signed export upload or secure server ingestion. | All canonical tables if the retailer can export them. | Freshness depends on export schedule. |
| Shopify Admin GraphQL | Orders/line items, products/SKUs, locations, inventory quantities by location. | Demand, product identity, current inventory. | Inbound supply and supplier lead time normally require WMS/ERP data or an approved export. |
| Square | Orders, catalog variations, locations, inventory counts/changes, read event webhooks. | Demand, product identity, inventory, incremental updates. | Inbound supply and supplier lead time normally require WMS/ERP data or an approved export. |
| WMS or ERP | Purchase orders, receipts, supplier lead times, transfer state. | Inbound supply and lead-time evidence. | Vendor-specific mapping and read-only authorisation. |

### RetailOps browser and worker APIs

The browser receives summaries and event records, never provider credentials or
raw customer exports. The versioned API surface is:

| Endpoint | Consumer | Purpose | Write boundary |
| --- | --- | --- | --- |
| GET /v1/health | Deployment checks | Service health and version. | None. |
| POST /v1/connector-runs/csv | Authorised operator | Starts the disabled-by-default CSV ingestion gate for a declared scope. | Creates an auditable run only; production use requires authenticated tenant access. |
| GET /v1/runs/{run_id} | Dashboard | Run status, scope, snapshots, and limitations. | None. |
| GET /v1/runs/{run_id}/events (SSE) | Dashboard | Persisted agent/job event stream. | None. |
| GET /v1/snapshots/{snapshot_id}/summary | Dashboard/reviewer | Provenance, quality checks, and exclusions. | None. |
| GET /v1/model-runs/{model_run_id} | Reviewer | Baseline/candidate metrics, split dates, and selection. | None. |
| GET /v1/review-cases | Planner | Critic-approved, evidence-linked cases only. | None. |
| POST /v1/review-cases/{case_id}/decision | Planner | Approve, decline, or defer a case. | Records a human decision; never executes an external action. |

There is no API that creates a purchase order, transfers stock, changes price,
or contacts a supplier.

## Live run and dashboard contract

The dashboard may animate only transitions emitted by the worker and stored in
the audit database:

    QUEUED -> FETCHING -> SNAPSHOT_STORED -> VALIDATING
           -> FEATURES_READY -> BASELINE_EVALUATED
           -> [DATA_CONTRACT | FORECAST_EVALUATION | INVENTORY_RISK | IMPACT_RANKING]
           -> POLICY_CRITIC -> REVIEW_READY

At any gate, REJECT, FAILED, or INCONCLUSIVE is terminal. Every event exposes
the source snapshot ID, artifact version, timestamp, duration, status,
evidence references, and limitation. CSS-only running animation is prohibited.

## Operating schedule proposal

All schedules use the retailer operating timezone and are recorded in run
metadata. They become active only after the source contract passes.

| Cadence | Job | Guardrail |
| --- | --- | --- |
| Event-driven plus 15-minute reconciliation | Incremental order ingestion where read webhooks exist. | Idempotency key, retrieval watermark, read-only credentials. |
| Hourly | Inventory snapshot. | Alert and block inventory-risk scoring when stale. |
| Daily after store close | Immutable daily snapshot, validation, features, and scoring. | Use only events available at the score timestamp. |
| Daily | Freshness, schema, coverage, feature, and realised-error monitoring. | Emit alert/proposal; do not retrain or change champion. |
| Weekly | Recompute realised metrics as actual demand arrives. | Compare incumbent to declared baseline. |
| Monthly or declared deterioration trigger | Train and evaluate a candidate model. | Human-reviewed promotion only; retain rollback champion. |

## CI/CD and model-control separation

| Trigger | Activity | Gate |
| --- | --- | --- |
| Pull request | Lint, unit tests, API contracts, malformed-source fixtures, schema compatibility, chronology/leakage tests, baseline regression tests, frontend production build. | All automated checks. |
| Merge to main | Build versioned API/worker artifact, deploy staging, run migration and smoke checks, then require production release approval. | Staging evidence and release approval. |
| New snapshot | Validate source and run data contract. This is an operational run, not a code deployment. | Snapshot acceptance. |
| Candidate model | Backtest against baseline and locked final test; register metrics and rollback. | Declared promotion threshold and reviewer approval. |
| Drift alert | Open a retrain/rollback proposal. | A human decides whether to act. |

Vercel remains responsible for the static dashboard. The API, worker, scheduler,
audit database, and snapshot store require a separate production service
environment.

## First execution decision

The production next build is not an animated agent or an ML library. It is one
authorised source decision. The separate FreshRetailNet public-benchmark track
can exercise only its forecast lifecycle contract and does not advance this
production queue:

1. CSV pilot, recommended first: fastest genuine, reproducible connector; use a
   de-identified sample/header mapping for the six tables.
2. Shopify: first live-commerce connector when a retailer can grant read-only
   server-side access and confirm historical-order scope.
3. Square: first live connector when the retailer uses Square POS and can grant
   corresponding read-only access.

Stage 2 is implemented locally as a disabled CSV connector gate. The next
source-dependent work is to place it behind authenticated tenant-scoped server
access, configure durable storage, and run it against an authorised sample
before any model claim.
