import api from './apiClient'

// ---------------------------------------------------------------------------
// Request types
// ---------------------------------------------------------------------------

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

export interface FcfIn {
  characteristic: string
  tolerance_value: number
  tolerance_unit?: string
  diameter_zone?: boolean
  modifier?: string
  datum_frame?: DatumFrameIn | null
  source_fcf_id?: string | null
}

export interface FosIn {
  fos_id: string
  kind: string
  nominal_mm?: number | null
  upper_limit_mm?: number | null
  lower_limit_mm?: number | null
  actual_size_mm?: number | null
  source_req_id?: string | null
  feature_id?: string | null
}

export interface ValidateRequest {
  req_id: string
  fcf: FcfIn
  fos?: FosIn | null
}

export interface InterpretRequest {
  req_id: string
  fcf: FcfIn
  fos?: FosIn | null
}

export interface BonusToleranceRequest {
  req_id: string
  fcf: FcfIn
  fos: FosIn
}

export interface VirtualConditionRequest {
  req_id: string
  fcf: FcfIn
  fos: FosIn
}

// ---------------------------------------------------------------------------
// Response types
// ---------------------------------------------------------------------------

export interface ValidationFinding {
  rule_id: string
  passed: boolean
  severity: string
  message: string
  ambiguity_kind: string | null
  ambiguity_description: string | null
  suggested_resolution: string | null
}

export interface ValidationResult {
  req_id: string
  overall: 'VALID' | 'INVALID' | 'INSUFFICIENT_DATA'
  findings: ValidationFinding[]
  disclaimer: string
}

export interface ToleranceZone {
  geometry: string
  diameter_zone: boolean
  value_mm: number
  unit: string
}

export interface DatumRefOut {
  label: string
  precedence: number
  modifier: string
}

export interface DatumFrameOut {
  primary: DatumRefOut
  secondary: DatumRefOut | null
  tertiary: DatumRefOut | null
}

export interface FosOut {
  fos_id: string
  kind: string
  nominal_mm: number | null
  upper_limit_mm: number | null
  lower_limit_mm: number | null
  mmc_size_mm: number | null
  lmc_size_mm: number | null
  actual_size_mm: number | null
  is_true_fos: boolean
}

export interface ProcessImplication {
  rule_id: string
  description: string
  severity: string
}

export interface InspectionImplication {
  method: string
  rationale: string
  for_modifier: boolean
}

export interface AmbiguityItem {
  ambiguity_id: string
  kind: string
  severity: string
  description: string
  suggested_resolution: string | null
}

export interface InterpretResult {
  req_id: string
  characteristic: string
  tolerance_value: number
  tolerance_unit: string
  modifier: string
  modifier_description: string
  diameter_zone: boolean
  tolerance_zone: ToleranceZone
  datum_frame: DatumFrameOut | null
  fos_context: FosOut | null
  process_implications: ProcessImplication[]
  inspection_implications: InspectionImplication[]
  ambiguities: AmbiguityItem[]
  confidence: string
  approval_status: string
  disclaimer: string
}

export interface BonusToleranceResult {
  req_id: string
  computed: boolean
  stated_tolerance_mm: number
  bonus_amount_mm: number | null
  total_tolerance_mm: number | null
  actual_size_mm: number | null
  mmc_or_lmc_size_mm: number | null
  reason_not_computed: string | null
  disclaimer: string
}

export interface VirtualConditionResult {
  req_id: string
  computed: boolean
  virtual_condition_mm: number | null
  description: string
  disclaimer: string
}

export interface GdtSchema {
  characteristics: string[]
  feature_modifiers: string[]
  datum_boundary_modifiers: string[]
  tolerance_zone_geometries: string[]
  feature_of_size_kinds: string[]
  confidence_states: string[]
  ambiguity_kinds: string[]
  inspection_methods: string[]
  validation_rule_ids: string[]
  disclaimer: string
}

// ---------------------------------------------------------------------------
// Service functions
// ---------------------------------------------------------------------------

export async function fetchGdtSchema(): Promise<GdtSchema> {
  return api<GdtSchema>('/api/gdt/schema')
}

export async function validateGdt(req: ValidateRequest): Promise<ValidationResult> {
  return api<ValidationResult>('/api/gdt/validate', { method: 'POST', body: JSON.stringify(req) })
}

export async function interpretGdt(req: InterpretRequest): Promise<InterpretResult> {
  return api<InterpretResult>('/api/gdt/interpret', { method: 'POST', body: JSON.stringify(req) })
}

export async function calcBonusTolerance(req: BonusToleranceRequest): Promise<BonusToleranceResult> {
  return api<BonusToleranceResult>('/api/gdt/bonus-tolerance', { method: 'POST', body: JSON.stringify(req) })
}

export async function calcVirtualCondition(req: VirtualConditionRequest): Promise<VirtualConditionResult> {
  return api<VirtualConditionResult>('/api/gdt/virtual-condition', { method: 'POST', body: JSON.stringify(req) })
}
