"""Atomic JSON persistence with stale-tab protection for the local dataset editor."""

import hashlib
import os
import tempfile
from pathlib import Path
from threading import Lock

from paid_tool_rl.dataset_schema import WorkspaceDocument


class WorkspaceConflictError(Exception):
    """The on-disk dataset changed after the editor loaded its revision."""


class DatasetStore:
    """Read and replace one fixed authoring file, never a path supplied by clients."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = Lock()

    def load_workspace(self) -> tuple[WorkspaceDocument, str]:
        content = self.path.read_bytes()
        return WorkspaceDocument.model_validate_json(content), hashlib.sha256(
            content
        ).hexdigest()

    def save_workspace(
        self,
        document: WorkspaceDocument,
        revision: str,
    ) -> tuple[WorkspaceDocument, str]:
        with self.lock:
            _, current_revision = self.load_workspace()
            if revision != current_revision:
                raise WorkspaceConflictError(
                    "Dataset changed on disk; reload before saving"
                )
            content = (document.model_dump_json(indent=2) + "\n").encode()
            descriptor, temporary = tempfile.mkstemp(
                prefix=".workspace-",
                suffix=".json",
                dir=self.path.parent,
            )
            try:
                with os.fdopen(descriptor, "wb") as output:
                    output.write(content)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, self.path)
            finally:
                Path(temporary).unlink(missing_ok=True)
            return document, hashlib.sha256(content).hexdigest()
