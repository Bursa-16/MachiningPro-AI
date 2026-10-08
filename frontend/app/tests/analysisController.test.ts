// HUMAN_CONFIRMATION_UI_02: the live analysis controller, driven with a fake API and a fake
// scheduler. No browser, no server, no model.

import assert from 'node:assert/strict'
import { describe, test } from 'node:test'

import {
  AnalysisController,
  POLL_INTERVAL_MS,
  aiStateFor,
  failureFromCode,
  isJobActive,
  type AnalysisApi,
  type ControllerState,
  type Scheduler,
} from '../src/lib/analysisController.ts'
import {
  AnalysisApiError,
  type AnalysisJob,
  type ApiErrorCode,
  type DrawingSummary,
  type JobStatus,
  type ReviewBody,
} from '../src/types/drawingAnalysis.ts'
import type { AdvisoryFinding, ReviewRecord } from '../src/types/drawingReview.ts'

const FILE = {} as File

const SUMMARY: DrawingSummary = {
  drawing_id: 'd'.repeat(32),
  deterministic: {
    status: 'VALID',
    diagnostics: [],
    items: [{ id: 'det-1', label: 'LINEAR', value: '100 mm', source: 'tesseract-ocr' }],
  },
  pages: [
    {
      page_number: 1,
      width_pt: 480,
      height_pt: 320,
      images: [{ index: 1, width_px: 480, height_px: 320 }],
    },
  ],
}

const FINDING: AdvisoryFinding = {
  evidence_id: 'vlm-ev-1',
  candidate_type: 'TEXT',
  original_value: '100 MM',
  legibility: 'CLEAR',
  confidence: 1,
  authority: 'ADVISORY',
  provider_id: 'ollama.chat',
  model_id: 'granite3.2-vision:2b',
  model_version: 'granite3.2-vision:2b',
  region_id: 'region-p1-0-0-480-320',
  request_id: 'vlm-req-1',
  box_basis: 'REGION_EXTENT',
  reconciliation: 'CORROBORATED',
}

const PENDING: ReviewRecord = {
  evidence_id: FINDING.evidence_id,
  status: 'PENDING_REVIEW',
  original_ai_value: '100 MM',
  reviewed_value: null,
  reviewed_by: null,
  reviewed_at: null,
  history: [],
}

function job(status: JobStatus, extra: Partial<AnalysisJob> = {}): AnalysisJob {
  const done = status === 'COMPLETED'
  return {
    job_id: 'j'.repeat(32),
    drawing_id: SUMMARY.drawing_id,
    status,
    progress_phase: done || status === 'FAILED' ? null : status,
    created_at: 't0',
    started_at: null,
    completed_at: null,
    error_code: null,
    error_message: null,
    finding_count: done ? 1 : null,
    region: done ? { region_id: FINDING.region_id, x0: 0, top: 0, x1: 480, bottom: 320, unit: 'pt' } : null,
    findings: done ? [FINDING] : [],
    reviews: done ? { [FINDING.evidence_id]: PENDING } : {},
    ...extra,
  }
}

class FakeApi implements AnalysisApi {
  calls: { name: string; args: unknown[] }[] = []
  uploadResult: DrawingSummary | Error = SUMMARY
  previewResult: string | Error = 'blob:preview'
  startResult: AnalysisJob | Error = job('QUEUED')
  getResults: (AnalysisJob | Error)[] = []
  reviewResult: ReviewRecord | Error = PENDING

  count(name: string): number {
    return this.calls.filter(c => c.name === name).length
  }
  private async answer<T>(value: T | Error): Promise<T> {
    if (value instanceof Error) throw value
    return value
  }
  upload(file: File) {
    this.calls.push({ name: 'upload', args: [file] })
    return this.answer(this.uploadResult)
  }
  preview(id: string, page: number) {
    this.calls.push({ name: 'preview', args: [id, page] })
    return this.answer(this.previewResult)
  }
  start(id: string, request: unknown) {
    this.calls.push({ name: 'start', args: [id, request] })
    return this.answer(this.startResult)
  }
  get(id: string, jobId: string) {
    this.calls.push({ name: 'get', args: [id, jobId] })
    const next = this.getResults.shift()
    return this.answer(next ?? job('ANALYZING'))
  }
  review(id: string, jobId: string, evidenceId: string, body: ReviewBody) {
    this.calls.push({ name: 'review', args: [id, jobId, evidenceId, body] })
    return this.answer(this.reviewResult)
  }
}

