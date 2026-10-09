/**
 * API client for the /api/import universal engineering import endpoint.
 *
 * Sends any supported engineering file to the backend for format detection
 * and Level 0–1 parsing using the universal adapter registry.
 *
 * Used for non-PDF files; PDF files continue through drawingAnalysisApi.
 * All calls are authenticated with the stored bearer token.
 */

import { getStoredAuth } from './apiClient'

const BASE = '/api/import'

function authHeaders(): Record<string, string> {
  const token = getStoredAuth().token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/** Structured response from POST /api/import */
export interface ImportResult {
  file_name: string
  format_id: string
  format_family: string
  format_family_label: string
  import_status:
    | 'SUCCESS'
    | 'PARTIAL'
    | 'FAILED'
    | 'UNSUPPORTED'
    | 'INSUFFICIENT_DATA'
    | 'UNRECOGNIZED'
    | 'PARSE_ERROR'
    | 'UNKNOWN'
  capability_level: string
  entity_count: number
  metadata: Record<string, string | number | boolean | null>
  fidelity_events?: Array<{ class: string; description: string }>
  adapter_id?: string
}

export class ImportApiError extends Error {
  readonly status: number
  readonly code: string
  constructor(status: number, code: string) {
    super(`ImportApiError ${status}: ${code}`)
    this.status = status
    this.code = code
  }
}

/**
 * Upload a file to /api/import and return the structured ImportResult.
 * Throws ImportApiError on HTTP error responses.
 */
export async function detectAndImport(file: File): Promise<ImportResult> {
  const form = new FormData()
  form.append('file', file, file.name)

  const response = await fetch(BASE, {
    method: 'POST',
    headers: authHeaders(),
    body: form,
  })

  if (!response.ok) {
    let code = 'REQUEST_FAILED'
    try {
      const data = await response.json()
      const detail = data?.detail
      if (detail && typeof detail === 'object' && typeof detail.error_code === 'string') {
        code = detail.error_code
      }
    } catch {
      /* non-JSON error body */
    }
    throw new ImportApiError(response.status, code)
  }

  return (await response.json()) as ImportResult
}

/**
 * Render a DXF file to a PNG raster and wrap it in a single-page PDF via the
 * backend /api/import/dxf-as-pdf endpoint.  Returns a Blob (application/pdf)
 * ready to upload directly to the drawing-analysis pipeline (POST /api/drawings).
 *
 * LOCAL_ONLY — the backend uses Pillow only, no cloud, no paid API.
 * Throws ImportApiError on HTTP error responses (e.g. RENDER_FAILED if the DXF
 * contains no renderable LINE/CIRCLE/ARC/LWPOLYLINE geometry).
 */
export async function fetchDxfAsPdf(file: File): Promise<Blob> {
  const form = new FormData()
  form.append('file', file, file.name)
  const response = await fetch(`${BASE}/dxf-as-pdf`, {
    method: 'POST',
    headers: authHeaders(),
    body: form,
  })
  if (!response.ok) {
    let code = 'RENDER_FAILED'
    try {
      const data = await response.json()
      const detail = data?.detail
      if (detail && typeof detail === 'object' && typeof detail.error_code === 'string') {
        code = detail.error_code
      }
    } catch { /* non-JSON error body */ }
    throw new ImportApiError(response.status, code)
  }
  return response.blob()
}
