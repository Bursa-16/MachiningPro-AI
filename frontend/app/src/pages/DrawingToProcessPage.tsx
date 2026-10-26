import { useEffect, useState, useCallback } from 'react'
import { useLocale } from '../i18n/index'
import {
  fetchD2PSchema,
  generateDrawingToProcess,
  type DrawingToProcessRequest,
  type DimensionalReqIn,
  type GeometricReqIn,
  type SurfaceFinishReqIn,
  type ThreadReqIn,
  type GeneratedProcessPlan,
  type D2PSchema,
} from '../services/drawingToProcess'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--tp-text-3)] mb-2">
      {children}
    </div>
  )
}

function FieldRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between items-baseline py-1.5 border-b border-[var(--tp-border)] last:border-0">
      <span className="text-xs text-[var(--tp-text-2)]">{label}</span>
      <span className="text-sm font-mono text-[var(--tp-text)] ml-4 text-right">{value ?? '—'}</span>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const color =
    status === 'DRAFT' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300'
    : status === 'PARTIAL' ? 'bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300'
    : 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300'
  return (
    <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-semibold ${color}`}>
      {status}
    </span>
  )
}

function OpBadge({ op, isInspection }: { op: string; isInspection: boolean }) {
  const base = 'inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold'
  if (isInspection) return <span className={`${base} bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300`}>{op}</span>
  return <span className={`${base} bg-[var(--tp-surface-2)] text-[var(--tp-text)]`}>{op}</span>
}

let _reqCounter = 0
function nextId(prefix: string) {
  _reqCounter += 1
  return `${prefix}-${_reqCounter.toString().padStart(4, '0')}`
}

// ---------------------------------------------------------------------------
// Sub-forms
// ---------------------------------------------------------------------------

function DimForm({
  item,
  onChange,
  onRemove,
  t,
}: {
  item: DimensionalReqIn
  onChange: (v: DimensionalReqIn) => void
  onRemove: () => void
  t: Record<string, string>
}) {
  return (
    <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-3 space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-[10px] text-[var(--tp-text-2)]">{t.d2pDimensionType}</label>
          <input
            className="mt-1 w-full bg-[var(--tp-bg)] border border-[var(--tp-border)] rounded px-2 py-1 text-sm text-[var(--tp-text)]"
            placeholder="e.g. DIAMETER, DEPTH"
            value={item.dimension_type}
            onChange={e => onChange({ ...item, dimension_type: e.target.value })}
          />
        </div>
        <div>
          <label className="text-[10px] text-[var(--tp-text-2)]">{t.d2pNominalValue}</label>
          <input
            type="number"
            className="mt-1 w-full bg-[var(--tp-bg)] border border-[var(--tp-border)] rounded px-2 py-1 text-sm text-[var(--tp-text)]"
            value={item.nominal_value}
            onChange={e => onChange({ ...item, nominal_value: parseFloat(e.target.value) || 0 })}
          />
        </div>
        <div>
          <label className="text-[10px] text-[var(--tp-text-2)]">{t.d2pUnit}</label>
          <input
            className="mt-1 w-full bg-[var(--tp-bg)] border border-[var(--tp-border)] rounded px-2 py-1 text-sm text-[var(--tp-text)]"
            placeholder="mm"
            value={item.unit}
            onChange={e => onChange({ ...item, unit: e.target.value })}
          />
        </div>
        <div>
          <label className="text-[10px] text-[var(--tp-text-2)]">{t.d2pToleranceUpper}</label>
          <input
            type="number"
            className="mt-1 w-full bg-[var(--tp-bg)] border border-[var(--tp-border)] rounded px-2 py-1 text-sm text-[var(--tp-text)]"
            placeholder="e.g. 0.025"
            value={item.tolerance_upper ?? ''}
            onChange={e => {
              const v = e.target.value === '' ? null : parseFloat(e.target.value)
              onChange({ ...item, tolerance_upper: v })
            }}
          />
        </div>
      </div>
      <div className="flex justify-end">
        <button
          className="text-xs text-red-500 hover:text-red-700"
          onClick={onRemove}
        >
          {t.d2pRemove}
        </button>
      </div>
    </div>
  )
}

function GeomForm({
  item,
  onChange,
  onRemove,
  schema,
  t,
}: {
  item: GeometricReqIn
  onChange: (v: GeometricReqIn) => void
  onRemove: () => void
  schema: D2PSchema | null
  t: Record<string, string>
}) {
  const chars = schema?.supported_gdt_characteristics ?? []
  return (
    <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-3 space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-[10px] text-[var(--tp-text-2)]">{t.d2pGdtCharacteristic}</label>
          <select
            className="mt-1 w-full bg-[var(--tp-bg)] border border-[var(--tp-border)] rounded px-2 py-1 text-sm text-[var(--tp-text)]"
            value={item.fcf.characteristic}
            onChange={e => onChange({ ...item, fcf: { ...item.fcf, characteristic: e.target.value } })}
          >
            {chars.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label className="text-[10px] text-[var(--tp-text-2)]">{t.d2pGdtTolerance}</label>
          <input
            type="number"
            className="mt-1 w-full bg-[var(--tp-bg)] border border-[var(--tp-border)] rounded px-2 py-1 text-sm text-[var(--tp-text)]"
            placeholder="e.g. 0.02"
            value={item.fcf.tolerance_value}
            onChange={e => onChange({ ...item, fcf: { ...item.fcf, tolerance_value: parseFloat(e.target.value) || 0.01 } })}
          />
        </div>
      </div>
      <div className="flex justify-end">
        <button className="text-xs text-red-500 hover:text-red-700" onClick={onRemove}>
          {t.d2pRemove}
        </button>
      </div>
    </div>
  )
}

function SfForm({
  item,
  onChange,
  onRemove,
  t,
}: {
  item: SurfaceFinishReqIn
  onChange: (v: SurfaceFinishReqIn) => void
  onRemove: () => void
  t: Record<string, string>
}) {
  return (
    <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-3 space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-[10px] text-[var(--tp-text-2)]">{t.d2pRaUm}</label>
          <input
            type="number"
            className="mt-1 w-full bg-[var(--tp-bg)] border border-[var(--tp-border)] rounded px-2 py-1 text-sm text-[var(--tp-text)]"
            placeholder="e.g. 1.6"
            value={item.ra_um ?? ''}
            onChange={e => onChange({ ...item, ra_um: e.target.value === '' ? null : parseFloat(e.target.value) })}
          />
        </div>
        <div>
          <label className="text-[10px] text-[var(--tp-text-2)]">{t.d2pRzUm}</label>
          <input
            type="number"
            className="mt-1 w-full bg-[var(--tp-bg)] border border-[var(--tp-border)] rounded px-2 py-1 text-sm text-[var(--tp-text)]"
            placeholder="optional"
            value={item.rz_um ?? ''}
            onChange={e => onChange({ ...item, rz_um: e.target.value === '' ? null : parseFloat(e.target.value) })}
          />
        </div>
      </div>
      <div className="flex justify-end">
        <button className="text-xs text-red-500 hover:text-red-700" onClick={onRemove}>
          {t.d2pRemove}
        </button>
      </div>
    </div>
  )
}

function ThreadForm({
  item,
  onChange,
  onRemove,
  t,
}: {
  item: ThreadReqIn
  onChange: (v: ThreadReqIn) => void
  onRemove: () => void
  t: Record<string, string>
}) {
  return (
    <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-3 space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-[10px] text-[var(--tp-text-2)]">{t.d2pThreadDesignation}</label>
          <input
            className="mt-1 w-full bg-[var(--tp-bg)] border border-[var(--tp-border)] rounded px-2 py-1 text-sm text-[var(--tp-text)]"
            placeholder="e.g. M12x1.75"
            value={item.designation ?? ''}
            onChange={e => onChange({ ...item, designation: e.target.value || null })}
          />
        </div>
        <div>
          <label className="text-[10px] text-[var(--tp-text-2)]">{t.d2pThreadHand}</label>
          <select
            className="mt-1 w-full bg-[var(--tp-bg)] border border-[var(--tp-border)] rounded px-2 py-1 text-sm text-[var(--tp-text)]"
            value={item.hand ?? 'RH'}
            onChange={e => onChange({ ...item, hand: e.target.value })}
          >
            <option value="RH">RH</option>
            <option value="LH">LH</option>
          </select>
        </div>
      </div>
      <div className="flex justify-end">
        <button className="text-xs text-red-500 hover:text-red-700" onClick={onRemove}>
          {t.d2pRemove}
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Plan results view
// ---------------------------------------------------------------------------

function PlanResultView({ plan, t }: { plan: GeneratedProcessPlan; t: Record<string, string> }) {
  const [tab, setTab] = useState<'steps' | 'routes' | 'trace' | 'material'>('steps')

  return (
    <div className="space-y-4">
      {/* Status row */}
      <div className="flex items-center gap-3">
        <StatusBadge status={plan.status} />
        <span className="text-sm text-[var(--tp-text-2)]">
          {t.d2pStepCount}: <strong className="text-[var(--tp-text)]">{plan.step_count}</strong>
        </span>
        {plan.drawing_number && (
          <span className="text-sm text-[var(--tp-text-2)]">
            {t.d2pDrawingNumber}: <strong className="text-[var(--tp-text)]">{plan.drawing_number}</strong>
          </span>
        )}
      </div>

      {/* Disclaimer */}
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3 text-xs text-yellow-900 dark:bg-yellow-900/20 dark:border-yellow-700 dark:text-yellow-200">
        <strong>{t.d2pDisclaimerTitle}: </strong>{plan.disclaimer}
      </div>

      {/* Warnings */}
      {plan.generation_warnings.length > 0 && (
        <div className="bg-orange-50 border border-orange-200 rounded-lg px-4 py-3 dark:bg-orange-900/20 dark:border-orange-700">
          <SectionLabel>{t.d2pWarnings}</SectionLabel>
          {plan.generation_warnings.map((w, i) => (
            <div key={i} className="text-xs text-orange-800 dark:text-orange-300">• {w}</div>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[var(--tp-border)] pb-px">
        {(['steps', 'routes', 'trace', 'material'] as const).map(t2 => (
          <button
            key={t2}
            className={`px-3 py-1.5 text-xs font-medium rounded-t transition-colors ${
              tab === t2
                ? 'bg-[var(--tp-surface)] text-[var(--tp-text)] border border-[var(--tp-border)] border-b-[var(--tp-bg)]'
                : 'text-[var(--tp-text-2)] hover:text-[var(--tp-text)]'
            }`}
            onClick={() => setTab(t2)}
          >
            {t2 === 'steps' ? t.d2pSectionPlan
              : t2 === 'routes' ? t.d2pSectionRoutes
              : t2 === 'trace' ? t.d2pSectionTraceability
              : t.d2pSectionMaterial}
          </button>
        ))}
      </div>

      {/* Steps tab */}
      {tab === 'steps' && (
        <div className="space-y-2">
          {plan.steps.map(step => (
            <div
              key={step.step_id}
              className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg px-4 py-3 flex items-start gap-3"
            >
              <div className="text-xs font-mono text-[var(--tp-text-3)] w-12 shrink-0 pt-0.5">
                {step.sequence_number}.
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <OpBadge op={step.operation} isInspection={step.is_inspection} />
                  {step.feature_id && (
                    <span className="text-[10px] text-[var(--tp-text-3)]">
                      {t.d2pFeatureLabel}: {step.feature_id.split('-').slice(-2).join('-')}
                    </span>
                  )}
                  {step.route_id && (
                    <span className="text-[10px] text-[var(--tp-text-3)]">
                      {t.d2pRouteLabel}: {step.route_id.split('-').slice(-1)[0]}
                    </span>
                  )}
                </div>
                {step.notes && (
                  <div className="text-xs text-[var(--tp-text-2)] mt-1 leading-relaxed">{step.notes}</div>
                )}
              </div>
              <div className="text-xs font-mono text-[var(--tp-text-3)] shrink-0">{step.step_id}</div>
            </div>
          ))}
        </div>
      )}

      {/* Routes tab */}
      {tab === 'routes' && (
        <div className="space-y-3">
          {plan.best_routes.map(route => (
            <div key={route.route_id} className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4 space-y-3">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-[var(--tp-text)]">{route.route_id}</span>
                <span className="text-xs text-[var(--tp-text-2)]">— {route.feature_type}</span>
                <span className="ml-auto text-xs font-semibold text-[var(--tp-accent)]">
                  {t.d2pScoreLabel}: {route.score.total}/100
                </span>
              </div>
              <div className="flex flex-wrap gap-1">
                {route.operations.map((op, i) => (
                  <span key={i} className="bg-[var(--tp-surface-2)] text-[var(--tp-text)] rounded px-2 py-0.5 text-xs font-medium">
                    {op}
                  </span>
                ))}
              </div>
              <div className="grid grid-cols-2 gap-x-4">
                {route.required_ra_um && (
                  <FieldRow label={t.d2pRequiredRa} value={`${route.required_ra_um} µm`} />
                )}
                <FieldRow label={t.d2pAchievableRa} value={`${route.achievable_ra_um} µm`} />
                <FieldRow label={t.d2pRequiresGrinding} value={route.requires_grinding ? '✓' : '—'} />
              </div>
              <div className="grid grid-cols-5 gap-1 text-center">
                {[
                  [t.d2pScoreCompleteness, route.score.completeness, 40],
                  [t.d2pScoreEfficiency, route.score.efficiency, 20],
                  [t.d2pScoreSeqCompliance, route.score.seq_compliance, 20],
                  [t.d2pScoreDfm, route.score.dfm_compliance, 10],
                  [t.d2pScoreAvailability, route.score.availability, 10],
                ].map(([label, val, max]) => (
                  <div key={label as string} className="bg-[var(--tp-bg)] rounded p-2">
                    <div className="text-sm font-semibold text-[var(--tp-text)]">{val}/{max}</div>
                    <div className="text-[9px] text-[var(--tp-text-3)] mt-0.5 leading-tight">{label}</div>
                  </div>
                ))}
              </div>
            </div>
          ))}
          {plan.best_routes.length === 0 && (
            <div className="text-sm text-[var(--tp-text-2)] text-center py-4">{t.d2pEmptyRequirements}</div>
          )}
        </div>
      )}

      {/* Traceability tab */}
      {tab === 'trace' && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="border-b border-[var(--tp-border)]">
                {[t.d2pTraceabilityReqId, t.d2pTraceabilityFeatureId, t.d2pTraceabilityStepId, t.d2pTraceabilityRule, t.d2pOperationLabel].map(h => (
                  <th key={h} className="text-left px-3 py-2 text-[var(--tp-text-2)] font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {plan.traceability.map((e, i) => (
                <tr key={i} className="border-b border-[var(--tp-border)] hover:bg-[var(--tp-surface)]">
                  <td className="px-3 py-1.5 font-mono">{e.req_id}</td>
                  <td className="px-3 py-1.5 font-mono text-[var(--tp-text-2)]">{e.feature_id.split('-').slice(-2).join('-')}</td>
                  <td className="px-3 py-1.5 font-mono">{e.step_id}</td>
                  <td className="px-3 py-1.5">{e.recognition_rule}</td>
                  <td className="px-3 py-1.5">{e.operation}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {plan.traceability.length === 0 && (
            <div className="text-sm text-[var(--tp-text-2)] text-center py-4">—</div>
          )}
        </div>
      )}

      {/* Material tab */}
      {tab === 'material' && (
        <div>
          {plan.material_resolution ? (
            <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4 space-y-1">
              <FieldRow label={t.d2pMaterialRaw} value={plan.material_resolution.raw_designation} />
              <FieldRow label={t.d2pMaterialMatched} value={plan.material_resolution.matched_designation ?? '—'} />
              <FieldRow label={t.d2pMaterialConfidence} value={plan.material_resolution.confidence} />
              <FieldRow label={t.d2pMaterialIsoGroup} value={plan.material_resolution.iso_group ?? '—'} />
            </div>
          ) : (
            <div className="text-sm text-[var(--tp-text-2)] text-center py-4">—</div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function DrawingToProcessPage() {
  const t = useLocale() as unknown as Record<string, string>

  const [schema, setSchema] = useState<D2PSchema | null>(null)
  const [schemaError, setSchemaError] = useState<string | null>(null)

  // Form state
  const [sourceId, setSourceId] = useState('drawing-001')
  const [drawingNumber, setDrawingNumber] = useState('')
  const [revision, setRevision] = useState('')
  const [materialDesignation, setMaterialDesignation] = useState('')

  const [dims, setDims] = useState<DimensionalReqIn[]>([])
  const [geoms, setGeoms] = useState<GeometricReqIn[]>([])
  const [sfs, setSfs] = useState<SurfaceFinishReqIn[]>([])
  const [threads, setThreads] = useState<ThreadReqIn[]>([])

  // Result state
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [plan, setPlan] = useState<GeneratedProcessPlan | null>(null)

  useEffect(() => {
    fetchD2PSchema()
      .then(setSchema)
      .catch(() => setSchemaError(t.d2pSchemaError))
  }, [])

  const addDim = () => {
    setDims(prev => [
      ...prev,
      { req_id: nextId('D'), dimension_type: 'DIAMETER', nominal_value: 10, unit: 'mm' },
    ])
  }

  const addGeom = () => {
    setGeoms(prev => [
      ...prev,
      { req_id: nextId('G'), fcf: { characteristic: 'POSITION', tolerance_value: 0.05, tolerance_unit: 'mm' } },
    ])
  }

  const addSf = () => {
    setSfs(prev => [...prev, { req_id: nextId('SF'), ra_um: 1.6 }])
  }

  const addThread = () => {
    setThreads(prev => [...prev, { req_id: nextId('T'), designation: 'M10x1.5', hand: 'RH' }])
  }

  const hasRequirements = dims.length > 0 || geoms.length > 0 || sfs.length > 0 || threads.length > 0

  const handleGenerate = useCallback(async () => {
    if (!hasRequirements) return
    setLoading(true)
    setError(null)
    setPlan(null)

    const req: DrawingToProcessRequest = {
      source_id: sourceId.trim() || 'drawing-001',
      drawing_number: drawingNumber.trim() || null,
      revision: revision.trim() || null,
      extraction_status: 'PARTIAL',
      dimensional: dims,
      geometric: geoms,
      surface_finish: sfs,
      threads,
      material: materialDesignation.trim()
        ? { req_id: 'MAT-0001', raw_designation: materialDesignation.trim() }
        : null,
      heat_treatment: [],
    }

    try {
      const result = await generateDrawingToProcess(req)
      setPlan(result)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t.d2pGenerateError)
    } finally {
      setLoading(false)
    }
  }, [sourceId, drawingNumber, revision, materialDesignation, dims, geoms, sfs, threads, hasRequirements])

  return (
    <div className="flex-1 min-h-0 overflow-y-auto">
      <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
        {/* Header */}
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold text-[var(--tp-text)]">{t.d2pPageTitle}</h1>
            <span className="text-[10px] font-semibold bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300 rounded px-1.5 py-0.5">
              {t.d2pDraftBadge}
            </span>
          </div>
          <p className="text-sm text-[var(--tp-text-2)]">{t.d2pPageSubtitle}</p>
        </div>

        {/* Disclaimer */}
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3 text-xs text-yellow-900 dark:bg-yellow-900/20 dark:border-yellow-700 dark:text-yellow-200">
          <strong>{t.d2pDisclaimerTitle}: </strong>{t.d2pDisclaimerText}
        </div>

        {schemaError && (
          <div className="text-sm text-red-600">{schemaError}</div>
        )}

        {/* Source info */}
        <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4 space-y-3">
          <SectionLabel>{t.d2pSectionRequirements}</SectionLabel>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-[10px] text-[var(--tp-text-2)]">{t.d2pSourceId}</label>
              <input
                className="mt-1 w-full bg-[var(--tp-bg)] border border-[var(--tp-border)] rounded px-2 py-1 text-sm text-[var(--tp-text)]"
                value={sourceId}
                onChange={e => setSourceId(e.target.value)}
              />
            </div>
            <div>
              <label className="text-[10px] text-[var(--tp-text-2)]">{t.d2pDrawingNumber}</label>
              <input
                className="mt-1 w-full bg-[var(--tp-bg)] border border-[var(--tp-border)] rounded px-2 py-1 text-sm text-[var(--tp-text)]"
                value={drawingNumber}
                placeholder="optional"
                onChange={e => setDrawingNumber(e.target.value)}
              />
            </div>
            <div>
              <label className="text-[10px] text-[var(--tp-text-2)]">{t.d2pRevision}</label>
              <input
                className="mt-1 w-full bg-[var(--tp-bg)] border border-[var(--tp-border)] rounded px-2 py-1 text-sm text-[var(--tp-text)]"
                value={revision}
                placeholder="A"
                onChange={e => setRevision(e.target.value)}
              />
            </div>
          </div>
          <div>
            <label className="text-[10px] text-[var(--tp-text-2)]">{t.d2pMaterial}</label>
            <input
              className="mt-1 w-full bg-[var(--tp-bg)] border border-[var(--tp-border)] rounded px-2 py-1 text-sm text-[var(--tp-text)]"
              value={materialDesignation}
              placeholder="e.g. 42CrMo4, AISI 304"
              onChange={e => setMaterialDesignation(e.target.value)}
            />
          </div>
        </div>

        {/* Dimensional requirements */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <SectionLabel>{t.d2pDimensional} ({dims.length})</SectionLabel>
            <button
              className="text-xs text-[var(--tp-accent)] hover:underline"
              onClick={addDim}
            >
              + {t.d2pAddDimensional}
            </button>
          </div>
          {dims.map((d, i) => (
            <DimForm
              key={d.req_id}
              item={d}
              onChange={v => setDims(prev => prev.map((x, j) => j === i ? v : x))}
              onRemove={() => setDims(prev => prev.filter((_, j) => j !== i))}
              t={t}
            />
          ))}
        </div>

        {/* Geometric (GD&T) requirements */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <SectionLabel>{t.d2pGeometric} ({geoms.length})</SectionLabel>
            <button
              className="text-xs text-[var(--tp-accent)] hover:underline"
              onClick={addGeom}
            >
              + {t.d2pAddGeometric}
            </button>
          </div>
          {geoms.map((g, i) => (
            <GeomForm
              key={g.req_id}
              item={g}
              onChange={v => setGeoms(prev => prev.map((x, j) => j === i ? v : x))}
              onRemove={() => setGeoms(prev => prev.filter((_, j) => j !== i))}
              schema={schema}
              t={t}
            />
          ))}
        </div>

        {/* Surface finish requirements */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <SectionLabel>{t.d2pSurfaceFinish} ({sfs.length})</SectionLabel>
            <button
              className="text-xs text-[var(--tp-accent)] hover:underline"
              onClick={addSf}
            >
              + {t.d2pAddSurfaceFinish}
            </button>
          </div>
          {sfs.map((s, i) => (
            <SfForm
              key={s.req_id}
              item={s}
              onChange={v => setSfs(prev => prev.map((x, j) => j === i ? v : x))}
              onRemove={() => setSfs(prev => prev.filter((_, j) => j !== i))}
              t={t}
            />
          ))}
        </div>

        {/* Thread requirements */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <SectionLabel>{t.d2pThreads} ({threads.length})</SectionLabel>
            <button
              className="text-xs text-[var(--tp-accent)] hover:underline"
              onClick={addThread}
            >
              + {t.d2pAddThread}
            </button>
          </div>
          {threads.map((th, i) => (
            <ThreadForm
              key={th.req_id}
              item={th}
              onChange={v => setThreads(prev => prev.map((x, j) => j === i ? v : x))}
              onRemove={() => setThreads(prev => prev.filter((_, j) => j !== i))}
              t={t}
            />
          ))}
        </div>

        {/* Generate button */}
        <button
          className={`w-full py-2.5 rounded-lg text-sm font-semibold transition-colors ${
            hasRequirements && !loading
              ? 'bg-[var(--tp-accent)] text-white hover:opacity-90'
              : 'bg-[var(--tp-surface-2)] text-[var(--tp-text-3)] cursor-not-allowed'
          }`}
          disabled={!hasRequirements || loading}
          onClick={handleGenerate}
        >
          {loading ? t.d2pGenerating : t.d2pGeneratePlan}
        </button>

        {!hasRequirements && (
          <p className="text-xs text-[var(--tp-text-2)] text-center">{t.d2pEmptyRequirements}</p>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700 dark:bg-red-900/20 dark:border-red-700 dark:text-red-300">
            {error}
          </div>
        )}

        {/* Results */}
        {plan && <PlanResultView plan={plan} t={t} />}
      </div>
    </div>
  )
}
