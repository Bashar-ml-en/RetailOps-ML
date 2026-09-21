from fastapi.testclient import TestClient

from app.main import app


def test_system_blueprint_is_explicit_about_what_is_not_live() -> None:
    response = TestClient(app).get("/system/blueprint")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "ARCHITECTURE_BLUEPRINT"
    assert payload["live_workloads"] == "NONE"
    assert len(payload["agents"]) == 6
    assert "asynchronous or parallel specialist worker" in payload["truthful_status"]["not_running_yet"]


def test_system_blueprint_keeps_human_approval_as_a_control() -> None:
    payload = TestClient(app).get("/system/blueprint").json()

    controls = {control["title"]: control for control in payload["controls"]}
    assert controls["Human decision boundary"]["state"] == "ENFORCED_BY_POLICY"


def test_system_blueprint_labels_the_disabled_csv_gate_as_implemented() -> None:
    payload = TestClient(app).get("/system/blueprint").json()

    stages = {stage["id"]: stage for stage in payload["stages"]}
    agents = {agent["id"]: agent for agent in payload["agents"]}
    assert stages["connector"]["state"] == "IMPLEMENTED"
    assert stages["pilot-readiness"]["state"] == "IMPLEMENTED"
    assert stages["production-foundation"]["state"] == "CONTRACT_DEFINED"
    assert stages["public-benchmark"]["state"] == "IMPLEMENTED"
    assert stages["features"]["state"] == "IMPLEMENTED"
    assert stages["evaluation"]["state"] == "IMPLEMENTED"
    assert stages["model-lifecycle"]["state"] == "IMPLEMENTED"
    assert stages["review"]["state"] == "IMPLEMENTED"
    assert stages["human"]["state"] == "CONTRACT_DEFINED"
    assert agents["data-contract"]["state"] == "IMPLEMENTED"
    assert agents["forecast-evaluation"]["state"] == "IMPLEMENTED"
    assert agents["inventory-risk"]["state"] == "IMPLEMENTED"
    assert agents["impact-ranking"]["state"] == "IMPLEMENTED"
    assert agents["policy-critic"]["state"] == "IMPLEMENTED"
    assert agents["action-drafting"]["state"] == "IMPLEMENTED"
