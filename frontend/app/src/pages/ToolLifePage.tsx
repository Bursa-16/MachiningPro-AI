import { useState, useEffect, useCallback } from 'react'
import { AlertTriangle, Database, FlaskConical, XCircle, ChevronDown } from 'lucide-react'
import { useLocale } from '../i18n'
import { toolLifeService } from '../services/toolLife'
import type { ToolLifeSummary, ToolSummary, ToolDetail } from '../services/toolLife'

// ── SVG chart helpers ────────────────────────────────────────────────────────

const CHART_W = 560
const CHART_H = 180
const PAD = { top: 14, right: 16, bottom: 36, left: 44 }
const INNER_W = CHART_W - PAD.left - PAD.right
const INNER_H = CHART_H - PAD.top - PAD.bottom

function scaleX(idx: number, total: number): number {
  if (total <= 1) return PAD.left
  return PAD.left + (idx / (total - 1)) * INNER_W
}

function scaleY(val: number, min: number, max: number): number {
  if (max === min) return PAD.top + INNER_H / 2
  return PAD.top + INNER_H - ((val - min) / (max - min)) * INNER_H
}

interface ChartProps {
  values: number[]
  yLabel: string
  color: string
  eolIndices?: number[]
  xLabel?: string
}

function LineChart({ values, yLabel, color, eolIndices = [], xLabel }: ChartProps) {
  if (values.length === 0) return null
  const min = Math.min(...values)
  const max = Math.max(...values)
  const n = values.length

  const points = values
    .map((v, i) => `${scaleX(i, n)},${scaleY(v, min, max)}`)
    .join(' ')

  const yTicks = [min, (min + max) / 2, max]
  const xTicks = n <= 1 ? [0] : [0, Math.floor((n - 1) / 2), n - 1]

  return (
    <svg
      width="100%"
      viewBox={`0 0 ${CHART_W} ${CHART_H}`}
      aria-label={yLabel}
      style={{ display: 'block', maxWidth: '100%', overflow: 'visible' }}
    >
      {/* Grid lines */}
      {yTicks.map((tick) => (
        <line
          key={tick}
          x1={PAD.left}
          y1={scaleY(tick, min, max)}
          x2={PAD.left + INNER_W}
          y2={scaleY(tick, min, max)}
          stroke="currentColor"
          strokeOpacity={0.08}
          strokeWidth={1}
        />
      ))}

      {/* Y-axis labels */}
      {yTicks.map((tick, i) => (
        <text
          key={i}
          x={PAD.left - 6}
          y={scaleY(tick, min, max) + 4}
          fontSize={9}
          fill="currentColor"
          fillOpacity={0.45}
          textAnchor="end"
        >
          {typeof tick === 'number' ? tick.toFixed(max - min < 1 ? 2 : 0) : tick}
        </text>
      ))}

      {/* X-axis labels */}
      {xTicks.map((idx) => (
        <text
          key={idx}
          x={scaleX(idx, n)}
          y={CHART_H - PAD.bottom + 14}
          fontSize={9}
          fill="currentColor"
          fillOpacity={0.45}
          textAnchor="middle"
        >
          {idx}
        </text>
      ))}

      {/* X-axis label */}
      {xLabel && (
        <text
          x={PAD.left + INNER_W / 2}
          y={CHART_H - 2}
          fontSize={9}
          fill="currentColor"
          fillOpacity={0.35}
          textAnchor="middle"
        >
          {xLabel}
        </text>
      )}

      {/* EOL markers */}
      {eolIndices.map((idx) => (
        <rect
          key={idx}
          x={scaleX(idx, n) - 1}
          y={PAD.top}
          width={2}
          height={INNER_H}
          fill="#ef4444"
          fillOpacity={0.6}
        />
      ))}

      {/* Data line */}
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />

      {/* EOL dots */}
      {eolIndices.map((idx) => (
        <circle
          key={`dot-${idx}`}
          cx={scaleX(idx, n)}
          cy={scaleY(values[idx], min, max)}
          r={3}
          fill="#ef4444"
        />
      ))}
    </svg>
  )
}

