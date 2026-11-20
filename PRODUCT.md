# Metis

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

React and TypeScript editor, local Python API, and repository JSON storage, approved by the user. Existing RL package uses Python 3.12 and Verifiers v1.

## Users

Environment authors building and inspecting a public RL taskset and resource discovery index.

## Product Purpose

Metis is a custom environment inspired by Prime Intellect's tooling for training models as agentic economic actors. Agents buy external information, observe the results, and may purchase complementary resources to complete a task within a budget.

## Operating Context

The editor authors resources and tasks consumed by a native Verifiers v1 runtime. Authors need to inspect listings, edit metadata, link task resources, author hidden outputs and correct answers, validate data, and preview the agent-visible inputs.

## Capabilities and Constraints

- Save edits as JSON files on disk, not only browser state.
- Resource metadata includes descriptions, tags, price, endpoint details, historical reliability, latency, domain age, request-origin countries, change history, and sample inputs/outputs.
- Separate public resource listings from evaluator-only responses and answers.
- Begin with a few clearly labeled synthetic examples of external-data tasks, not a claimed research benchmark.
- The `metis` taskset loads saved authoring data. All 1,000 listings are searchable; six authored cases have task-specific response fixtures. Reference workflows are not model benchmarks.
- Local single-user operation without authentication, purchases, or training controls was proposed and approved.

## Brand Commitments

The project is called Metis. Public positioning is an agentic economic environment, not a learning project. The user approved a restrained, data-dense interface with clear forms.

## Evidence on Hand

The public runtime lives in `src/metis/`, alongside shared authoring code in `src/paid_tool_rl/`. Native MCP reference rollouts and regression tests verify infrastructure. No actual model baseline, model improvement results, validated benchmark, or production resource directory is claimed.
