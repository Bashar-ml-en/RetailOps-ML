"""Server-only command for generating one bounded public planner brief.

This command is deliberately separate from the browser and API operator route:
it reads the server process configuration and never accepts credentials, source
paths, prompts, or raw evidence on the command line.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from app.config import settings
from app.copilot.client import CopilotUnavailable, OpenAIResponsesPlannerCopilot
from app.copilot.evidence import PublicBenchmarkEvidenceGateway
from app.runtime.store import RuntimeStore


def main(argv: Sequence[str] | None = None) -> int:
    """Generate one critic-gated brief from an already persisted public run."""

    parser = argparse.ArgumentParser(
        description="Generate one bounded RetailOps public planner brief from persisted evidence."
    )
    parser.add_argument("--run-id", required=True, help="Completed public benchmark run identifier.")
    arguments = parser.parse_args(argv)

    runtime_store = RuntimeStore(settings.runtime_root)
    copilot = OpenAIResponsesPlannerCopilot(
        runtime_store=runtime_store,
        gateway=PublicBenchmarkEvidenceGateway(runtime_store, audit_root=settings.audit_root),
        config=settings,
    )
    try:
        result = copilot.create_brief(arguments.run_id)
    except CopilotUnavailable as error:
        print(f"Planner Copilot unavailable: {error}")
        return 2

    brief_id = None
    if result.payload is not None:
        payload_brief_id = result.payload.get("planner_brief_id")
        brief_id = payload_brief_id if isinstance(payload_brief_id, str) else None
    fields = [arguments.run_id, result.status, result.trace_id]
    if brief_id is not None:
        fields.append(brief_id)
    print(" ".join(fields))
    return 0 if result.status in {"PASS", "PASS_WITH_LIMITATIONS"} else 1


if __name__ == "__main__":  # pragma: no cover - command-line entry point
    raise SystemExit(main())
