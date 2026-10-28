import React, { useState, useEffect, useCallback } from 'react'
import { useLocale } from '../i18n'
import {
  generatePlan,
  listPlans,
  getPlan,
  validatePlan,
  markReviewed,
  approvePlan,
  rejectPlan,
  exportPlan,
  getNcHandoff,
} from '../services/manufacturingPlan'
import type {
  ManufacturingPlanSummary,
  ManufacturingPlanDetail,
  ValidationResult,
  GeneratePlanRequest,
} from '../types/manufacturingPlan'
import { usePipeline } from '../context/PipelineContext'
import { DEMO_SPOOL_REQ_SET, DEMO_SPOOL_META } from '../data/demoSpool'

const DISCLAIMER =
  'REFERENCE ONLY — Advisory manufacturing plan. Engineer review required. AUTO_GENERATED_PLAN_MARKED_APPROVED=NO'

type TabId =
  | 'overview'
  | 'flow'
  | 'setups'
  | 'operations'
  | 'inspection'
  | 'control'
  | 'review'
  | 'export'

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    DRAFT: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
    ENGINEER_REVIEWED: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
    APPROVED: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    REJECTED: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
    SUPERSEDED: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400',
  }
  const cls = colors[status] ?? 'bg-gray-100 text-gray-700'
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${cls}`}>
      {status}
    </span>
  )
}

function GateBadge({ gate }: { gate: string }) {
  const colors: Record<string, string> = {
    READY_FOR_ENGINEERING_REVIEW:
      'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    REVIEW_REQUIRED:
      'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
    INCOMPLETE: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
    BLOCKED: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
  }
  const cls = colors[gate] ?? 'bg-gray-100 text-gray-700'
  const labels: Record<string, string> = {
    READY_FOR_ENGINEERING_REVIEW: 'Ready for Review',
    REVIEW_REQUIRED: 'Review Required',
    INCOMPLETE: 'Incomplete',
    BLOCKED: 'Blocked',
  }
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${cls}`}>
      {labels[gate] ?? gate}
    </span>
  )
}