class FakeScheduler implements Scheduler {
  tasks = new Map<number, { callback: () => void; ms: number }>()
  private next = 1
  set(callback: () => void, ms: number) {
    const id = this.next++
    this.tasks.set(id, { callback, ms })
    return id
  }
  clear(handle: unknown) {
    this.tasks.delete(handle as number)
  }
  get pending() {
    return this.tasks.size
  }
  async tick() {
    const entries = [...this.tasks.entries()]
    this.tasks.clear()
    for (const [, task] of entries) task.callback()
    await flush()
  }
}

const flush = async () => {
  for (let i = 0; i < 10; i++) await Promise.resolve()
}

async function ready(api = new FakeApi()) {
  const scheduler = new FakeScheduler()
  const controller = new AnalysisController(api, scheduler)
  await controller.upload(FILE)
  return { api, scheduler, controller }
}

describe('upload', () => {
  test('uploading reads the drawing deterministically and never starts AI', async () => {
    const { api, controller, scheduler } = await ready()
    const state = controller.getState()
    assert.equal(state.drawing?.drawing_id, SUMMARY.drawing_id)
    assert.equal(state.previewUrl, 'blob:preview')
    assert.equal(api.count('upload'), 1)
    assert.equal(api.count('start'), 0)
    assert.equal(api.count('get'), 0)
    assert.equal(scheduler.pending, 0)
    assert.deepEqual(aiStateFor(state), { kind: 'IDLE' })
  })

  test('UI02-T10 a failed preview does not block the deterministic result', async () => {
    const api = new FakeApi()
    api.previewResult = new AnalysisApiError(422, 'PREVIEW_UNAVAILABLE')
    const { controller } = await ready(api)
    assert.equal(controller.getState().drawing?.deterministic.items.length, 1)
    assert.equal(controller.getState().previewUrl, null)
  })

  test('a failed upload is reported and leaves nothing half-loaded', async () => {
    const api = new FakeApi()
    api.uploadResult = new AnalysisApiError(422, 'INVALID_DRAWING')
    const { controller } = await ready(api)
    const state = controller.getState()
    assert.equal(state.uploadFailed, true)
    assert.equal(state.drawing, null)
    assert.equal(state.uploading, false)
  })
})

describe('starting an analysis', () => {
  test('UI02-T23 the start action calls the live analysis API with an explicit AI request', async () => {
    const { api, controller } = await ready()
    await controller.startAnalysis()
    assert.equal(api.count('start'), 1)
    assert.deepEqual(api.calls.find(c => c.name === 'start')?.args, [
      SUMMARY.drawing_id,
      { ai_enabled: true, page_number: 1, image_index: 1 },
    ])
    assert.equal(controller.getState().job?.status, 'QUEUED')
  })

  test('nothing starts without a drawing', async () => {
    const api = new FakeApi()
    const controller = new AnalysisController(api, new FakeScheduler())
    await controller.startAnalysis()
    assert.equal(api.count('start'), 0)
  })

  test('UI02-T29 duplicate starts are ignored while starting and while a job is active', async () => {
    const { api, controller } = await ready()
    const first = controller.startAnalysis()
    const second = controller.startAnalysis() // while the request is in flight
    await Promise.all([first, second])
    await controller.startAnalysis() // while the job is QUEUED
    assert.equal(api.count('start'), 1)
    assert.equal(isJobActive(controller.getState().job), true)
  })

  test('a drawing without a raster image fails closed before any request', async () => {
    const api = new FakeApi()
    api.uploadResult = { ...SUMMARY, pages: [{ ...SUMMARY.pages[0], images: [] }] }
    const { controller } = await ready(api)
    await controller.startAnalysis()
    assert.equal(api.count('start'), 0)
    assert.equal(controller.getState().startFailure, 'INVALID_REGION')
  })

  test('UI02-T26 a rejected start is a structured failure, not a job', async () => {
    const api = new FakeApi()
    api.startResult = new AnalysisApiError(503, 'AI_DISABLED')
    const { controller, scheduler } = await ready(api)
    await controller.startAnalysis()
    const state = controller.getState()
    assert.equal(state.job, null)
    assert.deepEqual(aiStateFor(state), { kind: 'FAILED', failure: 'DISABLED' })
    assert.equal(scheduler.pending, 0)
    assert.equal(state.drawing?.deterministic.items.length, 1, 'deterministic result stays')
  })

  test('a network failure on start is a safe unknown failure', async () => {
    const api = new FakeApi()
    api.startResult = new TypeError('Failed to fetch')
    const { controller } = await ready(api)
    await controller.startAnalysis()
    assert.deepEqual(aiStateFor(controller.getState()), { kind: 'FAILED', failure: 'UNKNOWN' })
  })
})

