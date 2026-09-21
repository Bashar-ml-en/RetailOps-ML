"""Connector-run orchestration stops after the real data-contract gate."""

from datetime import datetime, timezone

from app.schemas.connector import ConnectorRunRequest
from app.services.orchestrator import CsvConnectorRunner
from app.services.validation import CsvBundle


def test_rejected_run_is_audited_but_never_advances_to_forecasting(tmp_path) -> None:
    bundle = CsvBundle.from_text(
        {
            "products": "product_id,sku,name,quantity_unit\np-1,sku-1,Coffee,each\n",
            "locations": "location_id,name,type\nstore-1,Main,store\n",
            "order_lines": "order_id,sku,location_id,occurred_at,quantity,status\no-1,unknown,store-1,2026-09-13T09:00:00+00:00,1,completed\n",
            "inventory_snapshots": "snapshot_at,sku,location_id,on_hand\n2026-09-14T02:30:00+00:00,sku-1,store-1,10\n",
        }
    )
    run = CsvConnectorRunner.for_root(tmp_path).run(
        ConnectorRunRequest(
            tenant_id="tenant-a",
            authorization_reference="authorisation-record-a",
            as_of=datetime(2026, 9, 14, 3, 0, tzinfo=timezone.utc),
        ),
        bundle,
    )

    assert run.result.status == "REJECT"
    assert run.events[-1].name == "REJECTED"
    assert not any("FORECAST" in event.name for event in run.events)