function SeverityBadge({ severity }: { severity: string }) {
  const colors: Record<string, string> = {
    BLOCKING: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
    REVIEW_REQUIRED: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
    ADVISORY: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  }
  const cls = colors[severity] ?? 'bg-gray-100 text-gray-700'
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${cls}`}>
      {severity}
    </span>
  )
}

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex gap-3 text-sm py-1 border-b border-[var(--tp-border)] last:border-0">
      <span className="w-44 shrink-0 text-[var(--tp-text-3)]">{label}</span>
      <span className="text-[var(--tp-text-1)]">{value}</span>
    </div>
  )
}

function TabButton({
  id,
  active,
  label,
  onClick,
}: {
  id: TabId
  active: boolean
  label: string
  onClick: (id: TabId) => void
}) {
  return (
    <button
      onClick={() => onClick(id)}
      className={`px-3 py-2 text-sm font-medium border-b-2 whitespace-nowrap transition-colors ${
        active
          ? 'border-blue-500 text-blue-600 dark:text-blue-400'
          : 'border-transparent text-[var(--tp-text-2)] hover:text-[var(--tp-text-1)]'
      }`}
    >
      {label}
    </button>
  )
}

// ─────────────────────────── Generate Panel ──────────────────────────────────
function GeneratePanel({ onGenerated }: { onGenerated: (s: ManufacturingPlanSummary) => void }) {
  const { t } = useLocale()
  const [sourceId, setSourceId] = useState('')
  const [drawingNumber, setDrawingNumber] = useState('')
  const [revision, setRevision] = useState('')
  const [loading, setLoading] = useState(false)
  const [demoLoading, setDemoLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [demoMode, setDemoMode] = useState(false)

  const handleGenerate = async () => {
    if (!sourceId.trim()) return
    setLoading(true)
    setError(null)
    try {
      const req: GeneratePlanRequest = {
        source_id: sourceId.trim(),
        drawing_number: drawingNumber.trim() || undefined,
        revision: revision.trim() || undefined,
      }
      const summary = await generatePlan(req)
      onGenerated(summary)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  const handleLoadDemo = async () => {
    setDemoLoading(true)
    setError(null)
    setDemoMode(false)
    try {
      const req: GeneratePlanRequest = {
        source_id: 'DEMO-SPOOL-001',
        drawing_number: DEMO_SPOOL_META.part_number,
        revision: DEMO_SPOOL_META.revision,
        req_set: DEMO_SPOOL_REQ_SET,
      }
      const summary = await generatePlan(req)
      setDemoMode(true)
      onGenerated(summary)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setDemoLoading(false)
    }
  }

  return (
    <div className="bg-[var(--tp-bg-2,#f8f9fa)] dark:bg-[#1e2530] rounded-lg p-4 mb-6 border border-[var(--tp-border)]">
      <h3 className="text-sm font-semibold text-[var(--tp-text-1)] mb-3">
        {t('mfpGenerateFromRoute')}
      </h3>
      {demoMode && (
        <div className="mb-3 p-2 rounded bg-yellow-100 dark:bg-yellow-900 border border-yellow-400 text-yellow-800 dark:text-yellow-200 text-xs font-semibold">
          {t('pipeline_demoModeBanner')}
        </div>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
        <div>
          <label className="block text-xs text-[var(--tp-text-3)] mb-1">{t('mfpSourceId')} *</label>
          <input
            className="w-full border border-[var(--tp-border)] rounded px-2 py-1.5 text-sm bg-white dark:bg-[#0d1117] text-[var(--tp-text-1)]"
            value={sourceId}
            onChange={e => setSourceId(e.target.value)}
            placeholder="route-plan-id"
          />
        </div>
        <div>
          <label className="block text-xs text-[var(--tp-text-3)] mb-1">{t('mfpDrawingNumber')}</label>
          <input
            className="w-full border border-[var(--tp-border)] rounded px-2 py-1.5 text-sm bg-white dark:bg-[#0d1117] text-[var(--tp-text-1)]"
            value={drawingNumber}
            onChange={e => setDrawingNumber(e.target.value)}
            placeholder="DWG-001"
          />
        </div>
        <div>
          <label className="block text-xs text-[var(--tp-text-3)] mb-1">{t('mfpRevision')}</label>
          <input
            className="w-full border border-[var(--tp-border)] rounded px-2 py-1.5 text-sm bg-white dark:bg-[#0d1117] text-[var(--tp-text-1)]"
            value={revision}
            onChange={e => setRevision(e.target.value)}
            placeholder="A"
          />
        </div>
      </div>
      {error && <p className="text-red-500 text-xs mb-2">{error}</p>}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={handleGenerate}
          disabled={loading || demoLoading || !sourceId.trim()}
          className="px-4 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded disabled:opacity-50 transition-colors"
        >
          {loading ? '...' : t('mfpGenerate')}
        </button>
        <button
          onClick={handleLoadDemo}
          disabled={demoLoading || loading}
          className="px-4 py-1.5 text-sm bg-amber-500 hover:bg-amber-600 text-white rounded disabled:opacity-50 transition-colors"
        >
          {demoLoading ? '...' : t('pipeline_loadDemoPart')}
        </button>
      </div>
    </div>
  )
}

// ─────────────────────── Plan List ───────────────────────────────────────────
function PlanList({
  plans,
  selectedId,
  onSelect,
}: {
  plans: ManufacturingPlanSummary[]
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  const { t } = useLocale()
  if (plans.length === 0) {
    return <p className="text-sm text-[var(--tp-text-3)] py-4">{t('mfpNoPlan')}</p>
  }
  return (
    <div className="space-y-2">
      {plans.map(p => (
        <button
          key={p.plan_id}
          onClick={() => onSelect(p.plan_id)}
          className={`w-full text-left p-3 rounded-lg border transition-colors ${
            selectedId === p.plan_id
              ? 'border-blue-500 bg-blue-50 dark:bg-blue-950'
              : 'border-[var(--tp-border)] hover:border-blue-300'
          }`}
        >
          <div className="flex items-center justify-between mb-1">
            <span className="text-sm font-medium text-[var(--tp-text-1)]">
              {p.drawing_number ?? p.plan_id.slice(0, 8)}
              {p.revision ? ` Rev ${p.revision}` : ''}
            </span>
            <StatusBadge status={p.status} />
          </div>
          <div className="flex items-center gap-2 text-xs text-[var(--tp-text-3)]">
            <GateBadge gate={p.release_gate} />
            <span>{Math.round(p.overall_completeness * 100)}% complete</span>
            {p.open_items_count > 0 && (
              <span className="text-orange-500">{p.open_items_count} open items</span>
            )}
          </div>
        </button>
      ))}
    </div>
  )
}

// ─────────────────────── Detail Tabs ─────────────────────────────────────────
function OverviewTab({ plan }: { plan: ManufacturingPlanDetail }) {
  const { t } = useLocale()
  return (
    <div className="space-y-4">
      <div className="bg-yellow-50 dark:bg-yellow-950 border border-yellow-300 rounded p-3 text-xs text-yellow-800 dark:text-yellow-200">
        {DISCLAIMER}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <InfoRow label={t('mfpPlanId')} value={<code className="text-xs">{plan.plan_id}</code>} />
          <InfoRow label={t('mfpDrawingNumber')} value={plan.drawing_number ?? '—'} />
          <InfoRow label={t('mfpRevision')} value={plan.revision ?? '—'} />
          <InfoRow label={t('mfpStatus')} value={<StatusBadge status={plan.status} />} />
          <InfoRow label={t('mfpReleaseGate')} value={<GateBadge gate={plan.release_gate} />} />
        </div>
        <div>
          <InfoRow
            label={t('mfpCompleteness')}
            value={
              <span>
                {Math.round(plan.overall_completeness * 100)}%
                <span className="ml-2 text-[var(--tp-text-3)]">{plan.completeness_status}</span>
              </span>
            }
          />
          <InfoRow label={t('mfpOperationsCount')} value={plan.operations_count} />
          <InfoRow label={t('mfpCharacteristicsCount')} value={plan.characteristics_count} />
          <InfoRow label={t('mfpOpenItems')} value={plan.open_items_count} />
          <InfoRow label={t('mfpCreatedAt')} value={plan.created_at?.slice(0, 19).replace('T', ' ') ?? '—'} />
        </div>
      </div>
      {plan.generation_warnings.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-[var(--tp-text-2)] mb-1">{t('mfpWarnings')}</h4>
          <ul className="list-disc ml-4 text-xs text-orange-600 dark:text-orange-400 space-y-0.5">
            {plan.generation_warnings.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      )}
      {plan.traceability_fingerprint && (
        <InfoRow
          label={t('mfpFingerprint')}
          value={<code className="text-xs">{plan.traceability_fingerprint}</code>}
        />
      )}
    </div>
  )
}

function ProcessFlowTab({ plan }: { plan: ManufacturingPlanDetail }) {
  const flow = plan.process_flow
  if (!flow || !flow.nodes?.length) {
    return <p className="text-sm text-[var(--tp-text-3)] py-4">No process flow data.</p>
  }
  const nodeMap = Object.fromEntries(flow.nodes.map((n: any) => [n.node_id, n]))
  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {flow.nodes.map((n: any) => {
          const isInspect = n.node_type === 'INSPECTION'
          const isSetup = n.node_type === 'SETUP'
          const isOp = n.node_type === 'OPERATION'
          const cls = isInspect
            ? 'bg-green-100 dark:bg-green-900 border-green-400'
            : isSetup
            ? 'bg-blue-100 dark:bg-blue-900 border-blue-400'
            : isOp
            ? 'bg-gray-100 dark:bg-gray-700 border-gray-400'
            : 'bg-white dark:bg-gray-800 border-gray-300'
          return (
            <div
              key={n.node_id}
              className={`border rounded px-3 py-1.5 text-xs font-medium ${cls}`}
            >
              {n.label}
            </div>
          )
        })}
      </div>
      <p className="text-xs text-[var(--tp-text-3)] mt-2">{flow.nodes.length} nodes, {flow.edges.length} edges</p>
    </div>
  )
}

function SetupsTab({ plan }: { plan: ManufacturingPlanDetail }) {
  const { t } = useLocale()
  if (!plan.setups?.length) return <p className="text-sm text-[var(--tp-text-3)] py-4">No setups.</p>
  return (
    <div className="space-y-4">
      {plan.setups.map((s: any) => (
        <div key={s.setup_id} className="border border-[var(--tp-border)] rounded-lg p-4">
          <h4 className="text-sm font-semibold text-[var(--tp-text-1)] mb-2">
            {t('mfpSetupNumber')} {s.setup_number} — {s.label}
          </h4>
          <InfoRow label={t('mfpMachine')} value={s.machine_label ?? s.machine_id ?? '—'} />
          <InfoRow label={t('mfpOpNumber')} value={`${s.operation_ids?.length ?? 0} operations`} />
          {s.orientation_note && <InfoRow label="Orientation" value={s.orientation_note} />}
          {s.fixturing_note && <InfoRow label="Fixturing" value={s.fixturing_note} />}
        </div>
      ))}
    </div>
  )
}

function OperationsTab({ plan }: { plan: ManufacturingPlanDetail }) {
  const { t } = useLocale()
  if (!plan.operations?.length) return <p className="text-sm text-[var(--tp-text-3)] py-4">No operations.</p>
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-[var(--tp-border)]">
            {[t('mfpOpNumber'), t('mfpOpType'), t('mfpMachine'), t('mfpTool'),
              t('mfpVc'), t('mfpFeed'), t('mfpRpm')].map(h => (
              <th key={h} className="text-left py-2 px-3 text-[var(--tp-text-3)] font-semibold">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {plan.operations.map((op: any) => (
            <tr key={op.op_id} className="border-b border-[var(--tp-border)] hover:bg-[var(--tp-bg-2,#f8f9fa)] dark:hover:bg-[#1e2530]">
              <td className="py-2 px-3">{op.op_number}</td>
              <td className="py-2 px-3 font-medium">{op.operation_type}</td>
              <td className="py-2 px-3">{op.machine_label ?? op.machine_id ?? '—'}</td>
              <td className="py-2 px-3">{op.tool_id ?? '—'}</td>
              <td className="py-2 px-3">{op.cutting_speed_m_min != null ? op.cutting_speed_m_min.toFixed(0) : '—'}</td>
              <td className="py-2 px-3">{op.feed_rate_mm_min != null ? op.feed_rate_mm_min.toFixed(2) : '—'}</td>
              <td className="py-2 px-3">{op.rpm != null ? Math.round(op.rpm) : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function InspectionTab({ plan }: { plan: ManufacturingPlanDetail }) {
  const { t } = useLocale()
  const ip = plan.inspection_plan
  if (!ip) return <p className="text-sm text-[var(--tp-text-3)] py-4">No inspection plan data.</p>
  return (
    <div>
      <div className="bg-blue-50 dark:bg-blue-950 border border-blue-200 rounded p-2 text-xs text-blue-700 dark:text-blue-300 mb-3">
        {t('mfpInspectionPlanDisclaimer')}
      </div>
      <div className="mb-3 text-sm">
        <span className="text-[var(--tp-text-3)]">{t('mfpCoverageRate')}: </span>
        <span className="font-semibold">{Math.round(ip.coverage_rate * 100)}%</span>
        {ip.uninspected_chars?.length > 0 && (
          <span className="ml-3 text-orange-500 text-xs">
            {ip.uninspected_chars.length} uninspected
          </span>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-[var(--tp-border)]">
              {[t('mfpCharLabel'), t('mfpCharType'), t('mfpCriticality'),
                t('mfpStage'), t('mfpMethod'), t('mfpGage'), t('mfpFrequency')].map(h => (
                <th key={h} className="text-left py-2 px-3 text-[var(--tp-text-3)] font-semibold">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ip.rows.map((r: any) => (
              <tr key={r.row_id} className="border-b border-[var(--tp-border)]">
                <td className="py-2 px-3">{r.char_label}</td>
                <td className="py-2 px-3">{r.char_type}</td>
                <td className="py-2 px-3">{r.criticality}</td>
                <td className="py-2 px-3">{r.stage}</td>
                <td className="py-2 px-3">{r.method}</td>
                <td className="py-2 px-3">{r.gage_suggestion ?? '—'}</td>
                <td className="py-2 px-3">{r.frequency?.frequency ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function ControlPlanTab({ plan }: { plan: ManufacturingPlanDetail }) {
  const { t } = useLocale()
  const cp = plan.control_plan
  if (!cp) return <p className="text-sm text-[var(--tp-text-3)] py-4">No control plan data.</p>
  return (
    <div>
      <div className="bg-orange-50 dark:bg-orange-950 border border-orange-200 rounded p-2 text-xs text-orange-700 dark:text-orange-300 mb-3">
        {t('mfpControlPlanDisclaimer')}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-[var(--tp-border)]">
              {[t('mfpCharLabel'), t('mfpCriticality'), t('mfpMethod'),
                t('mfpGage'), t('mfpFrequency'), t('mfpReactionPlan'), t('mfpResponsibility')].map(h => (
                <th key={h} className="text-left py-2 px-3 text-[var(--tp-text-3)] font-semibold">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {cp.rows.map((r: any) => (
              <tr key={r.row_id} className="border-b border-[var(--tp-border)]">
                <td className="py-2 px-3">{r.char_label}</td>
                <td className="py-2 px-3">{r.criticality}</td>
                <td className="py-2 px-3">{r.method}</td>
                <td className="py-2 px-3">{r.gage_suggestion ?? '—'}</td>
                <td className="py-2 px-3">{r.frequency?.frequency ?? '—'}</td>
                <td className="py-2 px-3">{r.reaction_plan}</td>
                <td className="py-2 px-3">{r.responsibility ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function ReviewTab({
  plan,
  planId,
  onAction,
}: {
  plan: ManufacturingPlanDetail
  planId: string
  onAction: () => void
}) {
  const { t } = useLocale()
  const [note, setNote] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [valResult, setValResult] = useState<ValidationResult | null>(null)

  const runValidate = async () => {
    setLoading(true)
    setError(null)
    try {
      const r = await validatePlan(planId)
      setValResult(r)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  const runAction = async (
    fn: (id: string, note: string) => Promise<ManufacturingPlanSummary>,
  ) => {
    setLoading(true)
    setError(null)
    try {
      await fn(planId, note)
      onAction()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Open Items */}
      <div>
        <h4 className="text-sm font-semibold text-[var(--tp-text-1)] mb-2">{t('mfpOpenItems')}</h4>
        {plan.open_items.length === 0 ? (
          <p className="text-sm text-[var(--tp-text-3)]">{t('mfpNoOpenItems')}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-[var(--tp-border)]">
                  {[t('mfpSeverity'), t('mfpDescription'), t('mfpResolutionHint')].map(h => (
                    <th key={h} className="text-left py-2 px-3 text-[var(--tp-text-3)] font-semibold">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {plan.open_items.map((item: any) => (
                  <tr key={item.item_id} className="border-b border-[var(--tp-border)]">
                    <td className="py-2 px-3"><SeverityBadge severity={item.severity} /></td>
                    <td className="py-2 px-3">{item.description}</td>
                    <td className="py-2 px-3 text-[var(--tp-text-3)]">{item.resolution_hint}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Validation */}
      <div>
        <div className="flex items-center gap-3 mb-2">
          <h4 className="text-sm font-semibold text-[var(--tp-text-1)]">{t('mfpValidate')}</h4>
          <button
            onClick={runValidate}
            disabled={loading}
            className="px-3 py-1 text-xs bg-blue-600 hover:bg-blue-700 text-white rounded disabled:opacity-50"
          >
            {loading ? '...' : t('mfpValidate')}
          </button>
        </div>
        {valResult && (
          <div className={`rounded p-3 text-xs border ${valResult.passed ? 'bg-green-50 dark:bg-green-950 border-green-300' : 'bg-red-50 dark:bg-red-950 border-red-300'}`}>
            <p className="font-semibold mb-1">
              {valResult.passed ? '✓ Passed' : '✗ Failed'} —{' '}
              {valResult.blocking_count} blocking, {valResult.review_required_count} review, {valResult.advisory_count} advisory
            </p>
            {valResult.findings.map((f, i) => (
              <p key={i} className="mt-0.5">
                <span className="font-mono">[{f.code}]</span> <SeverityBadge severity={f.severity} />{' '}
                {f.message}
              </p>
            ))}
          </div>
        )}
      </div>

      {/* Actions */}
      <div>
        <h4 className="text-sm font-semibold text-[var(--tp-text-1)] mb-2">Actions</h4>
        <div className="mb-2">
          <label className="block text-xs text-[var(--tp-text-3)] mb-1">{t('mfpEngineerNote')}</label>
          <input
            className="w-full border border-[var(--tp-border)] rounded px-2 py-1.5 text-sm bg-white dark:bg-[#0d1117] text-[var(--tp-text-1)]"
            value={note}
            onChange={e => setNote(e.target.value)}
            placeholder="Optional engineer note..."
          />
        </div>
        {error && <p className="text-red-500 text-xs mb-2">{error}</p>}
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => runAction(markReviewed)}
            disabled={loading}
            className="px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-700 text-white rounded disabled:opacity-50"
          >
            {t('mfpMarkReviewed')}
          </button>
          <button
            onClick={() => {
              if (window.confirm(t('mfpConfirmApprove'))) runAction(approvePlan)
            }}
            disabled={loading}
            className="px-3 py-1.5 text-xs bg-green-600 hover:bg-green-700 text-white rounded disabled:opacity-50"
          >
            {t('mfpApprove')}
          </button>
          <button
            onClick={() => runAction(rejectPlan)}
            disabled={loading}
            className="px-3 py-1.5 text-xs bg-red-600 hover:bg-red-700 text-white rounded disabled:opacity-50"
          >
            {t('mfpReject')}
          </button>
        </div>
      </div>
    </div>
  )
}

function ExportTab({ planId }: { planId: string }) {
  const { t } = useLocale()
  const [loading, setLoading] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [ncHandoffData, setNcHandoffData] = useState<unknown>(null)

  const doExport = async (fmt: 'json' | 'csv_operations' | 'csv_inspection' | 'html') => {
    setLoading(fmt)
    setError(null)
    try {
      const result = await exportPlan(planId, fmt)
      const content = result.content as string
      const mime =
        fmt === 'json' ? 'application/json' :
        fmt.startsWith('csv') ? 'text/csv' :
        'text/html'
      const ext = fmt === 'json' ? 'json' : fmt.startsWith('csv') ? 'csv' : 'html'
      const blob = new Blob([content], { type: mime })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `manufacturing-plan-${planId.slice(0, 8)}.${ext}`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(null)
    }
  }

  const doNcHandoff = async () => {
    setLoading('nc_handoff')
    setError(null)
    setNcHandoffData(null)
    try {
      const data = await getNcHandoff(planId)
      setNcHandoffData(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="space-y-3">
      <div className="bg-yellow-50 dark:bg-yellow-950 border border-yellow-300 rounded p-3 text-xs text-yellow-800 dark:text-yellow-200">
        {DISCLAIMER}
      </div>
      {error && <p className="text-red-500 text-xs">{error}</p>}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {(
          [
            ['json', t('mfpExportJson')],
            ['csv_operations', t('mfpExportCsvOps')],
            ['csv_inspection', t('mfpExportCsvInspection')],
            ['html', t('mfpExportHtml')],
          ] as const
        ).map(([fmt, label]) => (
          <button
            key={fmt}
            onClick={() => doExport(fmt)}
            disabled={loading !== null}
            className="px-3 py-2 text-sm border border-[var(--tp-border)] rounded hover:bg-blue-50 dark:hover:bg-blue-950 disabled:opacity-50 text-[var(--tp-text-1)] transition-colors"
          >
            {loading === fmt ? '...' : label}
          </button>
        ))}
        <div className="px-3 py-2 text-sm border border-[var(--tp-border)] rounded opacity-40 text-[var(--tp-text-3)]">
          {t('mfpExportXlsxDeferred')}
        </div>
        <button
          onClick={doNcHandoff}
          disabled={loading !== null}
          className="px-3 py-2 text-sm border border-[var(--tp-border)] rounded hover:bg-blue-50 dark:hover:bg-blue-950 disabled:opacity-50 text-[var(--tp-text-1)] transition-colors col-span-2 md:col-span-1"
        >
          {loading === 'nc_handoff' ? '...' : t('pipeline_ncHandoffExport')}
        </button>
      </div>
      {ncHandoffData && (
        <div className="mt-3">
          <div className="text-xs font-semibold text-[var(--tp-text-2)] mb-1">{t('pipeline_ncHandoffExport')}</div>
          <pre className="text-[10px] bg-[var(--tp-bg-2,#f8f9fa)] dark:bg-[#1e2530] rounded p-3 border border-[var(--tp-border)] overflow-x-auto max-h-60">
            {JSON.stringify(ncHandoffData, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}

// ────────────────────────── Main Page ────────────────────────────────────────
export default function ManufacturingPlanPage() {
  const { t } = useLocale()
  const { manufacturingPlanId } = usePipeline()
  const [plans, setPlans] = useState<ManufacturingPlanSummary[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<ManufacturingPlanDetail | null>(null)
  const [loadingList, setLoadingList] = useState(false)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [activeTab, setActiveTab] = useState<TabId>('overview')
  const [listError, setListError] = useState<string | null>(null)
  const [pipelineBanner, setPipelineBanner] = useState<string | null>(null)

  const fetchList = useCallback(async () => {
    setLoadingList(true)
    setListError(null)
    try {
      const data = await listPlans()
      setPlans(data)
    } catch (e) {
      setListError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoadingList(false)
    }
  }, [])

  useEffect(() => {
    fetchList()
  }, [fetchList])

  // Pipeline prefill: if manufacturingPlanId is in context, auto-load it
  useEffect(() => {
    if (!manufacturingPlanId) return
    setPipelineBanner(manufacturingPlanId)
    setSelectedId(manufacturingPlanId)
    setActiveTab('overview')
    setLoadingDetail(true)
    getPlan(manufacturingPlanId)
      .then(d => setDetail(d))
      .catch(() => setDetail(null))
      .finally(() => setLoadingDetail(false))
  }, [manufacturingPlanId])

  const fetchDetail = useCallback(async (id: string) => {
    setLoadingDetail(true)
    try {
      const d = await getPlan(id)
      setDetail(d)
    } catch {
      setDetail(null)
    } finally {
      setLoadingDetail(false)
    }
  }, [])

  const handleSelect = (id: string) => {
    setSelectedId(id)
    setActiveTab('overview')
    fetchDetail(id)
  }

  const handleGenerated = (summary: ManufacturingPlanSummary) => {
    setPlans(prev => [summary, ...prev])
    handleSelect(summary.plan_id)
  }

  const handleAction = () => {
    if (selectedId) fetchDetail(selectedId)
    fetchList()
  }

  const TABS: { id: TabId; labelKey: string }[] = [
    { id: 'overview', labelKey: 'mfpTabOverview' },
    { id: 'flow', labelKey: 'mfpTabProcessFlow' },
    { id: 'setups', labelKey: 'mfpTabSetups' },
    { id: 'operations', labelKey: 'mfpTabOperations' },
    { id: 'inspection', labelKey: 'mfpTabInspection' },
    { id: 'control', labelKey: 'mfpTabControlPlan' },
    { id: 'review', labelKey: 'mfpTabReview' },
    { id: 'export', labelKey: 'mfpTabExport' },
  ]

  return (
    <div className="p-4 md:p-6 max-w-7xl mx-auto">
      <h1 className="text-xl font-bold text-[var(--tp-text-1)] mb-1">{t('mfpTitle')}</h1>
      <p className="text-xs text-[var(--tp-text-3)] mb-4">{DISCLAIMER}</p>

      {pipelineBanner && (
        <div className="mb-4 p-2 rounded bg-blue-100 dark:bg-blue-900 border border-blue-400 text-blue-800 dark:text-blue-200 text-xs">
          {t('pipeline_planGeneratedFrom')}: <span className="font-mono">{pipelineBanner}</span>
        </div>
      )}

      <GeneratePanel onGenerated={handleGenerated} />

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Sidebar — plan list */}
        <div className="lg:col-span-1">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-sm font-semibold text-[var(--tp-text-1)]">Plans</h2>
            <button
              onClick={fetchList}
              disabled={loadingList}
              className="text-xs text-blue-600 hover:underline disabled:opacity-50"
            >
              {loadingList ? '...' : 'Refresh'}
            </button>
          </div>
          {listError && <p className="text-xs text-red-500 mb-2">{listError}</p>}
          <PlanList plans={plans} selectedId={selectedId} onSelect={handleSelect} />
        </div>

        {/* Main panel */}
        <div className="lg:col-span-3">
          {!selectedId && (
            <p className="text-sm text-[var(--tp-text-3)] py-8 text-center">
              Select a plan to view details, or generate a new one.
            </p>
          )}
          {selectedId && loadingDetail && (
            <p className="text-sm text-[var(--tp-text-3)] py-8 text-center">Loading...</p>
          )}
          {selectedId && !loadingDetail && detail && (
            <div>
              {/* Tab bar */}
              <div className="flex gap-1 border-b border-[var(--tp-border)] overflow-x-auto mb-4">
                {TABS.map(tab => (
                  <TabButton
                    key={tab.id}
                    id={tab.id}
                    active={activeTab === tab.id}
                    label={t(tab.labelKey as any)}
                    onClick={setActiveTab}
                  />
                ))}
              </div>

              {/* Tab content */}
              {activeTab === 'overview' && <OverviewTab plan={detail} />}
              {activeTab === 'flow' && <ProcessFlowTab plan={detail} />}
              {activeTab === 'setups' && <SetupsTab plan={detail} />}
              {activeTab === 'operations' && <OperationsTab plan={detail} />}
              {activeTab === 'inspection' && <InspectionTab plan={detail} />}
              {activeTab === 'control' && <ControlPlanTab plan={detail} />}
              {activeTab === 'review' && (
                <ReviewTab plan={detail} planId={selectedId} onAction={handleAction} />
              )}
              {activeTab === 'export' && <ExportTab planId={selectedId} />}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
