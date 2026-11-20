"""Verifiers v1 taskset for budget-constrained synthetic data selection."""

from typing import Any

import verifiers.v1 as vf
from pydantic import Field

from paid_tool_rl.purchase_simulator import (
    PurchaseScenario,
    PurchaseState,
    generate_purchase_scenario,
    purchase_task_metrics,
)
from paid_tool_rl.purchase_tools import PurchaseToolset


class PurchaseTaskConfig(vf.TaskConfig):
    tools: vf.ToolsetConfig = vf.ToolsetConfig()


class PurchaseTask(vf.Task[PurchaseScenario, PurchaseState, PurchaseTaskConfig]):
    """Initialize the ledger per rollout and score evaluator-owned ground truth."""

    @classmethod
    def toolsets(cls, config: PurchaseTaskConfig) -> list[vf.Toolset[Any, Any]]:
        return [PurchaseToolset(config.tools)]

    async def setup(
        self,
        trace: vf.Trace[Any, Any],
        runtime: vf.Runtime,
    ) -> None:
        trace.state = PurchaseState(initial_budget_units=self.data.budget_units)

    @vf.stop
    def purchase_finished(
        self, trace: vf.Trace[PurchaseScenario, PurchaseState]
    ) -> bool:
        return trace.state.finished or trace.num_turns >= 8

    @vf.metric
    async def purchase_metrics(
        self,
        trace: vf.Trace[PurchaseScenario, PurchaseState],
    ) -> dict[str, float]:
        metrics = purchase_task_metrics(self.data, trace.state)
        return {key: value for key, value in metrics.items() if key != "reward"}

    @vf.reward
    async def purchase_reward(
        self, trace: vf.Trace[PurchaseScenario, PurchaseState]
    ) -> float:
        return purchase_task_metrics(self.data, trace.state)["reward"]


class PurchaseTasksetConfig(vf.TasksetConfig):
    num_tasks: int = Field(30, ge=1)
    seed: int = Field(0, ge=0)
    # Verifiers documents config specialization, but its base field is mutable.
    task: PurchaseTaskConfig = PurchaseTaskConfig()  # ty: ignore[incompatible-mutable-override]


# Verifiers' TaskT bound fixes invariant defaults instead of accepting custom state.
class PurchaseTaskset(vf.Taskset[PurchaseTask, PurchaseTasksetConfig]):  # ty: ignore[invalid-type-arguments]
    """A small deterministic smoke dataset, not a frozen research benchmark."""

    def load(self) -> list[PurchaseTask]:
        return [
            PurchaseTask(
                generate_purchase_scenario(self.config.seed + i), self.config.task
            )
            for i in range(self.config.num_tasks)
        ]
