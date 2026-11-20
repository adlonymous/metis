"""Verifiers v1 taskset loaded from Metis's authored workspace."""

from importlib.resources import files
from pathlib import Path
from typing import Any, Literal

import verifiers.v1 as vf
from pydantic import Field

from metis.episode import MetisState, metis_episode_metrics
from paid_tool_rl.dataset_schema import (
    DatasetTask,
    ResourceListing,
    WorkspaceDocument,
    agent_task_preview,
)

METIS_INSTRUCTIONS = """Complete the user task using synthetic paid resources.
Use metis_search_resources to discover listings and metis_inspect_resource
to read full metadata. Both are free but consume actions.
metis_purchase authorizes the listed price. no_matching_data may still be charged.
Repeat purchases of a resource are free. All money and responses are simulated.
Never request real endpoints. When ready, call metis_finish with only the requested
value as a string. You may finish without buying if you already know the answer.
Keep an action available for finishing. Tool calls execute sequentially.
"""


class MetisTaskData(vf.TaskData):
    """Evaluator-owned inputs; only prompt and public tool responses reach the model."""

    record: DatasetTask
    catalog: list[ResourceListing]


class MetisTaskConfig(vf.TaskConfig):
    tools: vf.ToolsetConfig = vf.ToolsetConfig()
    cost_weight: float = Field(0.15, ge=0, lt=1)


class MetisTask(vf.Task[MetisTaskData, MetisState, MetisTaskConfig]):
    """Reset episode state, cap interactions, and preserve the economic action trace."""

    config: MetisTaskConfig

    @classmethod
    def toolsets(cls, config: MetisTaskConfig) -> list[vf.Toolset[Any, Any]]:
        from metis.tools import MetisToolset

        return [MetisToolset(config.tools)]

    async def setup(self, trace: vf.Trace[Any, Any], runtime: vf.Runtime) -> None:
        trace.state = MetisState(
            initial_budget_units=self.data.record.budget_units,
            max_actions=self.data.record.max_actions,
        )

    @vf.stop
    def episode_finished(self, trace: vf.Trace) -> bool:
        # The pinned stop dispatcher requires the unparameterized Trace annotation.
        assert isinstance(trace.state, MetisState)
        return (
            trace.state.finished or trace.num_turns >= 2 * self.data.record.max_actions
        )

    async def finalize(
        self,
        trace: vf.Trace[Any, Any],
        runtime: vf.Runtime,
    ) -> None:
        if not trace.state.finished:
            trace.state.finished = True
            trace.state.termination_reason = "agent_stopped_without_submission"
        trace.info["metis"] = trace.state.model_dump(mode="json")

    @vf.metric
    async def economic_metrics(
        self,
        trace: vf.Trace[MetisTaskData, MetisState],
    ) -> dict[str, float]:
        return metis_episode_metrics(self.data.record, trace.state)

    @vf.reward
    async def economic_reward(
        self, trace: vf.Trace[MetisTaskData, MetisState]
    ) -> float:
        metrics = metis_episode_metrics(self.data.record, trace.state)
        return metrics["success"] - self.config.cost_weight * metrics["cost_fraction"]


class MetisConfig(vf.TasksetConfig):
    dataset: Path | None = None
    split: Literal["all", "train", "validation", "test"] = "all"
    # Specializing the documented mutable Verifiers config field needs this override.
    task: MetisTaskConfig = MetisTaskConfig()  # ty: ignore[incompatible-mutable-override]


def load_metis_workspace(path: Path | None = None) -> WorkspaceDocument:
    """Read an explicit dataset, the wheel's data, or the editable checkout's source."""
    if path is not None:
        return WorkspaceDocument.model_validate_json(path.read_bytes())
    bundled = files("metis").joinpath("data/workspace.json")
    if bundled.is_file():
        return WorkspaceDocument.model_validate_json(bundled.read_bytes())
    source = Path(__file__).resolve().parents[2] / "datasets/workspace.json"
    return WorkspaceDocument.model_validate_json(source.read_bytes())


# Verifiers' invariant TaskT bound does not accept a specialized State statically.
class MetisTaskset(vf.Taskset[MetisTask, MetisConfig]):  # ty: ignore[invalid-type-arguments]
    """Six runnable synthetic smoke cases; split labels are not benchmark guarantees."""

    def load(self) -> list[MetisTask]:
        document = load_metis_workspace(self.config.dataset)
        tasks = []
        for record in document.tasks:
            if record.status == "draft":
                continue
            if self.config.split != "all" and record.split != self.config.split:
                continue
            if not record.prompt.strip() or not record.expected_answer.strip():
                raise ValueError(
                    f"Metis task {record.id} lacks a request or expected answer"
                )
            observation = agent_task_preview(document, record)
            tasks.append(
                MetisTask(
                    MetisTaskData(
                        name=record.id,
                        prompt=observation.model_dump_json(),
                        system_prompt=METIS_INSTRUCTIONS,
                        record=record,
                        catalog=document.resources,
                    ),
                    self.config.task,
                )
            )
        if not tasks:
            raise ValueError(
                "Metis dataset has no non-draft tasks for the selected split"
            )
        return tasks
