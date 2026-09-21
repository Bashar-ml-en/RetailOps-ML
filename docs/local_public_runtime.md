# Local Public-Benchmark Runtime

This is the executable development path for RetailOps. It drives the existing
FreshRetailNet mapping and forecast lifecycle through a durable queue and a
separate worker. It is not a customer connector, cloud deployment, scheduler,
or purchasing system.

## What it does

1. The API accepts only a bounded FreshRetailNet store/product selection and an
   idempotency key.
2. SQLite persists the request and `QUEUED` event.
3. A separately started worker reads the server-configured public parquet file,
   validates it, persists an immutable snapshot, runs the baseline and fixed
   candidate, and reports the locked final test.
4. The API/UI display only those persisted records. A missing source or unsafe
   artifact chain ends in an explicit terminal state.

Neither the API nor browser accepts a source file path. The worker never
downloads a dataset or calls a retailer system.

## Run locally

Set server-side paths in your shell (do not commit them):

```powershell
$env:RETAILOPS_PUBLIC_BENCHMARK_SOURCE_PATH = 'C:\approved-public-data\train.parquet'
$env:RETAILOPS_RUNTIME_ROOT = 'C:\Retialsopps\data\runtime'
$env:RETAILOPS_AUDIT_ROOT = 'C:\Retialsopps\data\audit'
$env:PYTHONPATH = 'C:\Retialsopps\backend'
```

Start FastAPI in one terminal and the UI in another. Submit a validated 20–50
scope request to `POST /v1/public-benchmark-runs`; use the same idempotency key
to safely retry the submission. Then start one worker explicitly:

```powershell
python -m app.runtime.worker --once
```

Inspect `GET /v1/public-benchmark-runs/{run_id}` and
`GET /v1/public-benchmark-runs/{run_id}/events`. A successful public run has
the lifecycle `QUEUED → VALIDATING → SNAPSHOT_STORED → BASELINE_EVALUATED →
REPORT_READY`, with additional persisted selection/final-test events. It still
cannot produce inventory risk, replenishment, or retailer-impact claims.

## Optional OpenAI explanation layer

The planner-brief endpoint is disabled by default. It makes no API call unless
all of the following are configured server-side:

- `OPENAI_API_KEY` in a local secret environment or deployment secret;
- `RETAILOPS_ENABLE_PLANNER_COPILOT=true`;
- a deliberate `RETAILOPS_OPENAI_MODEL` selection;
- positive per-run and monthly budget caps in cents; and
- `RETAILOPS_COPILOT_NO_PROVIDER_STORAGE_APPROVED=true`; and
- a separate `RETAILOPS_COPILOT_OPERATOR_TOKEN`, supplied as
  `X-RetailOps-Operator-Token` when invoking the planner-brief endpoint.

When enabled, the adapter sends `store: false`, allows only compact read-only
evidence functions for the single completed public run, caps tool calls and
output tokens, and validates strict JSON output after the model responds. It
does not accept a user prompt, source rows, arbitrary tools, customer data, or
an action request. A rejected/unavailable model response is never shown as a
planner brief.

The operator token constrains local public-runtime spend. It is not a tenant
identity/RBAC implementation and does not make the service pilot-ready.

To configure all of those values without placing a key in a repository file,
run this interactive command after revoking the exposed key and creating a new
one in the OpenAI dashboard:

```powershell
.\scripts\configure-local-copilot.ps1 -Model 'your-approved-model-id' -ApproveNoProviderStorage
```

The script hides key input, creates a local operator token, writes only Windows
user environment variables, and never prints either secret. Restart the API
afterward. It deliberately requires a model argument: model selection is an
owner decision, not something the script silently makes.

After a public run reaches `REPORT_READY`, generate a brief from the same
server terminal. The command accepts only the persisted run ID; it cannot
accept a prompt, source path, credentials, or browser input:

```powershell
python -m app.copilot.cli --run-id '<completed-public-run-id>'
```

It prints a status, trace ID, and (only when critic-approved) the persisted
brief ID. The UI reads approved briefs through its read-only API and cannot
trigger a provider call or access the API key/operator token.

The applicable prompt and policy are versioned in
[planner_copilot_prompt.md](planner_copilot_prompt.md). Exact model choice and
budget allocation remain owner decisions; available account credit alone is
not an allocation.
