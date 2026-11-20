# Metis authoring dataset

`workspace.json` is the editor's versioned source file. It contains 1,000 fictional resource listings and 6 illustrative external-data tasks. All endpoints, historical telemetry, sample outputs, and task responses are synthetic. No directory listings were scraped or live requests made.

The records demonstrate finance, weather, logistics, trade, travel, and research tasks, including complementary purchases. They are a starting point for authoring, not a benchmark or evidence of model performance.

## Discovery index generation

Run `scripts/generate-index` to rebalance the index to 1,000 entries. Curated records, author edits, task-linked listings, and all task records are preserved. Only untouched, unlinked generated listings may be replaced. Re-running against unchanged catalogs is byte-for-byte idempotent; the script refuses to delete preserved records to make room.

The catalog defines 200 distinct capabilities across 50 categories. `resource_capabilities.json` retains the original 30 templates; `resource_capabilities_extended.json` adds 170 capabilities. Each has its own operation, description, request example, and response example. The generator is `src/paid_tool_rl/discovery_generator.py`.

Generation visits every capability before adding another provider round, rotating through 33 fictional provider profiles. The current index retains the original 10 listings, plus 990 generated listings: four or five variants per capability, rather than 33 variants of only 30 capabilities. The same total of 1,000 resources therefore covers all 200 capability types and 50 categories.

Categories now also include healthcare, public health, clinical research, pharmaceutical data, nutrition, agriculture, food safety, fisheries, biodiversity, land use, environment, air quality, water, ocean, geology, mining, aviation, satellite imagery, maritime, automotive, road mobility, cycling, insurance, banking, payments, blockchain data, cybersecurity, telecommunications, internet infrastructure, cloud infrastructure, education, culture, sports, events, media, language, and accessibility.

Generated IDs and metadata retain stable version-1 seeds and the workspace snapshot date. Provider domain dates are consistent across endpoints. Listings vary in coverage, snapshot freshness, price, reliability, latency, domain history, and request origins. These are authored synthetic capabilities, not independently researched services or verified live APIs.

Every task can discover all 1,000 listings. The six tasks retain small sets of task-specific response fixtures. Buying any other known listing charges its quoted price and returns `no_matching_data`; task relevance is not exposed as a free purchase error. To supply useful data for another listing, link it to the task and author its paid response.

## Public and private data

- Resource listings are public discovery information, including generic sample inputs/outputs.
- Initial observations contain task prompts, budgets, action limits, directory size, snapshot date, category names, and discovery tool names. Listings are retrieved through paginated search and inspection, not dumped into the prompt.
- Task-specific fixture-resource IDs, purchased responses, expected answers, reference purchase paths, and grading notes are evaluator-only data. Resource reliability metadata is not used as an oracle for these fixture outcomes.
- The local authoring API intentionally exposes the complete workspace to its human editor. It is not an agent-facing API or a confidentiality boundary against the editor user.

The preview whitelists public fields. Authors must still inspect public samples for answer leakage. Structural validation does not prove task solvability, answer correctness, or multi-step dependence.

## Conventions

- Prices are nonnegative integer simulation units, not real currencies or token prices.
- Reliability and availability are fractions between 0 and 1, displayed as percentages by the UI.
- Latencies are in milliseconds; change history uses calendar dates, not precise timestamps.
- Country shares refer to request origins, not resource coverage. Listed shares may total less than 1.
- Domain creation and recorded age may be unknown. The snapshot date provides historical context.
- Stable record IDs are not editable in the UI. Duplicate a record to create a new ID.
- `resource_ids` links task-specific fixtures, not an exclusive directory allowlist. Each linked resource has one static JSON response. Request-dependent routing, query prerequisites, latency simulation, and sampled provider failures remain future work.
- Reference purchases are author documentation, not agent-visible instructions or a required policy.
- Split/status fields are editable labels. These six examples have not been frozen, audited for leakage, or reviewed as evaluation data.

## Validation and persistence

The canonical contract is `src/paid_tool_rl/dataset_schema.py`. Frontend types are generated from its serialized schema with `scripts/generate-types`; do not edit `web/src/dataset-contract.d.ts` directly.

The server validates writes, compares the loaded file revision, and atomically replaces the JSON file. An invalid write or stale editor tab leaves the existing file untouched. This protects saves inside a single editor-server process; do not run multiple servers against the same file.

The saved dataset is consumed by the native `metis` Verifiers taskset. Draft tasks are excluded. Installed wheels bundle a snapshot; source checkouts load this file, or an explicit `--env.taskset.dataset` override. Scripted reference rollouts verify these six episodes, not model performance or weight updates. They are smoke cases, not training/evaluation data of established statistical validity.

All files under `datasets/` are dedicated under [CC0 1.0](LICENSE). They are fictional data, not medical, legal, financial, operational, or navigation advice.
