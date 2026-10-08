// Synthetic, non-sensitive sample used to exercise the review workflow.
//
// The two suggestions reproduce what one real local Granite run returned for this
// synthetic drawing (one label was missed). They are sample data, not live output,
// and the UI labels the whole session as a synthetic sample.

import type {
  AdvisoryFinding,
  AiAnalysisState,
  DeterministicItem,
  SourceRegion,
} from '../types/drawingReview.ts'

export const SAMPLE_REGION: SourceRegion = {
  region_id: 'vlm-region-1',
  x0: 0,
  top: 0,
  x1: 480,
  bottom: 320,
}

export const SAMPLE_DETERMINISTIC: readonly DeterministicItem[] = [
  { id: 'det-dim-1', label: 'Linear dimension', value: '100 mm', source: 'OCR · tesseract' },
]

const common = {
  authority: 'ADVISORY',
  provider_id: 'ollama.chat',
  model_id: 'granite3.2-vision:2b',
  model_version: 'granite3.2-vision:2b',
  region_id: SAMPLE_REGION.region_id,
  request_id: 'vlm-req-63567ef75e5dbe1449f15aaa57d4c397',
  box_basis: 'REGION_EXTENT',
  legibility: 'CLEAR',
  candidate_type: 'TEXT',
} as const

export const SAMPLE_FINDINGS: readonly AdvisoryFinding[] = [
  {
    ...common,
    evidence_id: 'vlm-ev-sample-0001',
    original_value: '100 MM',
    confidence: 1,
    reconciliation: 'CORROBORATED',
  },
  {
    ...common,
    evidence_id: 'vlm-ev-sample-0002',
    original_value: 'HOLE 20 MM',
    confidence: 1,
    reconciliation: 'ADVISORY_ONLY',
  },
]

export const PREVIEW_STATE_KEYS = [
  'READY',
  'EMPTY',
  'RUNNING_1',
  'RUNNING_2',
  'RUNNING_3',
  'RUNNING_4',
  'TIMEOUT',
  'OLLAMA',
  'MODEL',
  'VALIDATION',
  'DISABLED',
  'NOT_CONNECTED',
] as const
export type PreviewStateKey = (typeof PREVIEW_STATE_KEYS)[number]

export function previewState(key: PreviewStateKey): AiAnalysisState {
  switch (key) {
    case 'READY':
      return { kind: 'READY', findings: SAMPLE_FINDINGS }
    case 'EMPTY':
      return { kind: 'READY', findings: [] }
    case 'RUNNING_1':
      return { kind: 'RUNNING', phase: 'PREPARING_DRAWING' }
    case 'RUNNING_2':
      return { kind: 'RUNNING', phase: 'ANALYZING_REGION' }
    case 'RUNNING_3':
      return { kind: 'RUNNING', phase: 'AI_IN_PROGRESS' }
    case 'RUNNING_4':
      return { kind: 'RUNNING', phase: 'VALIDATING_RESPONSE' }
    case 'TIMEOUT':
      return { kind: 'FAILED', failure: 'TIMEOUT' }
    case 'OLLAMA':
      return { kind: 'FAILED', failure: 'OLLAMA_UNAVAILABLE' }
    case 'MODEL':
      return { kind: 'FAILED', failure: 'MODEL_UNAVAILABLE' }
    case 'VALIDATION':
      return { kind: 'FAILED', failure: 'VALIDATION_FAILED' }
    case 'DISABLED':
      return { kind: 'FAILED', failure: 'DISABLED' }
    case 'NOT_CONNECTED':
      return { kind: 'FAILED', failure: 'NOT_CONNECTED' }
  }
}
