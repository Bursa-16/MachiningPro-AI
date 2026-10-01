// MachiningPro AI API Types — derived from backend/app.py contracts

export interface LoginRequest { username: string; password: string }
export interface LoginResponse { token: string; display_name: string; role: string; expires_in: number }
export interface HealthResponse { status: string; version: string; database_ok: boolean; server_time: string }




export interface SystemInfo {
  status: string; version: string; database_ok: boolean; database_size_kb: number
  total_users: number; active_users: number; calculation_count: number
  audit_count: number; schema_version: number; server_time: string
}

export type UserRole = 'admin' | 'engineer' | 'viewer'
export interface AuthUser { id: number; username: string; display_name: string; role: UserRole; is_active: number }
export type FeatureStatus = 'ready' | 'beta' | 'planned'
export type EngineeringStatus = 'validated' | 'calculated' | 'warning' | 'error' | 'draft' | 'review' | 'ai_assisted'
