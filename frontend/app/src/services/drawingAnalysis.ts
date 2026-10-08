import { getStoredAuth } from './apiClient'
import type { AnalysisApi } from '../lib/analysisController.ts'
import {
  AnalysisApiError,
  type AnalysisJob,
  type DrawingSummary,
  type ReviewBody,
  type StartAnalysisRequest,
} from '../types/drawingAnalysis.ts'
import type { ReviewRecord } from '../types/drawingReview.ts'

const BASE = '/api/drawings'

function headers(extra: Record<string, string> = {}): Record<string, string> {
  const token = getStoredAuth().token
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra
}

async function failure(response: Response): Promise<AnalysisApiError> {
  let code = 'REQUEST_FAILED'
  try {
    const data = await response.json()
    const detail = data?.detail
    if (detail && typeof detail === 'object' && typeof detail.error_code === 'string') {
      code = detail.error_code
    }
  } catch {
    /* non-JSON error body: keep the generic code; never surface raw text */
  }
  return new AnalysisApiError(response.status, code)
}

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) throw await failure(response)
  return (await response.json()) as T
}

/** Talks only to this application's own authenticated backend; no AI endpoint is known here. */
export const drawingAnalysisApi: AnalysisApi = {
  async upload(file: File): Promise<DrawingSummary> {
    const form = new FormData()
    form.append('file', file, 'drawing.pdf')
    const response = await fetch(BASE, { method: 'POST', headers: headers(), body: form })
    return json<DrawingSummary>(response)
  },

  async preview(drawingId: string, pageNumber: number): Promise<string> {
    const response = await fetch(`${BASE}/${drawingId}/pages/${pageNumber}/preview`, {
      headers: headers(),
    })
    if (!response.ok) throw await failure(response)
    return URL.createObjectURL(await response.blob())
  },

  async start(drawingId: string, request: StartAnalysisRequest): Promise<AnalysisJob> {
    const response = await fetch(`${BASE}/${drawingId}/analysis`, {
      method: 'POST',
      headers: headers({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(request),
    })
    return json<AnalysisJob>(response)
  },

  async get(drawingId: string, jobId: string): Promise<AnalysisJob> {
    const response = await fetch(`${BASE}/${drawingId}/analysis/${jobId}`, { headers: headers() })
    return json<AnalysisJob>(response)
  },

  async review(
    drawingId: string,
    jobId: string,
    evidenceId: string,
    body: ReviewBody,
  ): Promise<ReviewRecord> {
    const response = await fetch(
      `${BASE}/${drawingId}/analysis/${jobId}/reviews/${encodeURIComponent(evidenceId)}`,
      {
        method: 'PUT',
        headers: headers({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(body),
      },
    )
    return json<ReviewRecord>(response)
  },
}
