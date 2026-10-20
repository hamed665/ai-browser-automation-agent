import asyncio
import os
import secrets
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict

from workbench.runner import run_task
from workbench.store import Store


class TaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["inspect", "screenshot"]


def create_app(directory=None, runner=run_task, origin=None):
    directory = Path(directory or os.environ.get("WORKBENCH_DATA", ".data"))
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    origin = origin or os.environ.get("WORKBENCH_BASE_URL", "http://127.0.0.1:3188")
    parsed = urlsplit(origin)
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.username
        or parsed.password
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Only a literal loopback HTTP origin is supported")
    store = Store(directory / "tasks.sqlite3")
    app = FastAPI(title="Browser task workbench")
    semaphore = asyncio.Semaphore(2)
    bearer = HTTPBearer(auto_error=False)

    def authenticated(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):  # noqa: B008 - FastAPI injection
        token = os.environ.get("WORKBENCH_API_TOKEN", "")
        if len(token) < 16:
            raise HTTPException(503, "Configure a dedicated demo token of at least 16 characters")
        if credentials is None or not secrets.compare_digest(
            credentials.credentials.encode(), token.encode()
        ):
            raise HTTPException(401, "Invalid token")

    def find(task_id):
        task = store.get(task_id)
        if task is None:
            raise HTTPException(404, "Unknown task")
        return task

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return (Path(__file__).parent / "dashboard.html").read_text()

    @app.get("/demo-fixture", response_class=HTMLResponse)
    def fixture():
        return "<title>Synthetic order desk</title><h1>Demo order 1042</h1><p>No customer data.</p>"

    @app.get("/api/tasks", dependencies=[Depends(authenticated)])
    def tasks():
        return store.list()

    @app.post("/api/tasks", dependencies=[Depends(authenticated)], status_code=201)
    def create(spec: TaskSpec):
        return store.create(spec.model_dump())

    @app.get("/api/tasks/{task_id}", dependencies=[Depends(authenticated)])
    def detail(task_id: str):
        return find(task_id)

    @app.post("/api/tasks/{task_id}/{decision}", dependencies=[Depends(authenticated)])
    async def decide(task_id: str, decision: Literal["approve", "reject", "run"]):
        task = find(task_id)
        before, after = (
            ("approved", "running")
            if decision == "run"
            else ("pending", "approved" if decision == "approve" else "rejected")
        )
        if not store.transition(task_id, before, after):
            raise HTTPException(409, "Task state changed; refresh before acting")
        if decision == "run":
            try:
                async with semaphore:
                    result = await asyncio.wait_for(runner(task, directory, origin), timeout=20)
                store.transition(task_id, "running", "succeeded", result)
            except asyncio.CancelledError:
                store.transition(task_id, "running", "failed", {"error": "ExecutionCancelled"})
                raise
            except Exception as error:  # noqa: BLE001 - record a terminal task state
                store.transition(task_id, "running", "failed", {"error": type(error).__name__})
        return find(task_id)

    @app.get("/api/tasks/{task_id}/screenshot", dependencies=[Depends(authenticated)])
    def screenshot(task_id: str):
        task = find(task_id)
        if task["state"] != "succeeded" or not (task["result"] or {}).get("screenshot"):
            raise HTTPException(404, "No screenshot")
        return FileResponse(directory / (task["id"] + ".png"), media_type="image/png")

    return app
