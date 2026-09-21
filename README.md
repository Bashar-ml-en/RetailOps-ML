# RetailOps ML

[![Verify RetailOps ML](https://github.com/Bashar-ml-en/RetailOps-ML/actions/workflows/verify.yml/badge.svg?branch=main)](https://github.com/Bashar-ml-en/RetailOps-ML/actions/workflows/verify.yml)

RetailOps ML is an evidence-first, reusable foundation for retail demand,
inventory, and replenishment decision support. It helps planners decide which
SKU-location cases deserve review; it never purchases stock, moves inventory,
changes prices, or contacts suppliers.

## What this repository is

This is a governed **local and pre-pilot foundation**, not a production retail
service. Its components are deliberately usable in three distinct modes:

| Mode | Intended use | Permitted claim |
| --- | --- | --- |
| Labelled fixtures | Development and safety tests | Contract behaviour only |
| Public benchmark | Reproducible forecast evaluation | Benchmark results only |
| Authorised pilot | A retailer's approved, read-only data scope | Pilot evidence only |

Customer ingestion remains hard-disabled until an authenticated, authorised
deployment exists. Public data (including FreshRetailNet-50K) is never treated
as customer data and cannot unlock operational recommendations.

## What works today

- A modular FastAPI service with stable system and connector-run routes.
- An opt-in, server-side CSV connector gate that validates the authorisation
  boundary before it accepts a snapshot; it is disabled by default.
- Chronology-safe naïve-baseline and fixed-candidate lifecycle evaluation with
  a locked final-test report for the public benchmark.
- Deterministic Data Contract, Forecast Evaluation, Inventory Risk, Impact
  Ranking, Policy Critic, and Action Drafting contracts for labelled fixtures.
- Failure-closed review flows: incomplete identity, units, stock, inbound, or
  lead-time evidence yields an inconclusive decision rather than an action.
- A React control-room surface, versioned documentation, fixture tests, and
  CI that runs backend tests and the frontend production build.

## Safety boundary

RetailOps ML is decision support for human planners. Forecasts and risk scores
are estimates, not guarantees. A draft is non-executable and requires a human
reviewer. The Policy Critic has veto authority and may return only `PASS`,
`PASS_WITH_LIMITATIONS`, `REJECT`, or `INCONCLUSIVE`.

Do not put credentials, customer exports, or customer identifiers in this
repository, issues, pull requests, or public benchmark artifacts.

## Quick start

Prerequisites: Python 3.12+, Node.js 22.12–24.x, and pnpm 11.19.0.

```powershell
git clone https://github.com/Bashar-ml-en/RetailOps-ML.git
Set-Location RetailOps-ML
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
pnpm --dir frontend install --frozen-lockfile
.\scripts\verify.ps1
```

Run the API and UI in separate terminals:

```powershell
python -m uvicorn app.main:app --app-dir backend --reload --port 8000
pnpm --dir frontend dev
```

Open `http://localhost:5173`. The local UI can render its explicitly labelled
blueprint without connecting to an API. For a local API, use
`http://localhost:8000`.

On macOS or Linux, use `./scripts/verify.sh`. Override the Python executable
with `PYTHON_BIN=/path/to/python ./scripts/verify.sh` when needed.

## Repository map

```text
backend/       FastAPI composition, governed workflow components, and tests
frontend/      React/Vite control-room interface
docs/          Product constitution, contracts, lifecycle, and evidence docs
scripts/       Cross-platform verification entry points
.github/       CI, Dependabot, and contribution templates
data/          Ignored local snapshots, benchmark material, and audit outputs
```

The API's current inspectable routes are:

- `GET /health`
- `GET /product/brief`
- `GET /system/blueprint`
- `POST /v1/connector-runs/csv` (hard-disabled without an authorised runtime)
- `GET /v1/runs/{run_id}`

## Reuse responsibly

1. Start with fixtures or the documented public benchmark; label every output
   with its source mode.
2. Read the [reuse guide](docs/reuse-guide.md) and the governing contracts
   before changing a connector, model, agent, policy, or API contract.
3. Introduce an authorised connector only with a defined tenant, approved
   source and transfer path, read-only credentials, retention rule, and
   fixture-backed boundary tests.
4. Evaluate models chronologically against a declared baseline and retain a
   rollback-ready champion. Never promote against the locked final test.
5. Keep operational actions human-approved and non-executable from this code.

## Key documentation

- [Product constitution](docs/constitution.md)
- [Retail connector contract](docs/data_contract.md)
- [Lifecycle governance](docs/lifecycle_governance.md)
- [Specialist agent contracts](docs/agent_prompts.md)
- [Autonomous Planner Copilot execution roadmap](docs/autonomous_agent_execution_roadmap.md)
- [Architecture](docs/architecture.md) and [system blueprint](docs/system_blueprint.md)
- [FreshRetailNet benchmark contract](docs/freshretailnet_benchmark_contract.md)
  and [locked final-test report](docs/freshretailnet_final_test_report.md)
- [Authorised pilot charter](docs/authorised_pilot_charter.md) and
  [authorisation request pack](docs/authorisation_request_pack.md)
- [Build track](docs/build_track.md) and [production roadmap](docs/production_roadmap.md)

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution workflow and
[SECURITY.md](SECURITY.md) for responsible disclosure guidance.

## Licence

No open-source licence is currently declared. The repository owner must select
and add a licence before third parties can legally reuse or distribute it.
