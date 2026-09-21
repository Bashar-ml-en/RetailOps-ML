"""Deterministic Inventory Risk Agent with explicit evidence and freshness gates."""

from datetime import timedelta

from app.agents.contracts import AgentDecision, EvidenceFinding
from app.schemas.review import InventoryRiskDecision, InventoryRiskRequest


class InventoryRiskAgent:
    """Qualify a review case only when inventory, supply, lead time, and forecast evidence are complete."""

    name = "inventory_risk"

    def decide(self, request: InventoryRiskRequest) -> InventoryRiskDecision:
        evidence_refs = (
            f"snapshot:{request.scope.snapshot_id}",
            f"forecast_model:{request.forecast.model_run_id}",
            f"scope:{request.scope.scope_ref}",
        )
        if request.data_classification == "PUBLIC_BENCHMARK":
            return self._decision(
                request,
                status="INCONCLUSIVE",
                limitations=("PUBLIC_BENCHMARK_INVENTORY_RISK_BLOCKED",),
                next_action="use_authorised_inventory_snapshot",
                statement="Public benchmark sales and stockout annotations are not current on-hand inventory evidence.",
                evidence_refs=evidence_refs,
            )
        if request.data_contract_status not in {"PASS", "PASS_WITH_LIMITATIONS"} or request.forecast_evaluation_status not in {"PASS", "PASS_WITH_LIMITATIONS"}:
            return self._decision(
                request,
                status="INCONCLUSIVE",
                limitations=("UPSTREAM_FORECAST_OR_DATA_CONTRACT_NOT_ACCEPTED",),
                next_action="supply_accepted_snapshot_and_forecast",
                statement="Inventory risk requires accepted data-contract and forecast-evaluation evidence.",
                evidence_refs=evidence_refs,
            )
        if request.on_hand_quantity is None or request.inventory_observed_at is None:
            return self._decision(
                request,
                status="INCONCLUSIVE",
                limitations=("MISSING_CURRENT_INVENTORY",),
                next_action="supply_current_inventory_snapshot",
                statement="No inventory-risk case can be qualified without a current on-hand inventory snapshot.",
                evidence_refs=evidence_refs,
            )
        if request.inventory_observed_at > request.as_of:
            return self._decision(
                request,
                status="REJECT",
                limitations=("INVENTORY_OBSERVATION_AFTER_AS_OF",),
                next_action="correct_inventory_timestamp",
                statement="Inventory evidence later than the score timestamp is not eligible for this case.",
                evidence_refs=evidence_refs,
            )
        if request.as_of - request.inventory_observed_at > timedelta(hours=request.max_inventory_age_hours):
            return self._decision(
                request,
                status="INCONCLUSIVE",
                limitations=("STALE_INVENTORY",),
                next_action="refresh_inventory_snapshot",
                statement="The on-hand inventory snapshot is older than the declared freshness limit.",
                evidence_refs=evidence_refs,
            )
        if request.lead_time_days is None:
            return self._decision(
                request,
                status="INCONCLUSIVE",
                limitations=("MISSING_LEAD_TIME",),
                next_action="supply_declared_lead_time",
                statement="Lead-time evidence is required before a stock-risk case can be qualified.",
                evidence_refs=evidence_refs,
            )
        if request.lead_time_days <= 0:
            return self._decision(
                request,
                status="REJECT",
                limitations=("INVALID_LEAD_TIME",),
                next_action="correct_lead_time",
                statement="Lead time must be a positive declared number of days.",
                evidence_refs=evidence_refs,
            )
        if not request.inbound_supply_complete:
            return self._decision(
                request,
                status="INCONCLUSIVE",
                limitations=("INBOUND_SUPPLY_COVERAGE_UNKNOWN",),
                next_action="supply_inbound_supply_coverage",
                statement="An empty or partial inbound feed cannot be assumed to mean no inbound supply.",
                evidence_refs=evidence_refs,
            )

        daily_rate = request.forecast.forecast_quantity / request.forecast.horizon_days
        lead_time_demand = daily_rate * request.lead_time_days
        cutoff = request.as_of + timedelta(days=request.lead_time_days)
        confirmed_supply = sum(
            item.quantity
            for item in request.inbound_supply
            if item.confirmed and item.expected_at <= cutoff
        )
        available = request.on_hand_quantity + confirmed_supply
        shortfall = max(lead_time_demand - available, 0.0)
        coverage_days = None if daily_rate == 0 else request.on_hand_quantity / daily_rate
        qualified = shortfall > 0
        fixture_limited = request.data_classification == "FIXTURE"
        status = "PASS_WITH_LIMITATIONS" if fixture_limited else "PASS"
        limitations = ("FIXTURE_ONLY_NOT_OPERATIONAL",) if fixture_limited else ()
        return InventoryRiskDecision(
            agent_decision=AgentDecision(
                agent=self.name,
                run_id=request.run_id,
                status=status,
                findings=(
                    EvidenceFinding(
                        statement=(
                            "Declared forecast, current inventory, confirmed inbound supply, and lead time "
                            "were evaluated deterministically for a human-review eligibility decision."
                        ),
                        evidence_refs=evidence_refs,
                    ),
                ),
                limitations=limitations,
                next_action="rank_qualified_risk_case" if qualified else "no_inventory_risk_case",
            ),
            data_classification=request.data_classification,
            scope=request.scope,
            risk_case_qualified=qualified,
            forecast_daily_rate=daily_rate,
            demand_during_lead_time=lead_time_demand,
            confirmed_supply_during_lead_time=confirmed_supply,
            shortfall_quantity=shortfall,
            coverage_days=coverage_days,
        )

    def _decision(
        self,
        request: InventoryRiskRequest,
        *,
        status: str,
        limitations: tuple[str, ...],
        next_action: str,
        statement: str,
        evidence_refs: tuple[str, ...],
    ) -> InventoryRiskDecision:
        return InventoryRiskDecision(
            agent_decision=AgentDecision(
                agent=self.name,
                run_id=request.run_id,
                status=status,  # type: ignore[arg-type]
                findings=(EvidenceFinding(statement=statement, evidence_refs=evidence_refs),),
                limitations=limitations,
                next_action=next_action,
            ),
            data_classification=request.data_classification,
            scope=request.scope,
        )
