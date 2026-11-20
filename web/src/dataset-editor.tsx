import { useEffect, useState } from 'react';
import type { DatasetTask, JsonValue, ResourceListing, WorkspaceDocument, WorkspaceEnvelope } from './dataset-contract';
import { createDatasetTask, createResourceListing, resourceTaskLinks } from './dataset-editing';
import { requestDataset, saveDataset } from './editor-api';
import { EditorField, EditorIcon, EditorSection, EditorText } from './editor-fields';
import type { JsonEditing } from './editor-fields';
import { ResourceEditor } from './resource-editor';
import { TaskEditor } from './task-editor';
import type { TaskEditorTab } from './task-editor';

type WorkspaceView = 'tasks' | 'resources' | 'validation';
interface ValidationReport { valid: boolean; warnings: string[] }

/** Local authoring shell: edits stay in memory until an explicit atomic save. */
export function DatasetEditor() {
  const [saved, setSaved] = useState<WorkspaceEnvelope | null>(null);
  const [document, setDocument] = useState<WorkspaceDocument | null>(null);
  const [view, setView] = useState<WorkspaceView>('tasks');
  const [taskId, setTaskId] = useState('');
  const [resourceId, setResourceId] = useState('');
  const [taskTab, setTaskTab] = useState<TaskEditorTab>('Task');
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [warnings, setWarnings] = useState<string[]>([]);
  const [jsonDrafts, setJsonDrafts] = useState(new Map<string, string>());
  const [jsonErrors, setJsonErrors] = useState(new Map<string, string>());
  const dirty = document !== null && saved !== null && (JSON.stringify(document) !== JSON.stringify(saved.document) || jsonDrafts.size > 0);

  async function loadWorkspace() {
    setBusy(true);
    const result = await requestDataset<WorkspaceEnvelope>('/api/workspace');
    setBusy(false);
    if (!result.ok) { setError(result.error); return; }
    setSaved(result.value); setDocument(result.value.document); setWarnings(result.value.warnings);
    setTaskId(result.value.document.tasks[0]?.id ?? '');
    setResourceId(result.value.document.resources[0]?.id ?? '');
    setError(''); setMessage(''); setJsonDrafts(new Map()); setJsonErrors(new Map());
  }
  useEffect(() => { void loadWorkspace(); }, []);
  useEffect(() => {
    function warnBeforeLeaving(event: BeforeUnloadEvent) { if (dirty) event.preventDefault(); }
    window.addEventListener('beforeunload', warnBeforeLeaving);
    return () => window.removeEventListener('beforeunload', warnBeforeLeaving);
  }, [dirty]);

  function changeDocument(next: WorkspaceDocument) { setDocument(next); setMessage(''); setError(''); }
  function selectView(next: WorkspaceView) { setView(next); setSearch(''); setFilter('all'); }
  function editTask(next: DatasetTask) {
    if (document) changeDocument({ ...document, tasks: document.tasks.map(task => task.id === next.id ? next : task) });
  }
  function editResource(next: ResourceListing) {
    if (document) changeDocument({ ...document, resources: document.resources.map(resource => resource.id === next.id ? next : resource) });
  }
  const editing: JsonEditing = {
    drafts: jsonDrafts, errors: jsonErrors,
    edit(key, text, apply) {
      setJsonDrafts(previous => new Map(previous).set(key, text));
      setMessage('');
      try {
        const value: JsonValue = JSON.parse(text);
        apply(value);
        setJsonErrors(previous => { const next = new Map(previous); next.delete(key); return next; });
      } catch (caught) {
        setJsonErrors(previous => new Map(previous).set(key, caught instanceof Error ? caught.message : 'Enter valid JSON.'));
      }
    },
  };
  async function saveWorkspace() {
    if (!document || !saved || jsonErrors.size) return;
    setBusy(true); setError('');
    const result = await saveDataset(document, saved.revision);
    setBusy(false);
    if (!result.ok) { setError(result.error); setMessage(''); return; }
    setSaved(result.value); setDocument(result.value.document); setWarnings(result.value.warnings);
    setJsonDrafts(new Map()); setJsonErrors(new Map()); setMessage('Workspace saved to datasets/workspace.json.');
  }
  async function validateWorkspace() {
    if (!document) return;
    if (jsonErrors.size) { setError('Fix the invalid JSON fields before validating. Your edits have not been discarded.'); return; }
    setBusy(true); setError('');
    const result = await requestDataset<ValidationReport>('/api/validate', 'POST', JSON.stringify(document));
    setBusy(false);
    if (!result.ok) { setError(result.error); setMessage(''); return; }
    setWarnings(result.value.warnings);
    setMessage(`Schema and resource links are valid. ${result.value.warnings.length} authoring warnings. This does not verify solvability or benchmark quality.`);
  }
  function addRecord(duplicate = false) {
    if (!document) return;
    const id = `${view === 'tasks' ? 'task' : 'resource'}-${crypto.randomUUID().slice(0, 8)}`;
    if (view === 'tasks') {
      const original = document.tasks.find(task => task.id === taskId);
      const next = duplicate && original ? { ...structuredClone(original), id, title: `${original.title} (copy)`, status: 'draft' as const } : createDatasetTask(id);
      changeDocument({ ...document, tasks: [...document.tasks, next] }); setTaskId(id); setTaskTab('Task');
    } else {
      const original = document.resources.find(resource => resource.id === resourceId);
      const next = duplicate && original ? { ...structuredClone(original), id, name: `${original.name} (copy)` } : createResourceListing(id);
      changeDocument({ ...document, resources: [...document.resources, next] }); setResourceId(id);
    }
    setSearch(''); setFilter('all');
  }
  function deleteRecord() {
    if (!document) return;
    const id = view === 'tasks' ? taskId : resourceId;
    const links = view === 'resources' ? resourceTaskLinks(document, id) : [];
    if (links.length) { setError(`Cannot delete this resource: linked to ${links.map(task => task.title).join(', ')}. Remove those task links first.`); return; }
    if (!window.confirm(`Delete ${id}? The deletion reaches disk only when you save the workspace.`)) return;
    if (view === 'tasks') {
      const tasks = document.tasks.filter(task => task.id !== id);
      changeDocument({ ...document, tasks }); setTaskId(tasks[0]?.id ?? '');
    } else {
      const resources = document.resources.filter(resource => resource.id !== id);
      changeDocument({ ...document, resources }); setResourceId(resources[0]?.id ?? '');
    }
    setJsonDrafts(previous => new Map([...previous].filter(([key]) => !key.startsWith(`${view === 'tasks' ? 'task' : 'resource'}:${id}:`))));
    setJsonErrors(previous => new Map([...previous].filter(([key]) => !key.startsWith(`${view === 'tasks' ? 'task' : 'resource'}:${id}:`))));
  }
  const selectedTask = document?.tasks.find(task => task.id === taskId);
  const selectedResource = document?.resources.find(resource => resource.id === resourceId);
  const query = search.toLowerCase();
  const tasks = document?.tasks.filter(task => `${task.id} ${task.title} ${task.category} ${task.prompt}`.toLowerCase().includes(query) && (filter === 'all' || task.split === filter)) ?? [];
  const resources = document?.resources.filter(resource => `${resource.id} ${resource.name} ${resource.description} ${resource.tags.join(' ')} ${resource.hostname}`.toLowerCase().includes(query) && (filter === 'all' || resource.category === filter)) ?? [];
  const showingTasks = view === 'tasks';
  const filterOptions = showingTasks ? ['train', 'validation', 'test'] : [...new Set(document?.resources.map(resource => resource.category) ?? [])].sort();
  return <div className="workspace-shell">
    <a className="skip-link" href="#workspace-main">Skip to dataset editor</a>
    <aside className="sidebar">
      <a className="brand" href="/" aria-label="Metis dataset editor"><svg viewBox="0 0 30 30" width="30" height="30" aria-hidden="true"><path d="M5 23V7l10 9L25 7v16M5 7l10 16L25 7" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" /></svg><span>Metis</span></a>
      <div className="workspace-label"><span className="local-dot" />Local workspace</div>
      <nav className="main-nav" aria-label="Workspace">
        <button className={showingTasks ? 'selected' : ''} aria-current={showingTasks ? 'page' : undefined} onClick={() => selectView('tasks')}><EditorIcon name="tasks" />Taskset<span>{document?.tasks.length ?? 0}</span></button>
        <button className={view === 'resources' ? 'selected' : ''} aria-current={view === 'resources' ? 'page' : undefined} onClick={() => selectView('resources')}><EditorIcon name="resources" />Discovery index<span>{document?.resources.length ?? 0}</span></button>
        <button className={view === 'validation' ? 'selected' : ''} aria-current={view === 'validation' ? 'page' : undefined} onClick={() => selectView('validation')}><EditorIcon name="check" />Workspace checks</button>
      </nav>
      <div className="sidebar-note"><span className="sidebar-tag">Synthetic data</span><p>Author resources.<br />Define tasks.<br />Keep the answer hidden.</p></div>
      <footer className="sidebar-footer"><span>Dataset editor</span><span>v0.1 · local only</span></footer>
    </aside>
    <div className="workspace-content">
      <header className="topbar"><span className="breadcrumb">Workspace <span>/</span> {showingTasks ? 'Taskset' : view === 'resources' ? 'Discovery index' : 'Checks'}</span>
        <div className="save-controls"><span className={`save-state ${dirty ? 'unsaved' : ''}`}><span />{busy ? 'Working…' : !saved ? 'Not loaded' : dirty ? 'Unsaved changes' : 'Saved to disk'}</span>
          <button className="primary-button" onClick={() => void saveWorkspace()} disabled={!dirty || busy || jsonErrors.size > 0}><EditorIcon name="save" size={16} />Save changes</button></div>
      </header>
      <main id="workspace-main" tabIndex={-1}>
        <div className="page-heading"><div><h1>{showingTasks ? 'Taskset' : view === 'resources' ? 'Discovery index' : 'Workspace checks'}</h1>
          <p>{showingTasks ? 'Define what the agent needs to know, buy, and solve.' : view === 'resources' ? 'The resources an agent can discover before it spends.' : 'Validate the structure, inspect warnings, and manage the authoring file.'}</p></div>
          {view !== 'validation' && <button className="secondary-button" onClick={() => addRecord()} disabled={busy || !document}><EditorIcon name="plus" size={16} />New {showingTasks ? 'task' : 'resource'}</button>}
        </div>
        <div className="dataset-strip"><span className="synthetic-label">Synthetic starter dataset</span><span>{document?.name ?? 'Loading workspace…'}</span><span className="dataset-date">As of {document?.as_of ?? '…'}</span></div>
        {error && <div className="feedback error" role="alert"><div><strong>Could not complete the action</strong><p>{error}</p></div><button className="quiet-button" onClick={() => setError('')} aria-label="Dismiss error"><EditorIcon name="close" /></button></div>}
        {message && <div className="feedback success" role="status"><EditorIcon name="check" /><p>{message}</p></div>}
        {jsonErrors.size > 0 && <div className="feedback error" role="alert"><p>{jsonErrors.size} invalid JSON field{jsonErrors.size === 1 ? '' : 's'}. Fix them before saving: {[...jsonErrors.keys()].join(', ')}.</p></div>}
        {!document ? <div className="loading-state"><p>{busy ? 'Loading resources and tasks…' : 'The dataset could not be loaded.'}</p>{!busy && <button className="secondary-button" onClick={() => void loadWorkspace()}>Retry loading</button>}</div> : view === 'validation' ? <div className="validation-layout">
          <fieldset disabled={busy} className="workspace-settings">
            <EditorSection title="Authoring workspace"><EditorField label="Dataset name" value={document.name} onChange={event => changeDocument({ ...document, name: event.target.value })} />
              <EditorText label="Description" value={document.description} onChange={value => changeDocument({ ...document, description: value })} />
              <EditorField label="Metadata snapshot date" type="date" value={document.as_of} onChange={event => changeDocument({ ...document, as_of: event.target.value })} hint="Historical reliability, age, and change metadata are interpreted relative to this date." />
            </EditorSection>
            <EditorSection title="Validation"><p className="muted">Checks schema constraints, unique IDs, resource links, JSON responses, and reference-path budgets. It cannot verify factual accuracy, answer leakage, or task solvability.</p><button className="primary-button fit" onClick={() => void validateWorkspace()} disabled={busy}>Validate dataset</button>
              <ul className="warning-list">{warnings.length ? warnings.map(warning => <li key={warning}>{warning}</li>) : <li className="muted">No authoring warnings in the last check. Revalidate after editing.</li>}</ul>
            </EditorSection>
            <EditorSection title="Local file"><code>datasets/workspace.json</code><p className="muted">Changes are saved only when you choose Save changes. The Metis taskset loads this file at the start of a run in the source checkout. New edits do not change an episode already running.</p>
              <button className="secondary-button fit" onClick={() => { if (!dirty || window.confirm('Discard all unsaved edits and reload the file from disk?')) void loadWorkspace(); }}>Reload from disk</button>
            </EditorSection>
          </fieldset>
        </div> : <div className="editor-layout">
          <section className="record-browser" aria-label={showingTasks ? 'Task list' : 'Resource list'}>
            <div className="browser-filters"><label className="search-field"><EditorIcon name="search" size={16} /><input aria-label={showingTasks ? 'Search tasks' : 'Search resources'} placeholder={showingTasks ? 'Search tasks…' : 'Search resources…'} value={search} onChange={event => setSearch(event.target.value)} /></label>
              <select aria-label={showingTasks ? 'Filter by split' : 'Filter by category'} value={filter} onChange={event => setFilter(event.target.value)}><option value="all">{showingTasks ? 'All splits' : 'All categories'}</option>{filterOptions.map(option => <option key={option}>{option}</option>)}</select>
            </div>
            <div className="list-summary"><span>{showingTasks ? tasks.length : resources.length} {showingTasks ? 'tasks' : 'resources'}</span><span>{showingTasks ? 'Budget' : 'Price'}</span></div>
            <div className="record-list">{showingTasks ? tasks.map(task => <button key={task.id} className={`record-row ${taskId === task.id ? 'active' : ''}`} aria-pressed={taskId === task.id} onClick={() => { setTaskId(task.id); setTaskTab('Task'); }}>
              <span className="record-row-heading"><span>{task.title}</span><span className="row-price">{task.budget_units}<small>units</small></span></span>
              <span className="record-row-meta"><span className={`split-label ${task.split}`}>{task.split}</span><span>{task.category}</span></span>
              <span className="record-row-footer"><code>{task.id}</code><span>{task.reference_purchases.length > 1 ? 'Multi-step' : 'Single-step'}</span></span>
            </button>) : resources.map(resource => <button key={resource.id} className={`record-row ${resourceId === resource.id ? 'active' : ''}`} aria-pressed={resourceId === resource.id} onClick={() => setResourceId(resource.id)}>
              <span className="record-row-heading"><span>{resource.name}</span><span className="row-price">{resource.price_units}<small>units</small></span></span>
              <span className="record-row-meta"><span>{resource.category}</span><span className="method-label">{resource.method}</span></span>
              <span className="record-row-footer"><code>{resource.hostname}</code></span>
            </button>)}</div>
            {(showingTasks ? tasks.length : resources.length) === 0 && <div className="empty-list"><h3>No matches</h3><p>Clear the search or filter, or create a new {showingTasks ? 'task' : 'resource'}.</p><button className="quiet-button" onClick={() => { setSearch(''); setFilter('all'); }}>Clear filters</button></div>}
            <div className="browser-footnote">{showingTasks ? 'Split labels are editable. This is not a frozen benchmark.' : 'All listings are fictional. No endpoint requests are made.'}</div>
          </section>
          <section className="record-detail" aria-label="Selected record editor">
            {(showingTasks ? selectedTask : selectedResource) ? <>
              <div className="detail-heading"><div><h2>{showingTasks ? selectedTask?.title : selectedResource?.name}</h2><div className="detail-meta"><code>{showingTasks ? selectedTask?.id : selectedResource?.id}</code>{showingTasks ? <span className={`status-badge ${selectedTask?.status}`}>{selectedTask?.status}</span> : <span className="status-badge ready">Public listing</span>}</div></div>
                <div className="record-actions"><button className="quiet-button" onClick={() => addRecord(true)} disabled={busy}>Duplicate</button><button className="quiet-button danger" onClick={deleteRecord} disabled={busy}>Delete</button></div>
              </div>
              {showingTasks && <div className="editor-tabs" aria-label="Task sections">{(['Task', 'Resources', 'Hidden data', 'Agent preview'] as const).map(tab => <button key={tab} aria-pressed={taskTab === tab} className={taskTab === tab ? 'active' : ''} onClick={() => setTaskTab(tab)}>{tab}{tab === 'Resources' && <span>{selectedTask?.resource_ids.length}</span>}</button>)}</div>}
              <fieldset className="editor-form" disabled={busy}>
                {showingTasks && selectedTask && <TaskEditor key={selectedTask.id} task={selectedTask} document={document} tab={taskTab} onChange={editTask} editing={editing} />}
                {!showingTasks && selectedResource && <ResourceEditor key={selectedResource.id} resource={selectedResource} onChange={editResource} editing={editing} />}
              </fieldset>
            </> : <div className="empty-list"><h2>No {showingTasks ? 'task' : 'resource'} selected</h2><p>Create a record to start authoring this dataset.</p><button className="secondary-button" onClick={() => addRecord()}>Create {showingTasks ? 'task' : 'resource'}</button></div>}
          </section>
        </div>}
      </main>
      <footer className="workspace-footer"><span>Metis · Agentic economic environments</span><button className="quiet-button" disabled={busy || !document} onClick={() => void validateWorkspace()}>Validate dataset<EditorIcon name="arrow" size={14} /></button></footer>
    </div>
  </div>;
}
