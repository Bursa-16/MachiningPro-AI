import { useState, useEffect } from 'react'
import { useLocale } from '../i18n'
import type { TranslationDictionary } from '../i18n/types'

type TFunc = (key: keyof TranslationDictionary) => string
import {
  fetchSelectionSchema,
  evaluateSelection,
  type SelectionSchemaResponse,
  type SelectionResponse,
  type CandidateEntry,
  type SelectionCriterionResult,
} from '../services/selection'
import type { RuleResult } from '../services/compatibility'

// ── Colour maps ────────────────────────────────────────────────────────────────

const RULE_STATUS_COLORS: Record<string, string> = {
  PASS: 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30',
  FAIL: 'bg-red-500/15 text-red-300 border border-red-500/30',
  UNKNOWN: 'bg-amber-500/15 text-amber-300 border border-amber-500/30',
  NOT_APPLICABLE: 'bg-tp-surface-2 text-tp-text-3 border border-tp-border',
}

const STATE_COLORS: Record<string, string> = {
  SELECTION_AVAILABLE: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300',
  COMPATIBLE_BUT_NO_DIFFERENTIATING_EVIDENCE: 'border-sky-500/40 bg-sky-500/10 text-sky-300',
  NO_COMPATIBLE_CONFIGURATION: 'border-red-500/40 bg-red-500/10 text-red-300',
  INSUFFICIENT_DATA_FOR_SELECTION: 'border-amber-500/40 bg-amber-500/10 text-amber-300',
}

// ── Helper components ──────────────────────────────────────────────────────────

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
      className="w-full bg-tp-surface border border-tp-border rounded px-3 py-2 text-sm text-tp-text focus:outline-none focus:border-tp-accent-light disabled:opacity-40 disabled:cursor-not-allowed"
    >
      <option value="">{placeholder}</option>
      {options.map(o => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  )
}

function NumericInput({
  value,
  onChange,
  placeholder,
  min,
}: {
  value: string
  onChange: (v: string) => void
  placeholder: string
  min?: number
}) {
  return (
    <input
      type="number"
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      min={min}
      className="w-full bg-tp-surface border border-tp-border rounded px-3 py-2 text-sm text-tp-text focus:outline-none focus:border-tp-accent-light"
    />
  )
}

function Badge({ label, cls }: { label: string; cls: string }) {
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide ${cls}`}>
      {label}
    </span>
  )
}

function SectionLabel({ text }: { text: string }) {
  return (
    <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light mb-2">
      {text}
    </div>
  )
}

// ── Rule trace row ─────────────────────────────────────────────────────────────

function RuleRow({ rule }: { rule: RuleResult }) {
  const cls = RULE_STATUS_COLORS[rule.status] ?? 'bg-tp-surface-2 text-tp-text-2 border border-tp-border'
  return (
    <tr className="border-b border-tp-border/40 last:border-0">
      <td className="py-1.5 pr-3 text-xs font-mono text-tp-text-2 whitespace-nowrap">{rule.rule_id}</td>
      <td className="py-1.5 pr-3">
        <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase ${cls}`}>
          {rule.status}
        </span>
      </td>
      <td className="py-1.5 pr-3 text-xs font-mono text-tp-text-3">{rule.reason_code}</td>
      <td className="py-1.5 text-xs text-tp-text-3">{rule.detail ?? '—'}</td>
    </tr>
  )
}

// ── Criterion trace row ────────────────────────────────────────────────────────

function CriterionRow({ c }: { c: SelectionCriterionResult }) {
  const appCls = c.applicable
    ? 'text-emerald-300'
    : 'text-tp-text-3'
  return (
    <tr className="border-b border-tp-border/40 last:border-0">
      <td className="py-1.5 pr-3 text-xs font-mono text-tp-text-2 whitespace-nowrap">{c.criterion_id}</td>
      <td className={`py-1.5 pr-3 text-xs font-semibold ${appCls}`}>
        {c.applicable ? c.value ?? '—' : 'N/A'}
      </td>
      <td className="py-1.5 text-xs text-tp-text-3">{c.note}</td>
    </tr>
  )
}

// ── Candidate card ─────────────────────────────────────────────────────────────

