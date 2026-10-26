import api from './apiClient'

// ---------------------------------------------------------------------------
// Request types
// ---------------------------------------------------------------------------

export interface DimensionalReqIn {
  req_id: string
  dimension_type: string
  nominal_value: number
  unit: string
  tolerance_upper?: number | null
  tolerance_lower?: number | null
  tolerance_type?: string | null
  authority?: string
  source_dimension_id?: string | null
  notes?: string | null
}

export interface DatumRefIn {
  label: string
  precedence: number
  modifier?: string
}

export interface DatumFrameIn {
  primary: DatumRefIn
  secondary?: DatumRefIn | null
  tertiary?: DatumRefIn | null
}

export interface GdtFcfIn {
  characteristic: string
  tolerance_value: number
  tolerance_unit?: string
  diameter_zone?: boolean
  modifier?: string
  datum_frame?: DatumFrameIn | null
  source_fcf_id?: string | null
}

export interface GeometricReqIn {
  req_id: string
  fcf: GdtFcfIn
  feature_ref?: string | null
  authority?: string
  source_fcf_id?: string | null
}

export interface SurfaceFinishReqIn {
  req_id: string
  ra_um?: number | null
  rz_um?: number | null
  feature_ref?: string | null
  authority?: string
}

export interface ThreadReqIn {
  req_id: string
  designation?: string | null
  standard?: string | null
  hand?: string
  nominal_diameter_mm?: number | null
  pitch_mm?: number | null
  thread_class?: string | null
  note_text?: string | null
}

export interface MaterialReqIn {
  req_id: string
  raw_designation: string
  standard?: string | null
}

export interface HeatTreatReqIn {
  req_id: string
  raw_note: string
  condition_code?: string | null
  hardness_target_hb?: number | null
  hardness_target_hrc?: number | null
}

export interface DrawingToProcessRequest {
  source_id: string
  drawing_number?: string | null
  revision?: string | null
  extraction_status?: string
  dimensional: DimensionalReqIn[]
  geometric: GeometricReqIn[]
  surface_finish: SurfaceFinishReqIn[]
  threads: ThreadReqIn[]
  material?: MaterialReqIn | null
  heat_treatment?: HeatTreatReqIn[]
  part_id?: string
}

// ---------------------------------------------------------------------------
// Response types
// ---------------------------------------------------------------------------

export interface RouteScore {
  total: number
  completeness: number
  efficiency: number
  seq_compliance: number
  dfm_compliance: number
  availability: number
}

export interface BestRoute {
  route_id: string
  feature_id: string
  feature_type: string
  operations: string[]
  required_ra_um: string | null
  achievable_ra_um: string
  requires_grinding: boolean
  route_description: string
  score: RouteScore
}

export interface RouteRejection {
  route_id: string
  reason: string
  detail: string
}

export interface RouteResult {
  feature_id: string
  feature_type: string
  route_count: number
  rejection_count: number
  rejections: RouteRejection[]
}

export interface GeneratedStep {
  step_id: string
  sequence_number: number
  operation: string
  feature_id: string | null
  route_id: string | null
  is_inspection: boolean
  notes: string
}

export interface TraceabilityEntry {
  req_id: string
  feature_id: string
  step_id: string
  recognition_rule: string
  operation: string
}

export interface MaterialResolution {
  raw_designation: string
  matched_material_id: string | null
  matched_designation: string | null
  iso_group: string | null
  confidence: string
}

export interface GeneratedProcessPlan {
  plan_id: string
  source_id: string
  drawing_number: string | null
  revision: string | null
  status: string
  step_count: number
  steps: GeneratedStep[]
  best_routes: BestRoute[]
  route_results: RouteResult[]
  traceability: TraceabilityEntry[]
  generation_warnings: string[]
  disclaimer: string
  material_resolution?: MaterialResolution
}

export interface D2PSchema {
  endpoint: string
  disclaimer: string
  supported_gdt_characteristics: string[]
  supported_gdt_modifiers: string[]
  extraction_status_values: string[]
  plan_status_values: string[]
  security_invariants: Record<string, string>
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

export async function fetchD2PSchema(): Promise<D2PSchema> {
  return api<D2PSchema>('/drawing-to-process/schema')
}

export async function generateDrawingToProcess(
  req: DrawingToProcessRequest
): Promise<GeneratedProcessPlan> {
  return api<GeneratedProcessPlan>('/drawing-to-process/generate', {
    method: 'POST',
    body: JSON.stringify(req),
  })
}
