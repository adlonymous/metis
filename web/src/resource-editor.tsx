import { useState } from 'react';
import type { ResourceListing } from './dataset-contract';
import { EditorField, EditorJson, EditorSection, EditorSelect, EditorText } from './editor-fields';
import type { JsonEditing } from './editor-fields';

interface ResourceProps {
  resource: ResourceListing;
  onChange: (resource: ResourceListing) => void;
  editing: JsonEditing;
}

/** The public directory editor exposes measured metadata without fetching endpoints. */
export function ResourceEditor({ resource, onChange, editing }: ResourceProps) {
  const [tagText, setTagText] = useState(resource.tags.join(', '));
  function update<K extends keyof ResourceListing>(key: K, value: ResourceListing[K]) {
    onChange({ ...resource, [key]: value });
  }
  return <>
    <EditorSection title="Resource identity" hint="This listing is visible to the agent before purchase.">
      <div className="field-grid">
        <EditorField label="Name" value={resource.name} onChange={event => update('name', event.target.value)} />
        <EditorField label="Category" value={resource.category} onChange={event => update('category', event.target.value)} />
      </div>
      <EditorText label="Description" value={resource.description} onChange={value => update('description', value)} />
      <EditorField label="Tags" value={tagText} hint="Comma-separated terms the agent can use to judge relevance." onChange={event => {
        setTagText(event.target.value);
        update('tags', event.target.value.split(',').map(tag => tag.trim()).filter(Boolean));
      }} />
    </EditorSection>
    <EditorSection title="Price & endpoint" hint="Simulation units only. Endpoint details are never executed by this editor.">
      <div className="field-grid three">
        <EditorField label="Price (units)" type="number" min="0" step="1" value={resource.price_units} onChange={event => update('price_units', Number(event.target.value))} />
        <EditorSelect label="Method" value={resource.method} options={['GET', 'POST']} onChange={value => update('method', value === 'POST' ? 'POST' : 'GET')} />
        <EditorField label="Stable resource ID" value={resource.id} readOnly className="mono" />
      </div>
      <EditorField label="Hostname" value={resource.hostname} onChange={event => update('hostname', event.target.value)} className="mono" />
      <EditorField label="Path pattern" value={resource.path_pattern} onChange={event => update('path_pattern', event.target.value)} className="mono" />
    </EditorSection>
    <EditorSection title="Historical reliability & speed" hint="Historical signals as of the workspace date, not guarantees about a task's outcome. Leave unknown values empty.">
      <div className="field-grid">
        <EditorField label="Post-payment success (%)" type="number" min="0" max="100" step="0.1" value={resource.post_payment_success_rate == null ? '' : Number((resource.post_payment_success_rate * 100).toFixed(4))} onChange={event => update('post_payment_success_rate', event.target.value === '' ? null : Number(event.target.value) / 100)} />
        <EditorField label="Availability, 7 days (%)" type="number" min="0" max="100" step="0.1" value={resource.availability_7d == null ? '' : Number((resource.availability_7d * 100).toFixed(4))} onChange={event => update('availability_7d', event.target.value === '' ? null : Number(event.target.value) / 100)} hint="Share of requests without a server error." />
        <EditorField label="Latency p50 (ms)" type="number" min="0" step="1" value={resource.latency_p50_ms ?? ''} onChange={event => update('latency_p50_ms', event.target.value === '' ? null : Number(event.target.value))} />
        <EditorField label="Latency p90 (ms)" type="number" min="0" step="1" value={resource.latency_p90_ms ?? ''} onChange={event => update('latency_p90_ms', event.target.value === '' ? null : Number(event.target.value))} />
      </div>
    </EditorSection>
    <EditorSection title="Domain & content history">
      <div className="field-grid">
        <EditorField label="Domain created" type="date" value={resource.domain_created ?? ''} onChange={event => {
          onChange({ ...resource, domain_created: event.target.value || null, domain_age_days: null });
        }} hint="Changing this date clears the recorded age; set the age relative to the workspace date." />
        <EditorField label="Domain age (days)" type="number" min="0" step="1" value={resource.domain_age_days ?? ''} onChange={event => update('domain_age_days', event.target.value === '' ? null : Number(event.target.value))} />
        <EditorField label="Last change" type="date" value={resource.last_change ?? ''} onChange={event => update('last_change', event.target.value || null)} />
        <EditorField label="Last persistent change" type="date" value={resource.last_persistent_change ?? ''} onChange={event => update('last_persistent_change', event.target.value || null)} hint="At least half of added content remained at the next view." />
      </div>
    </EditorSection>
    <EditorSection title="Request origins" hint="Where requests come from, not the geographic coverage of the resource. Shares may total less than 100%.">
      {resource.top_countries.map((country, index) => <div className="country-row" key={index}>
        <EditorField label={`Country ${index + 1} (ISO code)`} maxLength={2} value={country.country_code} onChange={event => update('top_countries', resource.top_countries.map((item, i) => i === index ? { ...item, country_code: event.target.value.toUpperCase() } : item))} />
        <EditorField label="Share (%)" type="number" min="0" max="100" step="0.1" value={Number((country.share * 100).toFixed(4))} onChange={event => update('top_countries', resource.top_countries.map((item, i) => i === index ? { ...item, share: Number(event.target.value) / 100 } : item))} />
        <button className="quiet-button" onClick={() => update('top_countries', resource.top_countries.filter((_, i) => i !== index))} aria-label={`Remove country ${index + 1}`}>Remove</button>
      </div>)}
      <button className="secondary-button fit" onClick={() => update('top_countries', [...resource.top_countries, { country_code: 'US', share: 0 }])}>Add country</button>
    </EditorSection>
    <EditorSection title="Public samples" hint="Use unrelated sample entities. Never put this task's answer into a directory sample.">
      <EditorJson label="Sample input" fieldKey={`resource:${resource.id}:input`} value={resource.sample_input} editing={editing} onChange={value => update('sample_input', value)} />
      <EditorJson label="Sample output" fieldKey={`resource:${resource.id}:output`} value={resource.sample_output} editing={editing} onChange={value => update('sample_output', value)} />
    </EditorSection>
  </>;
}
