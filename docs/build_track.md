# RetailOps ML Build Track

Work sequentially. A stage is complete only when its acceptance checks pass.

| Stage | Deliverable | Acceptance |
| --- | --- | --- |
| 0. Product decision | Defined buyer, workflow, four-question case, pilot metric | Prompt review returns PROCEED or a documented REFINE. |
| 1. Foundation | Constitution, connector contract, agent contracts, API/UI scaffold | No legacy domain wording; health/API and frontend build pass. |
| P0. Production-foundation contract | Non-secret resource declaration, fixture tenant-role checks, SQLite audit migration, and blocked worker/scheduler protocols | Implemented locally as a provisioning-only contract. It cannot authenticate a tenant, provision an external service, expose a customer API, execute a job, or enable customer-data ingestion. |
| 2. CSV connector | Versioned server-side CSV import, immutable local-pilot snapshot, and deterministic validation | Implemented locally and disabled by default; valid, malformed, duplicate, unknown-SKU, stale-inventory, and unauthorised-use fixtures pass. |
| 3. Demand baseline | SKU-location-unit daily demand series and chronology-safe naïve baseline | Implemented locally; future observations reject, validation MAE/RMSE are recorded, final test days stay locked, and insufficient-history fixtures are INCONCLUSIVE. |
| 4. Model lifecycle | Fixed-candidate comparison, local registry artifact, and rollback baseline | Implemented locally: the predeclared candidate cannot replace baseline without strict per-scope validation success, and final-test days remain locked. Production monitoring remains a later pilot control. |
| 4b. Public final-test report | One immutable post-selection FreshRetailNet final-test report | Implemented locally for the recorded public run: the retained baseline was evaluated once across 20 seven-day scopes without changing validation-only selection. |
| 4a. Public benchmark adapter | FreshRetailNet-50K mapping into an immutable, limited benchmark snapshot | Implemented locally: an explicit 20–50 store-product / one-to-three-store subset preserves zero-sales dates and may enter only benchmark forecast evaluation. Inventory, replenishment, production scoring, and retailer claims remain blocked. |
| 5. Risk and review | Inventory-risk cases, policy critic, reviewer queue, action drafts | Deterministic specialist contracts, a synchronous fixture-only persisted workflow, and a reviewer queue are implemented. Real local transitions end in a critic-approved non-executing queue case or terminal `REJECTED`, `INCONCLUSIVE`, or `FAILED`; the queue records approve/decline/defer events. Authenticated human identity and customer activation remain required. |
| 6. Production pilot | Read-only connector, access controls, scheduled jobs, observability | One authorised pilot measures declared metrics against baseline. |

Stages 2, 3, 4, 5, and the P0 foundation contract are implemented locally.
Before any can receive customer data, provision and security-review
authenticated tenant-scoped server access with durable audit/object storage,
then use a declared retailer operating timezone.
The Phase 0 pilot-readiness gate and authorisation templates are implemented
locally, but remain `BLOCKED` until a retailer supplies the required evidence.
Do not implement an inventory-risk recommendation before the connector contract
is accepted and an authorised baseline and candidate evaluation pass chronology
checks.