describe('polling real job state', () => {
  test('UI02-T24 each backend state maps to its real running phase, never a percentage', () => {
    const phases: Record<string, string> = {
      QUEUED: 'QUEUED',
      PREPARING: 'PREPARING_DRAWING',
      ANALYZING: 'AI_IN_PROGRESS',
      VALIDATING: 'VALIDATING_RESPONSE',
    }
    for (const [status, phase] of Object.entries(phases)) {
      const state = { job: job(status as JobStatus), startFailure: null } as ControllerState
      assert.deepEqual(aiStateFor(state), { kind: 'RUNNING', phase })
      assert.deepEqual(Object.keys(aiStateFor(state)).sort(), ['kind', 'phase'])
      assert.doesNotMatch(JSON.stringify(aiStateFor(state)), /percent|pct|%/i)
    }
  })

  test('the controller polls on the interval, follows the states and stops when completed', async () => {
    const api = new FakeApi()
    api.getResults = [job('PREPARING'), job('ANALYZING'), job('VALIDATING'), job('COMPLETED')]
    const { controller, scheduler } = await ready(api)
    await controller.startAnalysis()
    assert.equal(scheduler.pending, 1)
    assert.equal([...scheduler.tasks.values()][0].ms, POLL_INTERVAL_MS)
    const seen: string[] = []
    while (scheduler.pending) {
      await scheduler.tick()
      seen.push(controller.getState().job?.status ?? '')
    }
    assert.deepEqual(seen, ['PREPARING', 'ANALYZING', 'VALIDATING', 'COMPLETED'])
    assert.equal(api.count('get'), 4)
    assert.equal(scheduler.pending, 0, 'no polling after a terminal state')
  })

  test('UI02-T25 a completed job renders the real validated findings', async () => {
    const api = new FakeApi()
    api.getResults = [job('COMPLETED')]
    const { controller, scheduler } = await ready(api)
    await controller.startAnalysis()
    await scheduler.tick()
    const ai = aiStateFor(controller.getState())
    assert.equal(ai.kind, 'READY')
    if (ai.kind === 'READY') {
      assert.deepEqual(ai.findings, [FINDING])
      assert.equal(ai.findings[0].authority, 'ADVISORY')
      assert.equal(ai.findings[0].box_basis, 'REGION_EXTENT')
    }
    assert.equal(controller.getState().job?.reviews[FINDING.evidence_id].status, 'PENDING_REVIEW')
  })

  test('UI02-T27 a completed job with no findings is an empty ready state', async () => {
    const api = new FakeApi()
    api.getResults = [job('COMPLETED', { findings: [], reviews: {}, finding_count: 0 })]
    const { controller, scheduler } = await ready(api)
    await controller.startAnalysis()
    await scheduler.tick()
    assert.deepEqual(aiStateFor(controller.getState()), { kind: 'READY', findings: [] })
  })

  test('UI02-T26 every backend error code maps to a safe failure and exposes no evidence', async () => {
    const expected: Record<ApiErrorCode, string> = {
      AI_DISABLED: 'DISABLED',
      OLLAMA_UNAVAILABLE: 'OLLAMA_UNAVAILABLE',
      MODEL_NOT_AVAILABLE: 'MODEL_UNAVAILABLE',
      REQUEST_TIMEOUT: 'TIMEOUT',
      R3B_VALIDATION_FAILURE: 'VALIDATION_FAILED',
      INVALID_DRAWING: 'INVALID_DRAWING',
      INVALID_REGION: 'INVALID_REGION',
      JOB_INTERNAL_ERROR: 'UNKNOWN',
    }
    for (const [code, failure] of Object.entries(expected)) {
      const api = new FakeApi()
      api.getResults = [
        job('FAILED', { error_code: code as ApiErrorCode, error_message: 'safe', findings: [FINDING] }),
      ]
      const { controller, scheduler } = await ready(api)
      await controller.startAnalysis()
      await scheduler.tick()
      assert.deepEqual(aiStateFor(controller.getState()), { kind: 'FAILED', failure })
    }
    assert.equal(failureFromCode('nonsense'), 'UNKNOWN')
    assert.equal(failureFromCode(null), 'UNKNOWN')
  })

  test('a transient poll error keeps polling and is not a job failure', async () => {
    const api = new FakeApi()
    api.getResults = [new TypeError('network'), job('ANALYZING'), job('COMPLETED')]
    const { controller, scheduler } = await ready(api)
    await controller.startAnalysis()
    await scheduler.tick()
    assert.equal(controller.getState().pollFailed, true)
    assert.equal(controller.getState().job?.status, 'QUEUED')
    assert.equal(scheduler.pending, 1)
    await scheduler.tick()
    assert.equal(controller.getState().pollFailed, false)
    await scheduler.tick()
    assert.equal(controller.getState().job?.status, 'COMPLETED')
  })

  test('there is no automatic retry after a failure: only an explicit new start creates a job', async () => {
    const api = new FakeApi()
    api.getResults = [job('FAILED', { error_code: 'OLLAMA_UNAVAILABLE' })]
    const { controller, scheduler } = await ready(api)
    await controller.startAnalysis()
    await scheduler.tick()
    await flush()
    assert.equal(api.count('start'), 1)
    assert.equal(scheduler.pending, 0)
    api.startResult = job('QUEUED', { job_id: 'k'.repeat(32) })
    await controller.startAnalysis() // the explicit retry
    assert.equal(api.count('start'), 2)
    assert.equal(controller.getState().job?.job_id, 'k'.repeat(32))
  })

  test('a disposed controller can be re-activated (StrictMode remount) and polling resumes', async () => {
    const api = new FakeApi()
    api.getResults = [job('COMPLETED')]
    const { controller, scheduler } = await ready(api)
    controller.dispose()
    controller.activate()
    await controller.startAnalysis()
    assert.equal(scheduler.pending, 1)
    await scheduler.tick()
    assert.equal(controller.getState().job?.status, 'COMPLETED')
  })

  test('disposing stops polling and ignores late results', async () => {
    const { controller, scheduler, api } = await ready()
    await controller.startAnalysis()
    controller.dispose()
    assert.equal(scheduler.pending, 0)
    assert.equal(api.count('get'), 0)
  })
})

