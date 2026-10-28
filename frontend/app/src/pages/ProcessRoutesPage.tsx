/**
 * Process Route Optimization Page — EPIC_04E Phase 2.
 *
 * FABRICATED_ROUTE=NO
 * AUTO_SELECTED_ROUTE_MARKED_APPROVED=NO
 * BLACK_BOX_AI_SCORE_USED=NO
 */

import { useCallback, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { PipelineBreadcrumb } from '../components/PipelineBreadcrumb'
import {
  processRoutesApi,
  type FeatureRouteRequestBody,
  type ProcessRouteCandidate,
  type RouteAlternativeSet,
  type OptimizePartRoutesResponse,
  type RouteScoreBreakdown,
  type RiskFlag,
} from '../services/processRoutes'
import { generatePlan } from '../services/manufacturingPlan'
import { usePipeline } from '../context/PipelineContext'

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

const STRATEGIES = [
  { value: 'BALANCED',                  label: 'Balanced' },
  { value: 'LOWEST_RISK',               label: 'Lowest Risk' },
  { value: 'MINIMUM_SETUP',             label: 'Minimum Setup' },
  { value: 'SHORTEST_CYCLE_TIME',       label: 'Shortest Cycle Time' },
  { value: 'HIGHEST_PROCESS_CAPABILITY', label: 'Highest Process Capability' },
]

const FEATURE_TYPES = [
  'HOLE', 'PRECISION_BORE', 'COUNTERBORE', 'COUNTERSINK', 'THREADED_HOLE',
  'POCKET', 'SLOT', 'PLANAR_FACE', 'TURNING_DIAMETER', 'GROOVE',
  'CHAMFER', 'FILLET', 'BOSS', 'STEP', 'THREAD',
]

const DISCLAIMER =
  'Results are REFERENCE_ONLY — DRAFT status, NOT approved for production. ' +
  'AUTO_SELECTED_ROUTE_MARKED_APPROVED=NO. ' +
  'Validate through engineering review before manufacturing use.'

// ─────────────────────────────────────────────────────────────────────────────
// Small helpers
// ─────────────────────────────────────────────────────────────────────────────

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--tp-text-3)] mb-2">
      {children}
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const color =
    status === 'FEASIBLE' ? 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300'
    : status === 'CONDITIONAL' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300'
    : status === 'DRAFT' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300'
    : 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300'
  return (
    <span className={`inline-flex items-center rounded px-2 py-0.5 text-[10px] font-semibold ${color}`}>
      {status}
    </span>
  )
}

function RiskBadge({ level }: { level: string }) {
  const color =
    level === 'LOW' ? 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300'
    : level === 'MEDIUM' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300'
    : level === 'HIGH' ? 'bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300'
    : 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300'
  return (
    <span className={`inline-flex items-center rounded px-2 py-0.5 text-[10px] font-semibold ${color}`}>
      {level}
    </span>
  )
}

