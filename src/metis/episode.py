"""Budgeted synthetic information purchasing, independent of model inference."""

import copy
import hashlib
import re
from decimal import Decimal

import verifiers.v1 as vf
from pydantic import BaseModel, Field, JsonValue

from paid_tool_rl.dataset_schema import DatasetTask, ResourceListing


class MetisAction(BaseModel):
    """One model-visible tool result and the ledger immediately after it."""

    sequence: int
    action: str
    arguments: dict[str, JsonValue]
    observation: dict[str, JsonValue]
    remaining_budget_units: int


class MetisState(vf.State):
    """Episode-local ledger; only paid observations enter the purchase cache."""

    initial_budget_units: int = Field(0, ge=0)
    spent_units: int = Field(0, ge=0)
    max_actions: int = Field(8, ge=2)
    actions: list[MetisAction] = Field(default_factory=list)
    purchases: dict[str, JsonValue] = Field(default_factory=dict)
    budget_rejections: int = 0
    invalid_actions: int = 0
    finished: bool = False
    termination_reason: str | None = None
    final_answer: str | None = None

    @property
    def remaining_budget_units(self) -> int:
        return self.initial_budget_units - self.spent_units


def metis_answer_matches(answer: str | None, expected: str) -> bool:
    """Compare exact text or equivalent finite decimals, not answer-shaped prose."""
    if answer is None or not expected.strip():
        return False
    prediction, reference = answer.strip(), expected.strip()
    numeric = r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
    if re.fullmatch(numeric, prediction) and re.fullmatch(numeric, reference):
        return Decimal(prediction.replace(",", "")) == Decimal(
            reference.replace(",", "")
        )
    return prediction == reference


def metis_episode_metrics(record: DatasetTask, state: MetisState) -> dict[str, float]:
    """Report success separately from cost and the training reward."""
    return {
        "success": float(
            metis_answer_matches(state.final_answer, record.expected_answer)
        ),
        "spent_units": float(state.spent_units),
        "remaining_budget_units": float(state.remaining_budget_units),
        "cost_fraction": state.spent_units / max(state.initial_budget_units, 1),
        "actions": float(len(state.actions)),
        "purchases": float(len(state.purchases)),
        "budget_rejections": float(state.budget_rejections),
        "invalid_actions": float(state.invalid_actions),
        "answered": float(state.final_answer is not None),
    }


class MetisEpisode:
    """Trusted task-side operations; no shell, HTTP, settlement, or wallet access."""

    def __init__(
        self,
        record: DatasetTask,
        catalog: list[ResourceListing],
        state: MetisState,
    ) -> None:
        self.record = record
        self.catalog = {resource.id: resource for resource in catalog}
        self.state = state

    def _record(
        self,
        action: str,
        arguments: dict[str, JsonValue],
        observation: dict[str, JsonValue],
    ) -> dict[str, JsonValue]:
        self.state.actions.append(
            MetisAction(
                sequence=len(self.state.actions) + 1,
                action=action,
                arguments=arguments,
                observation=copy.deepcopy(observation),
                remaining_budget_units=self.state.remaining_budget_units,
            )
        )
        if (
            len(self.state.actions) >= self.state.max_actions
            and not self.state.finished
        ):
            self.state.finished = True
            self.state.termination_reason = "action_limit"
        return observation

    def search_resources(
        self,
        query: str = "",
        category: str = "",
        offset: int = 0,
        limit: int = 10,
    ) -> dict[str, JsonValue]:
        """Search only public metadata, with reproducible per-task tie-breaking."""
        if self.state.finished:
            return {"error": "episode_finished"}
        arguments = {
            "query": query,
            "category": category,
            "offset": offset,
            "limit": limit,
        }
        if offset < 0 or not 1 <= limit <= 20:
            self.state.invalid_actions += 1
            return self._record(
                "search_resources", arguments, {"error": "invalid_page"}
            )
        stopwords = {"the", "a", "an", "and", "or", "for", "to", "in", "on", "of"}
        terms = set(re.findall(r"[a-z0-9]+", query.lower())) - stopwords
        ranked = []
        for resource in self.catalog.values():
            if category and resource.category.casefold() != category.casefold():
                continue
            text = " ".join(
                (
                    resource.id,
                    resource.name,
                    resource.description,
                    *resource.tags,
                )
            ).casefold()
            score = sum(term in text for term in terms)
            if terms and not score:
                continue
            tie = hashlib.sha256(f"{self.record.id}:{resource.id}".encode()).hexdigest()
            ranked.append((-score, tie, resource))
        ranked.sort(key=lambda entry: (entry[0], entry[1]))
        matches: list[JsonValue] = [
            resource.model_dump(
                mode="json",
                include={
                    "id",
                    "name",
                    "category",
                    "description",
                    "tags",
                    "price_units",
                },
            )
            for _, _, resource in ranked[offset : offset + limit]
        ]
        next_offset = offset + limit if offset + limit < len(ranked) else None
        return self._record(
            "search_resources",
            arguments,
            {
                "matches": matches,
                "total": len(ranked),
                "next_offset": next_offset,
                "remaining_budget_units": self.state.remaining_budget_units,
            },
        )

    def inspect_resource(self, resource_id: str) -> dict[str, JsonValue]:
        """Reveal all public metadata and samples, never a task-specific response."""
        if self.state.finished:
            return {"error": "episode_finished"}
        resource = self.catalog.get(resource_id)
        observation: dict[str, JsonValue]
        if resource is None:
            self.state.invalid_actions += 1
            observation = {"error": "unknown_resource"}
        else:
            observation = {"resource": resource.model_dump(mode="json")}
        return self._record(
            "inspect_resource", {"resource_id": resource_id}, observation
        )

    def purchase(self, resource_id: str) -> dict[str, JsonValue]:
        """Authorize the integer price once; empty paid lookups can still cost money."""
        if self.state.finished:
            return {"error": "episode_finished"}
        resource = self.catalog.get(resource_id)
        arguments = {"resource_id": resource_id}
        if resource is None:
            self.state.invalid_actions += 1
            return self._record("purchase", arguments, {"error": "unknown_resource"})
        if resource_id in self.state.purchases:
            return self._record(
                "purchase",
                arguments,
                {
                    "result": copy.deepcopy(self.state.purchases[resource_id]),
                    "charged_units": 0,
                    "remaining_budget_units": self.state.remaining_budget_units,
                },
            )
        if resource.price_units > self.state.remaining_budget_units:
            self.state.budget_rejections += 1
            return self._record(
                "purchase",
                arguments,
                {
                    "error": "insufficient_budget",
                    "charged_units": 0,
                    "remaining_budget_units": self.state.remaining_budget_units,
                },
            )
        self.state.spent_units += resource.price_units
        result: dict[str, JsonValue] = (
            {
                "status": "ok",
                "data": copy.deepcopy(self.record.resource_responses[resource_id]),
            }
            if resource_id in self.record.resource_responses
            else {"status": "no_matching_data", "data": None}
        )
        self.state.purchases[resource_id] = copy.deepcopy(result)
        return self._record(
            "purchase",
            arguments,
            {
                "result": result,
                "charged_units": resource.price_units,
                "remaining_budget_units": self.state.remaining_budget_units,
            },
        )

    def finish(self, answer: str) -> dict[str, JsonValue]:
        """Submit an answer without revealing correctness or reward to the agent."""
        if self.state.finished:
            return {"error": "episode_finished"}
        self.state.final_answer = answer.strip()
        self.state.finished = True
        self.state.termination_reason = "submitted"
        return self._record("finish", {"answer": answer}, {"finished": True})
