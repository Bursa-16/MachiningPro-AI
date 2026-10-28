/**
 * Process Capability & Calibration Page — EPIC_04F.
 *
 * FABRICATED_PROCESS_CAPABILITY=NO
 * FABRICATED_CYCLE_TIME=NO
 * UNKNOWN_TIME_COMPONENT_TREATED_AS_ZERO=NO
 * PARTIAL_TIME_PRESENTED_AS_TOTAL=NO
 */

import { useCallback, useState } from 'react'
import { calibrationService } from '../services/calibration'
import type {
  CapabilityMargin,
  CycleTimeEstimate,
  ShopCalibrationProfile,
  SurfaceCapabilityMargin,
} from '../types/calibration'

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

const DISCLAIMER =
  'REFERENCE_ONLY — public engineering handbooks. ' +
  'FABRICATED_PROCESS_CAPABILITY=NO. FABRICATED_CYCLE_TIME=NO. ' +
  'Validate before manufacturing use.'

const TOLERANCE_OPS = [
  'ROUGH_TURNING', 'FINISH_TURNING', 'ROUGH_MILLING', 'FINISH_MILLING',
  'DRILLING', 'REAMING', 'ROUGH_BORING', 'FINISH_BORING',
  'THREADING', 'GRINDING', 'HONING',
]

const SURFACE_OPS = [
  'ROUGH_TURNING', 'FINISH_TURNING', 'ROUGH_MILLING', 'FINISH_MILLING',
  'REAMING', 'BORING', 'GRINDING', 'HONING', 'LAPPING',
]

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function CapBadge({ status }: { status: string }) {
  const cls =
    status === 'ROBUST' ? 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300' :
    status === 'ACCEPTABLE' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300' :
    status === 'MARGINAL' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300' :
    status === 'NOT_CAPABLE' ? 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300' :
    'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400'
  return (
    <span className={`px-2 py-0.5 text-[11px] font-semibold rounded ${cls}`}>{status}</span>
  )
}

function CompBadge({ completeness }: { completeness: string }) {
  const cls =
    completeness === 'FULLY_CALCULATED' ? 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300' :
    completeness === 'PARTIALLY_CALCULATED' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300' :
    'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400'
  return (
    <span className={`px-2 py-0.5 text-[11px] font-semibold rounded ${cls}`}>{completeness}</span>
  )
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--tp-text-3)] mb-2">
      {children}
    </div>
  )
}

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between items-center py-1 border-b border-[var(--tp-border)] last:border-0">
      <span className="text-xs text-[var(--tp-text-2)]">{label}</span>
      <span className="text-xs font-medium text-[var(--tp-text-1)]">{value ?? '—'}</span>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Tolerance tab
// ─────────────────────────────────────────────────────────────────────────────

