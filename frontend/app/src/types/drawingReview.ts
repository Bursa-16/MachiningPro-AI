// Human-review model for advisory AI drawing findings.
//
// Mirrors the backend `DrawingVlmEvidence` provenance. AI authority is always
// ADVISORY; a human review is a separate, append-only provenance event and never
// rewrites the AI finding or the deterministic result.

export type ReviewStatus = 'PENDING_REVIEW' | 'ACCEPTED' | 'REJECTED' | 'EDITED'

/** Where the finding's box came from. REGION_EXTENT is a source region, not a text box. */
export type BoxBasis = 'REGION_EXTENT' | 'MODEL_PIXEL_BOX'

/** Result of comparing the AI finding with deterministic evidence (backend R3C). */
export type Reconciliation =
  | 'CORROBORATED'
  | 'CONFLICT'
  | 'RECOVERY_CANDIDATE'
  | 'ADVISORY_ONLY'
  | 'AMBIGUOUS'
  | 'NOT_COMPARABLE'

export interface AdvisoryFinding {
  evidence_id: string
  candidate_type: string
  /** The model's transcription, kept verbatim. Never edited. */
  original_value: string
  legibility: 'CLEAR' | 'DEGRADED' | 'ILLEGIBLE'
  /** 0..1 or null when the model gave none. */
  confidence: number | null
  /** Constant ADVISORY: the UI has no way to represent an authoritative AI finding. */
  authority: 'ADVISORY'
  provider_id: string
  model_id: string
  model_version: string
  region_id: string
  request_id: string
  box_basis: BoxBasis
  reconciliation: Reconciliation | null
  /** Present on live evidence; the sample fixture omits them. */
  prompt_contract_version?: string
  schema_version?: string
}

/** A value produced by the deterministic parser/OCR pipeline. */
export interface DeterministicItem {
  id: string
  label: string
  value: string
  source: string
}

export interface SourceRegion {
  region_id: string
  /** Region extent in the drawing's own coordinate space (page points). */
  x0: number
  top: number
  x1: number
  bottom: number
}

export interface ReviewEvent {
  status: Exclude<ReviewStatus, 'PENDING_REVIEW'>
  /** Present for EDITED: the human-supplied value. Accepted keeps the AI value. */
  reviewed_value: string | null
  reviewed_by: string | null
  reviewed_at: string
}

/** Append-only review record for one finding. */
export interface ReviewRecord {
  evidence_id: string
  status: ReviewStatus
  original_ai_value: string
  reviewed_value: string | null
  reviewed_by: string | null
  reviewed_at: string | null
  history: readonly ReviewEvent[]
}

export type ReviewState = Readonly<Record<string, ReviewRecord>>

export type ReviewAction =
  | { type: 'ACCEPT'; evidence_id: string; reviewed_by: string | null; reviewed_at: string }
  | { type: 'REJECT'; evidence_id: string; reviewed_by: string | null; reviewed_at: string }
  | {
      type: 'EDIT'
      evidence_id: string
      value: string
      reviewed_by: string | null
      reviewed_at: string
    }

/** Mirrors the backend job states QUEUED / PREPARING / ANALYZING / VALIDATING. */
export type AnalysisPhase =
  | 'QUEUED'
  | 'PREPARING_DRAWING'
  | 'AI_IN_PROGRESS'
  | 'VALIDATING_RESPONSE'

export type AiFailureKind =
  | 'DISABLED'
  | 'OLLAMA_UNAVAILABLE'
  | 'MODEL_UNAVAILABLE'
  | 'TIMEOUT'
  | 'VALIDATION_FAILED'
  | 'INVALID_DRAWING'
  | 'INVALID_REGION'
  | 'NOT_CONNECTED'
  | 'UNKNOWN'

export type AiAnalysisState =
  | { kind: 'IDLE' }
  | { kind: 'RUNNING'; phase: AnalysisPhase }
  | { kind: 'READY'; findings: readonly AdvisoryFinding[] }
  | { kind: 'FAILED'; failure: AiFailureKind }
