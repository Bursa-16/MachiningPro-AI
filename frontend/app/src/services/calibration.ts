/**
 * Calibration API service — EPIC_04F.
 */

import {
  CalibrationSchema,
  CapabilityMargin,
  CycleTimeEstimate,
  CycleTimeEstimateRequest,
  ShopCalibrationProfile,
  SurfaceCapabilityMargin,
  SurfaceEvalRequest,
  ToleranceEvalRequest,
} from '../types/calibration';

const BASE = '/api/calibration';

async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem('auth_token');
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail?.detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const calibrationService = {
  getSchema(): Promise<CalibrationSchema> {
    return apiFetch(`${BASE}/schema`);
  },

  evaluateTolerance(req: ToleranceEvalRequest): Promise<CapabilityMargin> {
    return apiFetch(`${BASE}/tolerance/evaluate`, {
      method: 'POST',
      body: JSON.stringify(req),
    });
  },

  evaluateSurface(req: SurfaceEvalRequest): Promise<SurfaceCapabilityMargin> {
    return apiFetch(`${BASE}/surface/evaluate`, {
      method: 'POST',
      body: JSON.stringify(req),
    });
  },

  estimateCycleTime(req: CycleTimeEstimateRequest): Promise<CycleTimeEstimate> {
    return apiFetch(`${BASE}/cycle-time/estimate`, {
      method: 'POST',
      body: JSON.stringify(req),
    });
  },

  createProfile(profile: Partial<ShopCalibrationProfile>): Promise<ShopCalibrationProfile> {
    return apiFetch(`${BASE}/profiles`, {
      method: 'POST',
      body: JSON.stringify(profile),
    });
  },

  listProfiles(params?: {
    site_id?: string;
    machine_id?: string;
    operation_family?: string;
  }): Promise<ShopCalibrationProfile[]> {
    const qs = new URLSearchParams();
    if (params?.site_id) qs.set('site_id', params.site_id);
    if (params?.machine_id) qs.set('machine_id', params.machine_id);
    if (params?.operation_family) qs.set('operation_family', params.operation_family);
    const q = qs.toString();
    return apiFetch(`${BASE}/profiles${q ? `?${q}` : ''}`);
  },

  getProfile(profileId: string): Promise<ShopCalibrationProfile> {
    return apiFetch(`${BASE}/profiles/${profileId}`);
  },

  updateProfile(
    profileId: string,
    updates: Partial<ShopCalibrationProfile>,
  ): Promise<ShopCalibrationProfile> {
    return apiFetch(`${BASE}/profiles/${profileId}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    });
  },
};