function ToleranceTab() {
  const [operation, setOperation] = useState(TOLERANCE_OPS[1])
  const [toleranceUm, setToleranceUm] = useState('25')
  const [sizeUm, setSizeUm] = useState('50')
  const [machineValidated, setMachineValidated] = useState(false)
  const [result, setResult] = useState<CapabilityMargin | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const evaluate = useCallback(async () => {
    const tol = parseFloat(toleranceUm)
    const sz = parseFloat(sizeUm)
    if (isNaN(tol) || tol <= 0 || isNaN(sz) || sz <= 0) {
      setError('Enter positive numeric values for tolerance and size.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const r = await calibrationService.evaluateTolerance({
        operation,
        required_tolerance_um: tol,
        nominal_size_mm: sz,
        machine_validated: machineValidated,
      })
      setResult(r)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Request failed')
    } finally {
      setLoading(false)
    }
  }, [operation, toleranceUm, sizeUm, machineValidated])

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-[var(--tp-text-2)] mb-1">Operation Family</label>
          <select
            value={operation}
            onChange={e => setOperation(e.target.value)}
            className="w-full border border-[var(--tp-border)] rounded px-2 py-1.5 text-sm bg-[var(--tp-bg-1)] text-[var(--tp-text-1)]"
          >
            {TOLERANCE_OPS.map(op => <option key={op}>{op}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-[var(--tp-text-2)] mb-1">Required Tolerance (µm)</label>
          <input
            type="number" min="0.1" step="0.1" value={toleranceUm}
            onChange={e => setToleranceUm(e.target.value)}
            className="w-full border border-[var(--tp-border)] rounded px-2 py-1.5 text-sm bg-[var(--tp-bg-1)] text-[var(--tp-text-1)]"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-[var(--tp-text-2)] mb-1">Nominal Size (mm)</label>
          <input
            type="number" min="1" max="500" step="1" value={sizeUm}
            onChange={e => setSizeUm(e.target.value)}
            className="w-full border border-[var(--tp-border)] rounded px-2 py-1.5 text-sm bg-[var(--tp-bg-1)] text-[var(--tp-text-1)]"
          />
        </div>
        <div className="flex items-end pb-1.5">
          <label className="flex items-center gap-2 text-xs text-[var(--tp-text-2)] cursor-pointer">
            <input
              type="checkbox" checked={machineValidated}
              onChange={e => setMachineValidated(e.target.checked)}
              className="accent-[var(--tp-accent)]"
            />
            Machine validated
          </label>
        </div>
      </div>
      <button
        onClick={evaluate} disabled={loading}
        className="px-4 py-2 text-sm rounded bg-[var(--tp-accent)] text-white font-medium hover:opacity-90 disabled:opacity-50"
      >
        {loading ? 'Evaluating…' : 'Evaluate'}
      </button>
      {error && <p className="text-xs text-red-500">{error}</p>}
      {result && (
        <div className="border border-[var(--tp-border)] rounded p-3 space-y-2">
          <div className="flex items-center gap-2">
            <SectionLabel>Result</SectionLabel>
            <CapBadge status={result.status} />
          </div>
          <InfoRow label="Operation" value={result.operation} />
          <InfoRow label="Required tolerance" value={`${result.required_tolerance_um} µm`} />
          <InfoRow label="Reference capability" value={result.reference_capability_um != null ? `${result.reference_capability_um} µm` : '—'} />
          <InfoRow label="Margin" value={result.margin_um != null ? `${result.margin_um.toFixed(1)} µm` : '—'} />
          <InfoRow label="Margin ratio" value={result.margin_ratio != null ? result.margin_ratio.toFixed(3) : '—'} />
          <InfoRow label="Source" value={result.source} />
          <InfoRow label="Confidence" value={result.confidence} />
          <div className="pt-1 text-[11px] text-[var(--tp-text-3)]">{result.reason}</div>
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Surface tab
// ─────────────────────────────────────────────────────────────────────────────

function SurfaceTab() {
  const [operation, setOperation] = useState(SURFACE_OPS[1])
  const [raUm, setRaUm] = useState('1.6')
  const [useTypical, setUseTypical] = useState(false)
  const [result, setResult] = useState<SurfaceCapabilityMargin | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const evaluate = useCallback(async () => {
    const ra = parseFloat(raUm)
    if (isNaN(ra) || ra <= 0) { setError('Enter a positive Ra value.'); return }
    setLoading(true); setError(null)
    try {
      const r = await calibrationService.evaluateSurface({ operation, required_ra_um: ra, use_typical: useTypical })
      setResult(r)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Request failed')
    } finally { setLoading(false) }
  }, [operation, raUm, useTypical])

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-[var(--tp-text-2)] mb-1">Operation Family</label>
          <select value={operation} onChange={e => setOperation(e.target.value)}
            className="w-full border border-[var(--tp-border)] rounded px-2 py-1.5 text-sm bg-[var(--tp-bg-1)] text-[var(--tp-text-1)]">
            {SURFACE_OPS.map(op => <option key={op}>{op}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-[var(--tp-text-2)] mb-1">Required Ra (µm)</label>
          <input type="number" min="0.01" step="0.01" value={raUm} onChange={e => setRaUm(e.target.value)}
            className="w-full border border-[var(--tp-border)] rounded px-2 py-1.5 text-sm bg-[var(--tp-bg-1)] text-[var(--tp-text-1)]" />
        </div>
        <div className="flex items-end pb-1.5">
          <label className="flex items-center gap-2 text-xs text-[var(--tp-text-2)] cursor-pointer">
            <input type="checkbox" checked={useTypical} onChange={e => setUseTypical(e.target.checked)} className="accent-[var(--tp-accent)]" />
            Use typical Ra (not best-case)
          </label>
        </div>
      </div>
      <button onClick={evaluate} disabled={loading}
        className="px-4 py-2 text-sm rounded bg-[var(--tp-accent)] text-white font-medium hover:opacity-90 disabled:opacity-50">
        {loading ? 'Evaluating…' : 'Evaluate'}
      </button>
      {error && <p className="text-xs text-red-500">{error}</p>}
      {result && (
        <div className="border border-[var(--tp-border)] rounded p-3 space-y-2">
          <div className="flex items-center gap-2"><SectionLabel>Result</SectionLabel><CapBadge status={result.status} /></div>
          <InfoRow label="Operation" value={result.operation} />
          <InfoRow label="Required Ra" value={`${result.required_ra_um} µm`} />
          <InfoRow label="Achievable Ra (best)" value={result.achievable_ra_um_best != null ? `${result.achievable_ra_um_best} µm` : '—'} />
          <InfoRow label="Achievable Ra (typical)" value={result.achievable_ra_um_typical != null ? `${result.achievable_ra_um_typical} µm` : '—'} />
          <InfoRow label="Margin ratio" value={result.margin_ratio != null ? result.margin_ratio.toFixed(3) : '—'} />
          <InfoRow label="Source" value={result.source} />
          <div className="pt-1 text-[11px] text-[var(--tp-text-3)]">{result.reason}</div>
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Cycle Time tab
// ─────────────────────────────────────────────────────────────────────────────

function CycleTimeTab() {
  const [cuttingMin, setCuttingMin] = useState('')
  const [cuttingMax, setCuttingMax] = useState('')
  const [rapidSec, setRapidSec] = useState('')
  const [atcSec, setAtcSec] = useState('')
  const [toolChanges, setToolChanges] = useState('1')
  const [setupSec, setSetupSec] = useState('')
  const [loadUnloadSec, setLoadUnloadSec] = useState('')
  const [batchQty, setBatchQty] = useState('')
  const [result, setResult] = useState<CycleTimeEstimate | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const num = (s: string): number | undefined => { const v = parseFloat(s); return isNaN(v) ? undefined : v }

  const estimate = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const r = await calibrationService.estimateCycleTime({
        cutting_sec_min: num(cuttingMin),
        cutting_sec_max: num(cuttingMax) ?? num(cuttingMin),
        rapid_sec: num(rapidSec),
        atc_time_sec: num(atcSec),
        tool_changes: parseInt(toolChanges) || 0,
        setup_sec: num(setupSec),
        load_unload_sec: num(loadUnloadSec),
        batch_quantity: num(batchQty),
      })
      setResult(r)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Request failed')
    } finally { setLoading(false) }
  }, [cuttingMin, cuttingMax, rapidSec, atcSec, toolChanges, setupSec, loadUnloadSec, batchQty])

  const fmtSec = (v: number | null | undefined) => v != null ? `${v.toFixed(1)} s` : '—'

  return (
    <div className="space-y-4">
      <div className="p-2 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded text-[11px] text-amber-800 dark:text-amber-300">
        PARTIAL_TIME_PRESENTED_AS_TOTAL=NO · UNKNOWN_TIME_COMPONENT_TREATED_AS_ZERO=NO · Leave fields blank for UNKNOWN components.
      </div>
      <div className="grid grid-cols-2 gap-3">
        {[
          ['Cutting Time Min (s)', cuttingMin, setCuttingMin],
          ['Cutting Time Max (s)', cuttingMax, setCuttingMax],
          ['Rapid Time (s)', rapidSec, setRapidSec],
          ['ATC Time per Change (s)', atcSec, setAtcSec],
          ['Tool Changes', toolChanges, setToolChanges],
          ['Setup Time (s)', setupSec, setSetupSec],
          ['Load/Unload Time (s)', loadUnloadSec, setLoadUnloadSec],
          ['Batch Quantity', batchQty, setBatchQty],
        ].map(([label, val, set]) => (
          <div key={label as string}>
            <label className="block text-xs font-medium text-[var(--tp-text-2)] mb-1">{label as string}</label>
            <input type="number" min="0" step="0.1" value={val as string}
              onChange={e => (set as (v: string) => void)(e.target.value)}
              placeholder="blank = UNKNOWN"
              className="w-full border border-[var(--tp-border)] rounded px-2 py-1.5 text-sm bg-[var(--tp-bg-1)] text-[var(--tp-text-1)]" />
          </div>
        ))}
      </div>
      <button onClick={estimate} disabled={loading}
        className="px-4 py-2 text-sm rounded bg-[var(--tp-accent)] text-white font-medium hover:opacity-90 disabled:opacity-50">
        {loading ? 'Estimating…' : 'Estimate'}
      </button>
      {error && <p className="text-xs text-red-500">{error}</p>}
      {result && (
        <div className="border border-[var(--tp-border)] rounded p-3 space-y-3">
          <div className="flex items-center gap-2"><SectionLabel>Cycle Time Estimate</SectionLabel><CompBadge completeness={result.completeness} /></div>
          <InfoRow label="Known total (min)" value={fmtSec(result.known_total_sec_min)} />
          <InfoRow label="Known total (max)" value={fmtSec(result.known_total_sec_max)} />
          <InfoRow label="Full cycle time (min)" value={result.total_cycle_time_sec_min != null ? fmtSec(result.total_cycle_time_sec_min) : 'UNKNOWN (partial data only)'} />
          <InfoRow label="Full cycle time (max)" value={result.total_cycle_time_sec_max != null ? fmtSec(result.total_cycle_time_sec_max) : '—'} />
          {result.unknown_components.length > 0 && (
            <div className="text-[11px] text-[var(--tp-text-3)]">
              Unknown: {result.unknown_components.join(', ')}
            </div>
          )}
          {result.uncertainty_note && (
            <div className="text-[11px] text-amber-600 dark:text-amber-400">{result.uncertainty_note}</div>
          )}
          <SectionLabel>Components</SectionLabel>
          <div className="space-y-1">
            {result.components.map(c => (
              <div key={c.component_id} className="flex justify-between text-xs border-b border-[var(--tp-border)] last:border-0 py-1">
                <span className="font-medium text-[var(--tp-text-1)]">{c.component_id}</span>
                <span className="text-[var(--tp-text-2)]">
                  {c.value_sec_min != null ? `${c.value_sec_min.toFixed(1)}–${(c.value_sec_max ?? c.value_sec_min).toFixed(1)} s` : 'UNKNOWN'}
                  {' · '}{c.status}
                </span>
              </div>
            ))}
          </div>
          {result.batch_model && (
            <>
              <SectionLabel>Batch Model (qty {result.batch_model.batch_quantity})</SectionLabel>
              <InfoRow label="Per-part setup" value={fmtSec(result.batch_model.per_part_setup_sec)} />
              <InfoRow label="Per-part total (min)" value={fmtSec(result.batch_model.per_part_total_sec_min)} />
              <InfoRow label="Per-part total (max)" value={fmtSec(result.batch_model.per_part_total_sec_max)} />
              <CompBadge completeness={result.batch_model.completeness} />
            </>
          )}
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Shop Profiles tab
// ─────────────────────────────────────────────────────────────────────────────

function ProfilesTab() {
  const [profiles, setProfiles] = useState<ShopCalibrationProfile[]>([])
  const [loaded, setLoaded] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [newLabel, setNewLabel] = useState('')
  const [newMachineId, setNewMachineId] = useState('')
  const [newAtc, setNewAtc] = useState('')
  const [newSetup, setNewSetup] = useState('')

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const r = await calibrationService.listProfiles()
      setProfiles(r); setLoaded(true)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load')
    } finally { setLoading(false) }
  }, [])

  const create = useCallback(async () => {
    if (!newLabel.trim()) { setError('Label is required.'); return }
    setLoading(true); setError(null)
    try {
      await calibrationService.createProfile({
        label: newLabel.trim(),
        machine_id: newMachineId || undefined,
        atc_time_sec: newAtc ? parseFloat(newAtc) : undefined,
        setup_time_sec: newSetup ? parseFloat(newSetup) : undefined,
      })
      setNewLabel(''); setNewMachineId(''); setNewAtc(''); setNewSetup('')
      await load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Create failed')
    } finally { setLoading(false) }
  }, [newLabel, newMachineId, newAtc, newSetup, load])

  return (
    <div className="space-y-4">
      <div className="border border-[var(--tp-border)] rounded p-3 space-y-3">
        <SectionLabel>New Shop Profile</SectionLabel>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-[var(--tp-text-2)] mb-1">Label *</label>
            <input value={newLabel} onChange={e => setNewLabel(e.target.value)} placeholder="e.g. VF2SS ATC validated"
              className="w-full border border-[var(--tp-border)] rounded px-2 py-1.5 text-sm bg-[var(--tp-bg-1)] text-[var(--tp-text-1)]" />
          </div>
          <div>
            <label className="block text-xs font-medium text-[var(--tp-text-2)] mb-1">Machine ID</label>
            <input value={newMachineId} onChange={e => setNewMachineId(e.target.value)} placeholder="optional"
              className="w-full border border-[var(--tp-border)] rounded px-2 py-1.5 text-sm bg-[var(--tp-bg-1)] text-[var(--tp-text-1)]" />
          </div>
          <div>
            <label className="block text-xs font-medium text-[var(--tp-text-2)] mb-1">ATC Time (s)</label>
            <input type="number" min="0" step="0.1" value={newAtc} onChange={e => setNewAtc(e.target.value)} placeholder="blank = unknown"
              className="w-full border border-[var(--tp-border)] rounded px-2 py-1.5 text-sm bg-[var(--tp-bg-1)] text-[var(--tp-text-1)]" />
          </div>
          <div>
            <label className="block text-xs font-medium text-[var(--tp-text-2)] mb-1">Setup Time (s)</label>
            <input type="number" min="0" step="1" value={newSetup} onChange={e => setNewSetup(e.target.value)} placeholder="blank = unknown"
              className="w-full border border-[var(--tp-border)] rounded px-2 py-1.5 text-sm bg-[var(--tp-bg-1)] text-[var(--tp-text-1)]" />
          </div>
        </div>
        <button onClick={create} disabled={loading}
          className="px-4 py-2 text-sm rounded bg-[var(--tp-accent)] text-white font-medium hover:opacity-90 disabled:opacity-50">
          {loading ? 'Creating…' : 'Create Profile'}
        </button>
      </div>

      <button onClick={load} disabled={loading}
        className="px-3 py-1.5 text-xs rounded border border-[var(--tp-border)] text-[var(--tp-text-2)] hover:bg-[var(--tp-bg-2)]">
        {loading ? 'Loading…' : 'Refresh Profiles'}
      </button>

      {error && <p className="text-xs text-red-500">{error}</p>}

      {loaded && profiles.length === 0 && (
        <p className="text-xs text-[var(--tp-text-3)] italic">No shop calibration profiles defined.</p>
      )}

      {profiles.map(p => (
        <div key={p.profile_id} className="border border-[var(--tp-border)] rounded p-3 space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-[var(--tp-text-1)]">{p.label}</span>
            <span className="text-[10px] text-[var(--tp-text-3)]">rev {p.revision}</span>
          </div>
          <InfoRow label="Machine ID" value={p.machine_id} />
          <InfoRow label="ATC Time" value={p.atc_time_sec != null ? `${p.atc_time_sec} s` : null} />
          <InfoRow label="Setup Time" value={p.setup_time_sec != null ? `${p.setup_time_sec} s` : null} />
          <InfoRow label="Source" value={p.source} />
          <InfoRow label="Confidence" value={p.confidence} />
        </div>
      ))}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Main page
// ─────────────────────────────────────────────────────────────────────────────

type Tab = 'tolerance' | 'surface' | 'cycletime' | 'profiles'

export default function ProcessCapabilityPage() {
  const [tab, setTab] = useState<Tab>('tolerance')

  const tabs: { id: Tab; label: string }[] = [
    { id: 'tolerance', label: 'Tolerance Capability' },
    { id: 'surface', label: 'Surface Finish' },
    { id: 'cycletime', label: 'Cycle Time' },
    { id: 'profiles', label: 'Shop Profiles' },
  ]

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-5">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-[var(--tp-text-1)]">Process Capability &amp; Calibration</h1>
        <p className="text-xs text-[var(--tp-text-3)] mt-0.5">Tolerance Capability · Surface Finish · Cycle Time · Shop Profiles</p>
      </div>

      {/* Disclaimer */}
      <div className="p-2 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded text-[11px] text-amber-800 dark:text-amber-300">
        {DISCLAIMER}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[var(--tp-border)]">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-3 py-2 text-xs font-medium rounded-t transition-colors ${
              tab === t.id
                ? 'bg-[var(--tp-bg-1)] text-[var(--tp-text-1)] border border-b-0 border-[var(--tp-border)]'
                : 'text-[var(--tp-text-3)] hover:text-[var(--tp-text-2)]'
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div>
        {tab === 'tolerance' && <ToleranceTab />}
        {tab === 'surface' && <SurfaceTab />}
        {tab === 'cycletime' && <CycleTimeTab />}
        {tab === 'profiles' && <ProfilesTab />}
      </div>
    </div>
  )
}
