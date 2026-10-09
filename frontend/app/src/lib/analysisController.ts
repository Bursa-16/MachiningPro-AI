// Framework-free controller for the live analysis flow. React wraps it in a hook; tests
// drive it with a fake API and a fake scheduler, so no browser, server or model is involved.

import {
  AnalysisApiError,
  type AnalysisJob,
  type ApiErrorCode,
  type DrawingSummary,
  type ReviewBody,
  type StartAnalysisRequest,
} from '../types/drawingAnalysis.ts'
import type {
  AiAnalysisState,
  AiFailureKind,
  AnalysisPhase,
  ReviewRecord,
} from '../types/drawingReview.ts'

export interface AnalysisApi {
  upload(file: File): Promise<DrawingSummary>
  uploadDxfRender?(file: File): Promise<DrawingSummary>
  preview(drawingId: string, pageNumber: number): Promise<string>
  start(drawingId: string, request: StartAnalysisRequest): Promise<AnalysisJob>
  get(drawingId: string, jobId: string): Promise<AnalysisJob>
  review(
    drawingId: string,
    jobId: string,
    evidenceId: string,
    body: ReviewBody,
  ): Promise<ReviewRecord>
}

export interface Scheduler {
  set(callback: () => void, ms: number): unknown
  clear(handle: unknown): void
}

export const POLL_INTERVAL_MS = 2000

export interface ControllerState {
  drawing: DrawingSummary | null
  previewUrl: string | null
  uploading: boolean
  uploadFailed: boolean
  starting: boolean
  job: AnalysisJob | null
  startFailure: AiFailureKind | null
  pollFailed: boolean
  reviewFailed: boolean
}

const INITIAL: ControllerState = {
  drawing: null,
  previewUrl: null,
  uploading: false,
  uploadFailed: false,
  starting: false,
  job: null,
  startFailure: null,
  pollFailed: false,
  reviewFailed: false,
}

const ACTIVE = new Set(['QUEUED', 'PREPARING', 'ANALYZING', 'VALIDATING'])

export function isJobActive(job: AnalysisJob | null): boolean {
  return job !== null && ACTIVE.has(job.status)
}

const FAILURE: Record<ApiErrorCode, AiFailureKind> = {
  AI_DISABLED: 'DISABLED',
  OLLAMA_UNAVAILABLE: 'OLLAMA_UNAVAILABLE',
  MODEL_NOT_AVAILABLE: 'MODEL_UNAVAILABLE',
  REQUEST_TIMEOUT: 'TIMEOUT',
  R3B_VALIDATION_FAILURE: 'VALIDATION_FAILED',
  INVALID_DRAWING: 'INVALID_DRAWING',
  INVALID_REGION: 'INVALID_REGION',
  JOB_INTERNAL_ERROR: 'UNKNOWN',
}

export function failureFromCode(code: string | null | undefined): AiFailureKind {
  return (code && (FAILURE as Record<string, AiFailureKind>)[code]) || 'UNKNOWN'
}

const PHASE: Record<string, AnalysisPhase> = {
  QUEUED: 'QUEUED',
  PREPARING: 'PREPARING_DRAWING',
  ANALYZING: 'AI_IN_PROGRESS',
  VALIDATING: 'VALIDATING_RESPONSE',
}

/** Maps real backend job state to the review UI state. Never invents progress. */
export function aiStateFor(state: ControllerState): AiAnalysisState {
  if (state.startFailure) return { kind: 'FAILED', failure: state.startFailure }
  const job = state.job
  if (!job) return { kind: 'IDLE' }
  if (job.status === 'COMPLETED') return { kind: 'READY', findings: job.findings }
  if (job.status === 'FAILED') return { kind: 'FAILED', failure: failureFromCode(job.error_code) }
  return { kind: 'RUNNING', phase: PHASE[job.status] ?? 'QUEUED' }
}

const defaultScheduler: Scheduler = {
  set: (callback, ms) => setTimeout(callback, ms),
  clear: handle => clearTimeout(handle as ReturnType<typeof setTimeout>),
}

export class AnalysisController {
  private state: ControllerState = INITIAL
  private listeners = new Set<() => void>()
  private timer: unknown = null
  private disposed = false

