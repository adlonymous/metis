"""Local editor API checks use temporary files and never mutate the starter dataset."""

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from paid_tool_rl.dataset_schema import WorkspaceDocument, workspace_warnings
from paid_tool_rl.dataset_server import create_dataset_app


@pytest.fixture
def editor_client(tmp_path):
    dataset_path = tmp_path / "workspace.json"
    shutil.copyfile("datasets/workspace.json", dataset_path)
    ui_directory = tmp_path / "ui"
    ui_directory.mkdir()
    (ui_directory / "index.html").write_text("<html>Metis editor</html>")
    app = create_dataset_app(dataset_path, ui_directory)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        yield client, dataset_path


def test_starter_dataset_is_valid_and_explicitly_synthetic():
    document = WorkspaceDocument.model_validate_json(
        Path("datasets/workspace.json").read_bytes()
    )
    assert document.provenance == "synthetic"
    assert len(document.resources) == 1000
    assert len(document.tasks) == 6
    assert workspace_warnings(document) == []
    assert all(
        resource.hostname.endswith(".example") for resource in document.resources
    )
    assert any(len(task.reference_purchases) > 1 for task in document.tasks)


def test_editor_serves_ui_and_schema(editor_client):
    client, _ = editor_client
    assert "Metis editor" in client.get("/").text
    schema = client.get("/api/schema").json()
    assert "ResourceListing" in schema["$defs"]
    assert "DatasetTask" in schema["$defs"]


def test_edits_persist_across_app_restart(editor_client):
    client, path = editor_client
    original = client.get("/api/workspace").json()
    original["document"]["resources"][0]["name"] = "Edited resource"
    original["document"]["tasks"][0]["prompt"] = "Edited task request"
    response = client.put(
        "/api/workspace",
        json={"document": original["document"], "revision": original["revision"]},
    )
    assert response.status_code == 200
    assert response.json()["revision"] != original["revision"]
    restarted = TestClient(create_dataset_app(path), base_url="http://127.0.0.1")
    document = restarted.get("/api/workspace").json()["document"]
    assert document["resources"][0]["name"] == "Edited resource"
    assert document["tasks"][0]["prompt"] == "Edited task request"
    assert not list(path.parent.glob(".workspace-*"))


@pytest.mark.parametrize(
    "invalid_edit",
    [
        "negative_price",
        "broken_link",
        "bad_latency",
        "missing_response",
        "duplicate_id",
        "country_shares",
    ],
)
def test_invalid_edits_never_overwrite_the_file(editor_client, invalid_edit):
    client, path = editor_client
    envelope = client.get("/api/workspace").json()
    before = path.read_bytes()
    document = envelope["document"]
    if invalid_edit == "negative_price":
        document["resources"][0]["price_units"] = -1
    elif invalid_edit == "broken_link":
        document["tasks"][0]["resource_ids"].append("missing")
        document["tasks"][0]["resource_responses"]["missing"] = {}
    elif invalid_edit == "bad_latency":
        document["resources"][0]["latency_p90_ms"] = 0
    elif invalid_edit == "missing_response":
        document["tasks"][0]["resource_responses"] = {}
    elif invalid_edit == "duplicate_id":
        document["resources"][1]["id"] = document["resources"][0]["id"]
    else:
        document["resources"][0]["top_countries"][0]["share"] = 1
    response = client.put(
        "/api/workspace",
        json={"document": document, "revision": envelope["revision"]},
    )
    assert response.status_code == 422
    assert path.read_bytes() == before


def test_stale_tabs_cannot_overwrite_saved_changes(editor_client):
    client, path = editor_client
    envelope = client.get("/api/workspace").json()
    payload = {"document": envelope["document"], "revision": envelope["revision"]}
    payload["document"]["name"] = "First edit"
    assert client.put("/api/workspace", json=payload).status_code == 200
    before = path.read_bytes()
    payload["document"]["name"] = "Stale edit"
    assert client.put("/api/workspace", json=payload).status_code == 409
    assert path.read_bytes() == before


def test_cross_origin_and_non_json_writes_are_rejected(editor_client):
    client, _ = editor_client
    envelope = client.get("/api/workspace").json()
    assert (
        client.post(
            "/api/validate",
            json=envelope["document"],
            headers={"origin": "https://unrelated.example"},
        ).status_code
        == 403
    )
    assert client.post("/api/validate", content="{}").status_code == 415
    assert (
        client.get("/api/workspace", headers={"host": "unrelated.example"}).status_code
        == 400
    )


def test_preview_excludes_evaluator_fields(editor_client):
    client, _ = editor_client
    document = client.get("/api/workspace").json()["document"]
    task = document["tasks"][0]
    response = client.post(
        "/api/agent-preview",
        json={"document": document, "task_id": task["id"]},
    )
    assert response.status_code == 200
    preview = response.json()
    assert set(preview) == {"task", "directory", "budget_units", "max_actions"}
    assert preview["directory"]["resource_count"] == 1000
    assert len(preview["directory"]["categories"]) == 50
    assert "resource_ids" not in json.dumps(preview)
    assert task["expected_answer"] not in json.dumps(preview)
    assert "reference_purchases" not in json.dumps(preview)
    assert "resource_responses" not in json.dumps(preview)
    assert "grading_notes" not in json.dumps(preview)


def test_validation_warns_about_reference_path_cost(editor_client):
    client, _ = editor_client
    document = client.get("/api/workspace").json()["document"]
    document["tasks"][0]["budget_units"] = 0
    result = client.post("/api/validate", json=document)
    assert result.status_code == 200
    assert any("exceeds the budget" in warning for warning in result.json()["warnings"])


def test_ready_tasks_need_nonempty_public_and_private_content():
    document = json.loads(Path("datasets/workspace.json").read_text())
    document["tasks"][0]["status"] = "ready"
    document["tasks"][0]["expected_answer"] = ""
    with pytest.raises(ValidationError, match="Ready tasks need"):
        WorkspaceDocument.model_validate(document)
