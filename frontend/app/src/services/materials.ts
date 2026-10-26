import api from './apiClient'
import type {
  MaterialListItem,
  MaterialDetail,
  MaterialSummary,
  IsoGroupInfo,
} from '../types/materials'

export type { MaterialListItem, MaterialDetail, MaterialSummary, IsoGroupInfo }

export interface MaterialListParams {
  iso_group?: string
  family?: string
  search?: string
  limit?: number
  offset?: number
}

export async function fetchMaterialIsoGroups(): Promise<IsoGroupInfo[]> {
  return api<IsoGroupInfo[]>('/materials/iso-groups')
}

export async function fetchMaterialSummary(): Promise<MaterialSummary> {
  return api<MaterialSummary>('/materials/summary')
}

export async function fetchMaterials(params: MaterialListParams = {}): Promise<MaterialListItem[]> {
  const query = new URLSearchParams()
  if (params.iso_group) query.set('iso_group', params.iso_group)
  if (params.family) query.set('family', params.family)
  if (params.search) query.set('search', params.search)
  if (params.limit !== undefined) query.set('limit', String(params.limit))
  if (params.offset !== undefined) query.set('offset', String(params.offset))
  const qs = query.toString()
  return api<MaterialListItem[]>(`/materials${qs ? '?' + qs : ''}`)
}

export async function fetchMaterialDetail(id: string): Promise<MaterialDetail> {
  return api<MaterialDetail>(`/materials/${id}`)
}

export async function searchMaterials(q: string, limit = 50): Promise<MaterialListItem[]> {
  const query = new URLSearchParams({ q, limit: String(limit) })
  return api<MaterialListItem[]>(`/materials/search?${query.toString()}`)
}

export async function fetchMaterialMachinability(id: string): Promise<Record<string, unknown>> {
  return api<Record<string, unknown>>(`/materials/${id}/machinability`)
}

export async function fetchMaterialCuttingContext(
  id: string,
  operation?: string,
  toolMaterial?: string,
): Promise<Record<string, unknown>> {
  const query = new URLSearchParams()
  if (operation) query.set('operation', operation)
  if (toolMaterial) query.set('tool_material', toolMaterial)
  const qs = query.toString()
  return api<Record<string, unknown>>(`/materials/${id}/cutting-context${qs ? '?' + qs : ''}`)
}
