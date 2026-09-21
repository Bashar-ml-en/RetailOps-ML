"""A truthful, synchronous first connector-run orchestrator."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from uuid import uuid4

from app.agents.data_quality import DataContractAgent
from app.schemas.connector import ConnectorRun, ConnectorRunRequest, RunEvent, RunEventName
from app.services.storage import SnapshotStore
from app.services.validation import CsvBundle, CsvConnectorValidator


class CsvConnectorRunner:
    """Run the first durable lifecycle gate for an authorised CSV bundle.

    This worker intentionally ends at the Data Contract Agent. Forecasting,
    risk scoring, and action drafting are unavailable until later gates are
    implemented and the contract has passed.
    """

    def __init__(
        self,
        store: SnapshotStore,
        validator: CsvConnectorValidator | None = None,
        agent: DataContractAgent | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.validator = validator or CsvConnectorValidator()
        self.agent = agent or DataContractAgent()
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @classmethod
    def for_root(cls, root: Path) -> "CsvConnectorRunner":
        return cls(store=SnapshotStore(root))

    def run(self, request: ConnectorRunRequest, bundle: CsvBundle) -> ConnectorRun:
        run_id = str(uuid4())
        events: list[RunEvent] = []

        def record(name: RunEventName, detail: str, *evidence_refs: str) -> None:
            events.append(
                RunEvent(
                    sequence=len(events) + 1,
                    name=name,
                    occurred_at=self.clock(),
                    detail=detail,
                    evidence_refs=tuple(evidence_refs),
                )
            )

        record("QUEUED", "Authorised CSV connector run queued.")
        record("FETCHING", "CSV files accepted for server-side validation.")
        record("VALIDATING", "Validating schema, identity, units, quantities, and freshness.")
        outcome = self.validator.validate(request, bundle)
        snapshot_path = self.store.persist_snapshot(outcome.manifest, bundle.tables)
        record(
            "SNAPSHOT_STORED",
            "Immutable connector snapshot stored.",
            f"snapshot:{outcome.manifest.snapshot_id}",
            f"snapshot_path:{snapshot_path.name}",
        )
        agent_decision = self.agent.decide(
            run_id=run_id, manifest=outcome.manifest, result=outcome.result
        )
        agent_payload = {
            "agent": agent_decision.agent,
            "status": agent_decision.status,
            "findings": [
                {"statement": finding.statement, "evidence_refs": list(finding.evidence_refs)}
                for finding in agent_decision.findings
            ],
            "limitations": list(agent_decision.limitations),
            "next_action": agent_decision.next_action,
        }
        terminal_event = {
            "PASS": "DATA_CONTRACT_PASSED",
            "PASS_WITH_LIMITATIONS": "DATA_CONTRACT_LIMITED",
            "REJECT": "REJECTED",
            "INCONCLUSIVE": "INCONCLUSIVE",
        }[outcome.result.status]
        record(
            terminal_event,
            f"Data Contract Agent returned {outcome.result.status}.",
            f"snapshot:{outcome.manifest.snapshot_id}",
        )
        run = ConnectorRun(
            run_id=run_id,
            request=request,
            manifest=outcome.manifest,
            result=outcome.result,
            agent_decision=agent_payload,
            events=tuple(events),
        )
        self.store.persist_run(run)
        return run
