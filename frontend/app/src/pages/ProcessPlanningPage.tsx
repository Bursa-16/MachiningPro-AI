import { useState, useEffect, useCallback } from 'react'
import { useLocale } from '../i18n'
import type { TranslationDictionary } from '../i18n/types'
import {
  fetchProcessPlanningSchema,
  generateProcessPlan,
  type ProcessPlanningSchema,
  type ProcessPlanResponse,
  type PlanStep,
  type OperationStepRequest,
  type EngineeringMetric,
  type StepEngineeringMetrics,
  type MetricStatus,
  type StepCycleTime,
  type CycleTimeStatus,
  type TimeComponentStatus,
} from '../services/process_planning'
import {
  analyzeNcPath,
  type NcAnalyzeRequest,
  type NcAnalyzeResponse,
  type NCProgramValidationSummary,
  type NCValidationFinding,
  type NCValidationSeverityValue,
  type NCValidationStatusValue,
  type NCProgramEngineeringReview,
  type EngReviewStatusValue,
  type ParserFeatureStateValue,
} from '../services/nc_path'

type TFunc = (key: keyof TranslationDictionary) => string

// ── Colour maps ────────────────────────────────────────────────────────────────

const STEP_STATUS_COLORS: Record<string, string> = {
  PLANNED: 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30',
  BLOCKED: 'bg-red-500/15 text-red-300 border border-red-500/30',
  INSUFFICIENT_DATA: 'bg-amber-500/15 text-amber-300 border border-amber-500/30',
  NOT_SUPPORTED: 'bg-tp-surface-2 text-tp-text-3 border border-tp-border',
}

const PLAN_STATUS_COLORS: Record<string, string> = {
  PLAN_COMPLETE: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300',
  PLAN_PARTIAL: 'border-sky-500/40 bg-sky-500/10 text-sky-300',
  PLAN_BLOCKED: 'border-red-500/40 bg-red-500/10 text-red-300',
  PLAN_INSUFFICIENT_DATA: 'border-amber-500/40 bg-amber-500/10 text-amber-300',
}

// ── Helpers ────────────────────────────────────────────────────────────────────

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

function FieldLabel({ text }: { text: string }) {
  return (
    <label className="block text-xs font-medium text-tp-text-2 mb-1">{text}</label>
  )
}

