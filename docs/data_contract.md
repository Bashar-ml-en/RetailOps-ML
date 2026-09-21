# RetailOps ML Retail Connector Contract

## Purpose

This contract turns authorised retailer exports or APIs, or a visibly labelled
public benchmark adapter, into a versioned,
comparable input for demand forecasting and inventory-risk review. Missing
evidence produces a limited use case or INCONCLUSIVE, never invented values.

## Canonical entities

| Entity | Required fields | Role |
| --- | --- | --- |
| Product | product_id, sku, name, quantity_unit | Product identity and compatible unit. |
| Location | location_id, name, type | Store or warehouse identity. |
| Order line | order_id, sku, location_id, occurred_at, quantity, status | Historical demand, returns, and cancellations. |
| Inventory snapshot | snapshot_at, sku, location_id, on_hand | Available stock evidence. |
| Inbound supply | supply_id, sku, location_id, expected_at, quantity, status | Expected replenishment. |
| Supplier terms | supplier_id, sku, lead_time_days | Replenishment-risk eligibility. |

Optional fields include net sales, committed quantity, safety-stock policy,
promotion, product category, and cost. They can enrich ranking but cannot
replace a required identity, quantity, or timestamp.

## Connector validation

The Data Contract Agent records connector type, account scope, retrieval time,
snapshot ID, schema version, mapping version, source row counts, duplicate
policy, exclusions, and field-level quality results.

| Check | Stop or limitation |
| --- | --- |
| Authorisation and tenant scope | REJECT if absent or cross-tenant. |
| SKU/location/unit mapping | REJECT for unknown or incompatible identities. |
| Orders | Exclude and record cancelled/duplicate lines; INCONCLUSIVE when usable history is inadequate. |
| Inventory | INCONCLUSIVE when current stock is stale or unavailable. |
| Supply and lead time | No replenishment recommendation without declared evidence. |
| Timestamp and quantity parsing | Reject invalid records rather than coercing values. |
| Snapshot immutability | REJECT if model input cannot be reproduced. |

## Public benchmark boundary

An explicitly labelled public benchmark may use a separate mapping contract
when its published schema does not represent retailer order lines or current
inventory. Its snapshot must identify `source_type: PUBLIC_BENCHMARK`, source
URL, licence, attribution, mapping version, hash, and a fixed non-retailer
namespace. It must never be called an authorised tenant snapshot.

FreshRetailNet-50K is the implemented example. Its normalised daily sales and
stockout-status fields permit only limited benchmark forecast evaluation.
Physical on-hand, inbound-supply, lead-time, customer authorization, and
retailer timezone evidence are absent, so inventory risk, replenishment, and
production scoring remain blocked. See the
[FreshRetailNet public benchmark contract](freshretailnet_benchmark_contract.md).

## Connector-agent output

~~~json
{
  "snapshot_id": "uuid",
  "connector_type": "csv | shopify | square | other",
  "mapping_version": "v1",
  "status": "PASS | PASS_WITH_LIMITATIONS | REJECT | INCONCLUSIVE",
  "approved_uses": ["demand_forecast"],
  "blocked_uses": ["replenishment_draft"],
  "entity_counts": {"order_lines": 0, "inventory_snapshots": 0},
  "limitations": [],
  "evidence_refs": []
}
~~~