function CandidateCard({ entry, t }: {
  entry: CandidateEntry
  t: TFunc
}) {
  const [expanded, setExpanded] = useState(false)

  const rankLabel = entry.rank != null ? `#${entry.rank}` : '—'
  const tieTag = entry.engineering_tie
    ? <Badge label={t('csEngineeringTie')} cls="bg-sky-500/15 text-sky-300 border border-sky-500/30 ml-2" />
    : null

  return (
    <div className="bg-tp-surface border border-tp-border rounded-lg overflow-hidden">
      {/* Header row */}
      <button
        onClick={() => setExpanded(v => !v)}
        className="w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-tp-surface-2/40 transition-colors"
      >
        <span className="text-sm font-bold text-tp-accent-light w-8 shrink-0">{rankLabel}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-mono text-tp-text">{entry.machine_id}</span>
            <span className="text-tp-text-3 text-xs">/</span>
            <span className="text-xs font-mono text-tp-text">{entry.holder_id}</span>
            <span className="text-tp-text-3 text-xs">/</span>
            <span className="text-xs font-mono text-tp-text">{entry.cutting_tool_id}</span>
            {tieTag}
          </div>
          {entry.ahead_reason && (
            <div className="text-[11px] text-emerald-400 mt-0.5">{entry.ahead_reason}</div>
          )}
        </div>
        <span className="text-tp-text-3 text-xs shrink-0">{expanded ? '▲' : '▼'}</span>
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-tp-border/60 px-4 py-3 space-y-4">
          {/* Engineering tie explanation */}
          {entry.engineering_tie && entry.engineering_tie_reason && (
            <div className="text-xs text-sky-300 bg-sky-500/10 border border-sky-500/20 rounded px-3 py-2">
              {entry.engineering_tie_reason}
            </div>
          )}

          {/* Selection criteria */}
          <div>
            <SectionLabel text={t('csCriteriaTrace')} />
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <tbody>
                  {entry.selection_criteria_trace.map((c, i) => (
                    <CriterionRow key={i} c={c} />
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Compatibility rule trace */}
          <div>
            <SectionLabel text={t('csCompatibilityTrace')} />
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="text-[10px] uppercase tracking-wide text-tp-text-3 border-b border-tp-border">
                    <th className="pb-1 pr-3 font-semibold">Rule</th>
                    <th className="pb-1 pr-3 font-semibold">Status</th>
                    <th className="pb-1 pr-3 font-semibold">Reason</th>
                    <th className="pb-1 font-semibold">Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {entry.compatibility_trace.map((r, i) => (
                    <RuleRow key={i} rule={r} />
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Sample list (rejected / not-rankable) ──────────────────────────────────────

function SampleList({ entries, title }: {
  entries: CandidateEntry[]
  title: string
}) {
  const [open, setOpen] = useState(false)
  if (entries.length === 0) return null

  return (
    <div className="bg-tp-surface border border-tp-border rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full text-left px-4 py-3 flex items-center justify-between hover:bg-tp-surface-2/40 transition-colors"
      >
        <span className="text-xs font-semibold text-tp-text-2">{title} ({entries.length})</span>
        <span className="text-tp-text-3 text-xs">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="border-t border-tp-border/60 px-4 py-3 space-y-2">
          {entries.map((e, i) => (
            <div key={i} className="text-xs text-tp-text-3">
              <span className="font-mono">{e.machine_id} / {e.holder_id} / {e.cutting_tool_id}</span>
              {(e.rejection_reason ?? e.not_rankable_reason) && (
                <div className="text-[11px] text-tp-text-3 mt-0.5 ml-2">
                  — {e.rejection_reason ?? e.not_rankable_reason}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function SelectionPage() {
  const { t } = useLocale()

  const [schema, setSchema] = useState<SelectionSchemaResponse | null>(null)
  const [schemaError, setSchemaError] = useState(false)

  const [operation, setOperation] = useState('')
  const [isoGroup, setIsoGroup] = useState('')
  const [machineId, setMachineId] = useState('')
  const [toolId, setToolId] = useState('')
  const [vc, setVc] = useState('')
  const [diameter, setDiameter] = useState('')

  const [loading, setLoading] = useState(false)
  const [evalError, setEvalError] = useState<string | null>(null)
  const [result, setResult] = useState<SelectionResponse | null>(null)

  useEffect(() => {
    fetchSelectionSchema()
      .then(setSchema)
      .catch(() => setSchemaError(true))
  }, [])

  const canEvaluate = operation !== '' && isoGroup !== ''

  async function handleEvaluate() {
    if (!canEvaluate) return
    setLoading(true)
    setEvalError(null)
    setResult(null)
    try {
      const resp = await evaluateSelection({
        operation,
        iso_material_group: isoGroup,
        machine_id: machineId || null,
        cutting_tool_id: toolId || null,
        cutting_speed_m_min: vc !== '' ? parseFloat(vc) : null,
        tool_diameter_mm: diameter !== '' ? parseFloat(diameter) : null,
      })
      setResult(resp)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setEvalError(msg)
    } finally {
      setLoading(false)
    }
  }

  const opOptions = (schema?.valid_operations ?? []).map(op => ({
    value: op,
    label: op.charAt(0).toUpperCase() + op.slice(1),
  }))

  const isoOptions = (schema?.valid_iso_groups ?? []).sort().map(g => ({
    value: g,
    label: `ISO ${g}`,
  }))

  const machineOptions = (schema?.machines ?? []).map(m => ({
    value: m.id,
    label: m.display,
  }))

  const toolOptions = (schema?.cutting_tools ?? []).map(m => ({
    value: m.id,
    label: m.display,
  }))

  const stateLabel: Record<string, string> = {
    SELECTION_AVAILABLE: t('csStateAvailable'),
    COMPATIBLE_BUT_NO_DIFFERENTIATING_EVIDENCE: t('csStateNoEvidence'),
    NO_COMPATIBLE_CONFIGURATION: t('csStateNoCompatible'),
    INSUFFICIENT_DATA_FOR_SELECTION: t('csStateInsufficientData'),
  }

  const stateDesc: Record<string, string> = {
    SELECTION_AVAILABLE: t('csStateAvailableDesc'),
    COMPATIBLE_BUT_NO_DIFFERENTIATING_EVIDENCE: t('csStateNoEvidenceDesc'),
    NO_COMPATIBLE_CONFIGURATION: t('csStateNoCompatibleDesc'),
    INSUFFICIENT_DATA_FOR_SELECTION: t('csStateInsufficientDataDesc'),
  }

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-4xl">
        {/* Page header */}
        <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light mb-2">
          MachiningPro AI
        </div>
        <h1 className="text-xl font-semibold text-tp-text mb-1">{t('csTitle')}</h1>
        <p className="text-sm text-tp-text-2 mb-6">{t('csSubtitle')}</p>

        {/* Schema loading / error */}
        {schemaError && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-sm text-red-300 mb-6">
            {t('csBackendError')}
          </div>
        )}

        {!schema && !schemaError && (
          <div className="text-sm text-tp-text-3 mb-6">{t('csLoadingSchema')}</div>
        )}

        {schema && (
          <div className="space-y-5">
            {/* ── Required inputs ─────────────────────────────────────────── */}
            <div className="bg-tp-surface border border-tp-border rounded-lg p-4">
              <SectionLabel text={t('csStepRequired')} />
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs text-tp-text-2 mb-1">{t('csStepOperation')}</label>
                  <Select
                    value={operation}
                    onChange={setOperation}
                    options={opOptions}
                    placeholder={t('csSelectOperation')}
                  />
                </div>
                <div>
                  <label className="block text-xs text-tp-text-2 mb-1">{t('csStepIsoGroup')}</label>
                  <Select
                    value={isoGroup}
                    onChange={setIsoGroup}
                    options={isoOptions}
                    placeholder={t('csSelectIsoGroup')}
                  />
                </div>
              </div>
            </div>

            {/* ── Optional filters ─────────────────────────────────────────── */}
            <div className="bg-tp-surface border border-tp-border rounded-lg p-4">
              <SectionLabel text={t('csStepFilters')} />
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs text-tp-text-2 mb-1">{t('csStepMachine')}</label>
                  <Select
                    value={machineId}
                    onChange={setMachineId}
                    options={machineOptions}
                    placeholder={t('csAllMachines')}
                  />
                </div>
                <div>
                  <label className="block text-xs text-tp-text-2 mb-1">{t('csStepTool')}</label>
                  <Select
                    value={toolId}
                    onChange={setToolId}
                    options={toolOptions}
                    placeholder={t('csAllTools')}
                  />
                </div>
              </div>
            </div>

            {/* ── Optional numeric (RPM margin criterion) ──────────────────── */}
            <div className="bg-tp-surface border border-tp-border rounded-lg p-4">
              <SectionLabel text={t('csStepCutParams')} />
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs text-tp-text-2 mb-1">
                    {t('csCuttingSpeed')}
                  </label>
                  <NumericInput
                    value={vc}
                    onChange={setVc}
                    placeholder="e.g. 120"
                    min={0}
                  />
                </div>
                <div>
                  <label className="block text-xs text-tp-text-2 mb-1">
                    {t('csToolDiameter')}
                  </label>
                  <NumericInput
                    value={diameter}
                    onChange={setDiameter}
                    placeholder="e.g. 6"
                    min={0.001}
                  />
                </div>
              </div>
              <p className="text-xs text-tp-text-3 mt-2">{t('csCutParamsNote')}</p>
            </div>

            {/* ── Evaluate button ───────────────────────────────────────────── */}
            <button
              onClick={handleEvaluate}
              disabled={!canEvaluate || loading}
              className="w-full py-2.5 px-4 bg-tp-accent hover:bg-tp-accent/90 disabled:opacity-40 disabled:cursor-not-allowed rounded font-semibold text-sm text-white transition-colors"
            >
              {loading ? t('csLoadingEvaluation') : t('csEvaluateBtn')}
            </button>

            {!canEvaluate && !result && (
              <p className="text-xs text-tp-text-3 text-center">{t('csSelectFields')}</p>
            )}

            {/* ── Evaluation error ─────────────────────────────────────────── */}
            {evalError && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-sm text-red-300">
                {t('csEvaluationError')}: {evalError}
              </div>
            )}

            {/* ── Results ──────────────────────────────────────────────────── */}
            {result && (
              <div className="space-y-4">
                {/* Overall state */}
                <div className={`border rounded-lg px-4 py-3 ${STATE_COLORS[result.overall_state] ?? ''}`}>
                  <div className="text-sm font-bold uppercase tracking-wide">
                    {stateLabel[result.overall_state] ?? result.overall_state}
                  </div>
                  <div className="text-xs mt-0.5 opacity-80">
                    {stateDesc[result.overall_state]}
                  </div>
                </div>

                {/* Summary counts */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {[
                    { label: t('csCandidatesEvaluated'), value: result.candidates_evaluated },
                    { label: t('csCompatibleCount'), value: result.compatible_count },
                    { label: t('csIncompatibleCount'), value: result.incompatible_count },
                    { label: t('csNotRankableCount'), value: result.not_rankable_count },
                  ].map(({ label, value }) => (
                    <div key={label} className="bg-tp-surface border border-tp-border rounded-lg px-3 py-2 text-center">
                      <div className="text-lg font-bold text-tp-text">{value}</div>
                      <div className="text-[10px] text-tp-text-3 uppercase tracking-wide mt-0.5">{label}</div>
                    </div>
                  ))}
                </div>

                {/* Ranked candidates */}
                {result.ranked_candidates.length > 0 && (
                  <div>
                    <SectionLabel text={t('csRankedCandidates')} />
                    <div className="space-y-2">
                      {result.ranked_candidates.map((entry, i) => (
                        <CandidateCard key={i} entry={entry} t={t} />
                      ))}
                    </div>
                  </div>
                )}

                {/* Sample lists */}
                <SampleList
                  entries={result.rejected_sample}
                  title={t('csRejectedSample')}
                />
                <SampleList
                  entries={result.not_rankable_sample}
                  title={t('csNotRankableSample')}
                />

                {/* Disclaimer */}
                <div className="bg-tp-surface border border-tp-border rounded-lg px-4 py-3 text-xs text-tp-text-3">
                  {result.disclaimer}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
