import type { DatasetTask, WorkspaceDocument } from './dataset-contract';
import { buildAgentPreview, resourceCostLabel, toggleTaskResource } from './dataset-editing';
import { EditorField, EditorJson, EditorSection, EditorSelect, EditorText } from './editor-fields';
import type { JsonEditing } from './editor-fields';

export type TaskEditorTab = 'Task' | 'Resources' | 'Hidden data' | 'Agent preview';
interface TaskProps {
  task: DatasetTask;
  document: WorkspaceDocument;
  tab: TaskEditorTab;
  onChange: (task: DatasetTask) => void;
  editing: JsonEditing;
}

/** Public task instructions and evaluator-only data live in separate editing tabs. */
export function TaskEditor({ task, document, tab, onChange, editing }: TaskProps) {
  function update<K extends keyof DatasetTask>(key: K, value: DatasetTask[K]) {
    onChange({ ...task, [key]: value });
  }
  const available = document.resources.filter(resource => task.resource_ids.includes(resource.id));
  const referenceIds = new Set(task.reference_purchases.map(step => step.resource_id));
  const referenceCost = available.filter(resource => referenceIds.has(resource.id)).reduce((sum, resource) => sum + resource.price_units, 0);
  if (tab === 'Agent preview') return <AgentPreview document={document} task={task} />;
  if (tab === 'Resources') return <>
    <EditorSection title="Task-specific resource fixtures" hint="All directory listings are discoverable. Checked resources have task-specific paid responses; other purchases return no matching data and may still charge. Removing a link removes its response and reference steps.">
      <div className="resource-checklist">{document.resources.map(resource => <label className="resource-option" key={resource.id}>
        <input type="checkbox" checked={task.resource_ids.includes(resource.id)} onChange={() => onChange(toggleTaskResource(task, resource.id))} />
        <span><span className="resource-option-title">{resource.name}<span className="price">{resourceCostLabel(resource.price_units)}</span></span>
          <span className="resource-option-detail">{resource.description}</span><code>{resource.id}</code></span>
      </label>)}</div>
      {document.resources.length === 0 && <p className="empty-inline">Create a resource in the discovery index before linking it to a task.</p>}
    </EditorSection>
    <EditorSection title="Reference purchase path" hint="An author-only example of how to solve the task. This is not shown to the agent or used as a required purchase sequence.">
      <div className={`reference-summary ${referenceCost > task.budget_units ? 'over-budget' : ''}`}>
        <span>{task.reference_purchases.length} purchases</span><span>{referenceCost} / {task.budget_units} budget units</span>
      </div>
      {task.reference_purchases.map((step, index) => <div className="reference-step" key={index}>
        <div className="step-heading"><span className="step-number">{index + 1}</span><span>{document.resources.find(resource => resource.id === step.resource_id)?.name}</span>
          <button className="quiet-button" disabled={index === 0} onClick={() => {
            const steps = [...task.reference_purchases];
            [steps[index - 1], steps[index]] = [steps[index], steps[index - 1]];
            update('reference_purchases', steps);
          }} aria-label={`Move purchase ${index + 1} earlier`}>Move up</button>
          <button className="quiet-button" onClick={() => update('reference_purchases', task.reference_purchases.filter((_, i) => i !== index))} aria-label={`Remove purchase ${index + 1}`}>Remove</button></div>
        <EditorSelect label="Resource" value={step.resource_id} options={task.resource_ids} onChange={value => update('reference_purchases', task.reference_purchases.map((item, i) => i === index ? { ...item, resource_id: value } : item))} />
        <EditorText label="Why this purchase is needed" value={step.purpose} onChange={value => update('reference_purchases', task.reference_purchases.map((item, i) => i === index ? { ...item, purpose: value } : item))} rows={2} />
      </div>)}
      <button className="secondary-button fit" disabled={available.length === 0} onClick={() => update('reference_purchases', [...task.reference_purchases, { resource_id: available[0].id, purpose: '' }])}>Add purchase step</button>
    </EditorSection>
  </>;
  if (tab === 'Hidden data') return <>
    <div className="privacy-notice"><span className="status-badge private">Evaluator only</span><p>These records are not part of the initial agent observation. The runtime reveals a task-specific response only after a purchase.</p></div>
    <EditorSection title="Expected answer" hint="The runtime checks exact text or equivalent decimal values. This is not an LLM judge.">
      <EditorText label="Canonical answer" value={task.expected_answer} onChange={value => update('expected_answer', value)} rows={2} />
      <EditorText label="Grading notes" value={task.grading_notes} onChange={value => update('grading_notes', value)} />
    </EditorSection>
    <EditorSection title="Purchased responses" hint="One synthetic response per linked resource. The editor does not execute requests or prove that these outputs support the answer.">
      {available.map(resource => <div className="response-section" key={resource.id}>
        <div className="response-heading"><h4>{resource.name}</h4><span className="price">{resourceCostLabel(resource.price_units)}</span></div>
        <EditorJson label={`${resource.name} response`} fieldKey={`task:${task.id}:${resource.id}`} value={task.resource_responses[resource.id]} editing={editing}
          onChange={value => update('resource_responses', { ...task.resource_responses, [resource.id]: value })} />
      </div>)}
      {available.length === 0 && <p className="empty-inline">Link a resource in the Resources tab to author its hidden response.</p>}
    </EditorSection>
  </>;
  return <>
    <EditorSection title="Task definition" hint="Give the agent a clear goal that requires external information.">
      <EditorField label="Title" value={task.title} onChange={event => update('title', event.target.value)} />
      <EditorText label="User request" value={task.prompt} onChange={value => update('prompt', value)} rows={5} hint="The goal the agent receives. Do not reveal the expected answer or purchase path." />
      <div className="field-grid"><EditorField label="Category" value={task.category} onChange={event => update('category', event.target.value)} />
        <EditorField label="Stable task ID" value={task.id} readOnly className="mono" /></div>
    </EditorSection>
    <EditorSection title="Episode constraints" hint="The runtime enforces the budget and counts discovery, inspection, purchase, and finish actions.">
      <div className="field-grid"><EditorField label="Budget (units)" type="number" min="0" step="1" value={task.budget_units} onChange={event => update('budget_units', Number(event.target.value))} />
        <EditorField label="Action limit" type="number" min="2" max="100" step="1" value={task.max_actions} onChange={event => update('max_actions', Number(event.target.value))} hint="Include the final-answer action." /></div>
    </EditorSection>
    <EditorSection title="Dataset assignment" hint="These are editable authoring labels, not frozen or leakage-audited benchmark splits.">
      <div className="field-grid"><EditorSelect label="Split" value={task.split} options={['train', 'validation', 'test']} onChange={value => {
        if (value === 'train' || value === 'validation' || value === 'test') update('split', value);
      }} />
        <EditorSelect label="Review status" value={task.status} options={['draft', 'review', 'ready']} onChange={value => {
          if (value === 'draft' || value === 'review' || value === 'ready') update('status', value);
        }} /></div>
    </EditorSection>
    <div className="task-brief"><h3>Resource plan</h3><p>{task.resource_ids.length} task-specific fixtures · {task.reference_purchases.length} reference purchases · {referenceCost} units reference cost</p><p className="muted">Use Resources to edit task-specific fixtures and the reference purchase path. Keep answers and purchased outputs in Hidden data.</p></div>
  </>;
}

