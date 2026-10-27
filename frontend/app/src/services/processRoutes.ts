/**
 * Process Route Optimization API service — EPIC_04E Phase 2.
 *
 * FABRICATED_ROUTE=NO
 * AUTO_SELECTED_ROUTE_MARKED_APPROVED=NO
 * BLACK_BOX_AI_SCORE_USED=NO
 */

const BASE = '/api/process-routes'

// ─────────────────────────────────────────────────────────────────────────────
// Request types
// ─────────────────────────────────────────────────────────────────────────────

export interface FeatureRouteRequestBody {
  feature_id: string
  feature_type: string
  required_ra_um?: number | null
  required_it_grade?: string | null
  diameter_mm?: number | null
  has_tight_position?: boolean
  has_runout?: boolean
  has_profile?: boolean
  has_inspection?: boolean
  iso_material_group?: string | null
  material_machinability?: string | null
  spindle_interface?: string | null
  available_machine_type_codes?: string[] | null
  material_incompatible_ops?: string[] | null
  inspection_notes?: string[] | null
  pattern_count?: number
  strategy?: string
}

export interface PartRouteRequestBody {
  source_id: string
  drawing_number?: string | null
  revision?: string | null
  features: FeatureRouteRequestBody[]
  same_setup_pairs?: string[][] | null
  datum_constraints?: Record<string, string> | null
  strategy?: string
  max_routes_per_feature?: number
  max_machine_candidates?: number
  max_tool_candidates?: number
  max_holder_candidates?: number
  beam_width?: number
  include_pareto?: boolean
  max_setups?: number
}

// ─────────────────────────────────────────────────────────────────────────────
// Response types
// ─────────────────────────────────────────────────────────────────────────────

export interface RouteScoreBreakdown {
  total: number
  technical_feasibility: number
  requirement_coverage: number
  process_capability: number
  gdt_confidence: number
  machine_compatibility: number
  tool_compatibility: number
  setup_efficiency: number
  cycle_time: number
  data_completeness: number
  risk_penalty: number
  strategy_bonus: number
}

export interface RouteOperation {
  op_id: string
  sequence_no: number
  operation_type: string
  sub_operation: string | null
  is_inspection: boolean
  notes: string
}

export interface MachineCandidateSummary {
  machine_id: string
  manufacturer: string
  model: string
  machine_type_code: string
  suitability_score: number
  notes: string
  REFERENCE_ONLY: boolean
}

export interface ToolCandidateSummary {
  tool_id: string
  manufacturer: string
  product_name: string
  tool_type_code: string
  suitability_score: number
  notes: string
  REFERENCE_ONLY: boolean
}

export interface HolderCandidateSummary {
  holder_id: string
  manufacturer: string
  product_name: string
  machine_interface_key: string
  suitability_score: number
  notes: string
  REFERENCE_ONLY: boolean
}

export interface ParameterVariant {
  variant: string
  vc_m_min: number | null
  fz_mm: number | null
  ap_mm: number | null
  confidence: string
  notes: string
}

export interface ParameterContext {
  material_iso_group: string | null
  variants: ParameterVariant[]
  REFERENCE_ONLY: boolean
}

export interface RiskFlag {
  flag_id: string
  category: string
  severity: string
  description: string
  mitigation_note: string
}

export interface RouteRisk {
  overall_risk: string
  flag_count: number
  critical_count: number
  high_count: number
  flags: RiskFlag[]
}

export interface RouteExplanation {
  why_selected: string
  gdt_tolerance_decisions: string[]
  machine_selection_rationale: string | null
  tool_selection_rationale: string | null
  rejected_alternatives_summary: string[]
  uncertain_data_items: string[]
}

export interface ParetoRoute {
  route_id: string
  score_total: number
  op_count: number
  setup_count: number
  risk_level: string
  is_pareto_optimal: boolean
  dominated_by: string[]
}

export interface ProcessRouteCandidate {
  route_id: string
  feature_id: string
  strategy: string
  status: string
  is_feasible: boolean
  feasibility: {
    status: string
    reason: string
    requirement_coverage: number
  }
  op_count: number
  setup_count: number
  operations: RouteOperation[]
  machine_candidates: MachineCandidateSummary[]
  tool_candidates: ToolCandidateSummary[]
  holder_candidates: HolderCandidateSummary[]
  parameter_context: ParameterContext | null
  score: RouteScoreBreakdown
  risk: RouteRisk
  explanation: RouteExplanation
  unresolved_items: string[]
  rejection_reasons: Array<{ reason: string; detail: string }>
  traceability_fingerprint: string
}

export interface RouteAlternativeSet {
  source_id: string
  feature_id: string
  selected_route_id: string | null
  selection_rationale: string
  feasible_count: number
  candidate_count: number
  pareto_count: number
  candidates: ProcessRouteCandidate[]
  pareto_frontier: ParetoRoute[]
}

export interface RouteBenchmark {
  total_candidates_generated: number
  feasible_candidates: number
  infeasible_candidates: number
  valid_route_recall: number
  setup_count: number
  requirement_coverage: number
  determinism_rate: number
  FABRICATED_ROUTE: boolean
  AUTO_SELECTED_ROUTE_MARKED_APPROVED: boolean
  BLACK_BOX_AI_SCORE_USED: boolean
}

export interface OptimizedPlan {
  plan_id: string
  source_id: string
  drawing_number: string | null
  revision: string | null
  status: string
  strategy: string
  step_count: number
  alternative_set_count: number
  risk: { overall_risk: string; flag_count: number }
  traceability_fingerprint: string
  generation_warnings: string[]
  disclaimer: string
}

export interface GenerateFeatureRoutesResponse {
  feature_id: string
  strategy: string
  alternative_set: RouteAlternativeSet
  disclaimer: string
}

export interface OptimizePartRoutesResponse {
  plan: OptimizedPlan
  alternative_sets: RouteAlternativeSet[]
  benchmark: RouteBenchmark
  disclaimer: string
}

// ─────────────────────────────────────────────────────────────────────────────
// API calls
// ─────────────────────────────────────────────────────────────────────────────

async function post<T>(path: string, body: unknown): Promise<T> {
  const resp = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail ?? `HTTP ${resp.status}`)
  }
  return resp.json()
}

async function get<T>(path: string): Promise<T> {
  const resp = await fetch(path)
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail ?? `HTTP ${resp.status}`)
  }
  return resp.json()
}

export const processRoutesApi = {
  generateFeatureRoutes: (body: FeatureRouteRequestBody): Promise<GenerateFeatureRoutesResponse> =>
    post(`${BASE}/generate`, body),

  optimizePart: (body: PartRouteRequestBody): Promise<OptimizePartRoutesResponse> =>
    post(`${BASE}/optimize`, body),

  getPlan: (planId: string): Promise<unknown> =>
    get(`${BASE}/${planId}`),

  getAlternatives: (planId: string): Promise<{ plan_id: string; alternative_sets: RouteAlternativeSet[] }> =>
    get(`${BASE}/${planId}/alternatives`),

  selectRoute: (
    planId: string,
    featureId: string,
    routeId: string,
    rationale?: string
  ): Promise<unknown> =>
    post(`${BASE}/${planId}/select`, { feature_id: featureId, route_id: routeId, rationale }),

  applyOverride: (
    planId: string,
    featureId: string,
    overrideType: string,
    targetId: string,
    value: string,
    note?: string
  ): Promise<unknown> =>
    post(`${BASE}/${planId}/override`, {
      feature_id: featureId,
      override_type: overrideType,
      target_id: targetId,
      value,
      note,
    }),
}
