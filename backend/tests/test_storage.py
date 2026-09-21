"""Tests for immutable local-pilot snapshot and run storage."""

import json
from datetime import datetime, timezone

from app.schemas.connector import ConnectorRunRequest
from app.services.orchestrator import CsvConnectorRunner
from app.services.validation import CsvBundle


def bundle() -> CsvBundle:
    return CsvBundle.from_text(
        {
            "products": "product_id,sku,name,quantity_unit\np-1,sku-1,Coffee,each\n",
            "locations": "location_id,name,type\nstore-1,Main,store\n",
            "order_lines": "order_id,sku,location_id,occurred_at,quantity,status\no-1,sku-1,store-1,2026-09-13T09:00:00+00:00,1,completed\n",
            "inventory_snapshots": "snapshot_at,sku,location_id,on_hand\n2026-09-14T02:30:00+00:00,sku-1,store-1,10\n",
        }
    )


def test_runner_persists_raw_snapshot_manifest_and_event_audit(tmp_path) -> None:
    runner = CsvConnectorRunner.for_root(tmp_path)
    run = runner.run(
        ConnectorRunRequest(
            tenant_id="tenant-a",
            authorization_reference="authorisation-record-a",
            as_of=datetime(2026, 9, 14, 3, 0, tzinfo=timezone.utc),
        ),
        bundle(),
    )

    snapshot_path = tmp_path / "snapshots" / run.manifest.snapshot_id
    assert (snapshot_path / "products.csv").read_bytes() == bundle().tables["products"]
    manifest = json.loads((snapshot_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_hash"] == run.manifest.source_hash

    persisted_run = json.loads((tmp_path / "runs" / f"{run.run_id}.json").read_text(encoding="utf-8"))
    assert [event["name"] for event in persisted_run["events"]] == [
        "QUEUED",
        "FETCHING",
        "VALIDATING",
        "SNAPSHOT_STORED",
        "DATA_CONTRACT_LIMITED",
    ]
    assert persisted_run["agent_decision"]["agent"] == "data_contract"