interface PreviewProps { document: WorkspaceDocument; task: DatasetTask }

/** The preview whitelists public inputs instead of hiding private fields with CSS. */
function AgentPreview({ document, task }: PreviewProps) {
  const preview = buildAgentPreview(document, task);
  return <>
    <div className="privacy-notice public"><span className="status-badge ready">Agent visible</span><p>The initial observation only. Expected answers, hidden responses, grading notes, split labels, and reference purchases are excluded.</p></div>
    <EditorSection title="User request"><p className="prompt-preview">{task.prompt || 'No request written yet.'}</p>
      <div className="preview-constraints"><span>Budget <strong>{task.budget_units} units</strong></span><span>Action limit <strong>{task.max_actions}</strong></span></div>
    </EditorSection>
    <EditorSection title="Discovery index" hint={`${preview.directory.resource_count} resources searchable through paginated discovery.`}>
      <p className="muted">Listings are not included in the initial prompt. The agent uses <code>{preview.directory.search_tool}</code> and <code>{preview.directory.inspect_tool}</code> to discover them without seeing which have task-specific fixtures.</p>
      <p className="muted">Categories: {preview.directory.categories.join(', ')}</p>
    </EditorSection>
    <details className="raw-preview"><summary>View complete agent observation as JSON</summary><pre>{JSON.stringify(preview, null, 2)}</pre></details>
  </>;
}
