"""Walk through a scripted episode without model inference or weight updates."""

import json

from paid_tool_rl.purchase_simulator import (
    PurchaseState,
    finish_purchase_task,
    generate_purchase_scenario,
    purchase_resource,
    purchase_task_metrics,
)


def main() -> None:
    """Show purchases, budget rejection, and exact-answer reward on the CPU."""
    scenario = generate_purchase_scenario(0)
    state = PurchaseState(initial_budget_units=scenario.budget_units)
    print(scenario.prompt_text)
    print("\nScripted actions (not a model and not RL training):")
    observations = {}
    for provider_id in ("free", "focused", "complete"):
        result = purchase_resource(scenario, state, provider_id)
        print(f"purchase({provider_id!r}) -> {json.dumps(result)}")
        observations.update(result.get("record", {}))
    # This demonstration reads the requested field from the public prompt only.
    field = "price" if "current price" in scenario.prompt_text else "stock"
    answer = observations[field]
    print(f"finish({answer!r}) -> {finish_purchase_task(state, answer)}")
    print(json.dumps(purchase_task_metrics(scenario, state), indent=2))
