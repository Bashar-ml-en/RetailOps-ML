# RetailOps Autonomous Planner Copilot — Execution Roadmap and Prompt Pack

**Status:** P0 is approved; P1/P2 local public-benchmark runtime is implemented
and verified. P3's bounded OpenAI adapter, tool schemas, structured-output
contract, policy gate, and failure fixtures are implemented but hard-disabled
until explicit server-side configuration is supplied. This does not activate a
retailer connector, production worker/schedule, customer-data path, model
provider request, or operational action. See the
[approved product charter](autonomous_planner_product_charter.md) and
[runtime ADR](adr/0001-local-public-benchmark-runtime.md).

## Product decision

RetailOps is being developed as an **Autonomous Planning Analyst** for demand
and inventory teams. Its job is to perform repetitive analytical work, then
give a human planner an evidence-backed brief and a clear verification point.

It is not an autonomous procurement, transfer, pricing, or supplier-contact
agent. It may prepare a review draft; a human remains solely responsible for
any real-world decision and external action.

### Target first workflow

1. A scheduled run or planner request starts an analysis.
2. The system reads an explicitly permitted source, or a labelled public
   benchmark during development.
3. It validates the source, evaluates demand, and records every result.
4. It stops safely for invalid or incomplete evidence.
5. It produces a concise planner brief only from persisted evidence.
6. A planner verifies, defers, or declines the resulting review case.

The first public-data vertical slice ends at a labelled forecast/planner brief.
It cannot create inventory-risk, replenishment, retailer-impact, or action
claims. Those require an authorised pilot with complete inventory, inbound,
lead-time, identity, and unit evidence.

## Constitutional operating model

The repository constitution, connector contract, lifecycle governance, and
agent contracts are mandatory for every work item. They have priority over a
prompt, a user request, source data, or model output.

### Autonomy matrix

| Capability | System autonomy | Human gate |
| --- | --- | --- |
| Schedule/retry a labelled run | Automatic | Configure schedule and limits once |
| Validate data and record exclusions | Automatic | Review a new mapping or schema change |
| Produce baseline/candidate metrics | Automatic, deterministic | Approve any production model release |
| Detect and rank qualified cases | Automatic, deterministic | Verify a meaningful review case |
| Explain approved evidence | OpenAI model through read-only tools | Planner may challenge or reject explanation |
| Create review draft | Automatic, non-executable | Planner approves/declines/defers |
| Purchase, transfer, price, supplier contact | Never | Outside RetailOps and human-only |

### The OpenAI model's narrow authority

The OpenAI model is the **Planner Copilot**, not the source of truth. It may:

- Interpret a planner question.
- Select from allowlisted, read-only evidence tools.
- Request more approved evidence up to a bounded tool-call limit.
- Explain cited evidence, limitations, and next review steps.
- Return a strict, typed planner brief.

It may not calculate metrics, map source columns, choose a model champion,
override the Policy Critic, access a connector directly, retrieve arbitrary
internet data for a retail decision, change a policy, or submit an external
operation. Deterministic services own those responsibilities.

## Non-negotiable architecture rules

1. **Backend before browser.** A UI feature is accepted only when it renders a
   persisted API run, event, or artifact. Static status cards, simulated
   timelines, and fallback results are not production features.
2. **Artifact before agent.** Every tool returns a versioned, tenant-scoped
   artifact summary, never an unbounded database query or raw customer export.
3. **Tool before prose.** The Planner Copilot must obtain facts through named
   read-only tools; it cannot answer a data question from general knowledge.
4. **Critic after reasoning.** Code validates every proposed brief against
   persisted evidence and the Policy Critic before it becomes reviewable.
5. **Human before external effect.** A planner decision is an audit event, not
   an integration call.
6. **Public data stays public.** A public benchmark branch terminates at
   labelled forecast reporting. It never enters inventory risk or action
   drafting.
7. **Secrets stay server-side.** `OPENAI_API_KEY` belongs only in a local
   secret store or deployment secret. Never commit, paste, display, or send it
   to the frontend.
8. **No hidden reasoning logs.** Persist concise tool calls, evidence
   references, structured output, and outcome—not private chain-of-thought.

## Controlled parallelism

“Parallel” means independent workstreams share a frozen contract and converge
at an explicit gate. It does not mean building dependent phases simultaneously
or merging conflicting interfaces.

