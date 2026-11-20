"""CPU correctness checks, including real Verifiers lifecycle and scoring hooks."""

import random

import pytest
import verifiers.v1 as vf

from paid_tool_rl import PurchaseTaskset
from paid_tool_rl.purchase_simulator import (
    PurchaseScenario,
    PurchaseState,
    finish_purchase_task,
    generate_purchase_scenario,
    purchase_resource,
    purchase_task_metrics,
)
from paid_tool_rl.purchase_taskset import PurchaseTask, PurchaseTasksetConfig
from paid_tool_rl.purchase_tools import PurchaseToolset


def test_scenarios_are_repeatable_and_varied():
    assert generate_purchase_scenario(10) == generate_purchase_scenario(10)
    assert generate_purchase_scenario(10) != generate_purchase_scenario(11)


def test_purchase_is_idempotent():
    scenario = generate_purchase_scenario(0)
    state = PurchaseState(initial_budget_units=scenario.budget_units)
    provider = next(p for p in scenario.providers if p.provider_id == "focused")
    first = purchase_resource(scenario, state, "focused")
    second = purchase_resource(scenario, state, "focused")
    assert first["record"] == second["record"]
    assert second["charged_units"] == 0
    assert state.spent_units == provider.price_units


def test_over_budget_purchase_does_not_debit():
    scenario = generate_purchase_scenario(0)
    state = PurchaseState(initial_budget_units=0)
    assert purchase_resource(scenario, state, "complete") == {
        "error": "insufficient_budget",
    }
    assert state.spent_units == 0
    assert state.purchases == {}


def test_unknown_provider_does_not_debit():
    scenario = generate_purchase_scenario(0)
    state = PurchaseState(initial_budget_units=5)
    assert (
        purchase_resource(scenario, state, "not-a-provider")["error"]
        == "unknown_provider"
    )
    assert state.spent_units == 0


def test_terminal_episode_rejects_purchases_and_answer_changes():
    scenario = generate_purchase_scenario(0)
    state = PurchaseState(initial_budget_units=5)
    finish_purchase_task(state, "wrong")
    before = state.model_dump()
    assert purchase_resource(scenario, state, "complete")["error"] == "episode_finished"
    assert finish_purchase_task(state, scenario.answer)["error"] == "episode_finished"
    assert state.model_dump() == before


def test_action_limit_terminates_repeated_invalid_calls():
    scenario = generate_purchase_scenario(0)
    state = PurchaseState(initial_budget_units=5)
    for _ in range(6):
        purchase_resource(scenario, state, "unknown")
    assert state.finished
    assert state.final_answer is None
    assert state.action_count == 6


def test_random_transitions_preserve_budget_and_isolation():
    rng = random.Random(42)
    for seed in range(200):
        scenario = generate_purchase_scenario(seed)
        state = PurchaseState(initial_budget_units=scenario.budget_units)
        other = PurchaseState(initial_budget_units=scenario.budget_units)
        for _ in range(10):
            purchase_resource(
                scenario,
                state,
                rng.choice(("free", "focused", "complete", "invalid")),
            )
            assert 0 <= state.spent_units <= state.initial_budget_units
            assert (
                state.remaining_budget_units + state.spent_units
                == scenario.budget_units
            )
            assert state.spent_units == sum(
                p.price_units
                for p in scenario.providers
                if p.provider_id in state.purchases
            )
            assert other.spent_units == 0
            assert other.purchases == {}


def test_reward_prefers_cheaper_success_and_never_rewards_wrong_answer():
    scenario = generate_purchase_scenario(0)
    cheap = PurchaseState(
        initial_budget_units=5, finished=True, final_answer=scenario.answer
    )
    expensive = cheap.model_copy(update={"spent_units": 5})
    wrong = cheap.model_copy(update={"final_answer": '{"reward": 1}'})
    cheap_metrics = purchase_task_metrics(scenario, cheap)
    expensive_metrics = purchase_task_metrics(scenario, expensive)
    assert cheap_metrics["success"] == expensive_metrics["success"] == 1
    assert cheap_metrics["reward"] > expensive_metrics["reward"] > 0
    assert purchase_task_metrics(scenario, wrong)["reward"] == 0


def test_hidden_answer_is_not_in_public_prompt():
    for seed in range(100):
        scenario = generate_purchase_scenario(seed)
        assert scenario.answer not in scenario.prompt_text
        assert "record" not in PurchaseToolset.purchase.__annotations__


@pytest.mark.parametrize("answer_is_correct", [True, False])
async def test_verifiers_lifecycle_and_scoring(answer_is_correct):
    scenario = generate_purchase_scenario(0)
    task = PurchaseTask(scenario)
    trace = vf.Trace[PurchaseScenario, PurchaseState](
        agent=vf.AgentInfo(config=vf.AgentConfig()),
        task=vf.TraceTask(type="PurchaseTask", data=scenario),
        state=PurchaseState(),
    )
    # Setup and scoring don't use a runtime for this in-memory task.
    await task.setup(trace, None)
    tools = PurchaseToolset(vf.ToolsetConfig())
    await tools.setup_task(scenario)
    tools.state.initial_budget_units = trace.state.initial_budget_units
    result = tools.purchase("free")
    assert "record" in result
    tools.finish(scenario.answer if answer_is_correct else "wrong")
    trace.state = tools.state
    assert task.purchase_finished(trace)
    await task.score(trace)
    assert trace.metrics["success"] == float(answer_is_correct)
    assert trace.reward == float(answer_is_correct)


def test_taskset_discovery_and_independent_tasks():
    tasks = list(PurchaseTaskset(PurchaseTasksetConfig()))
    assert len(tasks) == 30
    assert len({task.data.name for task in tasks}) == 30
    assert isinstance(PurchaseToolset(vf.ToolsetConfig()).state, PurchaseState)
