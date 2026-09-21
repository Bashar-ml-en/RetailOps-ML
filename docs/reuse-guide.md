# Reusing RetailOps ML safely

RetailOps ML is reusable as an evidence-first foundation, not as a turnkey
production system. A fork starts in **fixture/public-benchmark mode**. It does
not become an authorised retailer deployment merely because the code runs.

## Choose the source mode first

| Source mode | What may be used | What may be claimed |
| --- | --- | --- |
| Fixture | Synthetic or labelled test data committed for contracts | Deterministic contract behaviour |
| Public benchmark | Public data documented in a benchmark contract | Benchmark forecast evaluation only |
| Authorised pilot | A tenant's approved, read-only operational scope | Declared pilot evidence, subject to review |

Keep the label in snapshots, metrics, user interfaces, demos, and reports. Do
not use public benchmark results to claim retailer impact, replenishment
quality, or production readiness.

## Adopt the foundation

1. Fork or clone the repository and run `scripts/verify` before changing it.
2. Read the [constitution](constitution.md),
   [connector contract](data_contract.md),
   [lifecycle governance](lifecycle_governance.md), and
   [specialist contracts](agent_prompts.md).
3. Build against fixtures first. Preserve explicit identity, SKU, location,
   quantity-unit, as-of, and source-version evidence.
4. Treat missing stock, inbound, lead-time, identity, or unit evidence as
   `INCONCLUSIVE`; do not infer it or create an action draft.
5. Record data snapshots, mappings, features, model configuration, metrics,
   decisions, and limitations as versioned artifacts.

## Adding an authorised connector

Only enable a connector after the retailer supplies the authorisation evidence
listed in the [pilot charter](authorised_pilot_charter.md) and
[authorisation request pack](authorisation_request_pack.md). At minimum, the
implementation needs a tenant identity, authorised source and transfer path,
read-only least-privilege access, allowed locations/categories, retention and
deletion rule, operating timezone, and named approvers.

A connector change needs fixture-backed success, failure, and safety-boundary
tests. It must reject unauthorised tenants and incompatible schemas; it must
not silently repair mappings or units. Credentials and operational data stay
server-side and out of version control.

## Changing forecasts or policies

Start from the documented baseline. Use chronological splits and
historical-only features, declare selection criteria before evaluation, and
lock a final test period before comparing candidates. A candidate may be
promoted only when it improves the declared validation criteria, while keeping
a rollback-ready champion.

The Policy Critic may veto an unsupported decision. Downstream action drafting
may only produce a non-executable human-review draft from critic-approved
evidence; it must never perform an external operation.

## Publishing and collaborating

Use [CONTRIBUTING.md](../CONTRIBUTING.md) for the review checklist and
[SECURITY.md](../SECURITY.md) for sensitive reports. Keep tests and CI green,
and update the corresponding contract whenever an implementation behaviour
changes.

This repository intentionally has no open-source licence yet. Before inviting
outside reuse or accepting external redistribution, the repository owner must
choose and add an appropriate licence.
