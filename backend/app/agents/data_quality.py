"""Deterministic Data Contract Agent for connector snapshots."""

from app.agents.contracts import AgentDecision, EvidenceFinding
from app.schemas.connector import DataContractResult, SnapshotManifest


class DataContractAgent:
    """Translate deterministic validation output into a typed agent decision."""

    name = "data_contract"

    def decide(
        self, *, run_id: str, manifest: SnapshotManifest, result: DataContractResult
    ) -> AgentDecision:
        contract_name = (
            "declared public benchmark mapping contract"
            if manifest.source_type == "PUBLIC_BENCHMARK"
            else "declared RetailOps CSV contract"
        )
        findings = (
            EvidenceFinding(
                statement=f"Snapshot was validated against the {contract_name}.",
                evidence_refs=(
                    f"snapshot:{manifest.snapshot_id}",
                    f"schema:{manifest.schema_hash}",
                    f"mapping:{manifest.mapping_version}",
                ),
            ),
        )
        return AgentDecision(
            agent=self.name,
            run_id=run_id,
            status=result.status,
            findings=findings,
            limitations=result.limitations,
            next_action=result.next_action,
        )
