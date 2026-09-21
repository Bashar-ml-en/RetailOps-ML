# RetailOps ML Prompt-Engineering Mechanism

## Purpose and boundary

This mechanism converts the remaining roadmap into small, auditable
implementation work items. It is for an implementation agent or engineer; it
is not a planner-facing decision engine. It prevents a capable general-purpose
model from treating a public benchmark as a retailer pilot, inventing evidence,
or widening a bounded change into an unsafe integration.

RetailOps remains decision support for human planners. No prompt may authorise
the purchase of stock, inventory transfers, price changes, supplier contact,
connector writes, or activation of a customer integration.

The mechanism complements the product-decision prompt in
`docs/prompting_standard.md`. Use the master prompt in
`docs/implementation_execution_prompt.md` for every implementation work item.

## Control loop

Every work item follows this loop:

1. **Supply an evidence envelope.** The requester names one bounded objective,
   its data/authority lane, relevant artifact references, acceptance evidence,
   and stop conditions.
2. **Run pre-flight.** The executor verifies the source classification and
   checks that required evidence is present. Unknown facts stay `UNKNOWN`.
3. **Choose one decision.** Only `PROCEED`, `REFINE`, or `REJECT` are allowed.
   `REFINE` means a safe foundation or fixture/test may be added, but an
   authority-dependent capability stays disabled. `REJECT` means no
   implementation that would imply unsupported readiness.
4. **Make the smallest coherent change.** Preserve public-data labels,
   versioned artifacts, typed specialist contracts, and terminal safety paths.
5. **Verify and report.** Run the named tests plus fixture success, failure,
   and safety-boundary tests when contracts, models, connectors, policies, or
   agents change. Report paths and evidence, not hidden reasoning.

An output may not skip from pre-flight to code changes. A failed gate is a
useful result: it becomes an auditable `INCONCLUSIVE` or `REJECT` path rather
than a guessed operational case.

## Evidence envelope

Pass this filled envelope above the master prompt. Do not infer omitted fields.

~~~yaml
work_item_id: "P2-reviewer-queue-contract-v1"
track: "AUTHORISATION_READINESS" # PUBLIC_BENCHMARK | AUTHORISATION_READINESS | AUTHORISED_PILOT
requested_capability: "Implement persisted fixture-only reviewer-decision contract"
current_state: "Stage 5 specialist contracts and failure-closed fixtures are implemented; no queue exists"
authority:
  authorisation_reference: "LOCAL_FIXTURE_ONLY"
  approved_source_and_channel: "Explicit synthetic fixture bundle"
  data_classification: "FIXTURE"
  permitted_operations: ["local fixture/test implementation", "local audit contract"]
  prohibited_operations: ["connector activation", "customer claim", "external action"]
evidence_references:
  - "docs/agent_prompts.md"
  - "backend/tests/test_review_specialists.py"
required_inputs: ["critic-approved fixture case", "planner role", "human decision"]
known_missing_inputs: ["authorised pilot source", "authenticated tenant", "production queue"]
target_artifacts: ["review decision schema", "local immutable audit artifact", "fixture suite"]
acceptance_evidence:
  - "approved fixture records approve, decline, or defer without external execution"
  - "missing critic approval returns INCONCLUSIVE"
  - "no external write capability is introduced"
stop_conditions:
  - "any source is not explicitly classified"
  - "a requested output would be an operational action or customer claim"
  - "test evidence cannot be produced"
~~~

`required_inputs` and `known_missing_inputs` are deliberately separate. A
missing prerequisite must not be silently repaired or replaced with a model
guess.

## Authority lanes

| Lane | Permitted work | Hard stop |
| --- | --- | --- |
| `PUBLIC_BENCHMARK` | Labelled schema adapters, snapshot provenance, demand-forecast mechanics, chronological evaluation, benchmark reports, fixtures, and safety tests. | No retailer claim, production model claim, inventory-risk case, replenishment/action draft, or connector activation. |
| `AUTHORISATION_READINESS` | Charter/authorisation templates, field mapping, disabled connector configuration, tenancy/RBAC design, local fixtures, and readiness assessments. | No access to retailer data, no credential use, no ingestion activation, and no claim that a pilot is authorised. |
| `AUTHORISED_PILOT` | Read-only, tenant-scoped implementation within the recorded approved source, scope, retention rule, and named human roles. | No provider write permissions or operational execution; incomplete identity, unit, inventory, inbound, or lead-time evidence ends the affected case as `INCONCLUSIVE`. |

An `AUTHORISED_PILOT` envelope is invalid until it contains all of the
following: retailer legal entity or tenant ID, planner owner, data owner,
security approver, authorisation reference, approved source and transfer
channel, retention/deletion rule, SKU/category scope, location IDs, operating
timezone, forecast horizon, review cadence, current planning baseline,
historical period, and a de-identified header or sample approval state.

## Required execution output

The executor returns the following headings, in order. It does not reveal
private chain-of-thought or fabricate a favourable decision.

1. `PRE_FLIGHT` — source classification, authority result, inputs present,
   inputs missing, and consulted evidence references.
2. `DECISION` — `PROCEED`, `REFINE`, or `REJECT`, with a short
   evidence-grounded reason.
