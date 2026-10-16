import { api } from './apiClient'

export interface ToolLifeSummary {
  seeded: boolean
  observation_count: number
  tool_count: number
  feature_count: number
  sensor_feature_count: number
  eol_observation_count: number
  evidence_status: string
  source_dataset: string
  source_doi: string | null
  source_sheet: string | null
  cycle_to_failure_semantics: string
  sensor_feature_headers: string[]
  limitations: string[]
}

export interface ToolSummary {
  tool_id: number
  tool_type: string
  observation_count: number
  total_cycles: number
  adoc_mm: number
  rdoc_mm: number
  eol_present: boolean
  min_cycle_to_failure: number
  max_cycle_to_failure: number
}

export interface LifecyclePoint {
  obs_idx: number
  cycle_number: number
  sample_index: number
  cycle_to_failure: number
  cycle_to_failure_normalized: number
  is_eol: boolean
}

export interface SensorSeries {
  feature_index: number
  feature_name: string
  values: number[]
}

export interface ToolDetail {
  tool_id: number
  tool_type: string
  observation_count: number
  total_cycles: number
  adoc_mm: number
  rdoc_mm: number
  tool_holder_length_mm: number
  hardness_mean: number
  eol_present: boolean
  lifecycle: LifecyclePoint[]
  sensor_series: SensorSeries
  source_doi: string | null
  evidence_status: string
}

export const toolLifeService = {
  getSummary: () => api<ToolLifeSummary>('/tool-life/summary'),
  getTools: () => api<ToolSummary[]>('/tool-life/tools'),
  getToolDetail: (toolId: number, featureIndex: number) =>
    api<ToolDetail>(`/tool-life/tools/${toolId}?feature_index=${featureIndex}`),
}
