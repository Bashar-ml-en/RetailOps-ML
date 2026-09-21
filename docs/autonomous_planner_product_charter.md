# RetailOps Autonomous Planner Copilot — Product and Autonomy Charter

**Version:** autonomous-planner-charter-v1
**Status:** APPROVED_FOR_PUBLIC_BENCHMARK_DEVELOPMENT
**Decision owner:** Repository owner
**Authority lane:** PUBLIC_BENCHMARK and AUTHORISATION_READINESS only

## Decision

RetailOps will become an autonomous, server-side planning analyst that performs
repeatable retail analysis and delivers an evidence-backed planner brief. The
first implementation target uses labelled public benchmark data only. It must
not claim retailer impact, activate a retailer connector, create an
inventory-risk/replenishment case, or execute any external operation.

The first human user is a retail demand or inventory planner. The product
reduces preparation and analysis time for a weekly demand-exception review; it
does not replace the planner's operational judgement.

## Why

Planners spend time assembling demand history, comparing forecast results,
checking data quality, and translating technical output into review questions.
The first useful product outcome is a reproducible weekly brief that states:

- What analysis ran and what source it used.
- What demand evidence changed within a selected scope.
- Whether the forecast lifecycle retained or promoted an eligible model.
- What evidence is missing or limited.
- What a planner should verify next.

The product does not promise sales, margin, availability, stockout reduction,
or operational savings before an authorised pilot measures those outcomes.

## First autonomous workflow

~~~text
Manual or scheduled public-benchmark run
  → immutable snapshot and validation
  → chronological baseline/candidate evaluation
  → persisted events, metrics, evidence, and limitations
  → OpenAI Planner Copilot creates a structured evidence brief
  → human reviews the brief and records feedback
~~~

The public-benchmark branch ends after the labelled planner brief. It never
enters inventory risk, impact ranking, action drafting, or external operations.

## First five planner questions

| Planner question | Required evidence/tool result | Expected structured answer | Stop condition |
| --- | --- | --- | --- |
| What analysis ran? | Run summary, source mode, snapshot and artifact versions | Run status, scope, source classification, timestamps, and evidence references | Run/artifact is absent or source mode is unknown. |
| What changed in demand? | Forecast evidence for an eligible SKU-location-unit scope | Observed/forecast comparison, declared horizon, and cited limitation | Scope/unit is incompatible or insufficient history exists. |
| Did the candidate beat the baseline? | Recorded validation metrics and selection artifact | Retained/promoted status, declared comparison, and rollback reference | Baseline, split, or matching snapshot is absent. |
| Can I rely on this result? | Data Contract decision, coverage/freshness checks, model limitations | Explicit limitations and what cannot be claimed | Evidence is incomplete, stale, or public data is presented as retailer evidence. |
| What should I review next? | Critic-approved public forecast brief and limitations | Non-operational verification steps; no order, transfer, or financial guarantee | The response requests a retail action or lacks cited evidence. |

## Autonomy and human gates

| Activity | Autonomous system responsibility | Human responsibility |
| --- | --- | --- |
| Run scheduling | Start/retry a permitted labelled job within configured limits | Configure schedule, timezone, and budget policy. |
| Data quality | Validate source, persist exclusions, and stop invalid runs | Approve a new source mapping or schema policy. |
| Forecast lifecycle | Build historical features, compare baseline/candidate, preserve final-test lock | Approve production promotion only after authorised evaluation. |
| Planner brief | Retrieve allowlisted evidence and produce a structured explanation | Verify usefulness, challenge limitations, and record feedback. |
| Operational action | Never execute | Decide outside RetailOps under the organisation's normal controls. |

## Planner brief contract

The OpenAI Planner Copilot must return a strict PlannerBriefV1 object after
reading compact evidence through allowlisted tools. The application validates
the object and its evidence references before persistence or display.

