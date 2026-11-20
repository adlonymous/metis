"""Per-task MCP tools for simulated purchases, never real HTTP or payments."""

import verifiers.v1 as vf

from paid_tool_rl.purchase_simulator import (
    PurchaseScenario,
    PurchaseState,
    finish_purchase_task,
    purchase_resource,
)


class PurchaseToolset(vf.Toolset[vf.ToolsetConfig, PurchaseState]):
    """Keep private provider records in a separate server for each rollout."""

    TOOL_PREFIX = "paid_data"
    scenario: PurchaseScenario

    async def setup_task(self, task: vf.TaskData) -> None:
        self.scenario = PurchaseScenario.model_validate(task.model_dump())

    @vf.tool
    def purchase(self, provider_id: str) -> dict:
        """Authorize the listed synthetic price and retrieve this provider's record."""
        return purchase_resource(self.scenario, self.state, provider_id)

    @vf.tool
    def finish(self, answer: str) -> dict:
        """Submit only the requested numeric value as a string and end the task."""
        return finish_purchase_task(self.state, answer)


if __name__ == "__main__":
    PurchaseToolset.run()