```text
P0 Product and authority contract
     |
     v
P1 Runtime interface freeze
  ├── P1A audit and event schema
  ├── P1B artifact and object-store adapter
  ├── P1C queue and worker adapter
  └── P1D API and UI client contract
     |
     v
P2 End-to-end deterministic public-data run
  ├── P2A source and snapshot worker
  ├── P2B forecast lifecycle worker
  ├── P2C event-stream and API tests
  └── P2D real-run UI
     |
     v
P3 OpenAI Planner Copilot
  ├── P3A read-only tool gateway
  ├── P3B strict output schema and prompt
  ├── P3C agent evaluation and red-team suite
  └── P3D planner-brief UI
     |
     v
P4 Operations, monitoring, and cost controls
     |
     v
P5 Authorised-pilot activation (external evidence required)
```

Before a stream fans out, its artifact/API contract must be versioned and
accepted. Before it merges, all workstreams must pass their own contract,
failure, safety, and integration tests. Workstreams never share an unversioned
in-memory object as a production interface.

## Phase roadmap and completion gates

| Phase | Purpose | May run in parallel after gate | Completion is accepted only when |
| --- | --- | --- | --- |
| P0 | Agree the autonomous product, user, authority lane, and human gates | None | Product/agent charter is approved and contains no unknown decision that blocks the intended work. |
| P1 | Replace local placeholders with a real local runtime contract | Audit schema, artifact storage, queue, API/UI contract | One fixture run receives a `run_id`, emits durable events, and survives service restart without a mock UI. |
| P2 | Automate the existing deterministic lifecycle on public data | Source worker, forecast worker, event API, real-run UI | A labelled public run completes data validation through forecast report with persisted artifact chain and terminal handling. |
| P3 | Add the bounded OpenAI Planner Copilot | Tool gateway, response schema/prompt, agent evals, planner brief UI | The copilot produces only schema-valid, evidence-cited public reports; adversarial tests prove it cannot invoke forbidden tools or invent an action. |
| P4 | Make automation observable, repeatable, and cost-controlled | Scheduler/retries, monitoring, cost ledger, release controls | Repeated runs are idempotent, budget-limited, traced, observable, and safe under failure/retry conditions. |
| P5 | Activate one authorised pilot | Only explicitly authorised source mapping and deployment work | Pilot charter, production controls, source acceptance, human review, and declared measurement protocol all pass. |

## Current implementation evidence

| Capability | State | Evidence | Deliberate limit |
| --- | --- | --- | --- |
| P1 durable contract | Implemented locally | SQLite idempotency key, worker lease, immutable event stream, restart test | Local adapter only; no tenant identity or production queue |
| P2 public lifecycle | Implemented locally | Explicit worker invokes the existing FreshRetailNet mapping, baseline, fixed candidate, and one locked-final-test report | Needs a server-configured local public parquet path and an explicitly started worker |
| Runtime UI | Implemented | Browser renders only `/v1/public-benchmark-runs` and persisted event records | A static deployment shows no fallback run or analysis |
| P3 evidence gateway | Implemented | Run-bound, read-only summary/forecast/limitation/case tools and fixture tests | Public reports only; no raw rows or customer scope |
| P3 copilot safety | Implemented but disabled | Strict JSON schema, no-provider-storage request mode, tool/output caps, operator token, post-model critic, injection/uncited/action fixtures | No provider request without key, named model, retention acknowledgement, operator token, and cost caps |
| P4 foundations | Partial | Idempotency, lease recovery, terminal outcomes, concise traces, and reservation ledger | Scheduler, production monitoring, actual usage reconciliation, and operator ownership require deployment decisions |

### P0 — Product and autonomy charter

**Demand being tested:** A planner needs a reliable weekly exception brief,
not another dashboard.

**Required inputs:** Named planner role; top five questions; first report
cadence; source mode; definitions of a material case; human approval points;
success metrics; explicit non-goals; public-data status or completed pilot
charter.

**Techniques:** Jobs-to-be-done interview, action/authority matrix, decision
table, traceable acceptance examples, and a written definition of a useful
weekly brief.

**Completion gate:** A reviewer can answer why, what, how, and measured impact
without assuming a retailer or promising a business outcome. Each requested
agent tool has a named owner, input artifact, output schema, and stop condition.

### P1 — Runtime foundation

**Demand being tested:** Automated work must survive beyond a browser session
and remain inspectable after failures.

**Required inputs:** Approved local runtime technology decision; tenant
isolation strategy; durable metadata store; immutable artifact store; queue;
scheduler; authentication/RBAC plan; event schema; deployment secret policy.

**Techniques:** Contract-first API design, database migrations, idempotency
keys, outbox/atomic-event pattern, replayable worker tests, and architecture
decision records. Do not choose cloud vendors, credentials, or identity
providers implicitly.

