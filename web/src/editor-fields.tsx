import { useId } from 'react';
import type { InputHTMLAttributes, ReactNode } from 'react';
import type { JsonValue } from './dataset-contract';

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  hint?: string;
}

/** Every authoring field has a visible label and an optional descriptive hint. */
export function EditorField({ label, hint, ...props }: FieldProps) {
  const id = useId();
  return <label className="field" htmlFor={id}>
    <span>{label}</span><input id={id} {...props} aria-label={label} aria-describedby={hint ? `${id}-hint` : undefined} />
    {hint && <small id={`${id}-hint`}>{hint}</small>}
  </label>;
}

interface TextProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  hint?: string;
  rows?: number;
}

/** Multiline authoring content uses native textareas with persistent labels. */
export function EditorText({ label, value, onChange, hint, rows = 3 }: TextProps) {
  const id = useId();
  return <label className="field" htmlFor={id}>
    <span>{label}</span><textarea id={id} aria-label={label} value={value} rows={rows} onChange={event => onChange(event.target.value)} aria-describedby={hint ? `${id}-hint` : undefined} />
    {hint && <small id={`${id}-hint`}>{hint}</small>}
  </label>;
}

interface SelectProps {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}

/** Select values remain strings; callers choose from their schema-owned options. */
export function EditorSelect({ label, value, options, onChange }: SelectProps) {
  const id = useId();
  return <label className="field" htmlFor={id}><span>{label}</span>
    <select id={id} aria-label={label} value={value} onChange={event => onChange(event.target.value)}>
      {options.map(option => <option key={option} value={option}>{option}</option>)}
    </select>
  </label>;
}

interface SectionProps { title: string; hint?: string; children: ReactNode }

/** Form sections use spacing and separators rather than nested cards. */
export function EditorSection({ title, hint, children }: SectionProps) {
  return <section className="form-section"><div className="section-heading"><h3>{title}</h3>{hint && <p>{hint}</p>}</div>{children}</section>;
}

export interface JsonEditing {
  drafts: ReadonlyMap<string, string>;
  errors: ReadonlyMap<string, string>;
  edit: (key: string, text: string, apply: (value: JsonValue) => void) => void;
}

interface JsonProps {
  label: string;
  fieldKey: string;
  value: JsonValue;
  editing: JsonEditing;
  onChange: (value: JsonValue) => void;
  hint?: string;
}

/** Invalid JSON remains editable across tabs but cannot be saved over valid data. */
export function EditorJson({ label, fieldKey, value, editing, onChange, hint }: JsonProps) {
  const id = useId();
  const error = editing.errors.get(fieldKey);
  return <label className="field json-field" htmlFor={id}>
    <span>{label}<span className="format-label">JSON</span></span>
    <textarea id={id} aria-label={label} spellCheck={false} value={editing.drafts.get(fieldKey) ?? JSON.stringify(value, null, 2)}
      rows={7} onChange={event => editing.edit(fieldKey, event.target.value, onChange)}
      aria-invalid={Boolean(error)} aria-describedby={`${id}-hint`} />
    <small id={`${id}-hint`} className={error ? 'field-error' : ''}>{error ?? hint ?? 'Valid JSON required. Changes remain local until you save.'}</small>
  </label>;
}

interface IconProps { name: 'tasks' | 'resources' | 'check' | 'search' | 'plus' | 'arrow' | 'save' | 'close'; size?: number }
const iconPaths = {
  tasks: 'M8 4H5a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V5a1 1 0 0 0-1-1h-3 M9 3h6v4H9z M8 12h8 M8 16h5',
  resources: 'M3 7l9-4 9 4-9 4z M3 12l9 4 9-4 M3 17l9 4 9-4',
  check: 'M5 12l4 4L19 6',
  search: 'M10.5 17a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13 M16 16l5 5',
  plus: 'M12 5v14 M5 12h14',
  arrow: 'M5 12h14 M13 6l6 6-6 6',
  save: 'M5 3h12l4 4v14H3V3z M7 3v6h10V3 M7 21v-8h10v8',
  close: 'M6 6l12 12 M6 18L18 6',
};

/** Small authored line icons share a single stroke and are always decorative. */
export function EditorIcon({ name, size = 18 }: IconProps) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={iconPaths[name]} /></svg>;
}
