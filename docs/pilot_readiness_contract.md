# RetailOps ML pilot-readiness contract

## Why this gate exists

An authorised pilot cannot begin from a generic intention to share data. It needs a declared retailer tenant, planner and approval roles, a bounded cohort, a read-only source mode, and a non-secret authorisation reference before source mapping is prepared. This local gate records that preparation and fails closed when the required evidence is missing.

## What exists locally

`PilotReadinessRunner` produces a versioned, immutable local assessment from pilot metadata only. It does not accept CSV rows, credentials, secrets, or an external identity assertion. Its local filesystem record is an audit artifact, not an access grant or a production authorisation registry.

The first-pilot policy requires:

- read-only CSV as the source mode;
- 20–50 established SKUs and 1–3 locations;
- weekly review cadence;
- declared tenant, planner, data-owner, and security-approver roles;
- a non-secret authorisation reference, approved transfer/retention rule, and de-identified header/sample reference; and
- declarations for products, locations, order lines, and inventory snapshots.

## Decision rules

| Condition | Result | Allowed next action |
| --- | --- | --- |
| Write access or a non-CSV first-pilot source | `REJECT` | Correct the access boundary. |
| Missing role, authorisation, retention, header, historical-period, or required-export evidence | `INCONCLUSIVE` | Complete the pilot charter and authorisation pack. |
| Cohort or cadence outside the declared first-pilot target | `INCONCLUSIVE` | Obtain an approved cohort/cadence decision. |
| All declared readiness fields are present | `PASS_WITH_LIMITATIONS` | Prepare source mapping and authenticated tenant deployment. |

Even a `PASS_WITH_LIMITATIONS` assessment blocks `customer_data_ingestion`, `demand_forecast`, `production_scoring`, and `replenishment_draft`. The authorisation is recorded as `DECLARED_NOT_EXTERNALLY_VERIFIED`; authenticated tenant-scoped server controls remain mandatory before any retailer data is received.

## Audit fields

Each assessment records pilot/tenant identifiers, roles, source and access boundary, cohort, timezone, horizon, cadence, current baseline, declared historical period, header reference, export declarations, decision status, limitations, and next action. It intentionally excludes raw data, credentials, and unnecessary personal information.

## Relationship to later gates

Pilot readiness is preparatory only. After production authentication and security controls exist, an authorised CSV snapshot must still pass the Data Contract gate. Only then can chronological baseline/candidate evaluation begin.
