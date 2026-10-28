import type {
  ManufacturingPlanSummary,
  ManufacturingPlanDetail,
  ValidationResult,
  GeneratePlanRequest,
} from '../types/manufacturingPlan';

const BASE = '/api/manufacturing-plan';

async function _json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export async function generatePlan(
  req: GeneratePlanRequest,
): Promise<ManufacturingPlanSummary> {
  const res = await fetch(`${BASE}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  return _json<ManufacturingPlanSummary>(res);
}

export async function listPlans(
  drawing_number?: string,
  source_id?: string,
): Promise<ManufacturingPlanSummary[]> {
  const params = new URLSearchParams();
  if (drawing_number) params.set('drawing_number', drawing_number);
  if (source_id) params.set('source_id', source_id);
  const res = await fetch(`${BASE}?${params.toString()}`);
  return _json<ManufacturingPlanSummary[]>(res);
}

export async function getPlan(planId: string): Promise<ManufacturingPlanDetail> {
  const res = await fetch(`${BASE}/${planId}`);
  return _json<ManufacturingPlanDetail>(res);
}

export async function getPlanSummary(
  planId: string,
): Promise<ManufacturingPlanSummary> {
  const res = await fetch(`${BASE}/${planId}/summary`);
  return _json<ManufacturingPlanSummary>(res);
}

export async function validatePlan(planId: string): Promise<ValidationResult> {
  const res = await fetch(`${BASE}/${planId}/validate`, { method: 'POST' });
  return _json<ValidationResult>(res);
}

export async function markReviewed(
  planId: string,
  engineer_note = '',
): Promise<ManufacturingPlanSummary> {
  const res = await fetch(`${BASE}/${planId}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ engineer_note }),
  });
  return _json<ManufacturingPlanSummary>(res);
}

export async function approvePlan(
  planId: string,
  engineer_note = '',
): Promise<ManufacturingPlanSummary> {
  const res = await fetch(`${BASE}/${planId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ engineer_note }),
  });
  return _json<ManufacturingPlanSummary>(res);
}

export async function rejectPlan(
  planId: string,
  engineer_note = '',
): Promise<ManufacturingPlanSummary> {
  const res = await fetch(`${BASE}/${planId}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ engineer_note }),
  });
  return _json<ManufacturingPlanSummary>(res);
}

export async function getNcHandoff(planId: string): Promise<unknown> {
  const res = await fetch(`${BASE}/${planId}/nc-handoff`);
  return _json<unknown>(res);
}

export async function exportPlan(
  planId: string,
  format: 'json' | 'csv_operations' | 'csv_inspection' | 'html' | 'package' = 'json',
): Promise<{ content?: string; [key: string]: unknown }> {
  const res = await fetch(`${BASE}/${planId}/export?format=${format}`);
  return _json<{ content?: string }>(res);
}
