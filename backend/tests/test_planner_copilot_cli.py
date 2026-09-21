"""Failure-closed command-line coverage for the server-only Planner Copilot."""

from dataclasses import replace

from app.config import settings
from app.copilot import cli


def test_cli_fails_closed_before_a_provider_call_without_owner_configuration(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.setattr(
        cli,
        "settings",
        replace(settings, runtime_root=tmp_path / "runtime", audit_root=tmp_path / "audit"),
    )

    exit_code = cli.main(["--run-id", "unconfigured-public-run"])

    assert exit_code == 2
    assert "COPILOT_NOT_ENABLED" in capsys.readouterr().out
