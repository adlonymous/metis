# Metis

A custom reinforcement learning environment for training models to become better agentic economic actors. Metis is inspired by Prime Intellect's environment ecosystem and built on [Verifiers v1](https://github.com/PrimeIntellect-ai/verifiers).

An agent receives a task and a budget, discovers external data resources, purchases useful information, and decides whether it needs another resource before answering. The environment scores task success and spending separately.

All resources, telemetry, responses, and payments are synthetic. There is no live x402 settlement, wallet access, or paid API execution.

## Quick start

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/adlonymous/metis.git
cd metis
uv sync --locked
scripts/smoke
```

The smoke command runs all six tasks through the native Verifiers harness, real MCP tool subprocesses, state synchronization, scoring, and trace persistence. Its local OpenAI-compatible endpoint is a scripted reference policy that knows the purchase path and calculates answers from purchased results. It is not an LLM, a pre-RL baseline, or evidence of learning. It uses no GPU, model credentials, or paid compute.

## Environment

The `metis` taskset loads `datasets/workspace.json` in a source checkout. Installed wheels include a snapshot of that file. A custom workspace can be selected with `--env.taskset.dataset /path/to/workspace.json`.

The directory contains 1,000 listings covering 200 capability types across 50 categories. The six authored tasks exercise finance, currency conversion, weather, logistics, customs, lodging, and transit, including complementary purchases.

The agent starts with the request, budget, action limit, directory size, and category names. It does not receive fixture-resource IDs, expected answers, reference purchase paths, or all 1,000 listings in its prompt.

| Tool                     | Behavior                                                            |
| ------------------------ | ------------------------------------------------------------------- |
| `metis_search_resources` | Free lexical search over public metadata, paginated up to 20 rows   |
| `metis_inspect_resource` | Free full listing, including historical metadata and public samples |
| `metis_purchase`         | Authorize the quoted price and reveal a synthetic result            |
| `metis_finish`           | Submit the requested answer as a string and end the episode         |

All four actions consume the task's action limit. Purchases cannot exceed the remaining budget. Repeating a purchase returns the cached result without a second debit. A known resource without a task-specific fixture charges its listed price and returns `no_matching_data`. An unknown ID or an unaffordable purchase is rejected without charging.

The default harness is Verifiers' MCP-capable `NullHarness`, not a coding agent. It exposes no shell or arbitrary HTTP tool. The task-scoped tool server serializes the full state synchronization cycle, so concurrent tool calls cannot overwrite the ledger.

## Reward and grading

```text
reward = success - cost_weight * (spent_units / max(initial_budget_units, 1))
```

`cost_weight` defaults to `0.15` and can be set with `--env.taskset.task.cost-weight`. It must be less than 1, so any correctly completed, affordable episode beats a free wrong answer.

Success uses exact trimmed text or equivalent decimal values. For example, `55.2` matches `55.20`; properly grouped numeric commas are accepted. Prose explanations, claimed rewards, and malformed numbers do not count as an answer. The agent must submit through `metis_finish`; simply stopping with text is recorded as unanswered.

Metrics include success, spending, remaining budget, cost fraction, action count, purchase count, budget rejections, invalid resource/page actions, and answer submission. MCP schema errors are bounded by the model-turn cap, not counted as successful environment actions.

## Evaluate a model

Use an OpenAI-compatible endpoint serving a tool-capable model. No base model has been selected or evaluated yet. Resource budgets do not cap model-provider inference fees; remote evaluation endpoints may charge separately.

1. Edit the model ID and endpoint in `configs/eval.toml`.
2. Copy `.env.example` to `.env`. Set `METIS_API_KEY` there if the endpoint requires authentication.
3. Run:

```bash
uv run --env-file .env vf-run @ configs/eval.toml
```

The example uses the validation split and explicitly selects a local subprocess runtime. It does not start a model server, rent GPUs, or run training. Do not omit the runtime setting: the pinned framework otherwise defaults to Prime sandboxes.

For a one-task check without a config file:

```bash
uv run vf-run metis -m YOUR_SERVED_MODEL -n 1 -r 1 \
  --client.base-url http://127.0.0.1:8000/v1 \
  --client.api-key-var METIS_API_KEY \
  --env.agent.runtime.type subprocess
```

Install the package in the orchestrator and environment-worker Python environments when using [Prime-RL](https://github.com/PrimeIntellect-ai/prime-rl). It exposes native v1 task, metric, reward, and toolset interfaces. Actual weight updates, training performance, and single-GPU compatibility have not been tested.

## Traces

Verifiers writes resolved configuration and `traces.jsonl` beneath `outputs/<run-name>/`. Each episode includes model messages, tool calls/results, model-call timing and usage when reported by the endpoint, reward, and metrics.

`trace.info.metis` preserves the ordered economic actions, paid observations, charges, remaining budget after each action, final answer, and termination reason. The native trace also contains evaluator-owned task data. Feed model messages, not the entire saved trace, back to a policy; never expose the reference fields as observations.

The scripted smoke endpoint has no real token usage. Its traces verify recording infrastructure, not model cost or quality.

## Dataset editor

The optional local editor requires Node.js 22.12+ and npm:

```bash
scripts/setup
scripts/editor
```

Open http://127.0.0.1:8765. Create/edit resource metadata, tasks, budgets, response fixtures, and reference purchase paths; inspect the initial agent observation; validate and save to disk. New runs load saved edits; in-flight episodes keep their original data. Draft tasks are excluded from execution.

The editor is for trusted local authors and must stay on loopback. It intentionally exposes evaluator-owned data to the author, not to an agent. It is not an authenticated public application.

## Checks and packaging

```bash
scripts/setup
scripts/check
uv build
```

Checks include Python/frontend lint and types, unit tests, local Verifiers setup/noop validation, frontend production build, and the native scripted integration run. Python-only users can run `uv run pytest` and `scripts/smoke` without installing the editor.

Technical agent instructions are in [AGENTS.md](AGENTS.md). Dataset provenance, generation, and authoring conventions are in [datasets/README.md](datasets/README.md).

## Limitations

- Six hand-authored tasks are smoke cases, not a benchmark. Split labels are editable and have not been frozen or audited for generalization.
- Resources have static task-specific responses. There is no request-dependent routing, enforced query prerequisite chain, latency simulation, or sampled provider failure distribution. Discovery metadata is descriptive synthetic data, not calibrated evidence of outcome quality.
- The directory is broad, but only the resources with authored fixtures return task-specific data. More realistic tasks and provider coverage are needed before drawing conclusions about economic behavior.
- Exact-answer grading does not prove that purchased data supports the answer. Inspect trajectories for guesses, shortcuts, and sample leakage.
- No trained model, measured improvement, frontier-model comparison, real purchasing, or x402 protocol conformance is claimed.

## License

Code and documentation outside `datasets/` are [MIT](LICENSE). Synthetic data and its documentation under `datasets/` are [CC0 1.0](datasets/LICENSE). Third-party dependencies retain their own licenses. Metis is an independent project, not an official Prime Intellect product.
