import { useState, useEffect } from 'react'
import { useLocale } from '../i18n'
import {
  fetchCompatibilitySchema,
  evaluateCompatibility,
  type CompatibilitySchemaResponse,
  type CompatibilityResponse,
  type RuleResult,
} from '../services/compatibility'

// ── Status badge colours ───────────────────────────────────────────────────────
const STATUS_COLORS: Record<string, string> = {
  PASS: 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30',
  FAIL: 'bg-red-500/15 text-red-300 border border-red-500/30',
  UNKNOWN: 'bg-amber-500/15 text-amber-300 border border-amber-500/30',
  NOT_APPLICABLE: 'bg-tp-surface-2 text-tp-text-3 border border-tp-border',
}

const OVERALL_COLORS: Record<string, string> = {
  COMPATIBLE: 'border-emerald-500/40 bg-emerald-500/10',
  INCOMPATIBLE: 'border-red-500/40 bg-red-500/10',
  INSUFFICIENT_DATA: 'border-amber-500/40 bg-amber-500/10',
}

const OVERALL_TEXT: Record<string, string> = {
  COMPATIBLE: 'text-emerald-300',
  INCOMPATIBLE: 'text-red-300',
  INSUFFICIENT_DATA: 'text-amber-300',
}

function RuleStatusBadge({ status, label }: { status: string; label: string }) {
  const cls = STATUS_COLORS[status] ?? 'bg-tp-surface-2 text-tp-text-2 border border-tp-border'
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide ${cls}`}>
      {label}
    </span>
  )
}

function Select({
  value,
  onChange,
  options,
  placeholder,
  disabled,
}: {
  value: string
  onChange: (v: string) => void
  options: Array<{ value: string; label: string }>
  placeholder: string
  disabled?: boolean
}) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      disabled={disabled}
      className={`
        w-full bg-tp-surface border border-tp-border rounded px-3 py-2
        text-sm text-tp-text focus:outline-none focus:border-tp-accent-light
        disabled:opacity-40 disabled:cursor-not-allowed
      `}
    >
      <option value="">{placeholder}</option>
      {options.map(o => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  )
}

function StepHeader({
  number,
  label,
  active,
  complete,
}: {
  number: number
  label: string
  active: boolean
  complete: boolean
}) {
  const dot = complete
    ? 'bg-emerald-500 text-white'
    : active
      ? 'bg-tp-accent text-white'
      : 'bg-tp-surface-2 text-tp-text-3 border border-tp-border'
  return (
    <div className="flex items-center gap-2 mb-2">
      <span className={`flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold ${dot}`}>
        {complete ? '✓' : number}
      </span>
      <span className={`text-xs font-semibold uppercase tracking-widest ${active ? 'text-tp-accent-light' : 'text-tp-text-3'}`}>
        {label}
      </span>
    </div>
  )
}

// ── Result view ────────────────────────────────────────────────────────────────
function ResultView({
  result,
  onReset,
}: {
  result: CompatibilityResponse
  onReset: () => void
}) {
  const { t } = useLocale()

  const statusLabel = {
    COMPATIBLE: t('ccResultCompatible'),
    INCOMPATIBLE: t('ccResultIncompatible'),
    INSUFFICIENT_DATA: t('ccResultInsufficient'),
  }[result.overall_status] ?? result.overall_status

  const statusDesc = {
    COMPATIBLE: t('ccResultCompatibleDesc'),
    INCOMPATIBLE: t('ccResultIncompatibleDesc'),
    INSUFFICIENT_DATA: t('ccResultInsufficientDesc'),
  }[result.overall_status] ?? ''

  const ruleStatusLabel = (status: string) => ({
    PASS: t('ccStatusPass'),
    FAIL: t('ccStatusFail'),
    UNKNOWN: t('ccStatusUnknown'),
    NOT_APPLICABLE: t('ccStatusNotApplicable'),
  }[status] ?? status)

  return (
    <div className="space-y-4">
      <button
        onClick={onReset}
        className="text-sm text-tp-accent-light hover:text-tp-accent transition-colors"
      >
        ← {t('ccNewEvaluation')}
      </button>

      {/* Overall result banner */}
      <div className={`rounded-lg border p-5 ${OVERALL_COLORS[result.overall_status] ?? 'border-tp-border bg-tp-surface'}`}>
        <div className={`text-xl font-bold tracking-wider mb-1 ${OVERALL_TEXT[result.overall_status] ?? 'text-tp-text'}`}>
          {statusLabel}
        </div>
        <div className="text-sm text-tp-text-2">{statusDesc}</div>

        {result.calculated_rpm != null && (
          <div className="mt-3 text-xs text-tp-text-3">
            {t('ccCalculatedRpm')}: <span className="font-semibold text-tp-text">{Math.round(result.calculated_rpm).toLocaleString()} {t('ccUnitRpm')}</span>
          </div>
        )}
      </div>

      {/* Rule trace table */}
      <div className="bg-tp-surface border border-tp-border rounded-lg overflow-hidden">
        <div className="px-4 py-3 border-b border-tp-border">
          <span className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light">
            {t('ccRuleTrace')}
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-tp-border text-[10px] uppercase tracking-wider text-tp-text-3">
                <th className="text-left px-4 py-2">{t('ccRuleId')}</th>
                <th className="text-left px-4 py-2">{t('ccRuleStatus')}</th>
                <th className="text-left px-4 py-2">{t('ccRuleReasonCode')}</th>
                <th className="text-left px-4 py-2 hidden md:table-cell">{t('ccRuleDetail')}</th>
              </tr>
            </thead>
            <tbody>
              {result.rule_results.map((r: RuleResult) => (
                <tr key={r.rule_id} className="border-b border-tp-border/50 hover:bg-tp-surface-2/40">
                  <td className="px-4 py-2 font-mono text-xs text-tp-text">{r.rule_id}</td>
                  <td className="px-4 py-2">
                    <RuleStatusBadge status={r.status} label={ruleStatusLabel(r.status)} />
                  </td>
                  <td className="px-4 py-2 font-mono text-[10px] text-tp-text-3 break-all">{r.reason_code}</td>
                  <td className="px-4 py-2 text-xs text-tp-text-2 hidden md:table-cell max-w-xs">{r.detail ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Missing fields */}
      {result.missing_fields.length > 0 && (
        <div className="bg-tp-surface border border-tp-border rounded-lg p-4">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light mb-2">
            {t('ccMissingFields')}
          </div>
          <ul className="space-y-1">
            {result.missing_fields.map(f => (
              <li key={f} className="text-xs text-tp-text-2 font-mono">{f}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Reference guidance note */}
      <div className="bg-tp-surface border border-tp-border rounded-lg p-4">
        <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light mb-1">
          {t('ccReferenceGuidance')}
        </div>
        <div className="text-xs text-tp-text-2">
          {result.reference_guidance_available
            ? t('ccReferenceGuidance')
            : t('ccReferenceNotAvailable')}
        </div>
      </div>

      {/* Disclaimer */}
      <div className="text-[10px] text-tp-text-3 leading-relaxed">
        {t('ccCompatibilityNote')}
      </div>
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────────
export default function CompatibilityPage() {
  const { t } = useLocale()

  const [schema, setSchema] = useState<CompatibilitySchemaResponse | null>(null)
  const [schemaError, setSchemaError] = useState(false)

  // Form state
  const [machineId, setMachineId] = useState('')
  const [holderId, setHolderId] = useState('')
  const [toolId, setToolId] = useState('')
  const [operation, setOperation] = useState('')
  const [isoGroup, setIsoGroup] = useState('')
  const [vc, setVc] = useState('')
  const [diameter, setDiameter] = useState('')

  // Evaluation state
  const [evaluating, setEvaluating] = useState(false)
  const [evalError, setEvalError] = useState<string | null>(null)
  const [result, setResult] = useState<CompatibilityResponse | null>(null)

  useEffect(() => {
    fetchCompatibilitySchema()
      .then(setSchema)
      .catch(() => setSchemaError(true))
  }, [])

  const canEvaluate =
    schema != null &&
    machineId !== '' &&
    holderId !== '' &&
    toolId !== '' &&
    operation !== '' &&
    isoGroup !== ''

  const operationLabel = (op: string) => {
    const map: Record<string, string> = {
      milling: t('ccOperationMilling'),
      drilling: t('ccOperationDrilling'),
      turning: t('ccOperationTurning'),
      reaming: t('ccOperationReaming'),
      boring: t('ccOperationBoring'),
      tapping: t('ccOperationTapping'),
    }
    return map[op] ?? op.charAt(0).toUpperCase() + op.slice(1)
  }

  const handleEvaluate = async () => {
    if (!canEvaluate) return
    setEvaluating(true)
    setEvalError(null)
    setResult(null)
    try {
      const vcNum = vc.trim() !== '' ? parseFloat(vc) : null
      const dNum = diameter.trim() !== '' ? parseFloat(diameter) : null
      const res = await evaluateCompatibility({
        machine_id: machineId,
        holder_id: holderId,
        cutting_tool_id: toolId,
        operation,
        iso_material_group: isoGroup,
        cutting_speed_m_min: vcNum,
        tool_diameter_mm: dNum,
      })
      setResult(res)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setEvalError(msg)
    } finally {
      setEvaluating(false)
    }
  }

  const handleReset = () => {
    setResult(null)
    setEvalError(null)
    setMachineId('')
    setHolderId('')
    setToolId('')
    setOperation('')
    setIsoGroup('')
    setVc('')
    setDiameter('')
  }

  // Show result view
  if (result) {
    return (
      <div className="h-full overflow-y-auto p-6">
        <div className="max-w-4xl space-y-3">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light">
            MachiningPro AI
          </div>
          <h1 className="text-xl font-semibold text-tp-text">{t('ccPageTitle')}</h1>
          <ResultView result={result} onReset={handleReset} />
        </div>
      </div>
    )
  }

  // Schema loading / error
  if (schemaError) {
    return (
      <div className="h-full overflow-y-auto p-6">
        <div className="max-w-3xl">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light mb-2">
            MachiningPro AI
          </div>
          <h1 className="text-xl font-semibold text-tp-text mb-3">{t('ccPageTitle')}</h1>
          <div className="bg-tp-surface border border-tp-border rounded-lg p-5 text-sm text-red-300">
            {t('ccBackendError')}
          </div>
        </div>
      </div>
    )
  }

  if (!schema) {
    return (
      <div className="h-full overflow-y-auto p-6">
        <div className="max-w-3xl">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light mb-2">
            MachiningPro AI
          </div>
          <h1 className="text-xl font-semibold text-tp-text mb-3">{t('ccPageTitle')}</h1>
          <div className="text-sm text-tp-text-2">{t('ccLoadingSchema')}</div>
        </div>
      </div>
    )
  }

  const machineOptions = schema.machines.map(m => ({ value: m.id, label: m.display }))
  const holderOptions = schema.holders.map(h => ({ value: h.id, label: h.display }))
  const toolOptions = schema.cutting_tools.map(tool => ({ value: tool.id, label: tool.display }))
  const operationOptions = schema.valid_operations.map(op => ({
    value: op,
    label: operationLabel(op),
  }))
  const isoOptions = schema.valid_iso_groups.map(g => ({ value: g, label: `ISO ${g}` }))

  const step1Done = machineId !== ''
  const step2Done = holderId !== ''
  const step3Done = toolId !== ''
  const step4Done = operation !== ''
  const step5Done = isoGroup !== ''

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-3xl space-y-3">
        {/* Header */}
        <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light">
          MachiningPro AI
        </div>
        <h1 className="text-xl font-semibold text-tp-text">{t('ccPageTitle')}</h1>
        <p className="text-sm text-tp-text-2">{t('ccPageSubtitle')}</p>

        {/* Evidence badge */}
        <div className="flex gap-2 items-center">
          <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide bg-amber-500/15 text-amber-300 border border-amber-500/30">
            {t('ccEvidenceStatus')}
          </span>
        </div>

        {/* Disclaimer */}
        <div className="bg-tp-surface border border-amber-500/20 rounded-lg p-3 text-xs text-tp-text-2">
          {t('ccProductionNotValidated')}
        </div>

        {/* Step 1 — Machine */}
        <div className="bg-tp-surface border border-tp-border rounded-lg p-4">
          <StepHeader number={1} label={t('ccStep1Machine')} active={true} complete={step1Done} />
          <Select
            value={machineId}
            onChange={v => { setMachineId(v); setHolderId(''); setToolId(''); setOperation(''); setIsoGroup('') }}
            options={machineOptions}
            placeholder={t('ccSelectMachine')}
          />
        </div>

        {/* Step 2 — Holder */}
        <div className={`bg-tp-surface border rounded-lg p-4 ${step1Done ? 'border-tp-border' : 'border-tp-border/40 opacity-60'}`}>
          <StepHeader number={2} label={t('ccStep2Holder')} active={step1Done} complete={step2Done} />
          <Select
            value={holderId}
            onChange={v => { setHolderId(v); setToolId(''); setOperation(''); setIsoGroup('') }}
            options={holderOptions}
            placeholder={t('ccSelectHolder')}
            disabled={!step1Done}
          />
        </div>

        {/* Step 3 — Cutting Tool */}
        <div className={`bg-tp-surface border rounded-lg p-4 ${step2Done ? 'border-tp-border' : 'border-tp-border/40 opacity-60'}`}>
          <StepHeader number={3} label={t('ccStep3Tool')} active={step2Done} complete={step3Done} />
          <Select
            value={toolId}
            onChange={v => { setToolId(v); setOperation(''); setIsoGroup('') }}
            options={toolOptions}
            placeholder={t('ccSelectTool')}
            disabled={!step2Done}
          />
        </div>

        {/* Step 4 — Operation */}
        <div className={`bg-tp-surface border rounded-lg p-4 ${step3Done ? 'border-tp-border' : 'border-tp-border/40 opacity-60'}`}>
          <StepHeader number={4} label={t('ccStep4Operation')} active={step3Done} complete={step4Done} />
          <Select
            value={operation}
            onChange={v => { setOperation(v); setIsoGroup('') }}
            options={operationOptions}
            placeholder={t('ccSelectOperation')}
            disabled={!step3Done}
          />
        </div>

        {/* Step 5 — ISO Material Group */}
        <div className={`bg-tp-surface border rounded-lg p-4 ${step4Done ? 'border-tp-border' : 'border-tp-border/40 opacity-60'}`}>
          <StepHeader number={5} label={t('ccStep5IsoGroup')} active={step4Done} complete={step5Done} />
          <Select
            value={isoGroup}
            onChange={setIsoGroup}
            options={isoOptions}
            placeholder={t('ccSelectIsoGroup')}
            disabled={!step4Done}
          />
        </div>

        {/* Step 6 — Optional Vc + diameter */}
        <div className={`bg-tp-surface border rounded-lg p-4 ${step5Done ? 'border-tp-border' : 'border-tp-border/40 opacity-60'}`}>
          <StepHeader number={6} label={t('ccStep6Vc')} active={step5Done} complete={false} />
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-tp-text-3 mb-1">{t('ccVcLabel')}</label>
              <input
                type="number"
                min="0"
                step="any"
                value={vc}
                onChange={e => setVc(e.target.value)}
                disabled={!step5Done}
                placeholder="e.g. 120"
                className="w-full bg-tp-surface border border-tp-border rounded px-3 py-2 text-sm text-tp-text focus:outline-none focus:border-tp-accent-light disabled:opacity-40"
              />
            </div>
            <div>
              <label className="block text-xs text-tp-text-3 mb-1">{t('ccDiameterLabel')}</label>
              <input
                type="number"
                min="0.001"
                step="any"
                value={diameter}
                onChange={e => setDiameter(e.target.value)}
                disabled={!step5Done}
                placeholder="e.g. 6"
                className="w-full bg-tp-surface border border-tp-border rounded px-3 py-2 text-sm text-tp-text focus:outline-none focus:border-tp-accent-light disabled:opacity-40"
              />
            </div>
          </div>
        </div>

        {/* Evaluate button */}
        <div className="pt-1">
          {!canEvaluate && (
            <p className="text-xs text-tp-text-3 mb-2">{t('ccSelectAll')}</p>
          )}
          <button
            onClick={handleEvaluate}
            disabled={!canEvaluate || evaluating}
            className={`
              w-full py-2.5 rounded font-semibold text-sm tracking-wide transition-colors
              ${canEvaluate && !evaluating
                ? 'bg-tp-accent hover:bg-tp-accent-light text-white cursor-pointer'
                : 'bg-tp-surface-2 text-tp-text-3 cursor-not-allowed border border-tp-border'}
            `}
          >
            {evaluating ? t('ccLoadingEvaluation') : t('ccEvaluateButton')}
          </button>
        </div>

        {/* Evaluation error */}
        {evalError && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-sm text-red-300">
            {t('ccEvaluationError')}: {evalError}
          </div>
        )}
      </div>
    </div>
  )
}