  private readonly api: AnalysisApi
  private readonly scheduler: Scheduler
  private readonly pollMs: number

  constructor(
    api: AnalysisApi,
    scheduler: Scheduler = defaultScheduler,
    pollMs: number = POLL_INTERVAL_MS,
  ) {
    this.api = api
    this.scheduler = scheduler
    this.pollMs = pollMs
  }

  getState = (): ControllerState => this.state

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  private set(patch: Partial<ControllerState>): void {
    this.state = { ...this.state, ...patch }
    for (const listener of this.listeners) listener()
  }

  /** Re-arms the controller; React StrictMode mounts, unmounts and remounts the same instance. */
  activate(): void {
    this.disposed = false
  }

  dispose(): void {
    this.disposed = true
    this.stopPolling()
    this.listeners.clear()
  }

  private async _doUpload(fn: (file: File) => Promise<DrawingSummary>, file: File): Promise<void> {
    if (this.state.uploading) return
    this.stopPolling()
    this.set({ ...INITIAL, uploading: true })
    try {
      const drawing = await fn(file)
      this.set({ drawing, uploading: false })
      const first = drawing.pages[0]
      if (first) {
        try {
          const previewUrl = await this.api.preview(drawing.drawing_id, first.page_number)
          if (!this.disposed) this.set({ previewUrl })
        } catch {
          /* the deterministic result stays usable without a preview image */
        }
      }
    } catch {
      this.set({ uploading: false, uploadFailed: true })
    }
  }

  /** Reads the drawing deterministically. AI is never started by an upload. */
  upload(file: File): Promise<void> {
    return this._doUpload(f => this.api.upload(f), file)
  }

  /** Like upload() but routes through the DXF-render endpoint (no OCR). */
  uploadDxfRender(file: File): Promise<void> {
    const fn = this.api.uploadDxfRender?.bind(this.api) ?? ((f: File) => this.api.upload(f))
    return this._doUpload(fn, file)
  }

  /** Explicit, user-triggered. A second call while a job is active does nothing. */
  async startAnalysis(): Promise<void> {
    const { drawing, job, starting } = this.state
    if (!drawing || starting || isJobActive(job)) return
    const page = drawing.pages.find(p => p.images.length > 0)
    if (!page) {
      this.set({ startFailure: 'INVALID_REGION' })
      return
    }
    this.set({ starting: true, startFailure: null, pollFailed: false, reviewFailed: false })
    try {
      const started = await this.api.start(drawing.drawing_id, {
        ai_enabled: true,
        page_number: page.page_number,
        image_index: page.images[0].index,
      })
      this.set({ starting: false, job: started })
      this.schedulePoll()
    } catch (error) {
      const code = error instanceof AnalysisApiError ? error.code : 'JOB_INTERNAL_ERROR'
      this.set({ starting: false, job: null, startFailure: failureFromCode(code) })
    }
  }

  private schedulePoll(): void {
    this.stopPolling()
    if (this.disposed || !isJobActive(this.state.job)) return
    this.timer = this.scheduler.set(() => void this.poll(), this.pollMs)
  }

  private stopPolling(): void {
    if (this.timer !== null) this.scheduler.clear(this.timer)
    this.timer = null
  }

  private async poll(): Promise<void> {
    const { drawing, job } = this.state
    this.timer = null
    if (this.disposed || !drawing || !job || !isJobActive(job)) return
    try {
      const next = await this.api.get(drawing.drawing_id, job.job_id)
      this.set({ job: next, pollFailed: false })
    } catch {
      this.set({ pollFailed: true }) // keep polling; a transient error is not a job failure
    }
    this.schedulePoll()
  }

  /** The server is the source of truth: the UI shows the record the server returns. */
  async review(evidenceId: string, body: ReviewBody): Promise<void> {
    const { drawing, job } = this.state
    if (!drawing || !job || job.status !== 'COMPLETED') return
    try {
      const record = await this.api.review(drawing.drawing_id, job.job_id, evidenceId, body)
      const latest = this.state.job
      if (!latest) return
      this.set({
        reviewFailed: false,
        job: { ...latest, reviews: { ...latest.reviews, [evidenceId]: record } },
      })
    } catch {
      this.set({ reviewFailed: true })
    }
  }
}
