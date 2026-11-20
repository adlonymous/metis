"""Episode-scoped MCP tools for the pinned Verifiers v1 state protocol."""

import asyncio
from collections.abc import Callable
from functools import wraps

import verifiers.v1 as vf

from metis.episode import MetisEpisode, MetisState
from metis.taskset import MetisTaskData


class MetisToolset(vf.Toolset[vf.ToolsetConfig, MetisState]):
    """Serialize the complete state pull/call/push cycle, including concurrent calls."""

    TOOL_PREFIX = "metis"
    data: MetisTaskData

    async def setup(self) -> None:
        self.call_lock = asyncio.Lock()

    async def setup_task(self, task: vf.TaskData) -> None:
        self.data = MetisTaskData.model_validate(task.model_dump())

    def _with_state(self, fn: Callable) -> Callable:
        # Lock outside the pinned framework's whole-state pull/push wrapper.
        synchronized = super()._with_state(fn)

        @wraps(fn)
        async def serialized(*args, **kwargs):
            async with self.call_lock:
                return await synchronized(*args, **kwargs)

        return serialized

    def _episode(self) -> MetisEpisode:
        return MetisEpisode(self.data.record, self.data.catalog, self.state)

    @vf.tool
    def search_resources(
        self,
        query: str = "",
        category: str = "",
        offset: int = 0,
        limit: int = 10,
    ) -> dict:
        """Search public metadata for free. limit is 1-20; offset pages results."""
        return self._episode().search_resources(query, category, offset, limit)

    @vf.tool
    def inspect_resource(self, resource_id: str) -> dict:
        """Read the full public listing and samples for free, not its paid task data."""
        return self._episode().inspect_resource(resource_id)

    @vf.tool
    def purchase(self, resource_id: str) -> dict:
        """Buy at the listed price. Empty matches can still be charged."""
        return self._episode().purchase(resource_id)

    @vf.tool
    def finish(self, answer: str) -> dict:
        """Submit only the requested value as a string and end the episode."""
        return self._episode().finish(answer)


if __name__ == "__main__":
    MetisToolset.run()