**Completion gate:** A fixture run can be submitted to the API, claimed by a
worker, restarted safely, queried by `run_id`, and rendered from persisted
events. The UI has no fallback mock run state.

### P2 — Automated deterministic lifecycle

**Demand being tested:** The system can reduce repetitive analysis work without
an LLM deciding facts.

**Required inputs:** Frozen P1 contracts; labelled public source adapter;
snapshot/version policy; baseline/candidate configuration; terminal-event
policy; event-stream contract.

**Techniques:** Immutable artifact chain, chronological backtesting,
historical-only features, deterministic orchestration, idempotent retries, and
golden fixture runs. Existing CSV, baseline, fixed-candidate, specialist, and
review-contract code must be reused rather than duplicated.

**Completion gate:** A fresh labelled public run emits the actual sequence
`QUEUED → VALIDATING → SNAPSHOT_STORED → BASELINE_EVALUATED → REPORT_READY`
or a persisted terminal failure. It records source, mapping, feature, and
model versions, evidence references, metrics, and limitations. A public run is
blocked from risk/action stages.

### P3 — OpenAI Planner Copilot

**Demand being tested:** A planner can understand an approved run faster than
by reading raw artifacts.

**Required inputs:** Server-side API credential stored outside the repository;
approved model configuration; monthly/per-run budget; response-retention
decision; strict request/response schemas; tool allowlist; evaluation corpus;
fallback behavior when the model is unavailable.

**Techniques:** Responses API custom function calling; strict structured
outputs; bounded context packs; read-only tool gateway; deterministic post-LLM
policy validation; prompt versioning; prompt-injection resistance; and agent
traces paired with local audit events.

**Allowed first tools:**

```text
get_run_summary(run_id)
get_forecast_evidence(run_id, scope_id)
get_qualified_cases(run_id)
get_case_evidence(case_id)
get_limitations(run_id_or_case_id)
create_planner_brief_draft(run_id, cited_evidence_refs)
```

Each tool validates tenant scope, input schema, actor role, and artifact state.
It returns compact, redacted evidence summaries only. No tool may write to a
retailer, query an arbitrary database table, fetch unapproved web content, or
activate a model/connector.

**Completion gate:** On a versioned evaluation corpus, all outputs validate
against the response schema; every factual claim cites a supplied evidence
reference; prohibited-action, missing-evidence, prompt-injection, unavailable
tool, and malformed-tool-output fixtures end safely; and no planner brief is
shown until deterministic policy validation passes.

### P4 — Operational reliability and controlled learning

**Demand being tested:** The autonomous system remains useful and bounded when
runs repeat, sources drift, a worker fails, or API spending approaches its
limit.

**Required inputs:** Schedule/cadence, timezone, retry/backoff policy,
idempotency policy, freshness/drift/error thresholds, cost ceiling, alert
owner, retraining proposal criteria, and rollback decision owner.

**Techniques:** Distributed tracing, structured logs, SLOs, dead-letter queue,
retry simulation, failure injection, usage ledger, token/tool-call caps,
schema/freshness drift monitors, realised-error monitor, and release canaries.

**Completion gate:** Duplicate deliveries do not duplicate business artifacts;
failed work retries only within limits; budget and tool caps stop further LLM
work safely; monitoring emits a proposal rather than changing a champion; and
operator dashboards display actual persisted health/events.

### P5 — Authorised pilot activation

**Demand being tested:** The autonomous analyst improves a named planner's
review workflow under an approved, read-only scope.

**Required inputs:** Complete pilot charter; verified deployment controls;
tenant authentication; named data/security/planner roles; approved source and
transfer channel; retention/deletion rule; SKU/location scope; timezone;
historical period; shadow-review plan; baseline and success measures.

**Techniques:** Least-privilege connector review, secure mapping review,
shadow mode, progressive rollout, outcome capture, weekly evidence review,
model release approval, and rollback rehearsal.

**Completion gate:** The pilot uses only the recorded tenant/source/scope;
human reviewers can authenticate and audit their decisions; measured outcomes
are compared to the declared baseline; and no external action is executed by
RetailOps.

## Master execution prompt

Use this prompt for one work item only. A coordinator may assign independent
P1/P2/P3 workstreams in parallel only after their parent contract is frozen.

