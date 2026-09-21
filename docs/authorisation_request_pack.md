# RetailOps ML read-only CSV authorisation request pack

## Request purpose

Request approval for a limited, read-only data export that supports a time-bounded RetailOps ML demand-forecast exception-review pilot. RetailOps will create evidence for a planner to review; it will not execute purchasing, inventory transfers, price changes, supplier contact, or any other external operational action.

## Requested access

| Item | Requested boundary |
| --- | --- |
| Source mode | Exported CSV files only for the first pilot |
| Access level | Read-only; no provider, inventory, order, price, or supplier write permission |
| Tenant scope | One named retailer legal entity and declared location/SKU cohort |
| Transfer | Retailer-approved secure channel; do not send credentials or source rows through chat, source control, or the dashboard |
| Storage | Tenant-isolated, server-side immutable snapshot and audit storage after security approval |
| Retention | Retailer security owner must declare retention, access, and deletion rules before transfer |
| User access | Named authorised pilot roles only; no browser exposure of raw source exports |

## Minimum CSV exports

Provide a de-identified header/sample first. After mapping and security approval, provide the authorised historical export through the approved transfer channel.

| Export | Required columns | Notes |
| --- | --- | --- |
| `products.csv` | `product_id`, `sku`, `name`, `quantity_unit` | Do not substitute an unapproved unit mapping. |
| `locations.csv` | `location_id`, `name`, `type` | Identify every included store/warehouse consistently. |
| `order_lines.csv` | `order_id`, `sku`, `location_id`, `occurred_at`, `quantity`, `status` | Include order status so cancelled/returned records can be handled explicitly. |
| `inventory_snapshots.csv` | `snapshot_at`, `sku`, `location_id`, `on_hand` | Required by the present connector contract; not used to automate a stock action. |

`inbound_supply.csv` and `supplier_terms.csv` are not required for this demand pilot. They do not become a reason to issue a replenishment recommendation without a separately approved inventory-risk and policy workflow.

## Authorisation confirmation

The retailer data owner and security approver should confirm each item before any operational data transfer.

- [ ] Retailer legal entity and tenant identifier are declared.
- [ ] The planner owner, data owner, and security approver roles are named.
- [ ] Read-only export authorisation and internal reference are recorded.
- [ ] Category, SKU, location, timezone, forecast horizon, and review cadence are declared.
- [ ] The supplied data is within the declared retailer tenant and cohort.
- [ ] Approved secure transfer, retention, access, and deletion rules are declared.
- [ ] A de-identified header/sample has been reviewed for mapping.
- [ ] No credentials, secrets, payment data, or unnecessary personal data are included.
- [ ] The retailer understands that the pilot creates reviewable forecast evidence, not operational instructions or guaranteed business results.

## Required reply template

```text
Retailer legal entity / tenant ID:
Pilot planner owner role:
Data owner role:
Security approver role:
Authorisation reference:
Approved source and transfer channel:
Retention and deletion rule:
Category / included SKU scope:
Included location IDs:
Operating timezone:
Forecast horizon:
Weekly review cadence:
Current planning baseline/process:
Historical period available:
Approved de-identified header/sample attached: YES / NO
```

## Data-contract outcome

The Data Contract Agent will return `PASS`, `PASS_WITH_LIMITATIONS`, `REJECT`, or `INCONCLUSIVE`. Missing authorisation, cross-tenant scope, incompatible identity/unit mappings, invalid timestamps/quantities, or unreproducible snapshots stop the run. Exclusions are recorded; source records are never silently repaired.

Before that stage, the local Pilot Readiness gate records whether this request has the required non-secret charter and source declarations. Its result is not external verification of authorisation and never enables CSV ingestion.
