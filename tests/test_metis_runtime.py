"""Runtime invariants, native scoring, and the pinned state synchronization contract."""

import asyncio
import inspect
import json
import random

import pytest
import verifiers.v1 as vf
from pydantic import ValidationError
from verifiers.v1.utils.loaders import default_harness_id, harness_class

from metis.episode import (
    MetisEpisode,
    MetisState,
    metis_answer_matches,
    metis_episode_metrics,
)
from metis.taskset import (
    MetisConfig,
    MetisTaskConfig,
    MetisTaskData,
    MetisTaskset,
    load_metis_workspace,
)
from metis.tools import MetisToolset


@pytest.fixture
def document():
    return load_metis_workspace()


@pytest.fixture
def episode(document):
    record = document.tasks[0]
    state = MetisState(initial_budget_units=record.budget_units, max_actions=100)
    return MetisEpisode(record, document.resources, state)


def test_search_pages_cover_the_entire_index_without_hidden_fixture_flags(episode):
    ids = []
    for offset in range(0, 1000, 20):
        result = episode.search_resources(offset=offset, limit=20)
        assert result["total"] == 1000
        ids.extend(resource["id"] for resource in result["matches"])
        assert set(result["matches"][0]) == {
            "id",
            "name",
            "category",
            "description",
            "tags",
            "price_units",
        }
    assert len(ids) == len(set(ids)) == 1000
    assert episode.state.spent_units == 0
    assert result["next_offset"] is None
    assert episode.record.expected_answer not in json.dumps(result)


def test_discovery_does_not_depend_on_private_task_outcomes(episode, document):
    before = episode.search_resources("company revenue", category="Finance")
    alternate_record = episode.record.model_copy(
        update={
            "expected_answer": "PRIVATE_SENTINEL",
            "resource_responses": {},
        }
    )
    alternate = MetisEpisode(alternate_record, document.resources, MetisState())
    after = alternate.search_resources("company revenue", category="finance")
    assert before["matches"] == after["matches"]
    assert before["total"] == after["total"]
    assert "PRIVATE_SENTINEL" not in json.dumps(after)


def test_inspection_never_reveals_task_response_or_answer(episode):
    result = episode.inspect_resource("filings")
    assert result["resource"]["sample_output"]["revenue"] != 24800000
    assert episode.record.expected_answer not in json.dumps(result)
    assert episode.state.spent_units == 0


def test_purchase_replay_returns_an_independent_cached_result(episode):
    first = episode.purchase("filings")
    assert first["charged_units"] == 7
    first["result"]["data"]["revenue"] = 0
    replay = episode.purchase("filings")
    assert replay["result"]["data"]["revenue"] == 24800000
    assert replay["charged_units"] == 0
    assert episode.state.spent_units == 7
    assert episode.state.actions[0].observation["result"]["data"]["revenue"] == 24800000


def test_budget_rejection_leaves_ledger_untouched(episode):
    episode.state.initial_budget_units = 1
    result = episode.purchase("filings")
    assert result["error"] == "insufficient_budget"
    assert episode.state.spent_units == 0
    assert episode.state.purchases == {}
    assert episode.state.budget_rejections == 1


def test_unconfigured_resource_costs_money_without_a_free_relevance_oracle(episode):
    first = episode.purchase("parcel")
    assert first["result"] == {"status": "no_matching_data", "data": None}
    assert first["charged_units"] == 2
    assert episode.purchase("parcel")["charged_units"] == 0
    assert episode.state.spent_units == 2


def test_action_limit_and_terminal_state_are_enforced(episode):
    episode.state.max_actions = 2
    episode.search_resources()
    episode.inspect_resource("filings")
    before = episode.state.model_dump()
    assert episode.state.finished
    assert episode.state.termination_reason == "action_limit"
    assert episode.purchase("filings") == {"error": "episode_finished"}
    assert episode.finish(episode.record.expected_answer) == {
        "error": "episode_finished"
    }
    assert episode.state.model_dump() == before


def test_final_action_can_submit_and_does_not_reveal_reward(episode):
    episode.state.max_actions = 2
    episode.search_resources()
    result = episode.finish(episode.record.expected_answer)
    assert result == {"finished": True}
    assert episode.state.termination_reason == "submitted"
    assert metis_episode_metrics(episode.record, episode.state)["success"] == 1


@pytest.mark.parametrize(
    "prediction,expected,correct",
    [
        ("22,816,000", "22816000", True),
        ("55.2", "55.20", True),
        ("4.0", "4", True),
        (" 2026-11-24 ", "2026-11-24", True),
        ("1,2", "12", False),
        ("NaN", "4", False),
        ('{"reward":1}', "4", False),
        ("The answer is 4", "4", False),
        (None, "4", False),
        ("", "", False),
    ],
)
def test_exact_or_decimal_scoring_resists_answer_format_exploits(
    prediction,
    expected,
    correct,
):
    assert metis_answer_matches(prediction, expected) is correct


