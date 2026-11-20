"""Authoring contracts for the discovery index and task dataset, not rollout state."""

from datetime import date
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

RecordId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,79}$")]


class DatasetRecord(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_serialization_defaults_required=True,
    )


class RequestCountry(DatasetRecord):
    """A historical share of request origins, not a provider's geographic coverage."""

    country_code: str = Field(pattern=r"^[A-Z]{2}$")
    share: float = Field(ge=0, le=1)


class ResourceListing(DatasetRecord):
    """Public discovery metadata; samples must not contain task-specific answers."""

    id: RecordId
    name: str = Field(min_length=1, max_length=160)
    category: str = Field(min_length=1, max_length=80)
    description: str = Field(max_length=8000)
    tags: list[str] = Field(default_factory=list)
    price_units: int = Field(ge=0, strict=True)
    hostname: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,}$")
    method: Literal["GET", "POST"] = "GET"
    path_pattern: str = Field(pattern=r"^/")
    post_payment_success_rate: float | None = Field(None, ge=0, le=1)
    availability_7d: float | None = Field(None, ge=0, le=1)
    latency_p50_ms: int | None = Field(None, ge=0)
    latency_p90_ms: int | None = Field(None, ge=0)
    domain_created: date | None = None
    domain_age_days: int | None = Field(None, ge=0)
    top_countries: list[RequestCountry] = Field(default_factory=list)
    last_change: date | None = None
    last_persistent_change: date | None = None
    sample_input: JsonValue = Field(default_factory=dict)
    sample_output: JsonValue = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_resource_metadata(self) -> Self:
        if (
            self.latency_p50_ms is not None
            and self.latency_p90_ms is not None
            and self.latency_p90_ms < self.latency_p50_ms
        ):
            raise ValueError("Resource latency p90 must be at least p50")
        if sum(country.share for country in self.top_countries) > 1.000001:
            raise ValueError("Resource request-origin shares must total at most 1")
        if (
            self.last_change is not None
            and self.last_persistent_change is not None
            and self.last_persistent_change > self.last_change
        ):
            raise ValueError("Resource persistent change cannot follow its last change")
        return self


class ReferencePurchase(DatasetRecord):
    """An author-only candidate solution step, not a required agent policy."""

    resource_id: RecordId
    purpose: str


class DatasetTask(DatasetRecord):
    """One authored task with public instructions and evaluator-only fixtures."""

    id: RecordId
    title: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=80)
    split: Literal["train", "validation", "test"] = "train"
    status: Literal["draft", "review", "ready"] = "draft"
    prompt: str = Field(max_length=16000)
    budget_units: int = Field(ge=0, strict=True)
    max_actions: int = Field(8, ge=2, le=100)
    resource_ids: list[RecordId] = Field(default_factory=list)
    resource_responses: dict[str, JsonValue] = Field(default_factory=dict)
    reference_purchases: list[ReferencePurchase] = Field(default_factory=list)
    expected_answer: str = Field(max_length=16000)
    grading_notes: str = Field("", max_length=16000)

    @model_validator(mode="after")
    def validate_task_references(self) -> Self:
        if len(self.resource_ids) != len(set(self.resource_ids)):
            raise ValueError("Task resource IDs must be unique")
        if set(self.resource_responses) != set(self.resource_ids):
            raise ValueError(
                "Task needs exactly one hidden response per available resource"
            )
        if any(
            step.resource_id not in self.resource_ids
            for step in self.reference_purchases
        ):
            raise ValueError("Task reference purchases must use available resources")
        if self.status == "ready" and (
            not self.prompt.strip()
            or not self.expected_answer.strip()
            or not self.resource_ids
        ):
            raise ValueError(
                "Ready tasks need a prompt, expected answer, and resources"
            )
        return self


class WorkspaceDocument(DatasetRecord):
    """Versioned authoring file; split assignments here are not benchmark guarantees."""

    schema_version: Literal[1] = 1
    name: str = Field(min_length=1)
    description: str
    provenance: Literal["synthetic"] = "synthetic"
    as_of: date
    resources: list[ResourceListing]
    tasks: list[DatasetTask]

    @model_validator(mode="after")
    def validate_workspace_links(self) -> Self:
        resource_ids = {resource.id for resource in self.resources}
        if len(resource_ids) != len(self.resources):
            raise ValueError("Workspace resource IDs must be unique")
        if len({task.id for task in self.tasks}) != len(self.tasks):
            raise ValueError("Workspace task IDs must be unique")
        for task in self.tasks:
            if not set(task.resource_ids) <= resource_ids:
                raise ValueError(
                    f"Workspace task {task.id} references missing resources"
                )
        return self


class DiscoveryOverview(DatasetRecord):
    """Initial discovery access, without identifying the task's fixture resources."""

    resource_count: int
    snapshot_date: date
    categories: list[str]
    search_tool: Literal["metis_search_resources"] = "metis_search_resources"
    inspect_tool: Literal["metis_inspect_resource"] = "metis_inspect_resource"


class AgentObservation(DatasetRecord):
    """The public initial task observation, shared by the runtime and editor."""

    task: str
    budget_units: int
    max_actions: int
    directory: DiscoveryOverview


def agent_task_preview(
    document: WorkspaceDocument,
    task: DatasetTask,
) -> AgentObservation:
    """Whitelist public inputs, excluding evaluator-only fields."""
    return AgentObservation(
        task=task.prompt,
        budget_units=task.budget_units,
        max_actions=task.max_actions,
        directory=DiscoveryOverview(
            resource_count=len(document.resources),
            snapshot_date=document.as_of,
            categories=sorted({resource.category for resource in document.resources}),
        ),
    )


def workspace_warnings(document: WorkspaceDocument) -> list[str]:
    """Flag incomplete records without claiming solvability or benchmark validity."""
    warnings = []
    prices = {resource.id: resource.price_units for resource in document.resources}
    for task in document.tasks:
        if not task.prompt.strip() or not task.expected_answer.strip():
            warnings.append(f"{task.id}: prompt or expected answer is empty")
        if not task.resource_ids:
            warnings.append(f"{task.id}: no resources are available")
        if not task.reference_purchases:
            warnings.append(f"{task.id}: no reference purchase path is documented")
        reference_cost = sum(
            prices[resource_id]
            for resource_id in {s.resource_id for s in task.reference_purchases}
        )
        if reference_cost > task.budget_units:
            warnings.append(f"{task.id}: reference purchase path exceeds the budget")
        if len(task.reference_purchases) + 1 > task.max_actions:
            warnings.append(f"{task.id}: reference path leaves no action to finish")
    return warnings
