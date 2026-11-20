"""Generated discovery metadata stays synthetic, repeatable, and referentially safe."""

from collections import Counter, defaultdict
from pathlib import Path

import pytest

from paid_tool_rl.dataset_schema import WorkspaceDocument
from paid_tool_rl.discovery_generator import (
    PROVIDER_NAMES,
    extend_discovery_index,
    generate_discovery_listing,
    load_discovery_capabilities,
    rebalance_discovery_index,
)


@pytest.fixture
def original_workspace():
    document = WorkspaceDocument.model_validate_json(
        Path("datasets/workspace.json").read_bytes()
    )
    return document.model_copy(update={"resources": document.resources[:10]})


@pytest.fixture
def capabilities():
    return load_discovery_capabilities()


def test_discovery_expansion_preserves_existing_records_and_tasks(
    original_workspace,
    capabilities,
):
    expanded = extend_discovery_index(original_workspace, capabilities)
    assert len(expanded.resources) == 1000
    assert expanded.resources[:10] == original_workspace.resources
    assert expanded.tasks == original_workspace.tasks
    assert len({resource.id for resource in expanded.resources}) == 1000
    assert len({resource.name for resource in expanded.resources}) == 1000
    assert (
        len(
            {
                (resource.hostname, resource.method, resource.path_pattern)
                for resource in expanded.resources
            }
        )
        == 1000
    )
    assert len(original_workspace.resources) == 10


def test_discovery_generation_is_repeatable_and_preserves_author_edits(
    original_workspace,
    capabilities,
):
    expanded = extend_discovery_index(original_workspace, capabilities)
    assert expanded == extend_discovery_index(original_workspace, capabilities)
    expanded.resources[10].name = "Author-edited resource"
    assert extend_discovery_index(expanded, capabilities) == expanded
    assert expanded.resources[10].name == "Author-edited resource"


def test_generated_metadata_is_coherent_and_varied(original_workspace, capabilities):
    generated = extend_discovery_index(original_workspace, capabilities).resources[10:]
    assert len(generated) == 990
    assert len({resource.category for resource in generated}) == 50
    assert len({resource.price_units for resource in generated}) >= 10
    assert any(resource.price_units == 0 for resource in generated)
    assert {resource.method for resource in generated} == {"GET", "POST"}
    domain_dates = defaultdict(set)
    for resource in generated:
        assert "synthetic" in resource.tags
        assert resource.hostname.endswith(".example")
        assert resource.domain_created is not None
        assert resource.last_persistent_change is not None
        assert resource.last_change is not None
        assert (
            resource.domain_created
            <= resource.last_persistent_change
            <= resource.last_change
            <= original_workspace.as_of
        )
        assert (
            resource.domain_age_days
            == (original_workspace.as_of - resource.domain_created).days
        )
        domain_dates[resource.hostname].add(resource.domain_created)
    assert all(len(dates) == 1 for dates in domain_dates.values())


def test_generation_refuses_to_silently_delete_resources(
    original_workspace,
    capabilities,
):
    with pytest.raises(ValueError, match="refusing to delete"):
        extend_discovery_index(original_workspace, capabilities, target_count=5)


def test_generation_reports_insufficient_unique_templates(original_workspace):
    with pytest.raises(ValueError, match="enough unique listings"):
        extend_discovery_index(original_workspace, [])


def test_catalog_has_distinct_capabilities_not_only_provider_variants(capabilities):
    assert len(capabilities) == 200
    assert len({capability.category for capability in capabilities}) == 50
    assert len({capability.id for capability in capabilities}) == 200
    assert len({capability.name for capability in capabilities}) == 200
    assert (
        len(
            {
                (capability.method, capability.path_pattern)
                for capability in capabilities
            }
        )
        == 200
    )
    assert all(
        capability.description
        and capability.tags
        and capability.sample_input
        and capability.sample_output
        for capability in capabilities
    )


def test_generation_covers_all_capabilities_before_repeating_providers(
    original_workspace,
    capabilities,
):
    expanded = extend_discovery_index(original_workspace, capabilities)
    capability_for_id = {
        f"synthetic-{capability.id}-{provider.lower()}": capability.id
        for capability in capabilities
        for provider in PROVIDER_NAMES
    }
    counts = Counter(
        capability_for_id[resource.id] for resource in expanded.resources[10:]
    )
    assert len(counts) == 200
    assert set(counts.values()) <= {4, 5}
    assert (
        len({capability_for_id[resource.id] for resource in expanded.resources[10:210]})
        == 200
    )


@pytest.fixture
def legacy_workspace(original_workspace, capabilities):
    resources = [
        generate_discovery_listing(capability, provider, original_workspace)
        for capability in capabilities[:30]
        for provider in PROVIDER_NAMES
    ]
    return original_workspace.model_copy(
        update={
            "resources": [*original_workspace.resources, *resources],
        }
    )


def test_rebalance_broadens_an_existing_full_index_idempotently(
    legacy_workspace,
    capabilities,
):
    assert len(legacy_workspace.resources) == 1000
    assert len({r.category for r in legacy_workspace.resources}) == 13
    expanded = rebalance_discovery_index(legacy_workspace, capabilities)
    assert len(expanded.resources) == 1000
    assert len({r.category for r in expanded.resources}) == 50
    assert expanded.resources[:10] == legacy_workspace.resources[:10]
    assert expanded.tasks == legacy_workspace.tasks
    assert rebalance_discovery_index(expanded, capabilities) == expanded


def test_rebalance_preserves_edited_and_task_linked_generated_resources(
    legacy_workspace,
    capabilities,
):
    edited = legacy_workspace.resources[100]
    edited.name = "Author-edited listing"
    linked = legacy_workspace.resources[200]
    task = legacy_workspace.tasks[0]
    task.resource_ids.append(linked.id)
    task.resource_responses[linked.id] = {"task_specific": True}
    expanded = rebalance_discovery_index(legacy_workspace, capabilities)
    by_id = {resource.id: resource for resource in expanded.resources}
    assert by_id[edited.id] == edited
    assert by_id[linked.id] == linked
    assert expanded.tasks == legacy_workspace.tasks
    assert len(expanded.resources) == 1000
    assert len({resource.category for resource in expanded.resources}) == 50