function ScoreBar({ label, value, max }: { label: string; value: number; max: number }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100))
  const color = value < 0 ? 'bg-red-400' : pct >= 70 ? 'bg-green-500' : pct >= 40 ? 'bg-yellow-500' : 'bg-orange-500'
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-36 text-[var(--tp-text-2)] shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-[var(--tp-border)] rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.abs(pct)}%` }} />
      </div>
      <span className="font-mono text-[var(--tp-text)] w-6 text-right">{value}</span>
    </div>
  )
}

function ScoreBreakdown({ score }: { score: RouteScoreBreakdown }) {
  return (
    <div className="space-y-1.5 mt-2">
      <ScoreBar label="Technical Feasibility" value={score.technical_feasibility} max={15} />
      <ScoreBar label="Req. Coverage" value={score.requirement_coverage} max={15} />
      <ScoreBar label="Process Capability" value={score.process_capability} max={15} />
      <ScoreBar label="GD&T Confidence" value={score.gdt_confidence} max={10} />
      <ScoreBar label="Machine Compat." value={score.machine_compatibility} max={10} />
      <ScoreBar label="Tool Compat." value={score.tool_compatibility} max={10} />
      <ScoreBar label="Setup Efficiency" value={score.setup_efficiency} max={10} />
      <ScoreBar label="Cycle Time" value={score.cycle_time} max={5} />
      <ScoreBar label="Data Completeness" value={score.data_completeness} max={5} />
      <ScoreBar label="Risk Penalty" value={score.risk_penalty} max={15} />
      <ScoreBar label="Strategy Bonus" value={score.strategy_bonus} max={10} />
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Route card
// ─────────────────────────────────────────────────────────────────────────────

function RouteCard({
  candidate,
  isSelected,
  isPareto,
}: {
  candidate: ProcessRouteCandidate
  isSelected: boolean
  isPareto: boolean
}) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div
      className={`border rounded-lg overflow-hidden transition-all ${
        isSelected
          ? 'border-[var(--tp-accent)] bg-[var(--tp-surface)]'
          : 'border-[var(--tp-border)] bg-[var(--tp-surface)]'
      }`}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-[var(--tp-surface-2)]"
        onClick={() => setExpanded(e => !e)}
      >
        <div className="flex items-center gap-2">
          {isSelected && (
            <span className="text-[10px] font-bold text-[var(--tp-accent)] uppercase tracking-widest">
              Selected
            </span>
          )}
          {isPareto && (
            <span className="text-[10px] font-bold text-purple-600 dark:text-purple-400 uppercase tracking-widest">
              Pareto
            </span>
          )}
          <span className="text-sm font-mono text-[var(--tp-text)]">{candidate.route_id}</span>
          <StatusBadge status={candidate.feasibility.status} />
        </div>
        <div className="flex items-center gap-3">
          <RiskBadge level={candidate.risk.overall_risk} />
          <span className="text-lg font-bold text-[var(--tp-text)] w-10 text-right">
            {candidate.score.total}
          </span>
          <span className="text-[10px] text-[var(--tp-text-2)]">/100</span>
          <span className="text-[var(--tp-text-2)] text-sm">{expanded ? '▲' : '▼'}</span>
        </div>
      </div>

      {/* Summary row */}
      <div className="px-4 pb-2 flex gap-4 text-xs text-[var(--tp-text-2)]">
        <span>{candidate.op_count} op{candidate.op_count !== 1 ? 's' : ''}</span>
        <span>{candidate.setup_count} setup{candidate.setup_count !== 1 ? 's' : ''}</span>
        <span>{candidate.machine_candidates.length} machine cand.</span>
        <span>{candidate.tool_candidates.length} tool cand.</span>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="px-4 pb-4 space-y-4 border-t border-[var(--tp-border)]">

          {/* Operations */}
          <div>
            <SectionLabel>Operations</SectionLabel>
            <div className="space-y-1">
              {candidate.operations.map((op) => (
                <div key={op.op_id} className="flex items-center gap-2 text-xs">
                  <span className="font-mono text-[var(--tp-text-3)] w-6">{op.sequence_no}</span>
                  <span
                    className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                      op.is_inspection
                        ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300'
                        : 'bg-[var(--tp-surface-2)] text-[var(--tp-text)]'
                    }`}
                  >
                    {op.operation_type}
                  </span>
                  {op.sub_operation && (
                    <span className="text-[var(--tp-text-2)]">{op.sub_operation}</span>
                  )}
                  {op.notes && <span className="text-[var(--tp-text-3)] truncate">{op.notes}</span>}
                </div>
              ))}
            </div>
          </div>

          {/* Score breakdown */}
          <div>
            <SectionLabel>Score Breakdown (BLACK_BOX_AI_SCORE_USED=NO)</SectionLabel>
            <ScoreBreakdown score={candidate.score} />
          </div>

          {/* Risk flags */}
          {candidate.risk.flags.length > 0 && (
            <div>
              <SectionLabel>Risk Flags ({candidate.risk.flags.length})</SectionLabel>
              <div className="space-y-2">
                {candidate.risk.flags.map((f) => (
                  <div
                    key={f.flag_id}
                    className="bg-[var(--tp-surface-2)] rounded p-2 space-y-1"
                  >
                    <div className="flex items-center gap-2">
                      <RiskBadge level={f.severity} />
                      <span className="text-xs font-medium text-[var(--tp-text)]">
                        {f.category.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <p className="text-xs text-[var(--tp-text-2)]">{f.description}</p>
                    <p className="text-[10px] text-[var(--tp-text-3)]">
                      ↪ {f.mitigation_note}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Machine candidates */}
          {candidate.machine_candidates.length > 0 && (
            <div>
              <SectionLabel>Machine Candidates (REFERENCE_ONLY)</SectionLabel>
              <div className="space-y-1">
                {candidate.machine_candidates.map((m) => (
                  <div key={m.machine_id} className="flex items-center justify-between text-xs">
                    <span className="text-[var(--tp-text)]">{m.manufacturer} {m.model}</span>
                    <span className="font-mono text-[var(--tp-text-2)]">{m.suitability_score}/100</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Tool candidates */}
          {candidate.tool_candidates.length > 0 && (
            <div>
              <SectionLabel>Tool Candidates (REFERENCE_ONLY)</SectionLabel>
              <div className="space-y-1">
                {candidate.tool_candidates.map((t) => (
                  <div key={t.tool_id} className="flex items-center justify-between text-xs">
                    <span className="text-[var(--tp-text)]">{t.manufacturer} {t.product_name}</span>
                    <span className="font-mono text-[var(--tp-text-2)]">{t.suitability_score}/100</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Explanation */}
          <div>
            <SectionLabel>Why Selected</SectionLabel>
            <p className="text-xs text-[var(--tp-text-2)]">{candidate.explanation.why_selected}</p>

            {candidate.explanation.uncertain_data_items.length > 0 && (
              <div className="mt-2">
                <SectionLabel>Uncertain / Unresolved</SectionLabel>
                <ul className="list-disc pl-4 space-y-0.5">
                  {candidate.explanation.uncertain_data_items.map((item, i) => (
                    <li key={i} className="text-xs text-orange-600 dark:text-orange-400">{item}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Traceability */}
          <div className="text-[10px] text-[var(--tp-text-3)] font-mono">
            FP: {candidate.traceability_fingerprint}
          </div>
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Alternative set panel
// ─────────────────────────────────────────────────────────────────────────────

function AlternativeSetPanel({ altSet }: { altSet: RouteAlternativeSet }) {
  const paretoIds = new Set(
    altSet.pareto_frontier.filter((p) => p.is_pareto_optimal).map((p) => p.route_id)
  )

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold text-[var(--tp-text)]">
          Feature: <span className="font-mono">{altSet.feature_id}</span>
        </div>
        <div className="flex gap-2 text-xs text-[var(--tp-text-2)]">
          <span>{altSet.feasible_count} feasible</span>
          <span>/ {altSet.candidate_count} candidates</span>
          {altSet.pareto_count > 0 && <span>· {altSet.pareto_count} Pareto</span>}
        </div>
      </div>

      {altSet.selection_rationale && (
        <p className="text-xs text-[var(--tp-text-2)]">{altSet.selection_rationale}</p>
      )}

      <div className="space-y-2">
        {altSet.candidates.map((c) => (
          <RouteCard
            key={c.route_id}
            candidate={c}
            isSelected={c.route_id === altSet.selected_route_id}
            isPareto={paretoIds.has(c.route_id)}
          />
        ))}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Feature form row
// ─────────────────────────────────────────────────────────────────────────────

interface FeatureFormState {
  id: string
  feature_id: string
  feature_type: string
  required_ra_um: string
  required_it_grade: string
  diameter_mm: string
  iso_material_group: string
  has_tight_position: boolean
  has_runout: boolean
  has_inspection: boolean
}

function newFeatureRow(idx: number): FeatureFormState {
  return {
    id: `row-${idx}-${Date.now()}`,
    feature_id: `F${String(idx + 1).padStart(3, '0')}`,
    feature_type: 'HOLE',
    required_ra_um: '1.6',
    required_it_grade: 'IT9',
    diameter_mm: '12',
    iso_material_group: 'P',
    has_tight_position: false,
    has_runout: false,
    has_inspection: false,
  }
}

function FeatureRow({
  row,
  onChange,
  onRemove,
}: {
  row: FeatureFormState
  onChange: (r: FeatureFormState) => void
  onRemove: () => void
}) {
  const inp = 'bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded px-2 py-1 text-sm text-[var(--tp-text)] w-full'
  const sel = `${inp} cursor-pointer`

  return (
    <div className="grid grid-cols-[auto_1fr_1fr_1fr_1fr_1fr_1fr_auto_auto_auto_auto] gap-2 items-center text-xs">
      <span className="font-mono text-[var(--tp-text-3)] w-12 truncate">{row.feature_id}</span>

      <select
        className={sel}
        value={row.feature_type}
        onChange={(e) => onChange({ ...row, feature_type: e.target.value })}
      >
        {FEATURE_TYPES.map((ft) => (
          <option key={ft} value={ft}>{ft}</option>
        ))}
      </select>

      <input
        className={inp}
        type="number"
        step="0.1"
        placeholder="Ra µm"
        value={row.required_ra_um}
        onChange={(e) => onChange({ ...row, required_ra_um: e.target.value })}
      />

      <input
        className={inp}
        placeholder="IT grade"
        value={row.required_it_grade}
        onChange={(e) => onChange({ ...row, required_it_grade: e.target.value })}
      />

      <input
        className={inp}
        type="number"
        placeholder="Ø mm"
        value={row.diameter_mm}
        onChange={(e) => onChange({ ...row, diameter_mm: e.target.value })}
      />

      <input
        className={inp}
        placeholder="ISO grp"
        value={row.iso_material_group}
        onChange={(e) => onChange({ ...row, iso_material_group: e.target.value })}
      />

      <label className="flex items-center gap-1 whitespace-nowrap">
        <input
          type="checkbox"
          checked={row.has_tight_position}
          onChange={(e) => onChange({ ...row, has_tight_position: e.target.checked })}
        />
        Pos.
      </label>
      <label className="flex items-center gap-1 whitespace-nowrap">
        <input
          type="checkbox"
          checked={row.has_runout}
          onChange={(e) => onChange({ ...row, has_runout: e.target.checked })}
        />
        Run.
      </label>
      <label className="flex items-center gap-1 whitespace-nowrap">
        <input
          type="checkbox"
          checked={row.has_inspection}
          onChange={(e) => onChange({ ...row, has_inspection: e.target.checked })}
        />
        Insp.
      </label>

      <button
        className="text-red-500 hover:text-red-700 text-xs px-1"
        onClick={onRemove}
      >
        ✕
      </button>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Main page
// ─────────────────────────────────────────────────────────────────────────────

export default function ProcessRoutesPage() {
  const navigate = useNavigate()
  const { confirmedRequirements, setManufacturingPlanId } = usePipeline()
  const [strategy, setStrategy] = useState('BALANCED')
  const [features, setFeatures] = useState<FeatureFormState[]>([newFeatureRow(0)])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<OptimizePartRoutesResponse | null>(null)
  const [activeTab, setActiveTab] = useState<'routes' | 'pareto' | 'benchmark'>('routes')
  const [genPlanLoading, setGenPlanLoading] = useState(false)
  const [genPlanError, setGenPlanError] = useState<string | null>(null)

  const addFeature = useCallback(() => {
    setFeatures((prev) => [...prev, newFeatureRow(prev.length)])
  }, [])

  const removeFeature = useCallback((id: string) => {
    setFeatures((prev) => prev.filter((r) => r.id !== id))
  }, [])

  const updateFeature = useCallback((row: FeatureFormState) => {
    setFeatures((prev) => prev.map((r) => (r.id === row.id ? row : r)))
  }, [])

  const handleOptimize = async () => {
    setError(null)
    setLoading(true)
    try {
      const body = {
        source_id: `PART-${Date.now()}`,
        drawing_number: null,
        revision: null,
        features: features.map((f) => ({
          feature_id: f.feature_id,
          feature_type: f.feature_type,
          required_ra_um: f.required_ra_um ? parseFloat(f.required_ra_um) : null,
          required_it_grade: f.required_it_grade || null,
          diameter_mm: f.diameter_mm ? parseFloat(f.diameter_mm) : null,
          iso_material_group: f.iso_material_group || null,
          has_tight_position: f.has_tight_position,
          has_runout: f.has_runout,
          has_inspection: f.has_inspection,
        })),
        strategy,
      }
      const res = await processRoutesApi.optimizePart(body)
      setResult(res)
      setActiveTab('routes')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  const handleGenerateManufacturingPlan = async () => {
    if (!result) return
    setGenPlanError(null)
    setGenPlanLoading(true)
    try {
      const summary = await generatePlan({
        source_id: result.plan.plan_id,
        req_set: confirmedRequirements ?? undefined,
        optimized_plan: result as unknown,
      })
      setManufacturingPlanId(summary.plan_id)
      navigate('/app/planning-quality/manufacturing-plan')
    } catch (e: unknown) {
      setGenPlanError(e instanceof Error ? e.message : String(e))
    } finally {
      setGenPlanLoading(false)
    }
  }

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-5xl mx-auto space-y-6">

        {/* Pipeline navigation */}
        <PipelineBreadcrumb />

        {/* Header */}
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--tp-accent-light)] mb-1">
            EPIC_04E · Phase 2
          </div>
          <h1 className="text-xl font-semibold text-[var(--tp-text)]">
            Process Route Optimization
          </h1>
          <p className="text-sm text-[var(--tp-text-2)] mt-1">
            Deterministic multi-objective route optimization.{' '}
            <span className="text-orange-500 font-medium">REFERENCE_ONLY — DRAFT</span>.{' '}
            BLACK_BOX_AI_SCORE_USED=NO. AUTO_SELECTED_ROUTE_MARKED_APPROVED=NO.
          </p>
        </div>

        {/* Strategy selector */}
        <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4">
          <SectionLabel>Optimization Strategy</SectionLabel>
          <div className="flex flex-wrap gap-2">
            {STRATEGIES.map((s) => (
              <button
                key={s.value}
                onClick={() => setStrategy(s.value)}
                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                  strategy === s.value
                    ? 'bg-[var(--tp-accent)] text-white'
                    : 'bg-[var(--tp-surface-2)] text-[var(--tp-text)] hover:bg-[var(--tp-border)]'
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        {/* Feature table */}
        <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <SectionLabel>Features</SectionLabel>
            <button
              onClick={addFeature}
              className="text-xs text-[var(--tp-accent)] hover:underline"
            >
              + Add Feature
            </button>
          </div>

          {/* Column headers */}
          <div className="grid grid-cols-[auto_1fr_1fr_1fr_1fr_1fr_1fr_auto_auto_auto_auto] gap-2 text-[10px] text-[var(--tp-text-3)] uppercase tracking-widest mb-2">
            <span className="w-12">ID</span>
            <span>Type</span>
            <span>Ra</span>
            <span>IT</span>
            <span>Ø</span>
            <span>Mat.</span>
            <span></span>
            <span>Pos</span>
            <span>Run</span>
            <span>Insp</span>
            <span></span>
          </div>

          <div className="space-y-2">
            {features.map((row) => (
              <FeatureRow
                key={row.id}
                row={row}
                onChange={updateFeature}
                onRemove={() => removeFeature(row.id)}
              />
            ))}
          </div>

          {features.length === 0 && (
            <p className="text-xs text-[var(--tp-text-2)] text-center py-4">
              No features. Click "+ Add Feature".
            </p>
          )}
        </div>

        {/* Run button */}
        <div className="flex items-center gap-4">
          <button
            onClick={handleOptimize}
            disabled={loading || features.length === 0}
            className="px-5 py-2 bg-[var(--tp-accent)] text-white rounded font-medium text-sm disabled:opacity-50 hover:opacity-90 transition-opacity"
          >
            {loading ? 'Optimizing…' : 'Optimize Routes'}
          </button>

          {error && (
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          )}
        </div>

        {/* Results */}
        {result && (
          <div className="space-y-4">
            {/* Plan summary */}
            <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <SectionLabel>Optimized Plan</SectionLabel>
                <StatusBadge status={result.plan.status} />
              </div>
              <div className="grid grid-cols-2 gap-x-8 gap-y-1 text-xs">
                <span className="text-[var(--tp-text-2)]">Plan ID</span>
                <span className="font-mono text-[var(--tp-text)]">{result.plan.plan_id}</span>
                <span className="text-[var(--tp-text-2)]">Strategy</span>
                <span className="text-[var(--tp-text)]">{result.plan.strategy}</span>
                <span className="text-[var(--tp-text-2)]">Steps</span>
                <span className="text-[var(--tp-text)]">{result.plan.step_count}</span>
                <span className="text-[var(--tp-text-2)]">Overall Risk</span>
                <RiskBadge level={result.plan.risk.overall_risk} />
                <span className="text-[var(--tp-text-2)]">Fingerprint</span>
                <span className="font-mono text-[var(--tp-text-3)]">{result.plan.traceability_fingerprint}</span>
              </div>
              {result.plan.generation_warnings.length > 0 && (
                <div className="mt-3">
                  <SectionLabel>Warnings</SectionLabel>
                  <ul className="list-disc pl-4 space-y-0.5">
                    {result.plan.generation_warnings.map((w, i) => (
                      <li key={i} className="text-xs text-orange-600 dark:text-orange-400">{w}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* Tabs */}
            <div className="flex gap-1 border-b border-[var(--tp-border)]">
              {(['routes', 'pareto', 'benchmark'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-2 text-sm font-medium capitalize transition-colors ${
                    activeTab === tab
                      ? 'border-b-2 border-[var(--tp-accent)] text-[var(--tp-accent)]'
                      : 'text-[var(--tp-text-2)] hover:text-[var(--tp-text)]'
                  }`}
                >
                  {tab === 'routes' ? 'Route Cards' : tab === 'pareto' ? 'Pareto View' : 'Benchmark'}
                </button>
              ))}
            </div>

            {/* Route cards tab */}
            {activeTab === 'routes' && (
              <div className="space-y-6">
                {result.alternative_sets.map((altSet) => (
                  <AlternativeSetPanel key={altSet.feature_id} altSet={altSet} />
                ))}
              </div>
            )}

            {/* Pareto tab */}
            {activeTab === 'pareto' && (
              <div className="space-y-4">
                {result.alternative_sets.map((altSet) => (
                  <div key={altSet.feature_id} className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4">
                    <SectionLabel>Feature: {altSet.feature_id}</SectionLabel>
                    {altSet.pareto_frontier.length === 0 ? (
                      <p className="text-xs text-[var(--tp-text-2)]">No Pareto data available.</p>
                    ) : (
                      <div className="space-y-2">
                        {altSet.pareto_frontier.map((p) => (
                          <div
                            key={p.route_id}
                            className={`flex items-center gap-3 text-xs p-2 rounded ${
                              p.is_pareto_optimal
                                ? 'bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-700'
                                : 'bg-[var(--tp-surface-2)]'
                            }`}
                          >
                            {p.is_pareto_optimal && (
                              <span className="text-[10px] font-bold text-purple-600 dark:text-purple-400 uppercase">★</span>
                            )}
                            <span className="font-mono w-36 truncate">{p.route_id}</span>
                            <span className="text-[var(--tp-text-2)]">Score: <strong className="text-[var(--tp-text)]">{p.score_total}</strong></span>
                            <span className="text-[var(--tp-text-2)]">Ops: {p.op_count}</span>
                            <span className="text-[var(--tp-text-2)]">Setups: {p.setup_count}</span>
                            <RiskBadge level={p.risk_level} />
                            {p.dominated_by.length > 0 && (
                              <span className="text-[var(--tp-text-3)]">dominated by {p.dominated_by.length}</span>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Benchmark tab */}
            {activeTab === 'benchmark' && (
              <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4">
                <SectionLabel>Benchmark Metrics</SectionLabel>
                <div className="grid grid-cols-2 gap-x-8 gap-y-1 text-xs">
                  <span className="text-[var(--tp-text-2)]">Total Candidates</span>
                  <span className="font-mono text-[var(--tp-text)]">{result.benchmark.total_candidates_generated}</span>
                  <span className="text-[var(--tp-text-2)]">Feasible</span>
                  <span className="font-mono text-[var(--tp-text)]">{result.benchmark.feasible_candidates}</span>
                  <span className="text-[var(--tp-text-2)]">Valid Recall</span>
                  <span className="font-mono text-[var(--tp-text)]">{(result.benchmark.valid_route_recall * 100).toFixed(1)}%</span>
                  <span className="text-[var(--tp-text-2)]">Setup Count</span>
                  <span className="font-mono text-[var(--tp-text)]">{result.benchmark.setup_count}</span>
                  <span className="text-[var(--tp-text-2)]">Req. Coverage</span>
                  <span className="font-mono text-[var(--tp-text)]">{(result.benchmark.requirement_coverage * 100).toFixed(1)}%</span>
                  <span className="text-[var(--tp-text-2)]">Determinism Rate</span>
                  <span className="font-mono text-green-600 dark:text-green-400">{result.benchmark.determinism_rate}</span>
                </div>
                <div className="mt-4 space-y-1">
                  <SectionLabel>Safety Invariants</SectionLabel>
                  {[
                    ['FABRICATED_ROUTE', result.benchmark.FABRICATED_ROUTE],
                    ['AUTO_SELECTED_ROUTE_MARKED_APPROVED', result.benchmark.AUTO_SELECTED_ROUTE_MARKED_APPROVED],
                    ['BLACK_BOX_AI_SCORE_USED', result.benchmark.BLACK_BOX_AI_SCORE_USED],
                  ].map(([key, val]) => (
                    <div key={String(key)} className="flex items-center gap-2 text-xs">
                      <span className={`w-3 h-3 rounded-full ${!val ? 'bg-green-500' : 'bg-red-500'}`} />
                      <span className="font-mono text-[var(--tp-text-2)]">{String(key)}=</span>
                      <span className={`font-bold ${!val ? 'text-green-600 dark:text-green-400' : 'text-red-600'}`}>
                        {String(val).toUpperCase()}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Disclaimer */}
            <div className="bg-orange-50 dark:bg-orange-950/20 border border-orange-200 dark:border-orange-800 rounded-lg p-3">
              <p className="text-xs text-orange-700 dark:text-orange-400">{DISCLAIMER}</p>
            </div>

            {/* Pipeline: Generate Manufacturing Plan */}
            <div className="flex items-center gap-3">
              <button
                onClick={handleGenerateManufacturingPlan}
                disabled={genPlanLoading}
                className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded font-medium text-sm disabled:opacity-50 transition-colors"
              >
                {genPlanLoading ? '...' : 'Generate Manufacturing Plan →'}
              </button>
              {genPlanError && (
                <span className="text-xs text-red-600 dark:text-red-400">{genPlanError}</span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
