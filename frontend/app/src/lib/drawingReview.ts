// Pure review logic: no React, no I/O, no clock. Imported by the UI and by node tests.

import type {
  AdvisoryFinding,
  AiFailureKind,
  AnalysisPhase,
  BoxBasis,
  ReviewAction,
  ReviewEvent,
  ReviewRecord,
  ReviewState,
  ReviewStatus,
} from '../types/drawingReview.ts'

export const MAX_REVIEW_VALUE_CHARS = 256

export const ANALYSIS_PHASES: readonly AnalysisPhase[] = [
  'QUEUED',
  'PREPARING_DRAWING',
  'AI_IN_PROGRESS',
  'VALIDATING_RESPONSE',
]

/** Every finding starts PENDING_REVIEW. There is no path that starts or ends accepted. */
export function createReviewState(findings: readonly AdvisoryFinding[]): ReviewState {
  const state: Record<string, ReviewRecord> = {}
  for (const finding of findings) {
    state[finding.evidence_id] = {
      evidence_id: finding.evidence_id,
      status: 'PENDING_REVIEW',
      original_ai_value: finding.original_value,
      reviewed_value: null,
      reviewed_by: null,
      reviewed_at: null,
      history: [],
    }
  }
  return state
}

export type EditValidation =
  | { ok: true; value: string }
  | { ok: false; reason: 'BLANK' | 'TOO_LONG' | 'CONTROL_CHARACTERS' | 'UNCHANGED' }

/** Mirrors the backend text rules for a value: non-blank, bounded, no control characters. */
export function validateEditedValue(raw: string, originalAiValue: string): EditValidation {
  const value = raw.trim()
  if (!value) return { ok: false, reason: 'BLANK' }
  if (value.length > MAX_REVIEW_VALUE_CHARS) return { ok: false, reason: 'TOO_LONG' }
  // eslint-disable-next-line no-control-regex
  if (/[\u0000-\u001f\u007f-\u009f]/.test(value)) return { ok: false, reason: 'CONTROL_CHARACTERS' }
  if (value === originalAiValue) return { ok: false, reason: 'UNCHANGED' }
  return { ok: true, value }
}

/**
 * Applies a human decision. Returns the same state object when the action is
 * invalid, so a bad edit can never change anything. The AI finding itself is not an
 * input here and therefore cannot be touched; only the review record changes.
 */
export function reviewReducer(state: ReviewState, action: ReviewAction): ReviewState {
  const current = state[action.evidence_id]
  if (!current) return state

  let event: ReviewEvent
  if (action.type === 'ACCEPT') {
    event = {
      status: 'ACCEPTED',
      reviewed_value: null,
      reviewed_by: action.reviewed_by,
      reviewed_at: action.reviewed_at,
    }
  } else if (action.type === 'REJECT') {
    event = {
      status: 'REJECTED',
      reviewed_value: null,
      reviewed_by: action.reviewed_by,
      reviewed_at: action.reviewed_at,
    }
  } else {
    const checked = validateEditedValue(action.value, current.original_ai_value)
    if (!checked.ok) return state
    event = {
      status: 'EDITED',
      reviewed_value: checked.value,
      reviewed_by: action.reviewed_by,
      reviewed_at: action.reviewed_at,
    }
  }

  const next: ReviewRecord = {
    ...current,
    status: event.status,
    reviewed_value: event.reviewed_value,
    reviewed_by: event.reviewed_by,
    reviewed_at: event.reviewed_at,
    history: [...current.history, event],
  }
  return { ...state, [action.evidence_id]: next }
}

/** The value a human has confirmed, or null when nothing is confirmed (pending/rejected). */
export function confirmedValue(record: ReviewRecord): string | null {
  if (record.status === 'ACCEPTED') return record.original_ai_value
  if (record.status === 'EDITED') return record.reviewed_value
  return null
}

export function countByStatus(state: ReviewState): Record<ReviewStatus, number> {
  const counts: Record<ReviewStatus, number> = {
    PENDING_REVIEW: 0,
    ACCEPTED: 0,
    REJECTED: 0,
    EDITED: 0,
  }
  for (const record of Object.values(state)) counts[record.status] += 1
  return counts
}

/** Translation key for how a box must be described. Never "exact AI detection box". */
export function boxBasisLabelKey(basis: BoxBasis): 'drSourceRegion' | 'drModelBoxLegacy' {
  return basis === 'REGION_EXTENT' ? 'drSourceRegion' : 'drModelBoxLegacy'
}

/** Only a model-supplied pixel box may be described as a model-reported position. */
export function claimsExactLocalization(basis: BoxBasis): boolean {
  return basis === 'MODEL_PIXEL_BOX'
}

/**
 * Maps the backend advisory diagnostics (constant `VLM_*` codes) to a UI failure kind.
 * `VLM_REQUEST_REJECTED` is what a missing Ollama model (HTTP 404) surfaces as.
 */
export function classifyAiFailure(diagnostics: readonly string[]): AiFailureKind {
  const first = diagnostics[0] ?? ''
  if (first === 'VLM_DISABLED' || first === 'VLM_UNSUPPORTED') return 'DISABLED'
  if (first === 'VLM_UNAVAILABLE') return 'OLLAMA_UNAVAILABLE'
  if (first === 'VLM_TIMEOUT' || first === 'VLM_BUDGET_EXHAUSTED') return 'TIMEOUT'
  if (first === 'VLM_REQUEST_REJECTED') return 'MODEL_UNAVAILABLE'
  if (first.startsWith('VLM_RESPONSE_') || first === 'VLM_MODEL_MISMATCH') {
    return 'VALIDATION_FAILED'
  }
  return 'UNKNOWN'
}

/** Position of a phase in the fixed sequence; used for state markers, never as a percentage. */
export function phaseIndex(phase: AnalysisPhase): number {
  return ANALYSIS_PHASES.indexOf(phase)
}

export function confidenceLabel(confidence: number | null): string | null {
  if (confidence === null) return null
  return `${Math.round(confidence * 100)}%`
}