3. `IMPLEMENTATION_SCOPE` — one bounded outcome, explicit non-goals, and
   whether the work remains disabled/local/benchmark-only.
4. `CHANGES` — files or artifacts to add/change and their versioned contracts.
5. `TEST_PLAN` — success, failure, and safety-boundary tests; exact commands
   to run where known.
6. `EVIDENCE_AND_LIMITATIONS` — resulting artifact references, unresolved
   assumptions, and claims that remain prohibited.
7. `NEXT_SMALLEST_ACTION` — one follow-up work item or the exact evidence that
   must be supplied before work can continue.

When the output represents a typed specialist decision, it must also contain
`status`, `evidence_refs`, `limitations`, and `next_action`, following
`docs/agent_prompts.md`.

## Stage prompt catalogue

Use these named objectives in the envelope; each is intentionally narrow.

| Remaining stage | Prompt objective | Allowed result before retailer authorisation |
| --- | --- | --- |
| Final benchmark reporting | Completed for recorded model `a4c2a81f-92f4-4e65-a3fa-289d033f796c`; preserve the immutable report and do not repeat evaluation. | Report `final-test-a4c2a81f-92f4-4e65-a3fa-289d033f796c` is public-benchmark-only and does not alter model selection. |
| Stage 5 — deterministic specialists | Completed locally: Inventory Risk, Impact Ranking, Policy Critic, and Action Drafting typed contracts plus failure-closed fixtures. | Public data cannot create a review case; missing inventory, inbound supply, lead time, unit, or scope identity returns `INCONCLUSIVE`; no external action exists. |
| Stage 5 — reviewer workflow | Completed locally: a fixture-only queue records approve, decline, or defer decisions against critic-approved fixture cases. | Cases and decisions are separate immutable records; public/retailer cases and every external action are blocked. |
| P2 — persisted specialist events | Completed locally: a synchronous fixture-only workflow records actual validation, specialist, terminal, and review-ready events. | It accepts only labelled fixtures, stores immutable events with evidence references, and never represents a production worker or customer workflow. |
| P0/Stage 6 — production foundation | Completed locally as a non-secret provisioning contract with fixture tenant-role checks, SQLite audit migration, and blocked queue/scheduler records. | No credential, connector, customer-data, or runtime activation; jobs/schedules may be recorded only as blocked fixtures, and external provisioning/security verification remain P0 work. |
| P0 — authorised pilot activation | Validate the completed pilot charter and map one approved, read-only source to canonical tables. | Not available until the authority lane is `AUTHORISED_PILOT` and all charter fields pass. |
| P2/P3 — incremental feeds and monitoring | Implement idempotent retrieval metadata, freshness/drift/error events, retrain proposals, and rollback contracts. | Fixture/local simulation only; alerts/proposals never retrain or promote automatically. |

## Current pre-filled readiness ledger

Use these facts as starting evidence, not as authorisation to expand scope:

| Topic | Current evidence | Execution consequence |
| --- | --- | --- |
| Public forecast benchmark | FreshRetailNet-50K is pinned to source revision `08c1fab7f9257bc73679d415d65d644165d351d4`; the local benchmark run is `3439b1a7-2073-4dd1-939b-2d1c91a8309c`. | The track is `PUBLIC_BENCHMARK` only. |
| Forecast lifecycle | Baseline run `3fc5c0c7-fea2-43f6-8494-dc6dfc996023`; model registry record `a4c2a81f-92f4-4e65-a3fa-289d033f796c`; immutable final-test report `final-test-a4c2a81f-92f4-4e65-a3fa-289d033f796c` records retained baseline macro MAE 0.6368571429 and RMSE 0.8062199696. | The report is benchmark-only, is evaluated once after selection, and may not change the validation-only selection. |
| Pilot authority | No named retailer, approved source/channel, or completed charter is recorded. | Production data, pilot activation, and customer-impact statements remain blocked. |
| Inventory and action evidence | No authorised current inventory, inbound supply, supplier lead-time, or compatible retailer scope is recorded. | Implemented specialist contracts must fail closed for any live-like case; only labelled fixtures can exercise a review-only draft. |
| Product implementation | Connector, snapshot, baseline, local fixed-candidate, final benchmark report, specialist contracts, synchronous fixture-only workflow, fixture-only reviewer queue, P0 non-secret foundation contract, and tenant-partitioned SQLite fixture audit adapter exist; authenticated reviewer workflow, external production provisioning, incremental feeds, and monitoring remain unfinished. | Select one catalogue objective at a time and verify its explicit boundary. |

## Quality checks for a prompt invocation

Reject or refine the invocation if any answer is “no”:

- Is exactly one roadmap objective named?
- Is the authority lane explicit and compatible with the requested capability?
- Are source/provenance and target artifacts named?
- Are unknown and missing prerequisites explicitly listed?
- Does the acceptance evidence include a safety-boundary test?
- Is every claimed metric tied to an immutable snapshot and declared time
  period?
- Does the requested output preserve a human decision point and avoid an
  external operational write?

This check makes the prompt reusable without allowing it to become a mechanism
for bypassing the product constitution.
