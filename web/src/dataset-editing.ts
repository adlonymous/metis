import type { AgentObservation, DatasetTask, ResourceListing, WorkspaceDocument } from './dataset-contract';

/** Match the runtime's initial observation without disclosing fixture-resource IDs. */
export function buildAgentPreview(document: WorkspaceDocument, task: DatasetTask): AgentObservation {
  return {
    task: task.prompt,
    budget_units: task.budget_units,
    max_actions: task.max_actions,
    directory: {
      resource_count: document.resources.length,
      snapshot_date: document.as_of,
      categories: [...new Set(document.resources.map(resource => resource.category))].sort(),
      search_tool: 'metis_search_resources',
      inspect_tool: 'metis_inspect_resource',
    },
  };
}

/** New records use stable IDs; reference editing never silently renames them. */
export function createResourceListing(id: string): ResourceListing {
  return {
    id, name: 'Untitled resource', category: 'Research', description: '', tags: [],
    price_units: 1, hostname: 'resource.metis.example', method: 'GET', path_pattern: '/v1/resource',
    post_payment_success_rate: null, availability_7d: null,
    latency_p50_ms: null, latency_p90_ms: null, domain_created: null, domain_age_days: null,
    top_countries: [], last_change: null, last_persistent_change: null,
    sample_input: {}, sample_output: {},
  };
}

/** Draft tasks can be saved incomplete, while ready tasks face stronger validation. */
export function createDatasetTask(id: string): DatasetTask {
  return {
    id, title: 'Untitled task', category: 'Research', split: 'train', status: 'draft',
    prompt: '', budget_units: 10, max_actions: 8, resource_ids: [],
    resource_responses: {}, reference_purchases: [], expected_answer: '', grading_notes: '',
  };
}

/** Linking and unlinking resources updates hidden fixture keys in the same edit. */
export function toggleTaskResource(task: DatasetTask, resourceId: string): DatasetTask {
  if (task.resource_ids.includes(resourceId)) {
    const responses = { ...task.resource_responses };
    delete responses[resourceId];
    return {
      ...task,
      resource_ids: task.resource_ids.filter(id => id !== resourceId),
      resource_responses: responses,
      reference_purchases: task.reference_purchases.filter(step => step.resource_id !== resourceId),
    };
  }
  return {
    ...task, resource_ids: [...task.resource_ids, resourceId],
    resource_responses: { ...task.resource_responses, [resourceId]: {} },
  };
}

/** Resource deletion is blocked until task authors explicitly remove all links. */
export function resourceTaskLinks(document: WorkspaceDocument, resourceId: string) {
  return document.tasks.filter(task => task.resource_ids.includes(resourceId));
}

/** Prices are integer simulation units, not fiat or token amounts. */
export function resourceCostLabel(units: number) {
  return units === 0 ? 'Free' : `${units} units`;
}
