# RetailOps ML authorised pilot charter

**Status:** BLOCKED — Phase 0 inputs are not yet supplied.
**Version:** 0.1
**Pilot decision:** REFINE — prepare the authorised source; do not ingest data or claim a model result.

## Why

The proposed pilot helps a retail planner identify SKU-location demand changes that deserve weekly review. It tests forecast evidence and review usefulness; it does not promise sales, margin, availability, or stockout improvement.

## What

**Pilot capability:** weekly demand-forecast exception review for established, repeat-purchase SKUs at a declared set of retailer locations.

**Explicit non-goals:** autonomous purchasing, replenishment instructions, inventory transfers, price changes, supplier contact, live-customer model claims, and business-impact claims.

## Required Phase 0 decisions

All values below are intentionally `UNKNOWN` until supplied by the retailer or the authorised pilot owner. Do not replace them with assumptions.

| Required field | Current value | Accountable role | Required evidence |
| --- | --- | --- | --- |
| Pilot retailer legal entity and tenant identifier | UNKNOWN | Retailer sponsor | Written pilot confirmation and tenant scope |
| Retail planner owner | UNKNOWN | Retailer sponsor | Role and approval responsibility; do not record unnecessary personal data |
| Data owner and security approver | UNKNOWN | Retailer sponsor | Authorisation to provide read-only exports |
| Category / product cohort | UNKNOWN | Planner | Category definition and included/excluded SKU list |
| SKU and location scope | UNKNOWN | Planner | Declared 20–50 established SKUs and 1–3 location IDs, or an approved alternative |
| Operating timezone | UNKNOWN | Data owner | IANA timezone, for example `Asia/Kuala_Lumpur` |
| Forecast horizon | UNKNOWN | Planner | Number of demand days and review purpose |
| Review cadence | UNKNOWN | Planner | Weekly review meeting/cut-off and case owner |
| Current planning method | UNKNOWN | Planner | Current comparison process and its baseline rule |
| Pilot evaluation window | UNKNOWN | Planner + product owner | Historical period and prospective shadow-review period |
| Impact measures | UNKNOWN | Planner + product owner | Baseline MAE/RMSE, coverage, exclusions, and planner usefulness measures |
| Authorisation reference | UNKNOWN | Data owner | Internal approval/ticket/contract reference; never credentials |
| Retention and secure transfer rule | UNKNOWN | Security approver | Approved storage, retention, and deletion requirements |

## Authorised input boundary

The first pilot uses a read-only CSV export. The current connector requires products, locations, order lines, and inventory snapshots. The demand-forecast use case relies on compatible product/location/unit identities and historical orders; inventory, inbound supply, and supplier terms do not authorise a replenishment decision in this pilot.

| Export | Minimum fields | Purpose |
| --- | --- | --- |
| Products | `product_id`, `sku`, `name`, `quantity_unit` | Product identity and unit compatibility |
| Locations | `location_id`, `name`, `type` | Location identity |
| Order lines | `order_id`, `sku`, `location_id`, `occurred_at`, `quantity`, `status` | Historical daily demand |
| Inventory snapshots | `snapshot_at`, `sku`, `location_id`, `on_hand` | Required connector evidence; no stock action is derived in this pilot |

## How the pilot will operate after approval

1. The Data Contract Agent validates and versions the authorised snapshot.
2. The Forecast Evaluation Agent evaluates the naïve baseline and the one fixed candidate on chronological validation only; the final test period remains locked until selection is complete.
3. A candidate is selected only on declared validation improvement; a tie or regression retains the naïve baseline and its rollback reference.
4. Future demand exceptions are reviewable evidence only. A planner decides whether any external action is appropriate outside RetailOps.

## Phase 0 exit gate

Proceed to Phase 1 only when every required decision above has evidence and an authorised owner. Otherwise retain `BLOCKED`, request the missing field, and do not activate a connector or ingest retailer data.

The local `PilotReadinessRunner` records this evidence as an immutable readiness artifact. A complete result is still only `PASS_WITH_LIMITATIONS`: it permits source-mapping preparation, not customer-data ingestion or model evaluation. Authenticated tenant-scoped deployment remains a separate gate.

## Exact inputs required to unlock Phase 1

1. Pilot retailer legal entity and tenant identifier.
2. Planner owner role and data/security approval roles.
3. Repeat-purchase category, SKU list, and location IDs in scope.
4. Operating timezone, forecast horizon, weekly review cadence, and current planning baseline/process.
5. Authorisation reference for a read-only CSV export.
6. Approved secure transfer, retention, and deletion rules.
7. A de-identified CSV header/sample for the four required exports; no live operational rows or credentials in chat, source control, or browser.
