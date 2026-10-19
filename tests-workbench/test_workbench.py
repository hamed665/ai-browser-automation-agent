import asyncio
import re

import pytest
from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.approval import authorize_action, redact
from workbench.store import Store


def test_approval_default_denies():
    assert not asyncio.run(authorize_action("click_element", {"index": 1}, None))
    assert not asyncio.run(authorize_action("mcp.transfer", {}, lambda *args: {"response": "yes"}))
    assert asyncio.run(authorize_action("done", {}, None))


def test_approval_exact_nonce_and_redaction():
    replies = []

    async def confirm(prompt, browser):
        assert "sensitive@example.test" not in prompt
        replies.append("APPROVE " + re.search(r"APPROVE ([a-f0-9]{64})", prompt)[1])
        return {"response": replies[0]}

    assert asyncio.run(authorize_action("input_text", {"text": "sensitive@example.test"}, confirm))
    assert not asyncio.run(
        authorize_action("input_text", {"text": "sensitive@example.test"}, confirm)
    )
    assert redact({"url": "https://u:p@example.test/path?token=hidden#secret"}) == {
        "url": "https://example.test/path"
    }


def test_store_atomic_state(tmp_path):
    store = Store(tmp_path / "tasks.db")
    task = store.create({"action": "inspect"})
    assert store.transition(task["id"], "pending", "approved")
    assert not store.transition(task["id"], "pending", "approved")
    assert store.get(task["id"])["spec"] == task["spec"]
    assert len(store.get(task["id"])["events"]) == 2
    with pytest.raises(ValueError):
        store.transition(task["id"], "approved", "succeeded")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKBENCH_API_TOKEN", "synthetic-test-token-123")

    async def runner(task, directory, origin):
        return {"title": "Synthetic result"}

    with TestClient(create_app(tmp_path, runner)) as client:
        yield client


HEADERS = {"Authorization": "Bearer synthetic-test-token-123"}


def test_auth_and_input(client, monkeypatch):
    assert client.get("/api/tasks").status_code == 401
    assert (
        client.post(
            "/api/tasks", headers=HEADERS, json={"action": "inspect", "url": "https://example.test"}
        ).status_code
        == 422
    )
    assert client.post("/api/tasks", headers=HEADERS, json={"action": "send"}).status_code == 422
    monkeypatch.delenv("WORKBENCH_API_TOKEN")
    assert client.get("/api/tasks", headers=HEADERS).status_code == 503


def test_lifecycle_single_use(client):
    task = client.post("/api/tasks", headers=HEADERS, json={"action": "inspect"}).json()
    path = "/api/tasks/" + task["id"]
    assert client.post(path + "/run", headers=HEADERS).status_code == 409
    assert client.post(path + "/approve", headers=HEADERS).status_code == 200
    result = client.post(path + "/run", headers=HEADERS).json()
    assert result["state"] == "succeeded"
    assert [e["state"] for e in result["events"]] == ["pending", "approved", "running", "succeeded"]
    assert client.post(path + "/run", headers=HEADERS).status_code == 409
    assert client.get(path + "/screenshot", headers=HEADERS).status_code == 404


def test_rejection_terminal(client):
    task = client.post("/api/tasks", headers=HEADERS, json={"action": "screenshot"}).json()
    path = "/api/tasks/" + task["id"]
    assert client.post(path + "/reject", headers=HEADERS).json()["state"] == "rejected"
    assert client.post(path + "/approve", headers=HEADERS).status_code == 409


def test_failure_logged(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKBENCH_API_TOKEN", "synthetic-test-token-123")

    async def broken(*args):
        raise RuntimeError("Do not disclose this private message")

    with TestClient(create_app(tmp_path, broken)) as client:
        task = client.post("/api/tasks", headers=HEADERS, json={"action": "inspect"}).json()
        path = "/api/tasks/" + task["id"]
        client.post(path + "/approve", headers=HEADERS)
        result = client.post(path + "/run", headers=HEADERS).json()
        assert result["state"] == "failed"
        assert result["result"] == {"error": "RuntimeError"}


def test_remote_origin_rejected(tmp_path):
    with pytest.raises(ValueError):
        create_app(tmp_path, origin="https://external.test")


def test_actual_controller_dispatch_gate():
    """Execute the real act method with SDK boundaries replaced, not a duplicate implementation."""
    import ast
    import logging
    from pathlib import Path
    from types import SimpleNamespace

    tree = ast.parse(Path("src/controller/custom_controller.py").read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "CustomController")
    method = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "act")
    method.decorator_list = []
    method.returns = None
    for arg in method.args.args:
        arg.annotation = None
    calls = []

    class Result:
        def __init__(self, **values):
            self.__dict__.update(values)

    async def execute(*args, **kwargs):
        calls.append(args)
        return Result(extracted_content="ok")

    module = ast.Module(body=[method], type_ignores=[])
    ast.fix_missing_locations(module)
    scope = {
        "authorize_action": authorize_action,
        "ActionResult": Result,
        "logger": logging.getLogger(__name__),
    }
    exec(compile(module, "actual_controller.act", "exec"), scope)  # noqa: S102 - trusted source AST
    controller = SimpleNamespace(
        ask_assistant_callback=None,
        registry=SimpleNamespace(execute_action=execute, registry=SimpleNamespace(actions={})),
    )
    action = SimpleNamespace(model_dump=lambda **kwargs: {"click_element": {"index": 1}})
    denied = asyncio.run(scope["act"](controller, action))
    assert "denied" in denied.error
    assert not calls
    mcp_action = SimpleNamespace(model_dump=lambda **kwargs: {"mcp.transfer": {}})
    assert "denied" in asyncio.run(scope["act"](controller, mcp_action)).error

    async def confirm(prompt, browser):
        return {"response": "APPROVE " + re.search(r"APPROVE ([a-f0-9]{64})", prompt)[1]}

    controller.ask_assistant_callback = confirm
    assert asyncio.run(scope["act"](controller, action)).extracted_content == "ok"
    assert len(calls) == 1