function SelectField({
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

function MultiSelectField({
  selected,
  onChange,
  options,
  placeholder,
  disabled,
}: {
  selected: string[]
  onChange: (v: string[]) => void
  options: Array<{ value: string; label: string }>
  placeholder: string
  disabled?: boolean
}) {
  const toggle = (val: string) => {
    if (selected.includes(val)) {
      onChange(selected.filter(v => v !== val))
    } else {
      onChange([...selected, val])
    }
  }
  return (
    <div className="border border-tp-border rounded bg-tp-surface p-2 flex flex-wrap gap-1.5 min-h-[40px]">
      {options.length === 0 && (
        <span className="text-xs text-tp-text-3 self-center">{placeholder}</span>
      )}
      {options.map(o => {
        const on = selected.includes(o.value)
        return (
          <button
            key={o.value}
            type="button"
            onClick={() => !disabled && toggle(o.value)}
            disabled={disabled}
            className={`px-2 py-0.5 rounded text-[11px] font-mono border transition-colors disabled:cursor-not-allowed
              ${on
                ? 'bg-tp-accent-light/20 border-tp-accent-light text-tp-accent-light'
                : 'bg-tp-surface-2 border-tp-border text-tp-text-3 hover:border-tp-text-3'
              }`}
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}

// ── Step editor row ───────────────────────────────────────────────────────────

interface StepForm {
  id: string
  step_id: string
  sequence_number: string
  operation: string
  machine_id: string
  cutting_tool_id: string
  predecessor_ids: string[]
  // Cycle-time explicit inputs
  cutting_path_length_mm: string
  cutting_path_source: string
  rapid_distance_mm: string
  dwell_sec: string
  // NC path evidence
  nc_text: string
  nc_init_origin: boolean
  nc_analysis: NcAnalyzeResponse | null
  nc_analysis_error: string | null
}

function newStep(seq: number): StepForm {
  return {
    id: crypto.randomUUID(),
    step_id: `OP${seq * 10}`,
    sequence_number: String(seq * 10),
    operation: '',
    machine_id: '',
    cutting_tool_id: '',
    predecessor_ids: [],
    cutting_path_length_mm: '',
    cutting_path_source: '',
    rapid_distance_mm: '',
    dwell_sec: '',
    nc_text: '',
    nc_init_origin: false,
    nc_analysis: null,
    nc_analysis_error: null,
  }
}

const NC_STATUS_CLS: Record<string, string> = {
  COMPLETE: 'text-emerald-300',
  PARTIAL: 'text-amber-300',
  UNSUPPORTED_SEMANTICS: 'text-red-400',
  INVALID_PROGRAM: 'text-red-400',
  INSUFFICIENT_DATA: 'text-tp-text-3',
}

function StepRow({
  step,
  index,
  allSteps,
  schema,
  onChange,
  onRemove,
  t,
}: {
  step: StepForm
  index: number
  allSteps: StepForm[]
  schema: ProcessPlanningSchema | null
  onChange: (updated: StepForm) => void
  onRemove: () => void
  t: TFunc
}) {
  const [ncAnalyzing, setNcAnalyzing] = useState(false)
  const handleAnalyzeNc = async () => {
    if (!step.nc_text.trim()) return
    setNcAnalyzing(true)
    onChange({ ...step, nc_analysis: null, nc_analysis_error: null })
    try {
      const req: NcAnalyzeRequest = {
        nc_text: step.nc_text,
        ...(step.nc_init_origin ? { initial_x: 0, initial_y: 0, initial_z: 0 } : {}),
        ...(step.machine_id ? { machine_id: step.machine_id } : {}),
        ...(step.cutting_tool_id ? { cutting_tool_id: step.cutting_tool_id } : {}),
        ...(step.operation ? { operation: step.operation } : {}),
      }
      const result = await analyzeNcPath(req)
      onChange({ ...step, nc_analysis: result, nc_analysis_error: null })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t('ppNcAnalysisError')
      onChange({ ...step, nc_analysis: null, nc_analysis_error: msg })
    } finally {
      setNcAnalyzing(false)
    }
  }

  const predecessorOptions = allSteps
    .filter(s => s.id !== step.id && s.step_id.trim() !== '')
    .map(s => ({ value: s.step_id, label: s.step_id }))

  const machineOptions = schema?.machines.map(m => ({ value: m.id, label: m.display })) ?? []
  const toolOptions = schema?.cutting_tools.map(m => ({ value: m.id, label: m.display })) ?? []
  const opOptions = schema?.valid_operations.map(o => ({ value: o, label: o })) ?? []

  return (
    <div className="border border-tp-border rounded-lg p-3 space-y-3 bg-tp-surface-2/30">
      {/* Row header */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-tp-accent-light">Step {index + 1}</span>
        <button
          type="button"
          onClick={onRemove}
          className="text-[11px] text-red-400 hover:text-red-300 transition-colors"
        >
          {t('ppRemoveOperation')}
        </button>
      </div>

      {/* Step ID + Sequence */}
      <div className="grid grid-cols-2 gap-2">
        <div>
          <FieldLabel text={t('ppStepId')} />
          <input
            type="text"
            value={step.step_id}
            onChange={e => onChange({ ...step, step_id: e.target.value })}
            className="w-full bg-tp-surface border border-tp-border rounded px-3 py-2 text-sm text-tp-text font-mono focus:outline-none focus:border-tp-accent-light"
            placeholder="OP10"
          />
        </div>
        <div>
          <FieldLabel text={t('ppSequenceNumber')} />
          <input
            type="number"
            value={step.sequence_number}
            min={1}
            onChange={e => onChange({ ...step, sequence_number: e.target.value })}
            className="w-full bg-tp-surface border border-tp-border rounded px-3 py-2 text-sm text-tp-text focus:outline-none focus:border-tp-accent-light"
          />
        </div>
      </div>

      {/* Operation */}
      <div>
        <FieldLabel text={t('ppOperation')} />
        <SelectField
          value={step.operation}
          onChange={v => onChange({ ...step, operation: v })}
          options={opOptions}
          placeholder={t('ppSelectOperation')}
        />
      </div>

      {/* Machine / Tool */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <div>
          <FieldLabel text={t('ppMachineConstraint')} />
          <SelectField
            value={step.machine_id}
            onChange={v => onChange({ ...step, machine_id: v })}
            options={machineOptions}
            placeholder={t('ppAllMachines')}
          />
        </div>
        <div>
          <FieldLabel text={t('ppToolConstraint')} />
          <SelectField
            value={step.cutting_tool_id}
            onChange={v => onChange({ ...step, cutting_tool_id: v })}
            options={toolOptions}
            placeholder={t('ppAllTools')}
          />
        </div>
      </div>

      {/* Predecessors */}
      {predecessorOptions.length > 0 && (
        <div>
          <FieldLabel text={t('ppPredecessors')} />
          <MultiSelectField
            selected={step.predecessor_ids}
            onChange={v => onChange({ ...step, predecessor_ids: v })}
            options={predecessorOptions}
            placeholder={t('ppNoPredecessors')}
          />
        </div>
      )}

      {/* Cycle-time explicit inputs */}
      <div className="border-t border-tp-border/40 pt-2">
        <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light mb-2">
          {t('ppTimeAnalysis')}
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          <div>
            <FieldLabel text={t('ppCuttingPathLength')} />
            <input
              type="number"
              min={0}
              step="any"
              value={step.cutting_path_length_mm}
              onChange={e => onChange({ ...step, cutting_path_length_mm: e.target.value })}
              placeholder={t('ppPathLengthRequired')}
              className="w-full bg-tp-surface border border-tp-border rounded px-3 py-2 text-sm text-tp-text focus:outline-none focus:border-tp-accent-light"
            />
          </div>
          <div>
            <FieldLabel text={t('ppRapidDistance')} />
            <input
              type="number"
              min={0}
              step="any"
              value={step.rapid_distance_mm}
              onChange={e => onChange({ ...step, rapid_distance_mm: e.target.value })}
              placeholder="—"
              className="w-full bg-tp-surface border border-tp-border rounded px-3 py-2 text-sm text-tp-text focus:outline-none focus:border-tp-accent-light"
            />
          </div>
          <div>
            <FieldLabel text={t('ppDwellTime')} />
            <input
              type="number"
              min={0}
              step="any"
              value={step.dwell_sec}
              onChange={e => onChange({ ...step, dwell_sec: e.target.value })}
              placeholder="—"
              className="w-full bg-tp-surface border border-tp-border rounded px-3 py-2 text-sm text-tp-text focus:outline-none focus:border-tp-accent-light"
            />
          </div>
        </div>
      </div>

      {/* NC Path Evidence */}
      <div className="border-t border-tp-border/40 pt-2">
        <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light mb-2">
          {t('ppNcPathEvidence')}
        </div>
        <textarea
          rows={4}
          value={step.nc_text}
          onChange={e => onChange({ ...step, nc_text: e.target.value, nc_analysis: null, nc_analysis_error: null })}
          placeholder={t('ppNcPasteHere')}
          className="w-full bg-tp-surface border border-tp-border rounded px-3 py-2 text-xs font-mono text-tp-text focus:outline-none focus:border-tp-accent-light resize-y"
          spellCheck={false}
        />
        <div className="flex items-center gap-3 mt-2 flex-wrap">
          <label className="flex items-center gap-1.5 text-xs text-tp-text-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={step.nc_init_origin}
              onChange={e => onChange({ ...step, nc_init_origin: e.target.checked })}
              className="accent-tp-accent-light"
            />
            {t('ppNcInitOrigin')}
          </label>
          <button
            type="button"
            disabled={!step.nc_text.trim() || ncAnalyzing}
            onClick={handleAnalyzeNc}
            className="text-xs px-3 py-1 bg-tp-accent-light/20 border border-tp-accent-light/50 text-tp-accent-light rounded hover:bg-tp-accent-light/30 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {ncAnalyzing ? t('ppNcAnalyzing') : t('ppAnalyzeNc')}
          </button>
        </div>

        {step.nc_analysis_error && (
          <div className="mt-2 text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded px-3 py-2">
            {t('ppNcAnalysisError')}: {step.nc_analysis_error}
          </div>
        )}

        {step.nc_analysis && (() => {
          const mr = step.nc_analysis.motion_result
          const fe = step.nc_analysis.feed_evidence
          const re = step.nc_analysis.rapid_evidence
          const vs = step.nc_analysis.validation_summary
          const statusLabel: Record<string, string> = {
            COMPLETE: t('ppNcStatusComplete'),
            PARTIAL: t('ppNcStatusPartial'),
            UNSUPPORTED_SEMANTICS: t('ppNcStatusUnsupportedSemantics'),
            INVALID_PROGRAM: t('ppNcStatusInvalidProgram'),
            INSUFFICIENT_DATA: t('ppNcStatusInsufficientData'),
          }
          return (
            <div className="mt-3 border border-tp-border/60 rounded bg-tp-surface/50 p-3 space-y-3 text-xs">
              <div className="flex items-center gap-3 flex-wrap">
                <span className="text-tp-text-3">{t('ppNcAnalysisStatus')}:</span>
                <span className={`font-semibold ${NC_STATUS_CLS[mr.analysis_status] ?? 'text-tp-text'}`}>
                  {statusLabel[mr.analysis_status] ?? mr.analysis_status}
                </span>
                <span className="text-tp-text-3 font-mono text-[10px]">{mr.parser_profile}</span>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="text-tp-text-3">{t('ppNcFeedMotionDistance')}: </span>
                  <span className="text-tp-text font-mono">{fe.distance_mm.toFixed(3)}</span>
                </div>
                <div>
                  <span className="text-tp-text-3">{t('ppNcRapidMotionDistance')}: </span>
                  <span className="text-tp-text font-mono">{re.distance_mm.toFixed(3)}</span>
                </div>
              </div>
              <div className="flex gap-4 text-tp-text-3 flex-wrap">
                <span>{t('ppNcSupportedMotions')}: <span className="text-tp-text">{mr.supported_motion_count}</span></span>
                {mr.arc_motion_count > 0 && (
                  <span>{t('ppNcArcMotions')}: <span className="text-tp-text">{mr.arc_motion_count}</span></span>
                )}
                {mr.tool_change_count > 0 && (
                  <span>{t('ppNcToolChangeDetected')}: <span className="text-tp-text">{mr.tool_change_count} {t('ppNcToolChanges')}</span></span>
                )}
                {mr.unknown_start_count > 0 && (
                  <span className="text-amber-400">{mr.unknown_start_count} {t('ppNcUnknownStartMoves')}</span>
                )}
              </div>
              {mr.nc_commanded_feed_mm_min !== null && (
                <div className="text-tp-text-3">
                  {t('ppNcCommandedFeed')}: <span className="text-tp-text font-mono">{mr.nc_commanded_feed_mm_min.toFixed(1)}</span>
                  <span className="ml-2 text-[10px] italic text-tp-text-3">≠ {t('ppNcReferenceFeed')}</span>
                </div>
              )}
              {mr.unsupported_features.length > 0 && (
                <div>
                  <span className="text-amber-400">{t('ppNcUnsupportedFeatures')}: </span>
                  <span className="text-amber-300 font-mono">{mr.unsupported_features.join(', ')}</span>
                </div>
              )}
              <div className="text-[10px] text-tp-text-3 italic">{t('ppNcFeedMotionNote')}</div>
              {mr.arc_motion_count > 0 && (
                <div className="text-[10px] text-tp-text-3 italic">{t('ppNcArcFeedNote')}</div>
              )}
              {mr.unsupported_features && mr.unsupported_features.some(f => /^G8[1-5]/.test(f) || f.includes('CANNED')) && (
                <div className="text-[10px] text-tp-text-3 italic">{t('ppNcCannedFeedNote')}</div>
              )}
              {mr.segments && mr.segments.length > 0 && (
                <div className="border-t border-tp-border/30 pt-2">
                  <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light mb-1.5">
                    {t('ppNcSegments')} ({mr.segments.length})
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-[10px] border-collapse">
                      <thead>
                        <tr className="text-tp-text-3 text-left">
                          <th className="pr-2 pb-1 font-medium">{t('ppNcSegmentId')}</th>
                          <th className="pr-2 pb-1 font-medium">{t('ppNcSegmentTool')}</th>
                          <th className="pr-2 pb-1 font-medium text-right">{t('ppNcSegmentFeed')}</th>
                          <th className="pr-2 pb-1 font-medium text-right">{t('ppNcSegmentRapid')}</th>
                          <th className="pr-2 pb-1 font-medium text-right">{t('ppNcSegmentLinear')}</th>
                          <th className="pr-2 pb-1 font-medium text-right">{t('ppNcSegmentArc')}</th>
                          <th className="pr-2 pb-1 font-medium">{t('ppNcAnalysisStatus')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {mr.segments.map(seg => {
                          const segStatusCls: Record<string, string> = {
                            COMPLETE: 'text-emerald-300',
                            PARTIAL: 'text-amber-300',
                            UNSUPPORTED_SEMANTICS: 'text-orange-300',
                            INVALID_PROGRAM: 'text-red-400',
                            INSUFFICIENT_DATA: 'text-tp-text-3',
                          }
                          const toolLabel = seg.tool_id_raw
                            ? `T${seg.tool_id_raw}`
                            : t('ppNcSegmentNoTool')
                          return (
                            <tr key={seg.segment_id} className="border-t border-tp-border/20">
                              <td className="pr-2 py-0.5 font-mono text-tp-text">
                                {seg.segment_id === 'SEG_PREAMBLE'
                                  ? t('ppNcSegmentPreamble')
                                  : seg.segment_id}
                              </td>
                              <td className="pr-2 py-0.5 text-tp-text-2">{toolLabel}</td>
                              <td className="pr-2 py-0.5 text-right font-mono text-tp-text">
                                {seg.feed_motion_distance_mm.toFixed(3)}
                              </td>
                              <td className="pr-2 py-0.5 text-right font-mono text-tp-text">
                                {seg.rapid_motion_distance_mm.toFixed(3)}
                              </td>
                              <td className="pr-2 py-0.5 text-right text-tp-text-2">
                                {seg.linear_motion_count}
                              </td>
                              <td className="pr-2 py-0.5 text-right text-tp-text-2">
                                {seg.arc_motion_count}
                              </td>
                              <td className={`py-0.5 font-semibold ${segStatusCls[seg.analysis_status] ?? 'text-tp-text-3'}`}>
                                {seg.analysis_status}
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                  <div className="text-[9px] text-tp-text-3 italic mt-1">{t('ppNcToolIdRawNote')}</div>
                  {mr.unsupported_features && mr.unsupported_features.some(f => f.includes('G83_PECK_RAPID')) && (
                    <div className="text-[9px] text-amber-400/80 italic mt-0.5">{t('ppNcCannedG83Note')}</div>
                  )}
                  {mr.unsupported_features && mr.unsupported_features.some(f => f.includes('G84_CYCLE_TIME')) && (
                    <div className="text-[9px] text-amber-400/80 italic mt-0.5">{t('ppNcCannedG84Note')}</div>
                  )}
                  {mr.unsupported_features && mr.unsupported_features.some(f => f.includes('G91_DEFERRED')) && (
                    <div className="text-[9px] text-orange-400/80 italic mt-0.5">{t('ppNcCannedG91Note')}</div>
                  )}
                </div>
              )}
              <div className="flex gap-2 flex-wrap pt-1 border-t border-tp-border/40">
                <span className="text-[10px] text-tp-text-3 self-center">{t('ppNcExplicitAssignment')}:</span>
                <button
                  type="button"
                  onClick={() => onChange({ ...step, cutting_path_length_mm: String(fe.distance_mm), cutting_path_source: 'NC_DERIVED' })}
                  className="text-[11px] px-2 py-0.5 bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 rounded hover:bg-emerald-500/25 transition-colors"
                >
                  {t('ppNcUseAsCuttingPath')}
                </button>
                <button
                  type="button"
                  onClick={() => onChange({ ...step, rapid_distance_mm: String(re.distance_mm) })}
                  className="text-[11px] px-2 py-0.5 bg-sky-500/15 border border-sky-500/30 text-sky-300 rounded hover:bg-sky-500/25 transition-colors"
                >
                  {t('ppNcUseAsRapidDistance')}
                </button>
              </div>
              {vs && <NcProgramValidationSection vs={vs} t={t} />}
              {step.nc_analysis.engineering_review && (
                <NcEngineeringReviewSection er={step.nc_analysis.engineering_review} t={t} />
              )}
            </div>
          )
        })()}
      </div>

    </div>
  )
}

// ── NC Program Validation section ────────────────────────────────────────────

const PV_SEVERITY_CLS: Record<NCValidationSeverityValue, string> = {
  BLOCKING: 'bg-red-500/15 text-red-300 border border-red-500/30',
  WARNING: 'bg-amber-500/15 text-amber-300 border border-amber-500/30',
  ADVISORY: 'bg-sky-500/15 text-sky-300 border border-sky-500/30',
  INFO: 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30',
  INSUFFICIENT_DATA: 'bg-tp-surface-2 text-tp-text-3 border border-tp-border',
  NOT_APPLICABLE: 'bg-tp-surface-2 text-tp-text-3 border border-tp-border',
}

function PvFindingRow({
  finding,
  label,
  t,
}: {
  finding: NCValidationFinding | null
  label: string
  t: TFunc
}) {
  if (!finding) return null
  const sevLabel: Record<NCValidationSeverityValue, string> = {
    BLOCKING: t('ncPvSeverityBlocking'),
    WARNING: t('ncPvSeverityAdvisory'),
    ADVISORY: t('ncPvSeverityAdvisory'),
    INFO: t('ncPvSeverityInfo'),
    INSUFFICIENT_DATA: t('ncPvSeverityInsuffData'),
    NOT_APPLICABLE: t('ncPvStatusNotApplicable'),
  }
  const statusLabel: Record<NCValidationStatusValue, string> = {
    WITHIN_LIMIT: t('ncPvStatusWithinLimit'),
    EXCEEDS_LIMIT: t('ncPvStatusExceedsLimit'),
    WITHIN_REFERENCE_RANGE: t('ncPvStatusWithinRef'),
    BELOW_REFERENCE_RANGE: t('ncPvStatusBelowRef'),
    ABOVE_REFERENCE_RANGE: t('ncPvStatusAboveRef'),
    NOT_COMPARABLE: t('ncPvStatusInsuffData'),
    INSUFFICIENT_DATA: t('ncPvStatusInsuffData'),
    NOT_APPLICABLE: t('ncPvStatusNotApplicable'),
  }
  return (
    <div className="flex items-center justify-between gap-2 text-[11px]">
      <span className="text-tp-text-2 min-w-0 truncate">{label}</span>
      <div className="flex items-center gap-1.5 shrink-0">
        {finding.observed_value != null && (
          <span className="text-tp-text font-mono">
            {finding.observed_value.toFixed(finding.observed_unit === 'rpm' ? 0 : 3)}
            <span className="text-tp-text-3 ml-0.5">{finding.observed_unit}</span>
          </span>
        )}
        {finding.limit_or_reference != null && (
          <span className="text-tp-text-3">
            / {finding.limit_or_reference.toFixed(finding.limit_unit === 'rpm' ? 0 : 3)}
            <span className="ml-0.5">{finding.limit_unit}</span>
          </span>
        )}
        <Badge label={sevLabel[finding.severity]} cls={PV_SEVERITY_CLS[finding.severity]} />
        <span className="text-tp-text-3 text-[10px]">{statusLabel[finding.status]}</span>
      </div>
    </div>
  )
}

function NcProgramValidationSection({
  vs,
  t,
}: {
  vs: NCProgramValidationSummary
  t: TFunc
}) {
  const hasFeedSpindle = vs.nc_commanded_spindle_rpm != null || vs.nc_commanded_feed_mm_min != null || vs.nc_commanded_feed_mm_rev != null
  const hasCalc = vs.calculated_cutting_speed_m_min != null || vs.calculated_feed_per_tooth_mm != null || vs.calculated_feed_per_rev_mm != null
  const hasLimitChecks = vs.machine_rpm_limit_check != null || vs.tool_rpm_limit_check != null || vs.holder_rpm_limit_check != null || vs.effective_rpm_limit_check != null
  const hasRefChecks = vs.cutting_speed_check != null || vs.feed_per_tooth_check != null || vs.feed_per_rev_check != null

  return (
    <div className="mt-3 pt-3 border-t border-tp-border/40 space-y-2.5">
      <SectionLabel text={t('ncProgramValidation')} />

      {/* Summary badges */}
      {(vs.blocking_count > 0 || vs.advisory_count > 0) && (
        <div className="flex gap-2 flex-wrap">
          {vs.blocking_count > 0 && (
            <Badge
              label={`${vs.blocking_count} ${t('ncPvBlockingCount')}`}
              cls={PV_SEVERITY_CLS.BLOCKING}
            />
          )}
          {vs.advisory_count > 0 && (
            <Badge
              label={`${vs.advisory_count} ${t('ncPvAdvisoryCount')}`}
              cls={PV_SEVERITY_CLS.ADVISORY}
            />
          )}
        </div>
      )}

      {/* Feed/spindle evidence */}
      {hasFeedSpindle && (
        <div className="space-y-1 p-2 bg-tp-surface-2 rounded border border-tp-border/40">
          <div className="text-[10px] font-semibold text-tp-text-3 uppercase tracking-wide mb-1">
            {t('ncPvFeedMode')}: {vs.nc_feed_mode ?? '—'}
          </div>
          {vs.nc_commanded_feed_mm_min != null && (
            <div className="flex justify-between text-[11px]">
              <span className="text-tp-text-2">{t('ncPvCommandedFeedMmMin')}</span>
              <span className="text-tp-text font-mono">{vs.nc_commanded_feed_mm_min.toFixed(1)}</span>
            </div>
          )}
          {vs.nc_commanded_feed_mm_rev != null && (
            <div className="flex justify-between text-[11px]">
              <span className="text-tp-text-2">{t('ncPvCommandedFeedMmRev')}</span>
              <span className="text-tp-text font-mono">{vs.nc_commanded_feed_mm_rev.toFixed(4)}</span>
            </div>
          )}
          {vs.nc_commanded_spindle_rpm != null && (
            <div className="flex justify-between text-[11px]">
              <span className="text-tp-text-2">{t('ncPvCommandedRpm')}</span>
              <span className="text-tp-text font-mono">{vs.nc_commanded_spindle_rpm.toFixed(0)}</span>
            </div>
          )}
          {vs.nc_spindle_state && (
            <div className="flex justify-between text-[11px]">
              <span className="text-tp-text-2">{t('ncPvSpindleState')}</span>
              <span className="text-tp-text font-mono">{vs.nc_spindle_state}</span>
            </div>
          )}
          <div className="text-[9px] text-tp-text-3 italic pt-0.5">{t('ncPvNcCommandedNotActual')}</div>
        </div>
      )}

      {/* RPM limit checks */}
      {hasLimitChecks && (
        <div className="space-y-1.5">
          <PvFindingRow finding={vs.machine_rpm_limit_check} label={t('ncPvRpmLimitMachine')} t={t} />
          <PvFindingRow finding={vs.tool_rpm_limit_check} label={t('ncPvRpmLimitTool')} t={t} />
          <PvFindingRow finding={vs.holder_rpm_limit_check} label={t('ncPvRpmLimitHolder')} t={t} />
          <PvFindingRow finding={vs.effective_rpm_limit_check} label={t('ncPvRpmLimitEffective')} t={t} />
        </div>
      )}

      {/* Calculated engineering values */}
      {hasCalc && (
        <div className="space-y-1 p-2 bg-tp-surface-2 rounded border border-tp-border/40">
          {vs.calculated_cutting_speed_m_min != null && (
            <div className="flex justify-between text-[11px]">
              <span className="text-tp-text-2">{t('ncPvCalcVc')}</span>
              <span className="text-tp-text font-mono">{vs.calculated_cutting_speed_m_min.toFixed(1)} m/min</span>
            </div>
          )}
          {vs.calculated_feed_per_tooth_mm != null && (
            <div className="flex justify-between text-[11px]">
              <span className="text-tp-text-2">{t('ncPvCalcFz')}</span>
              <span className="text-tp-text font-mono">{vs.calculated_feed_per_tooth_mm.toFixed(4)} mm/tooth</span>
            </div>
          )}
          {vs.calculated_feed_per_rev_mm != null && (
            <div className="flex justify-between text-[11px]">
              <span className="text-tp-text-2">{t('ncPvCalcFeedRev')}</span>
              <span className="text-tp-text font-mono">{vs.calculated_feed_per_rev_mm.toFixed(4)} mm/rev</span>
            </div>
          )}
        </div>
      )}

      {/* Reference range checks */}
      {hasRefChecks && (
        <div className="space-y-1.5">
          <PvFindingRow finding={vs.cutting_speed_check} label={t('ncPvCalcVc')} t={t} />
          <PvFindingRow finding={vs.feed_per_tooth_check} label={t('ncPvCalcFz')} t={t} />
          <PvFindingRow finding={vs.feed_per_rev_check} label={t('ncPvCalcFeedRev')} t={t} />
          <div className="text-[9px] text-tp-text-3 italic">{t('ncPvReferenceAdvisoryNote')}</div>
        </div>
      )}
    </div>
  )
}

// ── NC Engineering Review section ────────────────────────────────────────────

const ER_STATUS_CLS: Record<EngReviewStatusValue, string> = {
  PASS_WITH_EVIDENCE: 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30',
  PASS_WITH_ADVISORIES: 'bg-sky-500/15 text-sky-300 border border-sky-500/30',
  REVIEW_REQUIRED: 'bg-amber-500/15 text-amber-300 border border-amber-500/30',
  BLOCKED_BY_KNOWN_LIMIT: 'bg-red-500/15 text-red-300 border border-red-500/30',
  INSUFFICIENT_DATA: 'bg-tp-surface-2 text-tp-text-3 border border-tp-border',
  UNSUPPORTED_FEATURES_PRESENT: 'bg-orange-500/15 text-orange-300 border border-orange-500/30',
}

const ER_STATE_CLS: Record<ParserFeatureStateValue, string> = {
  SUPPORTED: 'text-emerald-400',
  BOUNDED: 'text-amber-400',
  DEFERRED: 'text-orange-400',
  UNSUPPORTED: 'text-red-400',
  INSUFFICIENT_SEMANTICS: 'text-tp-text-3',
}

function NcEngineeringReviewSection({
  er,
  t,
}: {
  er: NCProgramEngineeringReview
  t: TFunc
}) {
  const statusLabel: Record<EngReviewStatusValue, string> = {
    PASS_WITH_EVIDENCE: t('ncErStatusPassWithEvidence'),
    PASS_WITH_ADVISORIES: t('ncErStatusPassWithAdvisories'),
    REVIEW_REQUIRED: t('ncErStatusReviewRequired'),
    BLOCKED_BY_KNOWN_LIMIT: t('ncErStatusBlockedByKnownLimit'),
    INSUFFICIENT_DATA: t('ncErStatusInsufficientData'),
    UNSUPPORTED_FEATURES_PRESENT: t('ncErStatusUnsupportedFeaturesPresent'),
  }
  const stateLabel: Record<ParserFeatureStateValue, string> = {
    SUPPORTED: t('ncErStateSupported'),
    BOUNDED: t('ncErStateBounded'),
    DEFERRED: t('ncErStateDeferred'),
    UNSUPPORTED: t('ncErStateUnsupported'),
    INSUFFICIENT_SEMANTICS: t('ncErStateInsufficientSemantics'),
  }

  return (
    <div className="mt-3 pt-3 border-t border-tp-border/40 space-y-3">
      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap">
        <SectionLabel text={t('ncEngineeringReview')} />
        <Badge label={statusLabel[er.review_status]} cls={ER_STATUS_CLS[er.review_status]} />
      </div>

      {/* Executive Summary */}
      <div className="p-2 bg-tp-surface-2 rounded border border-tp-border/40 space-y-1">
        <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light mb-1">
          {t('ncErExecutiveSummary')}
        </div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-[11px]">
          <span className="text-tp-text-3">{t('ncErSegments')}</span>
          <span className="text-tp-text font-mono">{er.segment_count}</span>
          <span className="text-tp-text-3">{t('ncErToolChanges')}</span>
          <span className="text-tp-text font-mono">{er.tool_change_count}</span>
          <span className="text-tp-text-3">{t('ncErSupportedMotions')}</span>
          <span className="text-tp-text font-mono">{er.supported_motion_count}</span>
          {er.unsupported_construct_count > 0 && (
            <>
              <span className="text-amber-400">{t('ncErUnsupportedConstructs')}</span>
              <span className="text-amber-300 font-mono">{er.unsupported_construct_count}</span>
            </>
          )}
          {er.blocking_count > 0 && (
            <>
              <span className="text-red-400">{t('ncErBlockingCount')}</span>
              <span className="text-red-300 font-mono">{er.blocking_count}</span>
            </>
          )}
          {er.warning_count > 0 && (
            <>
              <span className="text-amber-400">{t('ncErWarningCount')}</span>
              <span className="text-amber-300 font-mono">{er.warning_count}</span>
            </>
          )}
          {er.advisory_count > 0 && (
            <>
              <span className="text-sky-400">{t('ncErAdvisoryCount')}</span>
              <span className="text-sky-300 font-mono">{er.advisory_count}</span>
            </>
          )}
          {er.unsupported_count > 0 && (
            <>
              <span className="text-orange-400">{t('ncErUnsupportedCount')}</span>
              <span className="text-orange-300 font-mono">{er.unsupported_count}</span>
            </>
          )}
        </div>
        {(er.total_feed_distance_mm > 0 || er.total_rapid_distance_mm > 0) && (
          <div className="border-t border-tp-border/20 pt-1 mt-1 grid grid-cols-2 gap-x-4 gap-y-0.5 text-[11px]">
            <span className="text-tp-text-3">{t('ncErTotalFeedDistance')}</span>
            <span className="text-tp-text font-mono">{er.total_feed_distance_mm.toFixed(3)}</span>
            <span className="text-tp-text-3">{t('ncErTotalRapidDistance')}</span>
            <span className="text-tp-text font-mono">{er.total_rapid_distance_mm.toFixed(3)}</span>
          </div>
        )}
        <div className="text-[9px] text-tp-text-3 italic pt-0.5">{t('ncErProgrammedFeedNote')}</div>
      </div>

      {/* Program Coverage */}
      <div className="border border-tp-border/40 rounded overflow-hidden">
        <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light px-2 py-1 bg-tp-surface-2">
          {t('ncErProgramCoverage')}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-[10px] border-collapse">
            <tbody>
              {er.feature_coverage.filter(f =>
                f.state !== 'SUPPORTED' || f.detected
              ).map(f => (
                <tr key={f.feature} className="border-t border-tp-border/20">
                  <td className="pr-3 py-0.5 pl-2 text-tp-text-2">{f.feature}</td>
                  <td className={`pr-3 py-0.5 font-semibold ${ER_STATE_CLS[f.state]}`}>
                    {stateLabel[f.state]}
                  </td>
                  <td className="pr-2 py-0.5 text-tp-text-3 italic text-[9px]">
                    {f.detected ? t('ncErDetected') : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Configuration */}
      {(er.equipment.machine_id || er.equipment.cutting_tool_id || er.equipment.tool_holder_id) && (
        <div className="p-2 bg-tp-surface-2 rounded border border-tp-border/40 space-y-1">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light mb-1">
            {t('ncErMachineConfig')}
          </div>
          <div className="text-[11px] space-y-0.5">
            {er.equipment.machine_display && (
              <div className="flex justify-between">
                <span className="text-tp-text-3">{t('ncErMachineConfig')}</span>
                <span className="text-tp-text">{er.equipment.machine_display}</span>
              </div>
            )}
            {er.equipment.cutting_tool_display && (
              <div className="flex justify-between">
                <span className="text-tp-text-3">{t('ncErToolConfig')}</span>
                <span className="text-tp-text">{er.equipment.cutting_tool_display}</span>
              </div>
            )}
            {er.equipment.tool_holder_display && (
              <div className="flex justify-between">
                <span className="text-tp-text-3">{t('ncErHolderConfig')}</span>
                <span className="text-tp-text">{er.equipment.tool_holder_display}</span>
              </div>
            )}
            {er.equipment.effective_rpm_limit != null && (
              <div className="flex justify-between">
                <span className="text-tp-text-3">{t('ncErEffectiveRpmLimit')}</span>
                <span className="text-tp-text font-mono">{er.equipment.effective_rpm_limit} rpm
                  {er.equipment.effective_rpm_limit_source && (
                    <span className="ml-1 text-tp-text-3 text-[9px]">
                      ({er.equipment.effective_rpm_limit_source})
                    </span>
                  )}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Cycle Time Evidence */}
      {er.cycle_time_known_subtotal_sec != null && (
        <div className="p-2 bg-tp-surface-2 rounded border border-tp-border/40 text-[11px]">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light mb-1">
            {t('ncErCycleTimeEvidence')}
          </div>
          <div className="flex justify-between">
            <span className="text-tp-text-3">{t('ncErCycleTimeSubtotalLabel')}</span>
            <span className="text-tp-text font-mono">
              {er.cycle_time_known_subtotal_sec.toFixed(1)} s
              <span className="ml-2 text-tp-text-3 text-[9px]">≠ Total</span>
            </span>
          </div>
        </div>
      )}

      {/* Canned Cycle Notes */}
      {er.canned_cycle_notes.length > 0 && (
        <div className="p-2 bg-tp-surface-2 rounded border border-tp-border/40">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light mb-1">
            {t('ncErCannedCycleReview')}
          </div>
          {er.canned_cycle_notes.map(note => (
            <div key={note.cycle_code_str} className="flex items-center gap-2 text-[11px] py-0.5">
              <span className="font-mono text-tp-text">{note.cycle_code_str}</span>
              <span className={`font-semibold ${ER_STATE_CLS[note.state]}`}>
                {stateLabel[note.state]}
              </span>
              {note.bounded_reason && (
                <span className="text-tp-text-3 italic text-[9px]">{note.bounded_reason}</span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Findings */}
      {er.findings.length > 0 ? (
        <div className="space-y-1">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light">
            {t('ncErFindings')}
          </div>
          {er.findings.map(f => (
            <div
              key={f.finding_code}
              className={`flex items-start gap-2 px-2 py-1 rounded border text-[11px] ${PV_SEVERITY_CLS[f.severity] ?? 'border-tp-border text-tp-text-3'}`}
            >
              <span className="font-semibold whitespace-nowrap">{t(f.title_key as keyof TranslationDictionary)}</span>
              {f.observed_value != null && (
                <span className="font-mono">{f.observed_value.toFixed(1)} {f.unit ?? ''}</span>
              )}
              {f.limit_value != null && (
                <span className="text-[10px] opacity-70">/ {f.limit_value.toFixed(0)}</span>
              )}
              {f.source && (
                <span className="text-[9px] opacity-60 ml-auto">{f.source}</span>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="text-[11px] text-tp-text-3 italic">{t('ncErNoFindings')}</div>
      )}

      {/* Limitations */}
      {er.limitations.length > 0 && (
        <div className="space-y-0.5">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light">
            {t('ncErLimitations')}
          </div>
          {er.limitations.map((lim, i) => (
            <div key={i} className="text-[10px] text-tp-text-3 italic">{lim}</div>
          ))}
        </div>
      )}

      {/* Safety disclaimer */}
      <div className="text-[9px] text-tp-text-3 italic border-t border-tp-border/20 pt-1">
        NC_FILE_EXECUTED=NO · COLLISION_CHECK_PERFORMED=NO · FALSE_PRODUCTION_APPROVAL_CLAIM=NO
      </div>
    </div>
  )
}

// ── Cycle-time section ────────────────────────────────────────────────────────

const CT_STATUS_CLS: Record<CycleTimeStatus, string> = {
  COMPLETE: 'text-emerald-300',
  PARTIAL: 'text-amber-300',
  INSUFFICIENT_DATA: 'text-tp-text-3',
  NOT_APPLICABLE: 'text-tp-text-3',
}

const TC_STATUS_CLS: Record<TimeComponentStatus, string> = {
  AVAILABLE: 'text-emerald-300',
  NOT_AVAILABLE: 'text-tp-text-3',
  INSUFFICIENT_DATA: 'text-amber-300',
  NOT_APPLICABLE: 'text-tp-text-3',
}

function fmtSec(v: number | null): string {
  if (v === null) return '—'
  return `${v.toFixed(1)} s`
}

function fmtSecRange(min: number | null, max: number | null): string {
  if (min === null || max === null) return '—'
  if (Math.abs(max - min) < 0.001) return `${min.toFixed(1)} s`
  return `${min.toFixed(1)}–${max.toFixed(1)} s`
}

function CycleTimeSection({ ct, t }: { ct: StepCycleTime; t: TFunc }) {
  const [open, setOpen] = useState(false)

  const statusLabel: Record<CycleTimeStatus, string> = {
    COMPLETE: t('ppCycleTimeComplete'),
    PARTIAL: t('ppCycleTimePartial'),
    INSUFFICIENT_DATA: t('ppCycleTimeInsuffData'),
    NOT_APPLICABLE: t('ppMetricNotAvailable'),
  }

  const scopeLabel: Record<string, string> = {
    CUTTING_ONLY: t('ppCuttingOnly'),
    CUTTING_PLUS_EXPLICIT_NONCUTTING: t('ppExplicitInputsOnly'),
    COMPLETE_EXPLICIT_CYCLE: t('ppExplicitInputsOnly'),
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-2 mb-2 group"
      >
        <SectionLabel text={t('ppTimeAnalysis')} />
        <span className={`text-[11px] ${CT_STATUS_CLS[ct.status]}`}>
          {statusLabel[ct.status]}
        </span>
        <span className="text-[10px] text-tp-text-3 group-hover:text-tp-text transition-colors">
          {open ? '▲' : '▼'}
        </span>
      </button>

      {open && (
        <div className="space-y-3 text-xs">
          {/* Scope */}
          <div className="flex gap-6 text-tp-text-3 flex-wrap">
            <span>{t('ppCycleTime')} · {scopeLabel[ct.scope] ?? ct.scope}</span>
          </div>

          {/* Cutting time */}
          {ct.cutting_time && (
            <div>
              <span className="text-tp-text-2 font-medium">{t('ppCalculatedCuttingTime')}</span>
              <span className={`ml-2 ${TC_STATUS_CLS[ct.cutting_time.status]}`}>
                {ct.cutting_time.status === 'AVAILABLE'
                  ? fmtSecRange(ct.cutting_time.time_sec_min, ct.cutting_time.time_sec_max)
                  : t('ppCycleTimeInsuffData')}
              </span>
              {ct.cutting_time.distance_mm !== null && (
                <span className="ml-2 text-tp-text-3">L={ct.cutting_time.distance_mm} mm</span>
              )}
            </div>
          )}

          {/* Rapid time */}
          {ct.rapid_time && (
            <div>
              <span className="text-tp-text-2 font-medium">{t('ppRapidTime')}</span>
              <span className={`ml-2 ${TC_STATUS_CLS[ct.rapid_time.status]}`}>
                {ct.rapid_time.status === 'AVAILABLE'
                  ? fmtSec(ct.rapid_time.time_sec_min)
                  : t('ppRapidDataUnavailable')}
              </span>
            </div>
          )}

          {/* Dwell time */}
          {ct.dwell_time && (
            <div>
              <span className="text-tp-text-2 font-medium">{t('ppDwellTime')}</span>
              <span className="ml-2 text-emerald-300">
                {fmtSec(ct.dwell_time.time_sec_min)}
              </span>
            </div>
          )}

          {/* Known subtotal */}
          {ct.known_subtotal_sec_min !== null && (
            <div className="border-t border-tp-border/40 pt-2">
              <span className="text-tp-text-2 font-semibold">{t('ppKnownSubtotal')}</span>
              <span className="ml-2 text-emerald-300">
                {fmtSecRange(ct.known_subtotal_sec_min, ct.known_subtotal_sec_max)}
              </span>
              <span className="ml-2 text-tp-text-3 text-[10px]">≠ {t('ppTotalCycleTime')}</span>
            </div>
          )}

          {/* Missing inputs */}
          {ct.missing_inputs.length > 0 && (
            <div className="space-y-1">
              <span className="text-amber-400">{t('ppMetricMissingInput')}:</span>
              {ct.missing_inputs.map((m, i) => (
                <div key={i} className="text-[11px] text-amber-300 font-mono ml-2">{m}</div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Engineering Metrics section ───────────────────────────────────────────────

const METRIC_STATUS_CLS: Record<MetricStatus, string> = {
  AVAILABLE: 'text-emerald-300',
  NOT_AVAILABLE: 'text-tp-text-3',
  INSUFFICIENT_DATA: 'text-amber-300',
  NOT_APPLICABLE: 'text-tp-text-3',
}

function MetricStatusBadge({ status, t }: { status: MetricStatus; t: TFunc }) {
  const label: Record<MetricStatus, string> = {
    AVAILABLE: t('ppMetricAvailable'),
    NOT_AVAILABLE: t('ppMetricNotAvailable'),
    INSUFFICIENT_DATA: t('ppMetricInsufficientData'),
    NOT_APPLICABLE: t('ppMetricNotAvailable'),
  }
  return (
    <span className={`text-[10px] font-medium uppercase tracking-wide ${METRIC_STATUS_CLS[status]}`}>
      {label[status]}
    </span>
  )
}

function MetricRow({ metric, t }: { metric: EngineeringMetric; t: TFunc }) {
  const [open, setOpen] = useState(false)

  const valueDisplay = (() => {
    if (metric.status !== 'AVAILABLE') return null
    if (metric.value !== null) {
      return `${metric.value} ${metric.unit ?? ''}`
    }
    if (metric.min_value !== null && metric.max_value !== null) {
      return `${metric.min_value} – ${metric.max_value} ${metric.unit ?? ''}`
    }
    return null
  })()

  return (
    <div className="border border-tp-border/40 rounded bg-tp-surface/30">
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-tp-surface-2/40 transition-colors rounded"
      >
        <span className="text-xs text-tp-text font-medium">{metric.metric_name}</span>
        <div className="flex items-center gap-2 shrink-0">
          {valueDisplay && (
            <span className="text-xs text-tp-text-2 font-mono">{valueDisplay}</span>
          )}
          <MetricStatusBadge status={metric.status} t={t} />
          <span className="text-[10px] text-tp-text-3 ml-1">{open ? '▲' : '▼'}</span>
        </div>
      </button>

      {open && (
        <div className="px-3 pb-3 space-y-1.5 text-[11px]">
          {metric.explanation && (
            <p className="text-tp-text-3 leading-relaxed">{metric.explanation}</p>
          )}
          {metric.formula_reference && (
            <div>
              <span className="text-tp-text-3">{t('ppReferenceFormula')}: </span>
              <code className="text-tp-accent-light font-mono">{metric.formula_reference}</code>
            </div>
          )}
          {metric.inputs_used.length > 0 && (
            <div>
              <span className="text-tp-text-3">{t('ppMetricInputsUsed')}: </span>
              <span className="text-tp-text-2">{metric.inputs_used.join(' · ')}</span>
            </div>
          )}
          {metric.missing_inputs.length > 0 && (
            <div>
              <span className="text-amber-400">{t('ppMetricMissingInput')}: </span>
              <span className="text-amber-300">{metric.missing_inputs.join(', ')}</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function EngineeringMetricsSection({
  metrics,
  t,
}: {
  metrics: StepEngineeringMetrics
  t: TFunc
}) {
  const [open, setOpen] = useState(false)
  const availCount = metrics.metrics_available_count

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-2 mb-2 group"
      >
        <SectionLabel text={t('ppEngineeringMetrics')} />
        <span className="text-[11px] text-tp-text-3">
          {availCount}/{metrics.metrics.length} {t('ppMetricAvailable').toLowerCase()}
        </span>
        <span className="text-[10px] text-tp-text-3 group-hover:text-tp-text transition-colors">
          {open ? '▲' : '▼'}
        </span>
      </button>
      {open && (
        <div className="space-y-1.5">
          {metrics.metrics.map(m => (
            <MetricRow key={m.metric_id} metric={m} t={t} />
          ))}
        </div>
      )}
    </div>
  )
}

// ── PlanStep result card ───────────────────────────────────────────────────────

function PlanStepCard({ step, t }: { step: PlanStep; t: TFunc }) {
  const [expanded, setExpanded] = useState(false)
  const [showCompat, setShowCompat] = useState(false)
  const [showSelection, setShowSelection] = useState(false)
  const [showCutParams, setShowCutParams] = useState(false)

  const statusCls = STEP_STATUS_COLORS[step.planning_status] ?? 'bg-tp-surface-2 text-tp-text-3 border border-tp-border'

  const statusLabel = {
    PLANNED: t('ppStepPlanned'),
    BLOCKED: t('ppStepBlocked'),
    INSUFFICIENT_DATA: t('ppStepInsufficientData'),
    NOT_SUPPORTED: t('ppStepNotSupported'),
  }[step.planning_status] ?? step.planning_status

  return (
    <div className="border border-tp-border rounded-lg overflow-hidden">
      {/* Header */}
      <button
        onClick={() => step.planning_status !== 'NOT_SUPPORTED' && setExpanded(v => !v)}
        className="w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-tp-surface-2/40 transition-colors"
      >
        <span className="text-sm font-mono text-tp-text-2 w-24 shrink-0">#{step.sequence_number}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-tp-text">{step.step_id}</span>
            <span className="text-xs font-mono text-tp-text-3">{step.operation}</span>
            <Badge label={statusLabel} cls={statusCls} />
            {step.engineering_tie && step.planning_status === 'PLANNED' && (
              <Badge label={t('ppEngineeringTie')} cls="bg-sky-500/15 text-sky-300 border border-sky-500/30" />
            )}
          </div>
          {step.sequence_warnings.length > 0 && (
            <div className="text-[11px] text-amber-400 mt-0.5">
              ⚠ {step.sequence_warnings.map(w => w.rule_id).join(', ')}
            </div>
          )}
        </div>
        {step.planning_status !== 'NOT_SUPPORTED' && (
          <span className="text-tp-text-3 text-xs shrink-0">{expanded ? '▲' : '▼'}</span>
        )}
      </button>

      {expanded && (
        <div className="border-t border-tp-border/60 px-4 py-4 space-y-4">

          {/* Counts */}
          <div className="flex gap-4 text-xs text-tp-text-3 flex-wrap">
            <span>{t('ppEvaluated')}: <span className="text-tp-text">{step.candidates_evaluated}</span></span>
            <span>{t('ppCompatible')}: <span className="text-emerald-300">{step.compatible_count}</span></span>
            <span>{t('ppIncompatible')}: <span className="text-red-400">{step.incompatible_count}</span></span>
            <span>{t('ppInsufficient')}: <span className="text-amber-300">{step.not_rankable_count}</span></span>
          </div>

          {/* Engineering tie description */}
          {step.engineering_tie && (
            <div className="text-xs text-sky-300 bg-sky-500/10 border border-sky-500/20 rounded px-3 py-2">
              {t('ppEngineeringTieDesc')}
            </div>
          )}

          {/* Sequence warnings */}
          {step.sequence_warnings.length > 0 && (
            <div>
              <SectionLabel text={t('ppSequenceWarnings')} />
              {step.sequence_warnings.map((w, i) => (
                <div key={i} className="text-xs bg-amber-500/10 border border-amber-500/20 rounded px-3 py-2 mb-1">
                  <span className="font-mono text-amber-300 mr-2">{w.rule_id}</span>
                  <span className="text-tp-text-2">{w.explanation}</span>
                </div>
              ))}
            </div>
          )}

          {/* Candidate configurations */}
          {step.candidate_configurations.length > 0 && (
            <div>
              <SectionLabel text={t('ppCandidateConfigs')} />
              <div className="space-y-1">
                {step.candidate_configurations.map((c, i) => (
                  <div key={i} className="text-xs bg-tp-surface border border-tp-border rounded px-3 py-2 flex items-center gap-2 flex-wrap">
                    <span className="text-tp-text-3 w-5 shrink-0">{c.rank != null ? `#${c.rank}` : '—'}</span>
                    <span className="font-mono text-tp-text-2">{c.machine_id}</span>
                    <span className="text-tp-text-3">/</span>
                    <span className="font-mono text-tp-text-2">{c.holder_id}</span>
                    <span className="text-tp-text-3">/</span>
                    <span className="font-mono text-tp-text-2">{c.cutting_tool_id}</span>
                    {c.engineering_tie && (
                      <Badge label={t('ppEngineeringTie')} cls="bg-sky-500/15 text-sky-300 border border-sky-500/30" />
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Cutting parameter references */}
          <div>
            <SectionLabel text={t('ppCuttingParams')} />
            {step.cutting_parameter_reference_available ? (
              <div className="text-xs text-emerald-300 mb-1">✓ {t('ppCuttingParamAvailable')}</div>
            ) : (
              <div className="text-xs text-tp-text-3 mb-1">{t('ppCuttingParamUnavailable')}</div>
            )}
            {step.cutting_parameter_references.length > 0 && (
              <button
                type="button"
                onClick={() => setShowCutParams(v => !v)}
                className="text-[11px] text-tp-accent-light hover:text-tp-text transition-colors"
              >
                {showCutParams ? '▲' : '▼'} {step.cutting_parameter_references.length} record(s)
              </button>
            )}
            {showCutParams && (
              <div className="mt-2 overflow-x-auto">
                <table className="w-full text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-tp-border text-tp-text-3 text-left">
                      <th className="pb-1 pr-3 font-medium">Type</th>
                      <th className="pb-1 pr-3 font-medium">Range</th>
                      <th className="pb-1 pr-3 font-medium">Unit</th>
                      <th className="pb-1 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {step.cutting_parameter_references.map((p, i) => (
                      <tr key={i} className="border-b border-tp-border/40 last:border-0">
                        <td className="py-1.5 pr-3 font-mono text-tp-text-2">{p.parameter_type}</td>
                        <td className="py-1.5 pr-3 text-tp-text">{p.min_value}–{p.max_value}</td>
                        <td className="py-1.5 pr-3 text-tp-text-3">{p.unit}</td>
                        <td className="py-1.5 text-tp-text-3">{p.evidence_status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Compatibility trace toggle */}
          {step.compatibility_trace.length > 0 && (
            <div>
              <button
                type="button"
                onClick={() => setShowCompat(v => !v)}
                className="text-[11px] text-tp-accent-light hover:text-tp-text transition-colors mb-1"
              >
                {showCompat ? '▲' : '▼'} {t('ppCompatibilityTrace')} ({step.compatibility_trace.length})
              </button>
              {showCompat && (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-tp-border text-tp-text-3 text-left">
                        <th className="pb-1 pr-3 font-medium">rule_id</th>
                        <th className="pb-1 pr-3 font-medium">status</th>
                        <th className="pb-1 pr-3 font-medium">reason_code</th>
                        <th className="pb-1 font-medium">detail</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(step.compatibility_trace as Array<{rule_id:string;status:string;reason_code:string;detail?:string}>).map((r, i) => {
                        const cls = {
                          PASS: 'text-emerald-300',
                          FAIL: 'text-red-400',
                          UNKNOWN: 'text-amber-300',
                          NOT_APPLICABLE: 'text-tp-text-3',
                        }[r.status] ?? 'text-tp-text-3'
                        return (
                          <tr key={i} className="border-b border-tp-border/40 last:border-0">
                            <td className="py-1.5 pr-3 font-mono text-tp-text-2 whitespace-nowrap">{r.rule_id}</td>
                            <td className={`py-1.5 pr-3 font-semibold text-[10px] uppercase ${cls}`}>{r.status}</td>
                            <td className="py-1.5 pr-3 font-mono text-tp-text-3">{r.reason_code}</td>
                            <td className="py-1.5 text-tp-text-3">{r.detail ?? '—'}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Selection criteria trace toggle */}
          {step.selection_criteria_trace.length > 0 && (
            <div>
              <button
                type="button"
                onClick={() => setShowSelection(v => !v)}
                className="text-[11px] text-tp-accent-light hover:text-tp-text transition-colors mb-1"
              >
                {showSelection ? '▲' : '▼'} {t('ppSelectionTrace')} ({step.selection_criteria_trace.length})
              </button>
              {showSelection && (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-tp-border text-tp-text-3 text-left">
                        <th className="pb-1 pr-3 font-medium">criterion_id</th>
                        <th className="pb-1 pr-3 font-medium">applicable</th>
                        <th className="pb-1 pr-3 font-medium">value</th>
                        <th className="pb-1 font-medium">note</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(step.selection_criteria_trace as Array<{criterion_id:string;applicable:boolean;value?:string|null;note:string}>).map((c, i) => (
                        <tr key={i} className="border-b border-tp-border/40 last:border-0">
                          <td className="py-1.5 pr-3 font-mono text-tp-text-2 whitespace-nowrap">{c.criterion_id}</td>
                          <td className={`py-1.5 pr-3 text-[10px] font-semibold uppercase ${c.applicable ? 'text-emerald-300' : 'text-tp-text-3'}`}>
                            {c.applicable ? 'YES' : 'N/A'}
                          </td>
                          <td className="py-1.5 pr-3 text-tp-text">{c.applicable ? (c.value ?? '—') : '—'}</td>
                          <td className="py-1.5 text-tp-text-3">{c.note}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Missing data */}
          {step.missing_data.length > 0 && (
            <div>
              <SectionLabel text={t('ppMissingData')} />
              <ul className="space-y-0.5">
                {step.missing_data.map((m, i) => (
                  <li key={i} className="text-xs text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded px-2 py-1">{m}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Engineering Metrics */}
          {step.engineering_metrics && step.planning_status === 'PLANNED' && (
            <EngineeringMetricsSection metrics={step.engineering_metrics} t={t} />
          )}

          {/* Time Analysis */}
          {step.cycle_time && (
            <CycleTimeSection ct={step.cycle_time} t={t} />
          )}

          {/* Planning notes */}
          {step.planning_notes && (
            <div className="text-xs text-tp-text-3 italic">{step.planning_notes}</div>
          )}

        </div>
      )}
    </div>
  )
}

// ── Plan result panel ─────────────────────────────────────────────────────────

function PlanResult({ result, t }: { result: ProcessPlanResponse; t: TFunc }) {
  const [showLimitations, setShowLimitations] = useState(false)

  const planStatusLabel: Record<string, string> = {
    PLAN_COMPLETE: t('ppStatusComplete'),
    PLAN_PARTIAL: t('ppStatusPartial'),
    PLAN_BLOCKED: t('ppStatusBlocked'),
    PLAN_INSUFFICIENT_DATA: t('ppStatusInsufficientData'),
  }

  const planStatusDesc: Record<string, string> = {
    PLAN_COMPLETE: t('ppStatusCompleteDesc'),
    PLAN_PARTIAL: t('ppStatusPartialDesc'),
    PLAN_BLOCKED: t('ppStatusBlockedDesc'),
    PLAN_INSUFFICIENT_DATA: t('ppStatusInsufficientDataDesc'),
  }

  const cls = PLAN_STATUS_COLORS[result.plan_status] ?? 'border-tp-border bg-tp-surface-2 text-tp-text'

  return (
    <div className="space-y-4">

      {/* Plan status banner */}
      <div className={`rounded-lg border p-4 ${cls}`}>
        <div className="text-sm font-bold tracking-wide">{planStatusLabel[result.plan_status] ?? result.plan_status}</div>
        <div className="text-xs mt-1 opacity-80">{planStatusDesc[result.plan_status] ?? ''}</div>
        <div className="text-xs mt-2 opacity-60">{result.part_name} · ISO {result.material_iso_group}</div>
      </div>

      {/* Dependency violations */}
      {!result.dependency_graph_valid && result.dependency_violations.length > 0 && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-3">
          <SectionLabel text={t('ppDependencyViolations')} />
          <ul className="space-y-0.5">
            {result.dependency_violations.map((v, i) => (
              <li key={i} className="text-xs text-red-300">{v}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Alternative sequence note */}
      {result.alternative_valid_sequence_supported && (
        <div className="text-xs text-sky-300 bg-sky-500/10 border border-sky-500/20 rounded px-3 py-2">
          {t('ppAlternativeSequence')}: {t('ppFlowVisualization')}
        </div>
      )}

      {/* Summary */}
      <div className="bg-tp-surface border border-tp-border rounded-lg p-4">
        <SectionLabel text={t('ppSummary')} />
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: t('ppStepPlanned'), val: result.summary.planned_count, cls: 'text-emerald-300' },
            { label: t('ppStepBlocked'), val: result.summary.blocked_count, cls: 'text-red-400' },
            { label: t('ppStepInsufficientData'), val: result.summary.insufficient_data_count, cls: 'text-amber-300' },
            { label: t('ppStepNotSupported'), val: result.summary.not_supported_count, cls: 'text-tp-text-3' },
          ].map(({ label, val, cls: c }) => (
            <div key={label} className="text-center">
              <div className={`text-2xl font-bold ${c}`}>{val}</div>
              <div className="text-[10px] text-tp-text-3 uppercase tracking-wide mt-0.5">{label}</div>
            </div>
          ))}
        </div>
        {result.summary.engineering_tie_count > 0 && (
          <div className="mt-3 text-xs text-sky-300 border-t border-tp-border pt-3">
            {result.summary.engineering_tie_count} step(s) have engineering ties.{' '}
            {t('ppEngineeringTieDesc')}
          </div>
        )}
      </div>

      {/* Steps */}
      <div className="space-y-2">
        {result.steps.map(step => (
          <PlanStepCard key={step.step_id} step={step} t={t} />
        ))}
      </div>

      {/* Limitations */}
      <div>
        <button
          type="button"
          onClick={() => setShowLimitations(v => !v)}
          className="text-[11px] text-tp-text-3 hover:text-tp-text-2 transition-colors"
        >
          {showLimitations ? '▲' : '▼'} {t('ppLimitations')} ({result.limitations.length})
        </button>
        {showLimitations && (
          <ul className="mt-2 space-y-1">
            {result.limitations.map((lim, i) => (
              <li key={i} className="text-[11px] text-tp-text-3 font-mono">{lim}</li>
            ))}
          </ul>
        )}
      </div>

      {/* Disclaimer */}
      <div className="text-[11px] text-tp-text-3 bg-tp-surface-2/50 border border-tp-border/50 rounded p-3 italic">
        {result.disclaimer}
      </div>

    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ProcessPlanningPage() {
  const { t } = useLocale()
  const [schema, setSchema] = useState<ProcessPlanningSchema | null>(null)
  const [schemaError, setSchemaError] = useState(false)

  const [partName, setPartName] = useState('')
  const [isoGroup, setIsoGroup] = useState('')
  const [steps, setSteps] = useState<StepForm[]>([newStep(1)])

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ProcessPlanResponse | null>(null)
  const [stale, setStale] = useState(false)

  // Load schema
  useEffect(() => {
    fetchProcessPlanningSchema()
      .then(s => setSchema(s))
      .catch(() => setSchemaError(true))
  }, [])

  // Mark result stale when inputs change
  const markStale = useCallback(() => {
    if (result) setStale(true)
  }, [result])

  const handleAddStep = () => {
    const maxSeq = steps.reduce((max, s) => Math.max(max, Number(s.sequence_number) || 0), 0)
    setSteps(prev => [...prev, newStep(Math.floor(maxSeq / 10) + 1 + prev.length)])
    markStale()
  }

  const handleChangeStep = (idx: number, updated: StepForm) => {
    setSteps(prev => prev.map((s, i) => (i === idx ? updated : s)))
    markStale()
  }

  const handleRemoveStep = (idx: number) => {
    setSteps(prev => prev.filter((_, i) => i !== idx))
    markStale()
  }

  const canSubmit = partName.trim() !== '' &&
    isoGroup !== '' &&
    steps.length > 0 &&
    steps.every(s => s.operation !== '' && s.step_id.trim() !== '' && s.sequence_number !== '')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    setLoading(true)
    setError(null)
    setStale(false)

    const ops: OperationStepRequest[] = steps.map(s => ({
      step_id: s.step_id.trim(),
      sequence_number: Number(s.sequence_number),
      operation: s.operation,
      machine_id: s.machine_id || null,
      cutting_tool_id: s.cutting_tool_id || null,
      predecessor_step_ids: s.predecessor_ids,
      cutting_path_length_mm: s.cutting_path_length_mm !== '' ? parseFloat(s.cutting_path_length_mm) : null,
      cutting_path_source: s.cutting_path_source !== ''
        ? s.cutting_path_source
        : (s.cutting_path_length_mm !== '' ? 'USER_INPUT' : null),
      rapid_distance_mm: s.rapid_distance_mm !== '' ? parseFloat(s.rapid_distance_mm) : null,
      dwell_sec: s.dwell_sec !== '' ? parseFloat(s.dwell_sec) : null,
    }))

    try {
      const res = await generateProcessPlan({ part_name: partName.trim(), material_iso_group: isoGroup, operations: ops })
      setResult(res)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t('ppPlanError')
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const isoOptions = schema?.valid_iso_groups.map(g => ({ value: g, label: g })) ?? []

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-bold text-tp-text">{t('ppTitle')}</h1>
        <p className="text-sm text-tp-text-3 mt-1 max-w-2xl">{t('ppSubtitle')}</p>
      </div>

      {/* Schema error */}
      {schemaError && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-sm text-red-300">
          {t('ppSchemaError')}
        </div>
      )}

      {/* Loading schema */}
      {!schema && !schemaError && (
        <div className="text-sm text-tp-text-3">{t('ppLoadingSchema')}</div>
      )}

      {schema && (
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Part name + ISO group */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <FieldLabel text={t('ppPartName')} />
              <input
                type="text"
                value={partName}
                onChange={e => { setPartName(e.target.value); markStale() }}
                placeholder={t('ppPartNamePlaceholder')}
                className="w-full bg-tp-surface border border-tp-border rounded px-3 py-2 text-sm text-tp-text focus:outline-none focus:border-tp-accent-light"
              />
            </div>
            <div>
              <FieldLabel text={t('ppMaterialGroup')} />
              <SelectField
                value={isoGroup}
                onChange={v => { setIsoGroup(v); markStale() }}
                options={isoOptions}
                placeholder="Select ISO group…"
              />
            </div>
          </div>

          {/* Operations */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <SectionLabel text={t('ppOperations')} />
              <button
                type="button"
                onClick={handleAddStep}
                className="text-xs text-tp-accent-light border border-tp-accent-light/40 hover:bg-tp-accent-light/10 rounded px-2 py-0.5 transition-colors"
              >
                + {t('ppAddOperation')}
              </button>
            </div>
            <div className="space-y-3">
              {steps.map((step, idx) => (
                <StepRow
                  key={step.id}
                  step={step}
                  index={idx}
                  allSteps={steps}
                  schema={schema}
                  onChange={updated => handleChangeStep(idx, updated)}
                  onRemove={() => handleRemoveStep(idx)}
                  t={t}
                />
              ))}
            </div>
          </div>

          {/* Submit */}
          <div className="flex items-center gap-4">
            <button
              type="submit"
              disabled={!canSubmit || loading}
              className="bg-tp-accent-light text-white font-semibold px-5 py-2.5 rounded-lg text-sm hover:bg-tp-accent-light/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? t('ppLoadingPlan') : t('ppGeneratePlan')}
            </button>
            {!canSubmit && !loading && (
              <span className="text-xs text-tp-text-3">{t('ppFillRequired')}</span>
            )}
            {stale && !loading && (
              <span className="text-xs text-amber-400">Inputs changed — regenerate plan.</span>
            )}
          </div>
        </form>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-sm text-red-300">
          {t('ppPlanError')}: {error}
        </div>
      )}

      {/* Result */}
      {result && !loading && (
        <div className={stale ? 'opacity-50 pointer-events-none select-none' : ''}>
          <PlanResult result={result} t={t} />
        </div>
      )}
    </div>
  )
}
