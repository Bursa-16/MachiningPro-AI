/**
 * Calibration domain types — EPIC_04F.
 * FABRICATED_PROCESS_CAPABILITY=NO
 * FABRICATED_CYCLE_TIME=NO
 */

export type CalibrationSource =
  | 'USER_OVERRIDE'
  | 'SHOP_VALIDATED'
  | 'MACHINE_PROFILE'
  | 'MANUFACTURER_REFERENCE'
  | 'LITERATURE_REFERENCE'
  | 'GLOBAL_REFERENCE'
  | 'ESTIMATED'
  | 'INSUFFICIENT_DATA';

export type CapabilityStatus =
  | 'ROBUST'
  | 'ACCEPTABLE'
  | 'MARGINAL'
  | 'NOT_CAPABLE'
  | 'INSUFFICIENT_DATA';

export type CycleComponentStatus =
  | 'CALCULATED'
  | 'REFERENCE'
  | 'USER_SUPPLIED'
  | 'ESTIMATED'
  | 'UNKNOWN';

export type CycleTimeCompleteness =
  | 'FULLY_CALCULATED'
  | 'PARTIALLY_CALCULATED'
  | 'ESTIMATED'
  | 'INSUFFICIENT_DATA';

export interface CapabilityMargin {
  status: CapabilityStatus;
  required_tolerance_um: number;
  reference_capability_um: number | null;
  margin_um: number | null;
  margin_ratio: number | null;
  confidence: string;
  source: CalibrationSource;
  operation: string;
  nominal_size_mm: number | null;
  reason: string;
  notes: string;
}

export interface SurfaceCapabilityMargin {
  status: CapabilityStatus;
  required_ra_um: number;
  achievable_ra_um_best: number | null;
  achievable_ra_um_typical: number | null;
  margin_ratio: number | null;
  confidence: string;
  source: CalibrationSource;
  operation: string;
  reason: string;
  notes: string;
}

export interface CycleTimeComponent {
  component_id: string;
  component_type: string;
  status: CycleComponentStatus;
  value_sec_min: number | null;
  value_sec_max: number | null;
  source: CalibrationSource;
  confidence: string;
  method: string;
  missing_inputs: string[];
  notes: string;
}

export interface CycleTimeEstimate {
  components: CycleTimeComponent[];
  completeness: CycleTimeCompleteness;
  known_total_sec_min: number | null;
  known_total_sec_max: number | null;
  total_cycle_time_sec_min: number | null;
  total_cycle_time_sec_max: number | null;
  unknown_components: string[];
  uncertainty_note: string;
  limitations: string[];
  batch_model?: BatchModel;
}

export interface BatchModel {
  batch_quantity: number;
  setup_sec: number | null;
  per_part_cutting_sec_min: number | null;
  per_part_cutting_sec_max: number | null;
  per_part_setup_sec: number | null;
  per_part_total_sec_min: number | null;
  per_part_total_sec_max: number | null;
  completeness: CycleTimeCompleteness;
}

export interface ShopCalibrationProfile {
  profile_id: string;
  label: string;
  site_id: string | null;
  machine_id: string | null;
  operation_family: string | null;
  material_iso_group: string | null;
  tool_family: string | null;
  feature_type: string | null;
  atc_time_sec: number | null;
  setup_time_sec: number | null;
  load_unload_time_sec: number | null;
  probing_time_sec: number | null;
  inspection_time_sec: number | null;
  validated_it_grade_min: number | null;
  validated_ra_um: number | null;
  source: CalibrationSource;
  confidence: string;
  notes: string;
  created_at: string;
  updated_at: string;
  revision: number;
}

export interface ToleranceEvalRequest {
  operation: string;
  required_tolerance_um: number;
  nominal_size_mm: number;
  machine_validated?: boolean;
}

export interface SurfaceEvalRequest {
  operation: string;
  required_ra_um: number;
  use_typical?: boolean;
}

export interface CycleTimeEstimateRequest {
  cutting_sec_min?: number;
  cutting_sec_max?: number;
  rapid_sec?: number;
  dwell_sec?: number;
  atc_time_sec?: number;
  tool_changes?: number;
  setup_sec?: number;
  load_unload_sec?: number;
  probing_sec?: number;
  machine_id?: string;
  batch_quantity?: number;
}

export interface CalibrationSchema {
  tolerance_operations: string[];
  surface_operations: string[];
  calibration_sources: string[];
  disclaimer: string;
}
