"""SQLite metadata/event store for local public benchmark runs."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from app.runtime.contracts import (
    PUBLIC_BENCHMARK_SOURCE_MODE,
    RuntimeEvent,
    RuntimeEventName,
    RuntimeRun,
    RuntimeStatus,
    TERMINAL_STATUSES,
    PublicBenchmarkSubmission,
)


class RuntimeStore:
    """Persist only public-run metadata and concise audit events.

    SQLite is a local development adapter. The contract intentionally avoids
    raw source rows, browser-supplied paths, customer identities, and model
    reasoning traces.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.db_path = root / "public-benchmark-runtime.sqlite3"
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS runtime_runs (
                    run_id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    source_mode TEXT NOT NULL CHECK (source_mode = 'PUBLIC_BENCHMARK'),
                    submission_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    lease_owner TEXT,
                    lease_expires_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    outcome_json TEXT
                );
                CREATE TABLE IF NOT EXISTS runtime_events (
                    run_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL,
                    PRIMARY KEY (run_id, sequence),
                    FOREIGN KEY (run_id) REFERENCES runtime_runs(run_id)
                );
                CREATE INDEX IF NOT EXISTS runtime_runs_claim_idx
                    ON runtime_runs(status, lease_expires_at, created_at);
                CREATE TABLE IF NOT EXISTS planner_briefs (
                    brief_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runtime_runs(run_id)
                );
                CREATE TABLE IF NOT EXISTS copilot_traces (
                    trace_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    provider_response_id TEXT,
                    tool_events_json TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runtime_runs(run_id)
                );
                CREATE TABLE IF NOT EXISTS copilot_budget_reservations (
                    reservation_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    month_key TEXT NOT NULL,
                    maximum_cents INTEGER NOT NULL CHECK (maximum_cents > 0),
                    state TEXT NOT NULL CHECK (state IN ('RESERVED', 'RELEASED')),
                    recorded_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runtime_runs(run_id)
                );
                CREATE INDEX IF NOT EXISTS copilot_budget_month_idx
                    ON copilot_budget_reservations(month_key, state);
                """
            )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _timestamp(value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError("persisted runtime timestamp is missing timezone")
        return parsed

    @staticmethod
    def _event(
        connection: sqlite3.Connection,
        run_id: str,
        name: RuntimeEventName,
        detail: str,
        evidence_refs: tuple[str, ...],
        occurred_at: datetime,
    ) -> None:
        sequence = int(
            connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM runtime_events WHERE run_id = ?",
                (run_id,),
            ).fetchone()[0]
        )
        connection.execute(
            """
            INSERT INTO runtime_events
                (run_id, sequence, name, occurred_at, detail, evidence_refs_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                sequence,
                name.value,
                occurred_at.isoformat(),
                detail,
                json.dumps(list(evidence_refs), separators=(",", ":")),
            ),
        )

    def enqueue(self, submission: PublicBenchmarkSubmission) -> tuple[RuntimeRun, bool]:
        """Create one durable run, or return the prior run for the same key."""

        now = self._now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM runtime_runs WHERE idempotency_key = ?",
                (submission.idempotency_key,),
            ).fetchone()
            if existing is not None:
                return self._row_to_run(existing), False
            run_id = str(uuid4())
            connection.execute(
                """
                INSERT INTO runtime_runs
                    (run_id, idempotency_key, source_mode, submission_json, status,
                     attempt_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    run_id,
                    submission.idempotency_key,
                    PUBLIC_BENCHMARK_SOURCE_MODE,
                    json.dumps(submission.to_dict(), sort_keys=True, separators=(",", ":")),
                    RuntimeStatus.QUEUED.value,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
            self._event(
                connection,
                run_id,
                RuntimeEventName.QUEUED,
                "Public benchmark run queued for a separate local worker.",
                (),
                now,
            )
            row = connection.execute("SELECT * FROM runtime_runs WHERE run_id = ?", (run_id,)).fetchone()
            assert row is not None
            return self._row_to_run(row), True

    def claim_next(self, worker_id: str, *, lease_seconds: int = 300) -> RuntimeRun | None:
        """Atomically claim one queued or expired leased run for a worker."""

        if not worker_id.strip():
            raise ValueError("worker_id is required")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        now = self._now()
        lease_expires_at = now + timedelta(seconds=lease_seconds)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM runtime_runs
                WHERE status = ?
                   OR (status = ? AND lease_expires_at IS NOT NULL AND lease_expires_at < ?)
                ORDER BY created_at, run_id
                LIMIT 1
                """,
                (RuntimeStatus.QUEUED.value, RuntimeStatus.RUNNING.value, now.isoformat()),
            ).fetchone()
            if row is None:
                return None
            requeued = row["status"] == RuntimeStatus.RUNNING.value
            connection.execute(
                """
                UPDATE runtime_runs
                SET status = ?, attempt_count = attempt_count + 1, lease_owner = ?,
                    lease_expires_at = ?, updated_at = ?
                WHERE run_id = ?
                """,
                (
                    RuntimeStatus.RUNNING.value,
                    worker_id,
                    lease_expires_at.isoformat(),
                    now.isoformat(),
                    row["run_id"],
                ),
            )
            if requeued:
                self._event(
                    connection,
                    str(row["run_id"]),
                    RuntimeEventName.REQUEUED,
                    "Expired worker lease recovered; no result was accepted from the prior worker.",
                    (),
                    now,
                )
            self._event(
                connection,
                str(row["run_id"]),
                RuntimeEventName.CLAIMED,
                f"Run claimed by local worker {worker_id}.",
                (),
                now,
            )
            claimed = connection.execute(
                "SELECT * FROM runtime_runs WHERE run_id = ?", (row["run_id"],)
            ).fetchone()
            assert claimed is not None
            return self._row_to_run(claimed)

    def record_progress(
        self,
        run_id: str,
        name: RuntimeEventName,
        detail: str,
        *evidence_refs: str,
    ) -> None:
        """Append a non-terminal event to an active run."""

        if name in {
            RuntimeEventName.REPORT_READY,
            RuntimeEventName.INCONCLUSIVE,
            RuntimeEventName.REJECTED,
            RuntimeEventName.FAILED,
        }:
            raise ValueError("terminal events must use finish")
        now = self._now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT status FROM runtime_runs WHERE run_id = ?", (run_id,)).fetchone()
            if row is None:
                raise KeyError("runtime run not found")
            if RuntimeStatus(str(row["status"])) in TERMINAL_STATUSES:
                raise ValueError("cannot append progress to a terminal run")
            self._event(connection, run_id, name, detail, tuple(evidence_refs), now)
            connection.execute(
                "UPDATE runtime_runs SET updated_at = ? WHERE run_id = ?", (now.isoformat(), run_id)
            )

    def finish(
        self,
        run_id: str,
        status: RuntimeStatus,
        event: RuntimeEventName,
        detail: str,
        outcome: dict[str, object],
        *evidence_refs: str,
    ) -> RuntimeRun:
        """Persist exactly one terminal status, concise outcome, and final event."""

        if status not in TERMINAL_STATUSES:
            raise ValueError("finish requires a terminal status")
        expected_event = RuntimeEventName(status.value)
        if event is not expected_event:
            raise ValueError("terminal status and event must agree")
        now = self._now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM runtime_runs WHERE run_id = ?", (run_id,)).fetchone()
            if row is None:
                raise KeyError("runtime run not found")
            current = RuntimeStatus(str(row["status"]))
            if current in TERMINAL_STATUSES:
                if current is status:
                    return self._row_to_run(row)
                raise ValueError("runtime run already has a different terminal status")
            connection.execute(
                """
                UPDATE runtime_runs
                SET status = ?, outcome_json = ?, lease_owner = NULL, lease_expires_at = NULL,
                    updated_at = ?
                WHERE run_id = ?
                """,
                (
                    status.value,
                    json.dumps(outcome, sort_keys=True, separators=(",", ":")),
                    now.isoformat(),
                    run_id,
                ),
            )
            self._event(connection, run_id, event, detail, tuple(evidence_refs), now)
            finished = connection.execute("SELECT * FROM runtime_runs WHERE run_id = ?", (run_id,)).fetchone()
            assert finished is not None
            return self._row_to_run(finished)

    def get_run(self, run_id: str) -> RuntimeRun | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM runtime_runs WHERE run_id = ?", (run_id,)).fetchone()
        return self._row_to_run(row) if row is not None else None

    def list_runs(self, *, limit: int = 20) -> list[RuntimeRun]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM runtime_runs ORDER BY created_at DESC, run_id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row_to_run(row) for row in rows]

    def list_events(self, run_id: str) -> list[RuntimeEvent]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM runtime_events WHERE run_id = ? ORDER BY sequence", (run_id,)
            ).fetchall()
        return [
            RuntimeEvent(
                sequence=int(row["sequence"]),
                name=RuntimeEventName(str(row["name"])),
                occurred_at=self._timestamp(str(row["occurred_at"])),
                detail=str(row["detail"]),
                evidence_refs=tuple(json.loads(str(row["evidence_refs_json"]))),
            )
            for row in rows
        ]

    def reserve_copilot_budget(
        self,
        *,
        run_id: str,
        maximum_cents: int,
        monthly_cap_cents: int,
        now: datetime | None = None,
    ) -> str | None:
        """Reserve a declared maximum spend before any provider request.

        This is an authorisation ceiling, not an attempt to infer provider
        pricing from tokens. The reservation is intentionally strict: no cap,
        no request.
        """

        if maximum_cents <= 0 or monthly_cap_cents <= 0 or maximum_cents > monthly_cap_cents:
            return None
        recorded_at = now or self._now()
        month_key = recorded_at.astimezone(timezone.utc).strftime("%Y-%m")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            exists = connection.execute(
                "SELECT 1 FROM runtime_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if exists is None:
                raise KeyError("runtime run not found")
            existing = connection.execute(
                """
                SELECT reservation_id FROM copilot_budget_reservations
                WHERE run_id = ? AND state = 'RESERVED'
                ORDER BY recorded_at DESC LIMIT 1
                """,
                (run_id,),
            ).fetchone()
            if existing is not None:
                return str(existing["reservation_id"])
            reserved = int(
                connection.execute(
                    """
                    SELECT COALESCE(SUM(maximum_cents), 0) FROM copilot_budget_reservations
                    WHERE month_key = ? AND state = 'RESERVED'
                    """,
                    (month_key,),
                ).fetchone()[0]
            )
            if reserved + maximum_cents > monthly_cap_cents:
                return None
            reservation_id = str(uuid4())
            connection.execute(
                """
                INSERT INTO copilot_budget_reservations
                    (reservation_id, run_id, month_key, maximum_cents, state, recorded_at)
                VALUES (?, ?, ?, ?, 'RESERVED', ?)
                """,
                (reservation_id, run_id, month_key, maximum_cents, recorded_at.isoformat()),
            )
            return reservation_id

    def release_copilot_budget(self, reservation_id: str) -> None:
        """Release a reservation when no provider request was sent."""

        with self._connect() as connection:
            connection.execute(
                "UPDATE copilot_budget_reservations SET state = 'RELEASED' WHERE reservation_id = ?",
                (reservation_id,),
            )

    def persist_copilot_trace(
        self,
        *,
        run_id: str,
        status: str,
        prompt_version: str,
        model_name: str,
        tool_events: tuple[dict[str, object], ...],
        evidence_refs: tuple[str, ...],
        provider_response_id: str | None = None,
    ) -> str:
        """Store a concise trace without prompts, raw data, or hidden reasoning."""

        trace_id = str(uuid4())
        now = self._now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO copilot_traces
                    (trace_id, run_id, status, prompt_version, model_name,
                     provider_response_id, tool_events_json, evidence_refs_json, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace_id,
                    run_id,
                    status,
                    prompt_version,
                    model_name,
                    provider_response_id,
                    json.dumps(list(tool_events), sort_keys=True, separators=(",", ":")),
                    json.dumps(sorted(set(evidence_refs)), separators=(",", ":")),
                    now.isoformat(),
                ),
            )
        return trace_id

    def persist_planner_brief(self, brief_id: str, run_id: str, payload: dict[str, object]) -> None:
        """Persist a critic-approved public brief exactly once."""

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO planner_briefs (brief_id, run_id, payload_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    brief_id,
                    run_id,
                    json.dumps(payload, sort_keys=True, separators=(",", ":")),
                    self._now().isoformat(),
                ),
            )

    def list_planner_briefs(self, run_id: str) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM planner_briefs WHERE run_id = ? ORDER BY created_at, brief_id",
                (run_id,),
            ).fetchall()
        return [json.loads(str(row["payload_json"])) for row in rows]

    @classmethod
    def _row_to_run(cls, row: sqlite3.Row) -> RuntimeRun:
        submission = PublicBenchmarkSubmission.from_dict(json.loads(str(row["submission_json"])))
        outcome = json.loads(str(row["outcome_json"])) if row["outcome_json"] else None
        return RuntimeRun(
            run_id=str(row["run_id"]),
            submission=submission,
            status=RuntimeStatus(str(row["status"])),
            created_at=cls._timestamp(str(row["created_at"])),
            updated_at=cls._timestamp(str(row["updated_at"])),
            attempt_count=int(row["attempt_count"]),
            outcome=outcome,
            lease_owner=str(row["lease_owner"]) if row["lease_owner"] else None,
            lease_expires_at=(
                cls._timestamp(str(row["lease_expires_at"])) if row["lease_expires_at"] else None
            ),
        )
