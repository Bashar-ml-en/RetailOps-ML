# RetailOps ML

RetailOps ML is a global, evidence-first decision-support foundation for
retailers and distributors. It helps human planners identify demand and
inventory cases that deserve review before a stockout or excess-stock decision
is made.

## The product answers four questions

| Question | RetailOps ML answer |
| --- | --- |
| Why is this worth solving? | Retail teams need a reliable way to prioritise stockout and excess-inventory risk from fragmented operational data. |
| What is it designed to do? | After its lifecycle gates are built and validated, it will produce evidence-backed demand forecasts, inventory-risk cases, and reviewable action drafts per compatible SKU and location. |
| What works today? | A disabled server-side CSV gate validates an authorised export, stores an immutable local-pilot snapshot, and records a typed Data Contract decision. It does not forecast or make an operational recommendation. |
| How will it work? | Authorised connector data is validated and versioned first; then chronological forecasting, deterministic specialist review, and final human approval are added as separately tested gates. |
| What impact can it make? | A future pilot will measure forecast error, qualified cases found, planner response time, stockout days, and excess inventory. It does not promise outcomes before measurement. |

## Current status

This is a clean RetailOps ML foundation. It contains the product constitution,
retail connector contract, ML lifecycle governance, agent contracts, reusable
skill, reframed product-decision prompt, and a minimal local scaffold. It also
includes a server-side CSV snapshot and validation gate that is disabled by
default until an authenticated authorised deployment exists. A local,
chronology-safe naïve baseline evaluator is also available, but it has no
authorised customer-data run or reported model metric.

P0 production-foundation preparation is also implemented as a non-secret,
fixture-only contract. It records the required identity, secret-store,
relational audit-store, immutable object-store, worker, scheduler, and RBAC
references; validates fixture tenant-role scope; and refuses all local worker
or scheduler execution. A local SQLite adapter records only tenant-partitioned
fixture audit metadata and blocked job/schedule records. It provisions no
external service, exposes no customer API, and keeps customer ingestion
hard-disabled.

It also includes a fixture-backed, fixed-candidate lifecycle gate: a seven-day
trailing-observed-mean candidate can be compared with the recorded naïve
baseline on chronological validation only, with the final test period locked.
The local registry artifact records configuration, metrics, selection, and a
rollback baseline; a tie or regression retains the baseline. This is not an
authorised customer evaluation, trained production model, deployed service, or
operational action.

The recorded FreshRetailNet local model has one separate immutable final-test
report. It evaluates the validation-selected retained naïve baseline over the
locked public split without changing the registry selection. Its metrics are
labelled benchmark-only and cannot support customer, inventory, replenishment,
or business-impact claims.

Stage 5 deterministic specialist contracts are also available for labelled
fixtures: Inventory Risk, Impact Ranking, Policy Critic, and Action Drafting.
They fail closed on missing evidence, prohibit external operations, and can
create only a non-executable human-review draft. A synchronous fixture-only
workflow records actual specialist and terminal events before a local queue
persists approve, decline, and defer audit events. There is not yet a worker,
authenticated reviewer workflow, or customer action path.

FreshRetailNet-50K can now enter the same local baseline and fixed-candidate
gates through an explicit, locally supplied **public benchmark** adapter. A
pinned, recorded local benchmark run exists, but its snapshots and metrics are
limited to benchmark forecast evaluation; the source is not bundled or
downloaded by the app, and it cannot unlock customer ingestion, inventory-risk
scoring, replenishment drafts, production scoring, or retailer-impact claims.

RetailOps intentionally has no live merchant connector, demand forecast,
inventory score, parallel-agent workload, or autonomous purchasing capability.
The CSV and model-lifecycle gates record local fixture behavior only; they are
not live customer integrations or production models. Those are upcoming
validated stages, not mocked features.

## Documentation

- [Constitution](docs/constitution.md)
- [Retail connector contract](docs/data_contract.md)
- [Agent contracts](docs/agent_prompts.md)
- [ML lifecycle governance](docs/lifecycle_governance.md)
- [Demand-baseline contract](docs/baseline_contract.md)
- [Fixed-candidate lifecycle contract](docs/model_lifecycle_contract.md)
- [Authorised pilot charter](docs/authorised_pilot_charter.md)
- [Read-only CSV authorisation request pack](docs/authorisation_request_pack.md)
- [Pilot-readiness contract](docs/pilot_readiness_contract.md)
- [Production-foundation contract](docs/production_foundation_contract.md)
- [Fixture tenant-audit contract](docs/fixture_tenant_audit_contract.md)
- [FreshRetailNet public benchmark contract](docs/freshretailnet_benchmark_contract.md)
- [FreshRetailNet final-test benchmark report](docs/freshretailnet_final_test_report.md)
- [Architecture](docs/architecture.md)
- [Inspectable system blueprint](docs/system_blueprint.md)
- [Experience system](docs/experience_system.md)
- [Production roadmap](docs/production_roadmap.md)
- [Build track](docs/build_track.md)
- [Product-decision prompt](docs/prompting_standard.md)
- [Prompt-engineering mechanism](docs/prompt_engineering_mechanism.md)
- [Implementation execution prompt](docs/implementation_execution_prompt.md)

## Local development

Backend, from backend/:

~~~powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest
uvicorn app.main:app --reload --port 8000
~~~

Frontend, from frontend/:

~~~powershell
pnpm install
pnpm dev
~~~

Open http://localhost:5173 after starting the API at http://localhost:8000.

## Vercel deployment

The checked-in Vercel configuration builds the static React control room from
`frontend/` and serves `frontend/dist`. It explicitly installs development
build tooling, so a `NODE_ENV=production` project variable cannot omit Vite or
TypeScript during Vercel's build. The public control room uses its embedded,
explicitly labelled architecture blueprint unless an HTTPS API is configured
with `VITE_API_URL`.

A Vercel deployment makes the inspectable product surface available; it does
not by itself activate retail connectors, model training, agent workloads, or
operational decisions. Before connecting a production API, deploy it separately
with authenticated connector credentials held only on the server, explicit
CORS for the Vercel domain, durable audit storage, and the lifecycle gates in
`docs/system_blueprint.md`.
