import api from './apiClient'

export interface AnalyzeRequest {
  source_id: string
  file_name: string
  content_b64: string
  title_block_unit?: string
  drawing_standard?: string
  material_raw?: string
  notes?: string[]
}

export interface AnalyzeResponse {
  session_id: string
  source_id: string
  status: string
  detection_count: number
  review_required_count: number
  detected_unit: string | null
  ocr_available: boolean
  warnings: string[]
  disclaimer: string
}

export interface DetectionOut {
  detection_id: string
  page: number | null
  source_type: string
  normalized_type: string
  normalized_value: string | null
  unit: string | null
  raw_text: string | null
  confidence: number
  confidence_method: string
  review_state: string
  review_required: boolean
  association_state: string
  association_feature_id: string | null
  association_feature_type: string
  subtype: string | null
  ambiguities: Array<{ kind: string; description: string }>
}

export interface DetectionsResponse {
  session_id: string
  detections: DetectionOut[]
  total: number
  review_required_count: number
  confirmed_count: number
  disclaimer: string
}

export interface RequirementsResponse {
  session_id: string
  source_id: string
  detected_unit: string | null
  material_status: string | null
  material_matched_id: string | null
  general_tolerance_standard: string | null
  general_tolerance_linear_mm: number | null
  confirmed_detections: DetectionOut[]
  unconfirmed_review_required: number
  disclaimer: string
}

export interface ActionResponse {
  detection_id: string
  review_state: string
  message: string
  disclaimer: string
}

export async function analyzeDrawing(req: AnalyzeRequest): Promise<AnalyzeResponse> {
  return api<AnalyzeResponse>('/api/drawing-parser/analyze', {
    method: 'POST',
    body: JSON.stringify(req),
  })
}

export async function getDetections(sessionId: string): Promise<DetectionsResponse> {
  return api<DetectionsResponse>(`/api/drawing-parser/${encodeURIComponent(sessionId)}/detections`)
}

export async function getRequirements(sessionId: string): Promise<RequirementsResponse> {
  return api<RequirementsResponse>(`/api/drawing-parser/${encodeURIComponent(sessionId)}/requirements`)
}

export async function confirmDetection(
  sessionId: string,
  detectionId: string,
  confirmedValue?: string,
  confirmedUnit?: string,
  confirmedFeatureId?: string,
): Promise<ActionResponse> {
  return api<ActionResponse>(
    `/api/drawing-parser/${encodeURIComponent(sessionId)}/detections/${encodeURIComponent(detectionId)}/confirm`,
    {
      method: 'POST',
      body: JSON.stringify({
        confirmed_value: confirmedValue ?? null,
        confirmed_unit: confirmedUnit ?? null,
        confirmed_feature_id: confirmedFeatureId ?? null,
      }),
    },
  )
}

export async function editDetection(
  sessionId: string,
  detectionId: string,
  newValue: string,
  newUnit?: string,
): Promise<ActionResponse> {
  return api<ActionResponse>(
    `/api/drawing-parser/${encodeURIComponent(sessionId)}/detections/${encodeURIComponent(detectionId)}/edit`,
    {
      method: 'POST',
      body: JSON.stringify({ new_value: newValue, new_unit: newUnit ?? null }),
    },
  )
}

export async function rejectDetection(
  sessionId: string,
  detectionId: string,
): Promise<ActionResponse> {
  return api<ActionResponse>(
    `/api/drawing-parser/${encodeURIComponent(sessionId)}/detections/${encodeURIComponent(detectionId)}/reject`,
    { method: 'POST', body: JSON.stringify({}) },
  )
}

export async function associateDetection(
  sessionId: string,
  detectionId: string,
  featureId: string,
  featureType?: string,
): Promise<ActionResponse> {
  return api<ActionResponse>(
    `/api/drawing-parser/${encodeURIComponent(sessionId)}/detections/${encodeURIComponent(detectionId)}/associate`,
    {
      method: 'POST',
      body: JSON.stringify({ feature_id: featureId, feature_type: featureType ?? null }),
    },
  )
}