def test_random_purchase_sequences_never_overspend_or_double_bill(document):
    rng = random.Random(101)
    for _ in range(100):
        state = MetisState(initial_budget_units=rng.randint(0, 20), max_actions=30)
        run = MetisEpisode(document.tasks[0], document.resources, state)
        for _ in range(35):
            resource_id = rng.choice(("filings", "fx-spot", "parcel", "unknown"))
            run.purchase(resource_id)
            assert 0 <= state.spent_units <= state.initial_budget_units
            assert (
                state.remaining_budget_units + state.spent_units
                == state.initial_budget_units
            )
            assert state.spent_units == sum(
                run.catalog[resource_id].price_units for resource_id in state.purchases
            )


@pytest.mark.parametrize(
    "split,count", [("all", 6), ("train", 3), ("validation", 2), ("test", 1)]
)
def test_taskset_split_selection_and_public_initial_prompt(split, count):
    tasks = list(MetisTaskset(MetisConfig(split=split)))
    assert len(tasks) == count
    for task in tasks:
        prompt = json.loads(task.data.prompt)
        assert prompt["directory"]["resource_count"] == 1000
        assert len(prompt["directory"]["categories"]) == 50
        assert set(prompt) == {"task", "budget_units", "max_actions", "directory"}
        assert task.data.record.expected_answer not in task.data.prompt
        assert "resource_responses" not in task.data.prompt
        assert "reference_purchases" not in task.data.prompt
    assert default_harness_id("metis") == "metis"
    assert harness_class("metis").SUPPORTS_MCP
    assert not harness_class("metis").EXECUTES_CODE


async def test_native_scoring_and_finalization_preserve_economic_trace():
    task = list(MetisTaskset(MetisConfig(task=MetisTaskConfig(cost_weight=0.3))))[0]
    trace = vf.Trace[MetisTaskData, MetisState](
        agent=vf.AgentInfo(config=vf.AgentConfig()),
        task=vf.TraceTask(type="MetisTask", data=task.data),
        state=MetisState(),
    )
    await task.setup(trace, None)
    episode = MetisEpisode(task.data.record, task.data.catalog, trace.state)
    episode.purchase("filings")
    episode.finish(task.data.record.expected_answer)
    assert task.episode_finished(trace)
    await task.finalize(trace, None)
    await task.score(trace)
    assert trace.reward == pytest.approx(1 - 0.3 * 0.7)
    assert trace.metrics["success"] == 1
    assert trace.metrics["spent_units"] == 7
    assert set(trace.info["metis"]["purchases"]) == {"filings"}
    assert [action["action"] for action in trace.info["metis"]["actions"]] == [
        "purchase",
        "finish",
    ]
    assert "state" not in trace.model_dump()


async def test_missing_submission_is_scored_as_unanswered():
    task = list(MetisTaskset(MetisConfig()))[0]
    trace = vf.Trace[MetisTaskData, MetisState](
        agent=vf.AgentInfo(config=vf.AgentConfig()),
        task=vf.TraceTask(type="MetisTask", data=task.data),
        state=MetisState(),
    )
    await task.setup(trace, None)
    await task.finalize(trace, None)
    await task.score(trace)
    assert trace.reward == 0
    assert trace.metrics["answered"] == 0
    assert (
        trace.info["metis"]["termination_reason"] == "agent_stopped_without_submission"
    )


def test_success_always_beats_free_failure_with_allowed_cost_weights():
    with pytest.raises(ValidationError):
        MetisTaskConfig(cost_weight=1)


async def test_concurrent_native_state_wrappers_compose_without_overspending(document):
    class InMemoryChannel(MetisToolset):
        async def _pull_state(self):
            await asyncio.sleep(0.001)
            return self.channel.model_copy(deep=True)

        async def _push_state(self, before):
            await asyncio.sleep(0.001)
            self.channel = self.state.model_copy(deep=True)

    tools = InMemoryChannel(vf.ToolsetConfig())
    tools.channel = MetisState(initial_budget_units=7, max_actions=8)
    await tools.setup()
    await tools.setup_task(
        MetisTaskData(
            prompt="",
            record=document.tasks[0],
            catalog=document.resources,
        )
    )
    purchase = tools._with_state(tools.purchase)
    assert inspect.signature(purchase) == inspect.signature(tools.purchase)
    await asyncio.gather(purchase("filings"), purchase("fx-spot"), purchase("filings"))
    assert tools.channel.spent_units == 7
    assert set(tools.channel.purchases) == {"filings"}
    assert tools.channel.budget_rejections == 1
    assert len(tools.channel.actions) == 3
