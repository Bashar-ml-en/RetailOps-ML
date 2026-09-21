# RetailOps ML production-foundation contract

**Status:** `CONTRACT_DEFINED` — local, non-secret, fixture-only preparation.
**Version:** `production-foundation-v1`

## Why

Customer data must not enter a filesystem adapter, an unauthenticated API, or
an unscoped background job. Before any authorised source is activated,
RetailOps needs explicit tenant isolation, identity, audit, storage, worker,
scheduler, and role boundaries.

## What is implemented locally

`ProductionFoundationRunner` validates and immutably records a declaration of
the seven required resource contracts. It validates fixture role and tenant
scope shapes. A local SQLite migration adapter now persists tenant-partitioned,
metadata-only fixture audit events and blocked job/schedule records. It is not
a cloud provisioning system, an identity provider, an authenticated API, or a
production deployment.

| Required resource | Contract purpose | Local status |
| --- | --- | --- |
| Identity provider | Verify a principal and bind it to a tenant. | Reference only; no identity adapter exists. |
| Secret store | Hold provider credentials outside source control, browser, and audit records. | Reference only; a secret value must never be submitted. |
| Relational audit store | Tenant-scoped runs, decisions, reviewer outcomes, and release records. | SQLite fixture migration and metadata-only partition adapter; not a production database. |
| Immutable object store | Versioned source snapshots and artifact payloads. | Reference only. |
| Worker queue | Tenant-scoped asynchronous execution after durable submission. | Fixture jobs can be persisted with an atomic audit event, but no worker can claim or execute one. |
| Scheduler | Tenant/timezone-scoped schedules with an auditable cadence. | Fixture schedules can be persisted with an atomic audit event, but no scheduler can dispatch one. |
| Role-based access | Enforce least privilege for planner, data owner, security approver, operator, and worker roles. | Fixture shape validation only; it is not authentication. |

## Foundation declaration rules

A declaration contains only non-secret identifiers and resource contract
versions. It must name the tenant-isolation strategy and the required roles.
Duplicate resources or roles are rejected. Credential-like values are rejected
before any local audit artifact is written.

The resulting status has a narrow meaning:

| Condition | Status | Allowed result |
| --- | --- | --- |
| A resource or required role is missing | `INCONCLUSIVE` | Complete the non-secret declaration. |
| The request asks to activate a runtime, ingest customer data, or run a worker | `REJECT` | Keep activation disabled. |
| Every declaration field is present | `PASS_WITH_LIMITATIONS` | Create a provisioning plan only. |

Every result blocks customer-data ingestion, connector activation, production
worker execution, production model evaluation, authenticated reviewer
decisions, and external operations. A complete local declaration does not
verify external resources or grant a production authorisation.

## Tenant and worker boundary

`FixtureTenantRoleDeclaration` can verify that a labelled fixture has the
declared tenant ID and role. It carries `authenticated: false` by construction
and may never be treated as a browser session, token, or identity assertion.

`DisabledTenantScopedWorkerQueue` and `DisabledTenantScopedScheduler` reject
every direct job. The SQLite fixture queue and scheduler may persist labelled
fixture metadata plus a corresponding atomic audit event, but their claim and
dispatch methods always reject execution. A future production implementation
must replace both paths with adapters that authenticate the principal, enforce
a tenant namespace at storage and query boundaries, record
submission/attempt/result events, and pass only named artifact references to
workers. See [fixture tenant-audit contract](fixture_tenant_audit_contract.md).

## Activation gate

Production activation remains blocked until all of the following are supplied
and independently verified outside this local contract:

1. A named authorised retailer/tenant and complete pilot charter.
2. Chosen and provisioned identity, secret, relational audit, immutable object,
   worker, scheduler, and RBAC services.
3. An authenticated tenant-aware API and worker implementation, with security
   review and durable migrations.
4. An authorised read-only source that passes the Data Contract gate.
5. A tenant-scoped human reviewer path. It must never execute a purchase,
   transfer, price, or supplier action.

## Test evidence

`backend/tests/test_production_foundations.py` covers a complete declaration,
missing resources/roles, activation requests, cross-tenant/missing-role fixture
checks, disabled worker/scheduler behavior, and the hard-disabled connector
runtime posture. `backend/tests/test_sqlite_tenant_audit.py` covers the local
migration, partitioned audit store, atomic blocked-job records, and blocked
dispatch behavior.
