import type { WorkspaceDocument, WorkspaceEnvelope } from './dataset-contract';

interface ValidationIssue { loc: (string | number)[]; msg: string }
interface ApiFailure { detail: string | ValidationIssue[] }

/** Expected network and validation failures stay explicit at the UI boundary. */
export type EditorResult<T> = { ok: true; value: T } | { ok: false; error: string };

/** Requests stay same-origin; resource URLs are metadata and are never fetched. */
export async function requestDataset<T>(path: string, method = 'GET', body?: string): Promise<EditorResult<T>> {
  try {
    const response = await fetch(path, { method, headers: { 'Content-Type': 'application/json' }, body });
    if (!response.ok) {
      const failure: ApiFailure = await response.json();
      const detail = Array.isArray(failure.detail)
        ? failure.detail.map(issue => `${issue.loc.slice(1).join('.') || 'Dataset'}: ${issue.msg}`).join('\n')
        : failure.detail;
      return { ok: false, error: detail || `Request failed (${response.status})` };
    }
    const value: T = await response.json();
    return { ok: true, value };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : 'Cannot reach the local editor API. Restart scripts/editor and retry.' };
  }
}

/** Save the complete workspace with the revision originally loaded from disk. */
export function saveDataset(document: WorkspaceDocument, revision: string) {
  return requestDataset<WorkspaceEnvelope>('/api/workspace', 'PUT', JSON.stringify({ document, revision }));
}
