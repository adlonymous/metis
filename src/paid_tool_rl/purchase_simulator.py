"""Synthetic data purchases, with integer prices and no network access."""

import random

import verifiers.v1 as vf
from pydantic import BaseModel, ConfigDict, Field


class DataProvider(BaseModel):
    """A synthetic provider; records are private until purchased."""

    model_config = ConfigDict(frozen=True)
    provider_id: str
    price_units: int = Field(ge=0)
    fields: tuple[str, ...]
    record: dict[str, str]

    def public_description(self) -> str:
        return (
            f"{self.provider_id}: price={self.price_units} units, "
            f"fields={','.join(self.fields)}"
        )


class PurchaseScenario(vf.TaskData):
    """Evaluator-owned task data, not an agent-visible observation."""

    answer: str
    budget_units: int = Field(ge=0)
    providers: tuple[DataProvider, ...]


class PurchaseState(vf.State):
    """Per-rollout ledger; repeated provider purchases reuse the paid result."""

    initial_budget_units: int = Field(0, ge=0)
    spent_units: int = Field(0, ge=0)
    purchases: dict[str, dict[str, str]] = Field(default_factory=dict)
    action_count: int = 0
    budget_rejections: int = 0
    finished: bool = False
    final_answer: str | None = None

    @property
    def remaining_budget_units(self) -> int:
        return self.initial_budget_units - self.spent_units


def generate_purchase_scenario(seed: int) -> PurchaseScenario:
    """Generate a repeatable lookup task with public coverage and hidden values."""
    rng = random.Random(seed)
    field = rng.choice(("price", "stock"))
    free_field = rng.choice(("price", "stock"))
    paid_field = "stock" if free_field == "price" else "price"
    record = {"price": str(rng.randint(100, 9999)), "stock": str(rng.randint(0, 999))}
    focused_price = rng.randint(1, 3)
    premium_price = focused_price + rng.randint(1, 3)
    providers = [
        DataProvider(
            provider_id="free",
            price_units=0,
            fields=(free_field,),
            record={free_field: record[free_field]},
        ),
        DataProvider(
            provider_id="focused",
            price_units=focused_price,
            fields=(paid_field,),
            record={paid_field: record[paid_field]},
        ),
        DataProvider(
            provider_id="complete",
            price_units=premium_price,
            fields=("price", "stock"),
            record=record,
        ),
    ]
    rng.shuffle(providers)
    budget = rng.randint(focused_price, premium_price)
    catalog = "\n".join(provider.public_description() for provider in providers)
    return PurchaseScenario(
        name=f"lookup-{seed}",
        prompt=(
            f"Find this product's current {field}. Your budget is {budget} units.\n"
            f"Available sources:\n{catalog}\n"
            "Use paid_data_purchase to retrieve a source's record. Calling it "
            "authorizes its listed price. Repeat calls to the same source are free. "
            "All sources are accurate but may lack the field you need. "
            "Use paid_data_finish with only the requested numeric value as a string. "
            "Do not guess. You have at most 6 purchase/finish actions."
        ),
        answer=record[field],
        budget_units=budget,
        providers=tuple(providers),
    )


def purchase_resource(
    scenario: PurchaseScenario,
    state: PurchaseState,
    provider_id: str,
) -> dict:
    """Fetch synthetic data without debiting rejected or repeated purchases."""
    if state.finished:
        return {"error": "episode_finished"}
    state.action_count += 1
    if state.action_count >= 6:
        state.finished = True
        return {"error": "action_limit"}
    provider = next(
        (p for p in scenario.providers if p.provider_id == provider_id),
        None,
    )
    if provider is None:
        return {"error": "unknown_provider"}
    if provider_id in state.purchases:
        return {"record": dict(state.purchases[provider_id]), "charged_units": 0}
    if provider.price_units > state.remaining_budget_units:
        state.budget_rejections += 1
        return {"error": "insufficient_budget"}
    state.spent_units += provider.price_units
    state.purchases[provider_id] = dict(provider.record)
    return {
        "record": dict(provider.record),
        "charged_units": provider.price_units,
        "remaining_budget_units": state.remaining_budget_units,
    }


def finish_purchase_task(state: PurchaseState, answer: str) -> dict:
    """End an episode explicitly; terminal answers cannot be overwritten."""
    if state.finished:
        return {"error": "episode_finished"}
    state.action_count += 1
    state.finished = True
    state.final_answer = answer.strip()
    return {"finished": True}


def purchase_task_metrics(
    scenario: PurchaseScenario,
    state: PurchaseState,
) -> dict[str, float]:
    """Score exact answers independently of the synthetic spending penalty."""
    success = float(state.final_answer == scenario.answer)
    cost_fraction = state.spent_units / max(state.initial_budget_units, 1)
    return {
        "success": success,
        "spent_units": float(state.spent_units),
        "budget_rejections": float(state.budget_rejections),
        "actions": float(state.action_count),
        "reward": success - 0.15 * cost_fraction,
    }
