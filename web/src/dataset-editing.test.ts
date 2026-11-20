import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import type { WorkspaceDocument } from './dataset-contract';
import { buildAgentPreview, createDatasetTask, createResourceListing, resourceTaskLinks, toggleTaskResource } from './dataset-editing.ts';

const document: WorkspaceDocument = JSON.parse(readFileSync(new URL('../../datasets/workspace.json', import.meta.url), 'utf8'));

test('agent preview includes directory access but never fixture-resource IDs', () => {
  const task = document.tasks[0];
  const preview = buildAgentPreview(document, task);
  assert.deepEqual(Object.keys(preview).sort(), ['budget_units', 'directory', 'max_actions', 'task']);
  assert.equal(preview.directory.resource_count, 1000);
  assert.equal(preview.directory.categories.length, 50);
  assert.equal(preview.directory.search_tool, 'metis_search_resources');
  assert.equal(Object.hasOwn(preview, 'resource_ids'), false);
  assert.equal(JSON.stringify(preview).includes(task.expected_answer), false);
  assert.equal(JSON.stringify(preview).includes('reference_purchases'), false);
});

test('unlinking removes corresponding private fixtures and reference steps', () => {
  const task = structuredClone(document.tasks[0]);
  const resourceId = task.reference_purchases[0].resource_id;
  const edited = toggleTaskResource(task, resourceId);
  assert.equal(edited.resource_ids.includes(resourceId), false);
  assert.equal(Object.hasOwn(edited.resource_responses, resourceId), false);
  assert.equal(edited.reference_purchases.some(step => step.resource_id === resourceId), false);
  assert.equal(task.resource_ids.includes(resourceId), true);
});

test('linking creates exactly one hidden response slot', () => {
  const task = createDatasetTask('new-task');
  const edited = toggleTaskResource(task, 'filings');
  assert.deepEqual(edited.resource_ids, ['filings']);
  assert.deepEqual(edited.resource_responses, { filings: {} });
  assert.deepEqual(toggleTaskResource(edited, 'filings').resource_ids, []);
});

test('resource links protect referenced records from deletion', () => {
  assert.ok(resourceTaskLinks(document, 'fx-spot').length > 0);
  assert.equal(resourceTaskLinks(document, 'not-linked').length, 0);
});

test('new records are synthetic and start with safe draft defaults', () => {
  const resource = createResourceListing('new-resource');
  const task = createDatasetTask('new-task');
  assert.ok(resource.hostname.endsWith('.example'));
  assert.equal(task.status, 'draft');
  assert.deepEqual(task.resource_responses, {});
});