```text
<ROLE>
You are the RetailOps Autonomous Planner Copilot Execution Lead. Deliver one
bounded, production-grade implementation work item. You build real, testable
server-side behaviour before any presentation layer. You never represent a
static mock, fixture-only result, or public benchmark as a live retailer run.
</ROLE>

<CONSTITUTION>
RetailOps automates analysis, not retail operations. It may read only the
approved source and may prepare a human review brief. It must never purchase,
transfer inventory, change prices, contact suppliers, grant permissions, or
execute an external action. Unknown identity, unit, source scope, inventory,
inbound, lead-time, or model evidence yields INCONCLUSIVE or REJECT.

Deterministic services own validation, metrics, source mapping, model
selection, risk calculation, policy enforcement, and external-action blocking.
The OpenAI Planner Copilot may use only allowlisted read-only tools and may
explain validated evidence in a strict output schema. It cannot invent facts,
metrics, evidence references, or tool results.
</CONSTITUTION>

<INPUT_ENVELOPE>
[Paste the completed work-item envelope below. Missing fields are UNKNOWN and
must not be inferred.]
</INPUT_ENVELOPE>

<EXECUTION_PROTOCOL>
1. Read the governing contracts and identify the parent phase, dependency
   artifacts, authority lane, tenant/source classification, and human gate.
2. Verify that the work item is independent of other active workstreams. If
   not, REFINE it into a contract-first prerequisite; never duplicate a shared
   interface or make incompatible changes in parallel.
3. Choose exactly one: PROCEED, REFINE, or REJECT. REFINE may create a local,
   disabled, fixture, or public-benchmark foundation only.
4. Implement the smallest vertical capability that creates or consumes named,
   versioned artifacts. A browser component may be added only after a real API
   contract and persisted event prove the state it renders.
5. For OpenAI work, keep credentials server-side; expose only strict tools;
   cap tokens, tool calls, timeout, retries, and spend; use structured output;
   run deterministic policy validation after every response; and persist a
   concise trace without hidden reasoning.
6. Add success, failure, idempotency, security-boundary, and integration tests.
   For model/prompt work, add a versioned eval case for every new behaviour and
   every discovered regression.
7. Run the relevant test suite, frontend production build when applicable,
   lifecycle audit, and the phase completion checks. Do not claim a phase is
   complete when an external dependency or human approval remains unresolved.
</EXECUTION_PROTOCOL>

<REQUIRED_OUTPUT>
PRE_FLIGHT
- Parent phase, authority lane, dependencies, inputs present, and inputs missing.

DECISION
- PROCEED, REFINE, or REJECT with a concise evidence-grounded reason.

IMPLEMENTATION
- Exact capability, artifact/API contracts, and explicit non-goals.

PARALLELISM
- Why this work is independent, its merge contract, and what must not run in parallel.

VERIFICATION
- Success, failure, idempotency, safety-boundary, and integration tests; exact results.

EVALUATION
- Applicable phase scorecard, evidence artifacts, known limitations, and human gate.

NEXT_ACTION
- The next dependency-aware work item or exact external input required.
</REQUIRED_OUTPUT>
```

## Work-item envelope

Every implementation invocation supplies this YAML. It is deliberately more
specific than a generic coding prompt.

```yaml
work_item_id: "P3A-read-only-tool-gateway-v1"
parent_phase: "P3"
workstream: "P3A"
objective: "Implement tenant-scoped, read-only evidence tools for the Planner Copilot."
authority_lane: "PUBLIC_BENCHMARK" # or AUTHORISATION_READINESS / AUTHORISED_PILOT
source_classification: "PUBLIC_BENCHMARK"
tenant_scope: "benchmark-only"
dependencies:
  contracts:
    - "versioned run/event API contract"
    - "artifact summary schema"
  required_artifacts:
    - "accepted public benchmark run"
  unresolved_external_dependencies:
    - "OpenAI credential is not needed for this tool-only work item"
allowed_operations:
  - "read persisted benchmark artifact summaries"
  - "validate tool input/output schema"
prohibited_operations:
  - "customer data access"
  - "connector activation"
  - "inventory-risk or action draft"
  - "external writes"
artifact_contracts_created:
  - "tool request/response schemas"
completion_evidence:
  - "tool tests reject cross-scope, malformed, and unapproved requests"
  - "tool output contains compact evidence references and limitations"
  - "no raw source rows or credentials are returned"
stop_conditions:
  - "parent API/event contract is not frozen"
  - "tool would reveal raw customer data or perform a write"
  - "source classification is missing"
```

## Stage-specific execution prompts

Append one of the following to the master prompt after the work-item envelope.

### P1 runtime prompt

