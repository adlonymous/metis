"""Deterministic synthetic discovery listings; never calls or measures real APIs."""

import hashlib
import random
from datetime import timedelta
from pathlib import Path
from typing import Literal

from pydantic import Field, JsonValue, TypeAdapter

from paid_tool_rl.dataset_schema import (
    DatasetRecord,
    RecordId,
    ResourceListing,
    WorkspaceDocument,
)
from paid_tool_rl.dataset_store import DatasetStore

PROVIDER_NAMES = (
    "Alder",
    "Birch",
    "Cedar",
    "Juniper",
    "Larch",
    "Maple",
    "Oak",
    "Pine",
    "Spruce",
    "Willow",
    "Aspen",
    "Beech",
    "Cypress",
    "Elm",
    "Fir",
    "Hazel",
    "Holly",
    "Laurel",
    "Magnolia",
    "Olive",
    "Poplar",
    "Redwood",
    "Rowan",
    "Sequoia",
    "Sycamore",
    "Tamarack",
    "Walnut",
    "Yew",
    "Acacia",
    "Banyan",
    "Ginkgo",
    "Hemlock",
    "Linden",
)
COVERAGE_REGIONS = (
    "global",
    "North American",
    "European",
    "Asia-Pacific",
    "Latin American",
)
FRESHNESS_DESCRIPTIONS = (
    "A daily snapshot; not a real-time feed.",
    "A weekly snapshot; recent changes may be absent.",
    "An hourly refreshed snapshot; timestamps accompany the returned records.",
    "An archived monthly snapshot intended for historical comparisons.",
)
REQUEST_COUNTRIES = (
    "US",
    "GB",
    "DE",
    "FR",
    "CA",
    "AU",
    "JP",
    "IN",
    "BR",
    "SG",
    "NL",
    "MX",
)


class ResourceCapability(DatasetRecord):
    """A hand-authored capability template, separate from provider metadata."""

    id: RecordId
    name: str
    category: str
    description: str
    tags: list[str]
    base_price_units: int = Field(ge=0)
    method: Literal["GET", "POST"]
    path_pattern: str
    sample_input: JsonValue
    sample_output: JsonValue


def load_discovery_capabilities() -> list[ResourceCapability]:
    """Load the two authored catalogs and reject duplicate capability IDs."""
    adapter = TypeAdapter(list[ResourceCapability])
    capabilities = [
        capability
        for path in (
            Path("datasets/resource_capabilities.json"),
            Path("datasets/resource_capabilities_extended.json"),
        )
        for capability in adapter.validate_json(path.read_bytes())
    ]
    if len({capability.id for capability in capabilities}) != len(capabilities):
        raise ValueError("Discovery capability IDs must be unique across catalogs")
    return capabilities


def generate_discovery_listing(
    capability: ResourceCapability,
    provider: str,
    document: WorkspaceDocument,
) -> ResourceListing:
    """Generate a stable listing from its ID and the workspace snapshot date."""
    provider_id = provider.lower()
    resource_id = f"synthetic-{capability.id}-{provider_id}"
    seed = int.from_bytes(hashlib.sha256(f"{resource_id}:v1".encode()).digest())
    rng = random.Random(seed)
    domain_age_days = random.Random(f"{provider_id}:domain:v1").randint(60, 6000)
    last_change_age = rng.randint(0, min(120, domain_age_days))
    latency_p50 = rng.randint(40, 2400)
    countries = rng.sample(REQUEST_COUNTRIES, 3)
    shares = (rng.randint(35, 65), rng.randint(8, 20), rng.randint(3, 10))
    region = rng.choice(COVERAGE_REGIONS)
    freshness = rng.choice(FRESHNESS_DESCRIPTIONS)
    multiplier = rng.choice((0.5, 1.0, 1.8, 3.2))
    price = (
        0
        if rng.random() < 0.1
        else max(
            1, round(capability.base_price_units * multiplier) + rng.randint(-1, 2)
        )
    )
    return ResourceListing.model_validate(
        {
            "id": resource_id,
            "name": f"{provider} Data · {capability.name}",
            "category": capability.category,
            "description": (
                f"{capability.description} Offers {region} coverage. {freshness} "
                "Synthetic provider listing; no live service is available."
            ),
            "tags": [*capability.tags, "synthetic", region.lower().replace(" ", "-")],
            "price_units": price,
            "hostname": f"{provider_id}.metis.example",
            "method": capability.method,
            "path_pattern": capability.path_pattern,
            "post_payment_success_rate": round(rng.uniform(0.75, 0.9999), 4),
            "availability_7d": round(rng.uniform(0.80, 0.9999), 4),
            "latency_p50_ms": latency_p50,
            "latency_p90_ms": latency_p50 + rng.randint(50, 4500),
            "domain_created": document.as_of - timedelta(days=domain_age_days),
            "domain_age_days": domain_age_days,
            "top_countries": [
                {"country_code": country, "share": share / 100}
                for country, share in zip(countries, shares, strict=True)
            ],
            "last_change": document.as_of - timedelta(days=last_change_age),
            "last_persistent_change": document.as_of
            - timedelta(
                days=last_change_age
                + rng.randint(0, min(90, domain_age_days - last_change_age))
            ),
            "sample_input": capability.sample_input,
            "sample_output": capability.sample_output,
        }
    )


