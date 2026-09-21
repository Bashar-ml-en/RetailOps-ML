# RetailOps ML fixture tenant-audit contract

**Status:** `IMPLEMENTED` for labelled local fixtures only.
**Migration version:** `fixture-tenant-audit-v1`

## Why

The future production API and worker need a durable, tenant-partitioned record
of what was submitted and why it did not run. This local adapter proves the
repository, migration, tenant-boundary, and blocked-execution contracts without
representing a customer database or background service.

## What is implemented

`SqliteFixtureTenantAuditStore` uses SQLite only for local, metadata-only test
artifacts. Its idempotent migration creates three tables:

| Table | Contents | Boundary |
| --- | --- | --- |
| `schema_migrations` | Applied local schema versions. | No environment or credential details. |
| `tenant_audit_events` | Immutable event ID, tenant ID, timestamp, named artifact reference, limitation, and fixture label. | No raw retail rows, credentials, or hidden reasoning. |
| `fixture_durable_jobs` | Immutable fixture job ID, tenant ID, kind, evidence references, blocked state, and optional cadence reference. | No executable payload or provider operation. |

Tenant ID is an indexed query partition. `FixtureTenantAuditReader` requires a
matching labelled fixture role declaration with the `DATA_OWNER` role before it
can read a partition. That declaration is explicitly unauthenticated and is
not an API identity mechanism.

## Durable fixture job rules

A declared `INGESTION_OPERATOR` role may queue or schedule a labelled fixture
job. Submission atomically writes the job and its corresponding audit event.
The only permitted stored states are:

| State | Meaning |
| --- | --- |
| `QUEUED_BLOCKED` | Fixture job metadata is stored; no worker can claim it. |
| `SCHEDULED_BLOCKED` | Fixture schedule metadata is stored; no scheduler can dispatch it. |

`claim_next` and `dispatch_due` always fail with a terminal disabled-boundary
error. They do not invoke a connector, model, reviewer workflow, or external
operation.

## Production replacement requirements

The adapter must be replaced—not merely reconfigured—before customer data:

1. Use an authenticated tenant-aware database connection and enforce tenant
   isolation in database policy, query layer, and object-store namespace.
2. Replace fixture role declarations with verified identity-provider claims and
   least-privilege RBAC.
3. Deploy a durable worker queue and scheduler with idempotency keys, retries,
   dead-letter handling, audit events, and operational monitoring.
4. Expose read endpoints only after authentication and tenant checks are
   implemented. This repository ships no customer-facing tenant audit API.
5. Independently security-review migrations, retention, backup, recovery, and
   deletion behavior.

## Test evidence

`backend/tests/test_sqlite_tenant_audit.py` verifies idempotent migration,
tenant partitioning, immutable event IDs, atomic blocked-job/event persistence,
role and cross-tenant failures, and permanently disabled worker/scheduler
execution.