describe('review decisions', () => {
  async function completed(api = new FakeApi()) {
    api.getResults = [job('COMPLETED')]
    const ctx = await ready(api)
    await ctx.controller.startAnalysis()
    await ctx.scheduler.tick()
    return ctx
  }

  test('UI02-T28 accept, reject and edit call the review API and show the server record', async () => {
    const api = new FakeApi()
    const { controller } = await completed(api)
    const accepted: ReviewRecord = { ...PENDING, status: 'ACCEPTED', reviewed_by: 'engineer-1' }
    api.reviewResult = accepted
    await controller.review(FINDING.evidence_id, { action: 'ACCEPT' })
    assert.deepEqual(controller.getState().job?.reviews[FINDING.evidence_id], accepted)

    const rejected: ReviewRecord = { ...PENDING, status: 'REJECTED' }
    api.reviewResult = rejected
    await controller.review(FINDING.evidence_id, { action: 'REJECT' })
    assert.equal(controller.getState().job?.reviews[FINDING.evidence_id].status, 'REJECTED')

    const edited: ReviewRecord = { ...PENDING, status: 'EDITED', reviewed_value: '100 mm' }
    api.reviewResult = edited
    await controller.review(FINDING.evidence_id, { action: 'EDIT', value: '100 mm' })
    const record = controller.getState().job?.reviews[FINDING.evidence_id]
    assert.equal(record?.original_ai_value, '100 MM')
    assert.equal(record?.reviewed_value, '100 mm')

    const reviewCalls = api.calls.filter(c => c.name === 'review')
    assert.deepEqual(
      reviewCalls.map(c => c.args[3]),
      [{ action: 'ACCEPT' }, { action: 'REJECT' }, { action: 'EDIT', value: '100 mm' }],
    )
    assert.ok(reviewCalls.every(c => c.args[0] === SUMMARY.drawing_id && c.args[2] === FINDING.evidence_id))
  })

  test('the AI finding itself is never altered by a review', async () => {
    const api = new FakeApi()
    const { controller } = await completed(api)
    const before = JSON.stringify(controller.getState().job?.findings)
    api.reviewResult = { ...PENDING, status: 'EDITED', reviewed_value: '999 mm' }
    await controller.review(FINDING.evidence_id, { action: 'EDIT', value: '999 mm' })
    assert.equal(JSON.stringify(controller.getState().job?.findings), before)
    assert.equal(controller.getState().drawing?.deterministic.items[0].value, '100 mm')
  })

  test('a failed review keeps the previous state and reports the failure', async () => {
    const api = new FakeApi()
    const { controller } = await completed(api)
    api.reviewResult = new AnalysisApiError(422, 'INVALID_REVIEW_VALUE')
    await controller.review(FINDING.evidence_id, { action: 'EDIT', value: 'x' })
    assert.equal(controller.getState().reviewFailed, true)
    assert.equal(controller.getState().job?.reviews[FINDING.evidence_id].status, 'PENDING_REVIEW')
  })

  test('review is refused locally unless the job is completed', async () => {
    const api = new FakeApi()
    const { controller } = await ready(api)
    await controller.startAnalysis()
    await controller.review(FINDING.evidence_id, { action: 'ACCEPT' })
    assert.equal(api.count('review'), 0)
  })

  test('UI02-T22 nothing is ever accepted automatically', async () => {
    const api = new FakeApi()
    await completed(api)
    assert.equal(api.count('review'), 0)
  })
})