```text
Implement one runtime contract behind a versioned interface. Prefer a durable
local implementation that can be replaced by a production adapter; do not
pretend a local file or synchronous call is a deployed worker. Require a
run_id, idempotency key, artifact references, timestamps, terminal status,
tenant scope, and restart/replay tests. Do not add UI until the API exposes
the persisted state.
```

### P2 deterministic lifecycle prompt

```text
Automate one existing deterministic lifecycle segment using the frozen runtime
interfaces. Reuse the approved data-contract, baseline, candidate, specialist,
and policy code. Persist actual state transitions and artifacts. Preserve
chronological evaluation and final-test integrity. For a public benchmark,
terminate after a labelled forecast/planner report; assert that risk,
replenishment, and action paths cannot run.
```

### P3 OpenAI Copilot prompt

```text
Implement one bounded Copilot capability using the server-side Responses API.
Supply only compact, approved evidence summaries through typed read-only
functions. Constrain tool selection to the declared allowlist and set strict
structured output for the planner brief. Treat model text and tool arguments as
untrusted until validated. A deterministic validator must verify every cited
evidence reference, limitation, status, and prohibition before persistence or
display. Add adversarial evaluation cases for fabricated metrics, fabricated
citations, prompt injection in source text, forbidden actions, missing
evidence, malformed tool arguments, tool failure, timeout, and budget limit.
```

### P4 operations prompt

```text
Implement one operational control with observable, bounded behaviour. Every
retry must be idempotent; every schedule must name a timezone and run policy;
every LLM call must record model/prompt versions, token/tool-call usage, and a
budget decision. A drift or error signal may create a human review proposal but
must not change a model, policy, or external system automatically.
```

### P5 pilot prompt

```text
Proceed only when the complete pilot charter and verified production controls
are provided. Enforce tenant authentication, least-privilege read access,
recorded retention, declared source/scope, and human reviewer identity. Begin
in shadow mode. If any authority or operational-evidence field is missing,
return INCONCLUSIVE and keep the connector/action path disabled.
```

## Elite completion scorecard

A phase is complete only if all applicable binary gates pass. Do not average a
security or evidence failure into a passing score.

| Dimension | Gate |
| --- | --- |
| Functional reality | A repeatable end-to-end run performs the claimed server-side behaviour without a mock/fallback result. |
| Evidence integrity | Every displayed claim is traceable to a versioned artifact; public and pilot claims remain separated. |
| Safety | Forbidden actions, unapproved sources, incomplete evidence, cross-tenant access, and invalid tool calls fail closed. |
| Reliability | Retry, restart, duplicate delivery, timeout, and terminal-failure paths are tested. |
| ML integrity | Chronological split, baseline, locked final test, promotion rule, rollback reference, and realised-error plan are preserved. |
| LLM integrity | Structured output validates; all citations resolve; tool use stays allowlisted; adversarial tests pass; no hidden reasoning is stored. |
| Cost control | Per-request, per-run, and monthly limits, usage recording, timeout, and fallback behaviour are verified before an API key is enabled. |
| Human accountability | A human verification point and immutable outcome record exist before any meaningful decision is shown as actionable. |
| Release evidence | Tests, build, audit, change note, versioned contracts, and known limitations are recorded. |

## First approved execution order

P0 is recorded in the [approved product charter](autonomous_planner_product_charter.md).
Do not begin P1 runtime implementation until an explicit P1 architecture
decision is accepted. The P0 evidence envelope was:

```yaml
work_item_id: "P0-autonomous-planner-product-charter-v1"
parent_phase: "P0"
workstream: "P0"
objective: "Record the agreed first planner workflow, autonomous duties, human gates, OpenAI authority boundary, public-data limitations, success measures, and phase acceptance tests."
authority_lane: "AUTHORISATION_READINESS"
source_classification: "FIXTURE_AND_PUBLIC_BENCHMARK"
allowed_operations:
  - "documentation"
  - "fixture/evaluation design"
  - "architecture decision records"
prohibited_operations:
  - "API credential use"
  - "customer data access"
  - "connector activation"
  - "production deployment"
completion_evidence:
  - "one approved product/agent charter"
  - "top five planner questions and expected structured answers"
  - "autonomy matrix and human gates"
  - "model/tool/cost/evaluation decision placeholders marked UNKNOWN where owner choice is needed"
stop_conditions:
  - "claim that a static interface is a runtime"
  - "unbounded LLM tool authority"
  - "attempt to use public data for a retailer claim"
```

Only after the P1 architecture decision is accepted may P1 fan out into
independent runtime workstreams.
