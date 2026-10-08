// Wire types for the live drawing-analysis API (backend/api/drawing_analysis.py).

import type { AdvisoryFinding, ReviewRecord } from './drawingReview.ts'

export type JobStatus = 'QUEUED' | 'PREPARING' | 'ANALYZING' | 'VALIDATING' | 'COMPLETED' | 'FAILED'

export type ApiErrorCode =
  | 'AI_DISABLED'
  | 'OLLAMA_UNAVAILABLE'
  | 'MODEL_NOT_AVAILABLE'
  | 'REQUEST_TIMEOUT'
  | 'R3B_VALIDATION_FAILURE'
  | 'INVALID_DRAWING'
  | 'INVALID_REGION'
  | 'JOB_INTERNAL_ERROR'

export interface DeterministicSummaryItem {
  id: string
  label: string
  value: string
  source: string
}

export interface PageSummary {
  page_number: number
  width_pt: number
  height_pt: number
  images: { index: number; width_px: number; height_px: number }[]
}

export interface DrawingSummary {
  drawing_id: string
  deterministic: {
    status: string
    diagnostics: string[]
    items: DeterministicSummaryItem[]
  }
  pages: PageSummary[]
}

export interface JobRegion {
  region_id: string
  x0: number
  top: number
  x1: number
  bottom: number
  unit: string
}

export interface AnalysisJob {
  job_id: string
  drawing_id: string
  status: JobStatus
  progress_phase: JobStatus | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  error_code: ApiErrorCode | null
  error_message: string | null
  finding_count: number | null
  region: JobRegion | null
  findings: AdvisoryFinding[]
  reviews: Record<string, ReviewRecord>
  reused?: boolean
}

export interface StartAnalysisRequest {
  ai_enabled: true
  page_number: number
  image_index: number
}

export type ReviewBody =
  | { action: 'ACCEPT' }
  | { action: 'REJECT' }
  | { action: 'EDIT'; value: string }

/** Structured failure raised by the service layer; carries only a safe code. */
export class AnalysisApiError extends Error {
  status: number
  code: string
  constructor(status: number, code: string) {
    super(code)
    this.status = status
    this.code = code
  }
}
