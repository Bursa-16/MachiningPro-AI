import api from './apiClient'

// ---------------------------------------------------------------------------
// Request / Response types
// ---------------------------------------------------------------------------

export interface AnalyzeCadRequest {
  file_name: string
  content_b64: string
  source_id?: string
}

export interface AnalyzeCadResponse {
  session_id: string
  source_id: string
  status: string
  face_count: number
  body_count: number
  feature_count: number
  pattern_count: number
  warnings: string[]
}

export interface ManufacturingFeatureOut {
  feature_id: string
  feature_type: string
  confidence: string
  method: string
  diameter_mm: number | null
  radius_mm: number | null
  depth_mm: number | null
  surface_type: string | null
  source_face_ids: string[]
  axis_count: string | null
  warnings: string[]
}

export interface FeaturesResponse {
  session_id: string
  total: number
  features: ManufacturingFeatureOut[]
}

export interface PatternOut {
  pattern_id: string
  pattern_type: string
  feature_ids: string[]
  count: number
  description: string
}

export interface PatternsResponse {
  session_id: string
  total: number
  patterns: PatternOut[]
}

export interface FusionStatusResponse {
  session_id: string
  fusion_available: boolean
  message: string
  fusion_id?: string
  completeness?: string
  cad_only_count?: number
  drawing_only_count?: number
  unresolved_count?: number
  auto_matched_count?: number
}

export interface ConfirmFeatureResponse {
  session_id: string
  feature_id: string
  status: string
  message: string
}

export interface RejectFeatureResponse {
  session_id: string
  feature_id: string
  status: string
  message: string
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export async function analyzeCad(req: AnalyzeCadRequest): Promise<AnalyzeCadResponse> {
  return api<AnalyzeCadResponse>('/cad-features/analyze', {
    method: 'POST',
    body: JSON.stringify(req),
  })
}

export async function getCadSession(sessionId: string): Promise<AnalyzeCadResponse> {
  return api<AnalyzeCadResponse>(`/cad-features/${encodeURIComponent(sessionId)}`)
}

export async function getCadFeatures(sessionId: string): Promise<FeaturesResponse> {
  return api<FeaturesResponse>(`/cad-features/${encodeURIComponent(sessionId)}/features`)
}

export async function getCadPatterns(sessionId: string): Promise<PatternsResponse> {
  return api<PatternsResponse>(`/cad-features/${encodeURIComponent(sessionId)}/patterns`)
}

export async function getFusionStatus(sessionId: string): Promise<FusionStatusResponse> {
  return api<FusionStatusResponse>(`/cad-features/${encodeURIComponent(sessionId)}/fusion`)
}

export async function confirmFeature(
  sessionId: string,
  featureId: string,
  userId: string,
): Promise<ConfirmFeatureResponse> {
  return api<ConfirmFeatureResponse>(
    `/cad-features/${encodeURIComponent(sessionId)}/features/${encodeURIComponent(featureId)}/confirm`,
    {
      method: 'POST',
      body: JSON.stringify({ user_id: userId }),
    },
  )
}

export async function rejectFeature(
  sessionId: string,
  featureId: string,
): Promise<RejectFeatureResponse> {
  return api<RejectFeatureResponse>(
    `/cad-features/${encodeURIComponent(sessionId)}/features/${encodeURIComponent(featureId)}/reject`,
    { method: 'POST', body: JSON.stringify({}) },
  )
}