// ── Summary cards ────────────────────────────────────────────────────────────

interface SummaryCardProps {
  label: string
  value: string | number
  sub?: string
}

function SummaryCard({ label, value, sub }: SummaryCardProps) {
  return (
    <div className="bg-tp-surface border border-tp-border rounded-lg px-4 py-3 flex flex-col gap-0.5 min-w-0">
      <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-text-3 truncate">{label}</div>
      <div className="text-xl font-semibold text-tp-text tabular-nums">{value}</div>
      {sub && <div className="text-[10px] text-tp-text-3">{sub}</div>}
    </div>
  )
}

// ── Status badge ─────────────────────────────────────────────────────────────

function StatusBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div className={`flex items-center gap-1.5 px-2 py-1 rounded text-[11px] font-medium border
      ${ok
        ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
        : 'bg-amber-500/10 border-amber-500/20 text-amber-400'
      }`}>
      <span className={`w-1.5 h-1.5 rounded-full ${ok ? 'bg-emerald-400' : 'bg-amber-400'}`} />
      {label}
    </div>
  )
}

// ── Main Page ────────────────────────────────────────────────────────────────

export default function ToolLifePage() {
  const { t } = useLocale()

  // Translated limitation bullets — derived from i18n, not from raw API strings.
  const translatedLimitations = [
    t('tlLimVb'),
    t('tlLimTaylor'),
    t('tlLimCtf'),
    t('tlLimLeakage'),
    t('tlLimPrediction'),
    t('tlLimHardness'),
    t('tlLimProduction'),
  ]

  const [summary, setSummary] = useState<ToolLifeSummary | null>(null)
  const [tools, setTools] = useState<ToolSummary[]>([])
  const [selectedToolId, setSelectedToolId] = useState<number | null>(null)
  const [selectedFeatureIdx, setSelectedFeatureIdx] = useState<number>(0)
  const [toolDetail, setToolDetail] = useState<ToolDetail | null>(null)
  const [loadingTools, setLoadingTools] = useState(false)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [limitationsOpen, setLimitationsOpen] = useState(false)

  // Load summary + tools
  useEffect(() => {
    let cancelled = false
    setLoadingTools(true)
    setError(null)
    toolLifeService.getSummary().then((s) => {
      if (cancelled) return
      setSummary(s)
      if (!s.seeded) {
        setLoadingTools(false)
        return
      }
      return toolLifeService.getTools()
    }).then((tl) => {
      if (cancelled || !tl) return
      setTools(tl)
      if (tl.length > 0) setSelectedToolId(tl[0].tool_id)
    }).catch((err) => {
      if (!cancelled) setError(err?.message ?? 'Failed to load tool data')
    }).finally(() => {
      if (!cancelled) setLoadingTools(false)
    })
    return () => { cancelled = true }
  }, [])

  // Load tool detail when selection changes
  const loadDetail = useCallback((toolId: number, featureIdx: number) => {
    setLoadingDetail(true)
    setDetailError(null)
    setToolDetail(null)
    toolLifeService.getToolDetail(toolId, featureIdx).then((d) => {
      setToolDetail(d)
    }).catch((err) => {
      setDetailError(err?.message ?? 'Failed to load tool detail')
    }).finally(() => {
      setLoadingDetail(false)
    })
  }, [])

  useEffect(() => {
    if (selectedToolId !== null) {
      loadDetail(selectedToolId, selectedFeatureIdx)
    }
  }, [selectedToolId, selectedFeatureIdx, loadDetail])

  // Feature selector options
  const featureHeaders = summary?.sensor_feature_headers ?? []

  // EOL indices
  const eolIndices = toolDetail?.lifecycle
    .filter((p) => p.is_eol)
    .map((p) => p.obs_idx) ?? []

  const lifecycleValues = toolDetail?.lifecycle.map((p) => p.cycle_to_failure_normalized) ?? []
  const sensorValues = toolDetail?.sensor_series.values ?? []

  return (
    <div className="h-full overflow-y-auto p-4 sm:p-6">
      <div className="max-w-4xl space-y-5">

        {/* Header */}
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light mb-1">
            MachiningPro AI
          </div>
          <h1 className="text-xl font-semibold text-tp-text">{t('tlPageTitle')}</h1>
          <p className="text-xs text-tp-text-3 mt-0.5">{t('tlPageSubtitle')}</p>
        </div>

        {/* Model Readiness Panel */}
        <div className="bg-tp-surface border border-tp-border rounded-lg p-4 space-y-2">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-text-3 mb-2">
            {t('validationQualificationStatus')}
          </div>
          <div className="flex flex-wrap gap-2">
            <StatusBadge ok={summary?.seeded ?? false} label={t('tlDatasetAvailable')} />
            <StatusBadge ok={summary?.seeded ?? false} label={t('tlEmpiricalExploration')} />
            <StatusBadge ok={false} label={t('tlProductionNotValidated')} />
          </div>
          {summary && (
            <div className="text-[10px] text-tp-text-3 mt-1 flex flex-wrap gap-3">
              <span>
                <span className="text-tp-text-2 font-medium">{t('tlEvidenceStatus')}:</span>{' '}
                {summary.evidence_status}
              </span>
              {summary.source_doi && (
                <span>
                  <span className="text-tp-text-2 font-medium">{t('tlSourceDoi')}:</span>{' '}
                  {summary.source_doi}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-lg p-3 text-xs text-red-400">
            <XCircle size={14} className="shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {/* Dataset not configured */}
        {!loadingTools && summary && !summary.seeded && !error && (
          <div className="bg-tp-surface border border-tp-border rounded-lg p-5 space-y-2">
            <div className="flex items-center gap-2 text-tp-text-2">
              <Database size={16} />
              <span className="font-medium text-sm">{t('tlDatasetNotConfigured')}</span>
            </div>
            <p className="text-xs text-tp-text-3">{t('tlDatasetNotConfiguredDetail')}</p>
            {translatedLimitations.length > 0 && (
              <div className="pt-2 border-t border-tp-border space-y-1">
                <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-text-3">
                  {t('tlLimitations')}
                </div>
                <ul className="space-y-1">
                  {translatedLimitations.map((lim, i) => (
                    <li key={i} className="text-xs text-tp-text-3 flex items-start gap-1.5">
                      <span className="text-tp-accent-light shrink-0 mt-0.5">·</span>
                      {lim}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* Loading */}
        {loadingTools && (
          <div className="text-xs text-tp-text-3 flex items-center gap-2 py-4">
            <FlaskConical size={13} className="animate-pulse" />
            {t('tlLoadingTools')}
          </div>
        )}

        {/* Summary cards */}
        {summary?.seeded && !loadingTools && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <SummaryCard label={t('tlObservations')} value={summary.observation_count} />
            <SummaryCard label={t('tlTools')} value={summary.tool_count} />
            <SummaryCard label={t('tlSensorFeatures')} value={summary.sensor_feature_count} />
            <SummaryCard label={t('tlEolObservations')} value={summary.eol_observation_count} />
          </div>
        )}

        {/* Tool selector + feature selector */}
        {summary?.seeded && tools.length > 0 && (
          <div className="flex flex-wrap gap-3 items-end">
            {/* Tool selector */}
            <div className="flex flex-col gap-1 min-w-0">
              <label className="text-[10px] font-semibold uppercase tracking-widest text-tp-text-3">
                {t('tlSelectTool')}
              </label>
              <div className="relative">
                <select
                  value={selectedToolId ?? ''}
                  onChange={(e) => {
                    setSelectedToolId(Number(e.target.value))
                  }}
                  className="appearance-none bg-tp-surface border border-tp-border rounded px-3 py-1.5
                             text-sm text-tp-text pr-8 focus:outline-none focus:border-tp-accent
                             min-w-[160px]"
                >
                  {tools.map((tool) => (
                    <option key={tool.tool_id} value={tool.tool_id}>
                      {t('tlToolLabel')} {tool.tool_id} — Type {tool.tool_type}
                      {' '}({tool.observation_count} obs)
                    </option>
                  ))}
                </select>
                <ChevronDown size={12} className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-tp-text-3" />
              </div>
            </div>

            {/* Feature selector */}
            {featureHeaders.length > 0 && (
              <div className="flex flex-col gap-1 min-w-0">
                <label className="text-[10px] font-semibold uppercase tracking-widest text-tp-text-3">
                  {t('tlSelectSensorFeature')}
                </label>
                <div className="relative">
                  <select
                    value={selectedFeatureIdx}
                    onChange={(e) => setSelectedFeatureIdx(Number(e.target.value))}
                    className="appearance-none bg-tp-surface border border-tp-border rounded px-3 py-1.5
                               text-sm text-tp-text pr-8 focus:outline-none focus:border-tp-accent
                               min-w-[200px] max-w-[280px]"
                  >
                    {featureHeaders.map((name, idx) => (
                      <option key={idx} value={idx}>
                        {idx}: {name}
                      </option>
                    ))}
                  </select>
                  <ChevronDown size={12} className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-tp-text-3" />
                </div>
              </div>
            )}
          </div>
        )}

        {/* Detail loading */}
        {loadingDetail && (
          <div className="text-xs text-tp-text-3 flex items-center gap-2 py-2">
            <FlaskConical size={13} className="animate-pulse" />
            {t('tlLoadingDetail')}
          </div>
        )}

        {/* Detail error */}
        {detailError && (
          <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-lg p-3 text-xs text-red-400">
            <XCircle size={14} className="shrink-0 mt-0.5" />
            <span>{detailError}</span>
          </div>
        )}

        {/* Tool detail panel */}
        {toolDetail && !loadingDetail && (
          <div className="bg-tp-surface border border-tp-border rounded-lg p-4 space-y-4">

            {/* Tool properties */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-2 text-xs">
              <div>
                <span className="text-tp-text-3">{t('tlToolType')}: </span>
                <span className="text-tp-text font-medium">{toolDetail.tool_type}</span>
              </div>
              <div>
                <span className="text-tp-text-3">{t('tlTotalCycles')}: </span>
                <span className="text-tp-text font-medium tabular-nums">{toolDetail.total_cycles}</span>
              </div>
              <div>
                <span className="text-tp-text-3">{t('tlAdocMm')}: </span>
                <span className="text-tp-text font-medium tabular-nums">{toolDetail.adoc_mm.toFixed(2)}</span>
              </div>
              <div>
                <span className="text-tp-text-3">{t('tlRdocMm')}: </span>
                <span className="text-tp-text font-medium tabular-nums">{toolDetail.rdoc_mm.toFixed(2)}</span>
              </div>
              <div>
                <span className="text-tp-text-3">{t('tlHolderLengthMm')}: </span>
                <span className="text-tp-text font-medium tabular-nums">{toolDetail.tool_holder_length_mm.toFixed(1)}</span>
              </div>
              <div>
                <span className="text-tp-text-3">{t('tlHardnessMean')}: </span>
                <span className="text-tp-text font-medium tabular-nums">{toolDetail.hardness_mean.toFixed(2)}</span>
              </div>
              <div>
                <span className="text-tp-text-3">{t('tlEolPresent')}: </span>
                <span className={`font-medium ${toolDetail.eol_present ? 'text-red-400' : 'text-tp-text'}`}>
                  {toolDetail.eol_present ? t('tlEolYes') : t('tlEolNo')}
                </span>
              </div>
            </div>

            {/* CycleToFailure semantics note */}
            <div className="text-[10px] text-tp-text-3 border-t border-tp-border pt-3">
              <span className="font-semibold text-tp-text-2">{t('tlCycleToFailureLabel')}: </span>
              {t('tlCycleToFailureSemantics')}
            </div>

            {/* Lifecycle chart */}
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-text-3 mb-2">
                {t('tlLifecycleChart')}
              </div>
              <div className="bg-tp-surface-2 rounded border border-tp-border text-tp-text-2 p-2 overflow-x-auto">
                <LineChart
                  values={lifecycleValues}
                  yLabel={t('tlNormalized')}
                  color="#60a5fa"
                  eolIndices={eolIndices}
                  xLabel={t('tlObsIndex')}
                />
              </div>
              <div className="flex items-center gap-3 mt-1.5 text-[10px] text-tp-text-3">
                <span className="flex items-center gap-1">
                  <span className="inline-block w-3 h-0.5 bg-blue-400 rounded" />
                  {t('tlNormalized')}
                </span>
                {eolIndices.length > 0 && (
                  <span className="flex items-center gap-1">
                    <span className="inline-block w-2 h-2 rounded-full bg-red-500" />
                    {t('tlEolMarker')}
                  </span>
                )}
              </div>
            </div>

            {/* Sensor chart */}
            {sensorValues.length > 0 && (
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-text-3 mb-1">
                  {t('tlSensorChart')}
                </div>
                <div className="text-[10px] text-tp-text-3 mb-2">
                  [{t('tlFeatureIndex')} {toolDetail.sensor_series.feature_index}] {toolDetail.sensor_series.feature_name}
                </div>
                <div className="bg-tp-surface-2 rounded border border-tp-border text-tp-text-2 p-2 overflow-x-auto">
                  <LineChart
                    values={sensorValues}
                    yLabel={toolDetail.sensor_series.feature_name}
                    color="#a78bfa"
                    eolIndices={eolIndices}
                    xLabel={t('tlObsIndex')}
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* Leakage warning */}
        {summary?.seeded && (
          <div className="flex items-start gap-2.5 bg-amber-500/10 border border-amber-500/20 rounded-lg p-3">
            <AlertTriangle size={14} className="shrink-0 mt-0.5 text-amber-400" />
            <div className="space-y-0.5 text-xs">
              <div className="font-semibold text-amber-300">{t('tlLeakageWarning')}</div>
              <div className="text-amber-200/70">{t('tlLeakageWarningDetail')}</div>
            </div>
          </div>
        )}

        {/* Limitations collapsible */}
        {summary && translatedLimitations.length > 0 && (
          <div className="bg-tp-surface border border-tp-border rounded-lg overflow-hidden">
            <button
              onClick={() => setLimitationsOpen((o) => !o)}
              className="w-full flex items-center justify-between px-4 py-3 text-xs text-tp-text-2 hover:bg-tp-surface-2 transition-colors"
            >
              <span className="font-semibold text-[10px] uppercase tracking-widest text-tp-text-3">
                {t('tlLimitations')}
              </span>
              <ChevronDown
                size={13}
                className={`text-tp-text-3 transition-transform ${limitationsOpen ? 'rotate-180' : ''}`}
              />
            </button>
            {limitationsOpen && (
              <div className="px-4 pb-4 pt-1 border-t border-tp-border space-y-1.5">
                {translatedLimitations.map((lim, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs text-tp-text-3">
                    <span className="text-tp-accent-light shrink-0 mt-0.5">·</span>
                    {lim}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Source provenance */}
        {summary?.source_doi && (
          <div className="text-[10px] text-tp-text-3 flex flex-wrap gap-4 pt-1 pb-2">
            <span className="font-semibold uppercase tracking-widest text-tp-text-3">{t('tlSourceProvenance')}</span>
            <span>
              <span className="text-tp-text-2">{t('tlSourceDoi')}: </span>
              {summary.source_doi}
            </span>
            {summary.source_sheet && (
              <span>
                <span className="text-tp-text-2">{t('tlSourceSheet')}: </span>
                {summary.source_sheet}
              </span>
            )}
          </div>
        )}

      </div>
    </div>
  )
}
