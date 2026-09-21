# RetailOps ML Agent Contracts

Specialists receive named, typed artifacts and return concise evidence. They do
not use hidden reasoning, browse customer systems directly, or write to a
customer system.

## Shared decision contract

~~~json
{
  "agent": "data_contract | forecast_evaluation | inventory_risk | impact_ranking | policy_critic | action_drafting",
  "run_id": "uuid",
  "status": "PASS | PASS_WITH_LIMITATIONS | REJECT | INCONCLUSIVE",
  "findings": [{"statement": "concise evidence-bound finding", "evidence_refs": ["artifact.field"]}],
  "limitations": [],
  "next_action": "named gate or stop"
}
~~~

## Specialist responsibilities

| Agent | Allowed inputs | Must stop when |
| --- | --- | --- |
| Data Contract | Connector metadata, mapping, validation, snapshot summary | Identity, unit, scope, or data provenance is unknown. |
| Forecast Evaluation | Approved demand series, recorded baseline, fixed candidate configuration, and chronological metrics | A baseline is absent, a split leaks future data, a snapshot/scope does not match, or metrics are ineligible. |
| Inventory Risk | Forecast artifact, current inventory, inbound supply, lead-time policy | Inventory is stale, a required unit is incompatible, or lead-time evidence is missing. |
| Impact Ranking | Qualified risk cases and declared ranking assumptions | It would turn an estimate into a revenue or profit guarantee. |
| Policy Critic | All prior decisions and draft claims/actions | Any unsupported claim, unsafe action, missing evidence, or policy breach exists. |
| Action Drafting | Critic-approved case and human-review template | Critic status is not PASS or PASS_WITH_LIMITATIONS. |

## Implemented Stage 5 local contract boundary

The deterministic Inventory Risk, Impact Ranking, Policy Critic, and Action
Drafting contracts are implemented with labelled fixtures only. A synchronous,
fixture-only local workflow persists its actual typed transitions before placing
a critic-approved case on the local reviewer queue. The queue persists
append-only approve, decline, or defer decisions; no shared worker,
authenticated reviewer identity, customer-facing operation, or external
execution exists.

- Inventory Risk requires accepted data-contract/forecast evidence, compatible
  scope identity/unit, current on-hand inventory, complete inbound-supply
  coverage, and declared positive lead time. Missing or stale evidence returns
  `INCONCLUSIVE`; an observation after its score timestamp returns `REJECT`.
- Public benchmark input returns `INCONCLUSIVE` for inventory risk and impact
  ranking, and is blocked from action drafting.
- Impact Ranking orders only qualified cases by declared shortfall then lower
  coverage. It does not calculate revenue, profit, or availability impact.
- Policy Critic rejects an external operational request and is the only gate
  that can approve a human-review draft.
- Action Drafting creates a non-executable planner-review message only. Its
  `external_execution_permitted` field is always `false`.
- The local queue accepts only `FIXTURE` cases with a critic-approved draft.
  A planner role can defer a case and later approve or decline it; terminal
  approval/decline decisions cannot be overwritten. Every case and decision is
  a separate immutable audit artifact, and approval never invokes an operation.
- The local workflow records only actual transitions: `QUEUED`, `VALIDATING`,
  upstream evidence checks, each deterministic specialist decision, and either
  `REVIEW_READY` or a terminal `REJECTED`, `INCONCLUSIVE`, or `FAILED` event.
  It rejects non-fixture input before invoking a specialist and never creates a
  review case after a terminal event.

## P0 production-foundation boundary

The local production-foundation contract records only non-secret references for
identity, secret, audit, object-storage, worker, scheduler, and role-based
access capabilities. Its tenant-role check is a labelled fixture shape with
`authenticated: false`; it cannot authenticate a user. Its worker and scheduler
adapters reject every job. A complete declaration is only
`PASS_WITH_LIMITATIONS` for external provisioning planning and always blocks
customer-data ingestion, connector activation, worker execution, and external
operations.

## Optional language-model use

An LLM may turn a critic-approved artifact into a concise reviewer explanation.
It must receive labelled, bounded context and a fixed output schema. It may not
compute metrics, map columns autonomously, access connectors, or issue a
purchase or transfer action.