def extend_discovery_index(
    document: WorkspaceDocument,
    capabilities: list[ResourceCapability],
    target_count: int = 1000,
) -> WorkspaceDocument:
    """Append listings without changing existing records, IDs, or task links."""
    if len(document.resources) > target_count:
        raise ValueError(
            "Discovery index exceeds the target; refusing to delete records"
        )
    resources = list(document.resources)
    existing_ids = {resource.id for resource in resources}
    for provider_round in range(len(PROVIDER_NAMES)):
        for index, capability in enumerate(capabilities):
            if len(resources) == target_count:
                break
            provider = PROVIDER_NAMES[(index + provider_round) % len(PROVIDER_NAMES)]
            listing = generate_discovery_listing(capability, provider, document)
            if listing.id not in existing_ids:
                resources.append(listing)
                existing_ids.add(listing.id)
    if len(resources) != target_count:
        raise ValueError("Discovery templates cannot produce enough unique listings")
    return WorkspaceDocument.model_validate(
        {
            **document.model_dump(),
            "resources": resources,
        }
    )


def rebalance_discovery_index(
    document: WorkspaceDocument,
    capabilities: list[ResourceCapability],
    target_count: int = 1000,
) -> WorkspaceDocument:
    """Broaden coverage by replacing only untouched, unlinked generated rows."""
    managed_specs = {
        f"synthetic-{capability.id}-{provider.lower()}": (capability, provider)
        for capability in capabilities
        for provider in PROVIDER_NAMES
    }
    linked_ids = {
        resource_id for task in document.tasks for resource_id in task.resource_ids
    }
    preserved = []
    for resource in document.resources:
        spec = managed_specs.get(resource.id)
        if (
            resource.id in linked_ids
            or spec is None
            or resource != generate_discovery_listing(spec[0], spec[1], document)
        ):
            preserved.append(resource)
    return extend_discovery_index(
        document.model_copy(update={"resources": preserved}),
        capabilities,
        target_count,
    )


def main() -> None:
    """Rebalance to 1,000 listings while preserving authored records and task links."""
    capabilities = load_discovery_capabilities()
    store = DatasetStore(Path("datasets/workspace.json"))
    document, revision = store.load_workspace()
    expanded = rebalance_discovery_index(document, capabilities)
    if expanded != document:
        store.save_workspace(expanded, revision)
    represented = sum(
        any(
            resource.id.startswith(f"synthetic-{capability.id}-")
            for resource in expanded.resources
        )
        for capability in capabilities
    )
    print(
        f"Discovery index: {len(expanded.resources)} synthetic resources, "
        f"{represented} capability types, "
        f"{len({resource.category for resource in expanded.resources})} categories, "
        f"{len(expanded.tasks)} tasks unchanged"
    )


if __name__ == "__main__":
    main()
