# RetailOps system blueprint

The control-room screen and `GET /system/blueprint` deliberately distinguish
the current foundation from the intended production operating model. They are
not a live-agent simulator and must not be described as one.

## What exists now

- The project constitution, lifecycle governance, connector contract, and
  deterministic agent decision contract.
- A local pilot-readiness gate. It records declared non-secret pilot scope,
  read-only CSV boundary, roles, retention/transfer rule, header reference,
  and missing evidence in an immutable local audit artifact. It can prepare
  source mapping but cannot authenticate a tenant, verify external approval,
  receive customer data, or activate a connector.
- A P0 non-secret production-foundation contract. It immutably records required
  identity, secret-store, audit-store, object-store, worker, scheduler, and
  role-boundary references; fixture tenant-role shapes are checked. A local
  SQLite migration adapter persists only tenant-partitioned fixture metadata
  and blocked job/schedule events. It does not provision a service, verify an
  identity, expose a customer API, or permit execution.
- A FreshRetailNet-50K public-benchmark adapter. It accepts only a locally
  supplied, explicitly selected 20–50 store-product subset across one to three
  stores, records an immutable licence-attributed public snapshot, preserves
  zero-sales days, and permits limited benchmark forecast evaluation. It blocks
  customer-data ingestion, inventory-risk scoring, replenishment drafting,
  production scoring, and retailer-impact claims.
- A server-side, disabled-by-default CSV connector endpoint. It accepts only
  declared authorised exports, validates canonical identity/time/unit/quantity
  fields, creates an immutable local-pilot snapshot, and records a typed Data
  Contract Agent decision and event timeline. It is not enabled for customer
  data and it does not forecast, score risk, or draft an action.
- A local chronological demand-baseline evaluator. It forms daily demand per
  compatible SKU, location, and unit in a declared operating timezone, measures
  a naïve last-observation baseline on validation days, and keeps the final
  test partition unevaluated during selection.
- A local fixed-candidate lifecycle. It compares only the predeclared
  seven-day trailing-observed-mean candidate against the recorded naïve
  baseline on validation days for an accepted matching snapshot. It retains the
  baseline on any tie or regression, records configuration, validation
  metrics, selection rationale, and rollback baseline in an immutable local
  registry artifact, and leaves that selection artifact unchanged by final-test
  reporting. It has
  no authorised customer-data evaluation, production registry, deployed model,
  or production score.
- One immutable FreshRetailNet public-benchmark final-test report. It evaluates
  the validation-selected model once after selection, checks the persisted
  snapshot and registry chain, and labels metrics as benchmark-only. It cannot
  modify selection or support a customer/operational claim.
- Deterministic Inventory Risk, Impact Ranking, Policy Critic, and Action
  Drafting contracts with labelled fixture success/failure tests. A synchronous
  fixture-only workflow stores their actual named transitions and stops at a
  terminal safety event; it has no worker, customer-facing case, authenticated
  reviewer identity, or external action path.
- A fixture-only persisted reviewer queue. It accepts only critic-approved
  fixture drafts and appends immutable `DEFER`, `APPROVE`, or `DECLINE` events.
  An approval is a recorded human-review outcome only; it never invokes an
  external operation.
- A FastAPI health endpoint, product brief, and versioned architecture
  blueprint endpoint.
- A React architecture explorer that can load the blueprint from the API and
  fall back to the same labelled local foundation data when the API is absent.
- Backend contract tests and a production frontend build.

## What must be implemented before a production claim

1. Provisioned and security-reviewed authenticated tenant-scoped server access
   and production durable object/audit storage for the existing read-only CSV
   connector, followed by an authorised retailer source. The local P0 contract
   records only declared references; the connector remains hard-disabled until
   these controls are implemented and verified.
2. An authorised baseline and fixed-candidate evaluation, durable
   tenant-isolated model registry, human-reviewed release decision, and
   rollback-ready champion. The local lifecycle code supplies chronology-safe
   fixture behavior and a local rollback reference but not a model claim.
3. A tenant-isolated job queue and durable audit storage that run the
   implemented specialist contracts on the same evidence bundle and record
   their typed decisions. The local synchronous fixture workflow is not this
   production worker.
4. An authenticated, tenant-scoped human review queue and outcome capture path
   replacing the local fixture queue. No agent may execute a purchase,
   transfer, pricing, or supplier action.
5. CI checks for code, contracts, data assumptions, and evaluation rules;
   followed by a release gate that packages only an approved version.
6. Production monitoring for schema, freshness, coverage, feature, and data
   drift plus realised forecast error. Drift proposes a retrain or rollback;
   it never changes the champion automatically.

## Parallel-agent rule

The data-contract, forecast-evaluation, inventory-risk, and impact-ranking
specialists may operate in parallel only after they receive the identical
versioned scope and evidence references. Their results converge at the Policy
Critic, which can return `REJECT` or `INCONCLUSIVE`. Action drafting occurs
only after that gate, and an authorised retail planner remains the sole
approver.

## Delivery sequence

The pilot-readiness, public-benchmark adapter, connector, snapshot contract,
naïve baseline evaluator, and fixed-candidate registry gates now exist locally
but are not live. The public adapter can exercise forecast lifecycle code only;
it does not substitute for a named authorised retailer or authenticated tenant
foundation. Those remain required before controlled scoring, review cases, and
monitoring can be implemented. Each stage must ship with its own tests,
artifacts, and documented acceptance criteria before the next is activated.
