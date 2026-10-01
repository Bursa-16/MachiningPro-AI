import api from './apiClient'
import type { SystemInfo } from '../types/api'

export const getSystemInfo = () => api<SystemInfo>('/admin/system')
export const getUsers = () => api<any[]>('/admin/users')
export const getAuditLog = () => api<any[]>('/admin/audit')
export const getHealth = () => api<any>('/health')
export const getQualityGate = () => api<any>('/admin/quality-gate')
export const getGoldenCases = () => api<any[]>('/admin/golden-cases')
export const getDataVersions = () => api<any[]>('/admin/data-versions')
export const getDataPackages = () => api<any[]>('/admin/data-packages')
export const getActiveData = () => api<any>('/data/active')
export const getEngineLibrary = () => api<any>('/data/engine-library')
export const getCalibrationCases = () => api<any[]>('/calibration/cases')
export const getCalibrationSummary = () => api<any>('/calibration/summary')