~~~text
planner_brief_id
run_id
source_mode: PUBLIC_BENCHMARK | AUTHORISED_PILOT
status: PASS | PASS_WITH_LIMITATIONS | REJECT | INCONCLUSIVE
headline
analysis_summary
forecast_findings[]
evidence_references[]
limitations[]
planner_verification_steps[]
human_decision_required: true | false
prohibited_operations[]
prompt_version
model_version
~~~

For public benchmark runs, human_decision_required concerns review of the
analysis only; it must never imply a retailer operational decision. Every
evidence_reference must resolve to a persisted artifact field. The brief must
state PUBLIC_BENCHMARK visibly and include the prohibition on customer,
inventory-risk, replenishment, and business-impact claims.

## OpenAI Copilot authority

The Copilot is an explanation and bounded planning layer. It can interpret a
planner question and call only read-only, server-side evidence functions:

~~~text
get_run_summary
get_forecast_evidence
get_model_selection_evidence
get_limitations
create_planner_brief_draft
~~~

The Copilot cannot access a connector, arbitrary database query, browser,
internet source, source-row export, secret, action endpoint, model-promotion
endpoint, or policy configuration. It cannot create a metric, evidence
reference, model-selection conclusion, or operational recommendation without a
deterministic artifact that supports it.

Model text, tool arguments, and tool outputs are treated as untrusted until
validated against their schemas and the Policy Critic. The deterministic system
remains authoritative for data validation, metrics, model selection, risk
calculation, policy enforcement, and action blocking.

## Evaluation and success definition

### P0 completion evidence

- This charter defines the buyer, recurring workflow, source mode, five
  questions, expected outputs, human gates, non-goals, and stop conditions.
- The product constitution and existing specialist contracts remain unchanged.
- The roadmap identifies a real runtime as the next phase; a browser mock is
  not accepted as an autonomous-agent result.

### P1/P2 runtime success

- A public run gets a durable run_id, event history, artifact references, and
  terminal status that survive a service restart.
- A public run either creates an evidence-linked forecast brief or records a
  terminal REJECT, INCONCLUSIVE, or FAILED result.
- The UI displays only API-persisted state and clearly fails when the runtime
  is unavailable.

### P3 Copilot quality gates

- Every generated brief conforms to PlannerBriefV1.
- Every factual output field cites a valid supplied evidence reference.
- Evaluation fixtures cover fabricated metrics/citations, prompt injection in
  source text, forbidden actions, missing evidence, malformed tool arguments,
  unavailable tools, timeout, and budget exhaustion.
- Any unsafe or unsupported answer is rejected or marked INCONCLUSIVE before
  a planner sees it as a reviewable result.

### Future pilot measures

After a complete authorised pilot charter and deployment controls exist, the
team may measure forecast error against the declared baseline, analyst/planner
preparation time, qualified review-case usefulness, coverage, exclusions, and
reviewer outcomes. No target business improvement is declared yet.

## Deferred choices that do not block P0

| Decision | Current state | Blocks |
| --- | --- | --- |
| OpenAI model identifier | UNKNOWN — choose after P3 evaluation corpus exists | P3 API activation only |
| Exact per-run/monthly API spend caps | UNKNOWN — the owner reported approximately USD 50 in available credits | P3 API activation only |
| API data-retention configuration | UNKNOWN — decide before any non-public data could be sent | P3 activation beyond public benchmark |
| Production cloud, identity provider, queue, database, and object store | UNKNOWN — require an explicit P1 architecture decision | P1 production-equivalent runtime implementation |
| Authorised retailer and pilot scope | UNKNOWN | P5 pilot activation only |

No API key, credentials, customer data, or retailer identity is required or
permitted for P0.

## P0 exit decision

**Result:** PROCEED to P1 architecture decision work.

The next bounded work item is P1-architecture-decision-record-v1: select the
local runtime approach and durable interfaces for API, audit/event store,
artifact store, queue/worker, scheduler, and authenticated-role boundary. It
must make no deployment or provider decision without explicit owner approval.
