# RetailOps ML Architecture

This is the target production architecture. Current local code implements the
CSV/data-contract gate, a chronology-safe baseline evaluator, and a
fixed-candidate local registry gate; it has no live retailer source, authorised
candidate evaluation, parallel worker, deployed model, or production score.

~~~text
Authorised CSV / commerce / inventory connectors
                    |
                    v
      Immutable snapshot store + connector validation
                    |
                    v
  Canonical retail tables: SKU, orders, inventory, inbound supply
                    |
                    v
 Dataset and feature versions -> baseline / candidate backtests
                    |                         |
                    v                         v
          Daily demand score         Model registry and monitoring
                    |
                    v
 Inventory-risk + impact-ranking specialists
                    |
                    v
             Policy Critic
                    |
                    v
  Human review queue -> approved action draft -> outcome capture
                    |
                    v
  Drift, realised error, and controlled retraining
~~~

## Responsibilities

| Layer | Responsibility |
| --- | --- |
| Connectors | Read authorised data, record scope and retrieval metadata, and preserve raw snapshots. |
| Data contract | Map to canonical retail entities, validate identities and quantities, and record exclusions. |
| ML lifecycle | Build chronology-safe features, evaluate baselines and candidates, register champions, and monitor production performance. |
| Specialists | Interpret compact typed artifacts and stop unsafe cases. |
| API and storage | Expose runs, events, artifacts, review cases, and immutable audit records. |
| Dashboard | In production, show live gate status, evidence, model version, limitations, review queue, and outcome measurements. The current dashboard is an explicitly labelled blueprint. |

## Security and deployment boundary

Customer credentials remain server-side and are scoped to the smallest read-only
access required. A production deployment uses a job queue, durable relational
storage, object storage for snapshots and artifacts, role-based access, and
observability. A browser receives only authorised API results.
