"""Local authoring API. Never executes resource endpoints or trains models."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from paid_tool_rl.dataset_schema import (
    AgentObservation,
    DatasetRecord,
    WorkspaceDocument,
    agent_task_preview,
    workspace_warnings,
)
from paid_tool_rl.dataset_store import DatasetStore, WorkspaceConflictError


class WorkspaceSaveRequest(DatasetRecord):
    document: WorkspaceDocument
    revision: str = Field(pattern=r"^[0-9a-f]{64}$")


class WorkspaceEnvelope(WorkspaceSaveRequest):
    warnings: list[str]


class WorkspacePreviewRequest(DatasetRecord):
    document: WorkspaceDocument
    task_id: str


def create_dataset_app(
    dataset_path: Path = Path("datasets/workspace.json"),
    ui_directory: Path = Path("web/dist"),
) -> FastAPI:
    """Serve one local workspace and the built editor on the same origin."""
    app = FastAPI(title="Metis dataset editor")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    store = DatasetStore(dataset_path)

    @app.middleware("http")
    async def protect_local_writes(request: Request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin is not None and origin != str(request.base_url).rstrip("/"):
                return JSONResponse(
                    {"detail": "Cross-origin writes are forbidden"}, 403
                )
            if (
                request.headers.get("content-type", "").split(";")[0]
                != "application/json"
            ):
                return JSONResponse({"detail": "Use application/json"}, 415)
        return await call_next(request)

    @app.get("/api/workspace", response_model=WorkspaceEnvelope)
    def read_workspace() -> WorkspaceEnvelope:
        document, revision = store.load_workspace()
        return WorkspaceEnvelope(
            document=document,
            revision=revision,
            warnings=workspace_warnings(document),
        )

    @app.put("/api/workspace", response_model=WorkspaceEnvelope)
    def write_workspace(payload: WorkspaceSaveRequest) -> WorkspaceEnvelope:
        try:
            document, revision = store.save_workspace(
                payload.document, payload.revision
            )
        except WorkspaceConflictError as error:
            raise HTTPException(409, str(error)) from error
        return WorkspaceEnvelope(
            document=document,
            revision=revision,
            warnings=workspace_warnings(document),
        )

    @app.post("/api/validate")
    def validate_workspace(payload: WorkspaceDocument) -> dict:
        return {"valid": True, "warnings": workspace_warnings(payload)}

    @app.post("/api/agent-preview", response_model=AgentObservation)
    def preview_workspace(payload: WorkspacePreviewRequest) -> AgentObservation:
        task = next(
            (task for task in payload.document.tasks if task.id == payload.task_id),
            None,
        )
        if task is None:
            raise HTTPException(404, "Task not found")
        return agent_task_preview(payload.document, task)

    @app.get("/api/schema")
    def workspace_schema() -> dict:
        return WorkspaceEnvelope.model_json_schema()

    if ui_directory.is_dir():
        app.mount("/", StaticFiles(directory=ui_directory, html=True), name="editor")
    return app
