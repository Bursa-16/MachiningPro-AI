import { useEffect, useState } from 'react'
import { useLocale } from '../i18n/index'
import {
  queryCuttingParameters,
  getCuttingParameterSchema,
  calculateMachiningParameters,
  type QueryResponse,
  type SchemaResponse,
  type CalculateResponse,
} from '../services/cuttingParameters'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function Badge({ label, variant }: { label: string; variant: 'match' | 'nomatch' | 'ref' }) {
  const base = 'inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide'
  const styles: Record<string, string> = {
    match: `${base} bg-[var(--tp-valid-muted)] text-[var(--tp-valid)]`,
    nomatch: `${base} bg-[var(--tp-warn-muted)] text-[var(--tp-warn)]`,
    ref: `${base} bg-[var(--tp-surface-3)] text-[var(--tp-text-2)]`,
  }
  return <span className={styles[variant]}>{label}</span>
}

function FieldRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between items-baseline py-1.5 border-b border-[var(--tp-border)] last:border-0">
      <span className="text-xs text-[var(--tp-text-2)]">{label}</span>
      <span className="text-sm font-mono text-[var(--tp-text)] ml-4">{value}</span>
    </div>
  )
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--tp-text-3)] mb-2">
      {children}
    </div>
  )
}

const PARAM_ORDER = ['CUTTING_SPEED', 'FEED_PER_REV', 'FEED_PER_TOOTH', 'AXIAL_DEPTH_OF_CUT']

// ---------------------------------------------------------------------------
// Tool material display labels (short)
// ---------------------------------------------------------------------------
const TOOL_MATERIAL_LABELS: Record<string, string> = {
  carbide: 'Carbide',
  HSS: 'HSS',
  cermet: 'Cermet',
  ceramic: 'Ceramic',
  CBN: 'CBN',
  PCD: 'PCD',
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function CuttingParametersPage() {
  const { t } = useLocale()

  // Selector state
  const [operation, setOperation] = useState('turning')
  const [isoGroup, setIsoGroup] = useState('P')
  const [toolMaterial, setToolMaterial] = useState('')

  // Schema (loaded once)
  const [schema, setSchema] = useState<SchemaResponse | null>(null)

  // Query result
  const [result, setResult] = useState<QueryResponse | null>(null)
  const [queryLoading, setQueryLoading] = useState(false)
  const [queryError, setQueryError] = useState<string | null>(null)

  // Calculation state
  const [diameter, setDiameter] = useState('')
  const [selectedVc, setSelectedVc] = useState('')
  const [toothCount, setToothCount] = useState('')
  const [feedPerRev, setFeedPerRev] = useState('')
  const [calcResult, setCalcResult] = useState<CalculateResponse | null>(null)
  const [calcLoading, setCalcLoading] = useState(false)
  const [calcError, setCalcError] = useState<string | null>(null)

  // Load schema on mount
  useEffect(() => {
    getCuttingParameterSchema()
      .then(setSchema)
      .catch(() => { /* schema failure is non-fatal */ })
  }, [])

  // Reset calc results when query inputs change
  useEffect(() => {
    setResult(null)
    setQueryError(null)
    setCalcResult(null)
    setCalcError(null)
  }, [operation, isoGroup, toolMaterial])

  function handleQuery() {
    setQueryLoading(true)
    setQueryError(null)
    setResult(null)
    setCalcResult(null)
    queryCuttingParameters(operation, isoGroup, toolMaterial || undefined)
      .then(setResult)
      .catch((err: unknown) => {
        setQueryError(err instanceof Error ? err.message : 'Query failed')
      })
      .finally(() => setQueryLoading(false))
  }

  function handleCalculate() {
    const d = parseFloat(diameter)
    const vc = parseFloat(selectedVc)
    if (!d || !vc || d <= 0 || vc <= 0) return

    const req: Parameters<typeof calculateMachiningParameters>[0] = {
      vc_m_min: vc,
      diameter_mm: d,
      operation,
    }

    if (operation === 'milling' && toothCount && feedPerRev === '') {
      req.tooth_count = parseInt(toothCount, 10)
      // fz comes from the reference; user can enter it or skip
    }

    // For turning/drilling/reaming — feed per rev
    const fn = parseFloat(feedPerRev)
    if (operation !== 'milling' && fn > 0) {
      req.feed_per_rev_mm = fn
    }

    setCalcLoading(true)
    setCalcError(null)
    calculateMachiningParameters(req)
      .then(setCalcResult)
      .catch((err: unknown) => {
        setCalcError(err instanceof Error ? err.message : 'Calculation failed')
      })
      .finally(() => setCalcLoading(false))
  }

  // Resolve parameter display label
  function paramLabel(pt: string): string {
    const map: Record<string, string> = {
      CUTTING_SPEED: t('cpVcRange'),
      FEED_PER_REV: t('cpFeedRange'),
      FEED_PER_TOOTH: t('cpFzRange'),
      AXIAL_DEPTH_OF_CUT: t('cpApRange'),
    }
    return map[pt] ?? pt
  }

  // Sort parameters in canonical display order
  const sortedParams = result?.parameters.slice().sort(
    (a, b) => {
      const ai = PARAM_ORDER.indexOf(a.parameter_type)
      const bi = PARAM_ORDER.indexOf(b.parameter_type)
      return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi)
    }
  ) ?? []

  // Vc range for calc hint
  const vcRecord = result?.parameters.find(p => p.parameter_type === 'CUTTING_SPEED')

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-5xl mx-auto px-4 py-6">

        {/* Header */}
        <div className="mb-6">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--tp-accent-light)] mb-1">
            MachiningPro AI
          </div>
          <h1 className="text-xl font-semibold text-[var(--tp-text)]">{t('cpPageTitle')}</h1>
          <p className="text-sm text-[var(--tp-text-2)] mt-1">{t('cpPageSubtitle')}</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">

          {/* ---- LEFT COLUMN: Inputs ---- */}
          <div className="flex flex-col gap-4">

            {/* Selector panel */}
            <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4">
              <SectionLabel>{t('cpSelectOperation')}</SectionLabel>
              <div className="grid grid-cols-2 gap-2 mb-4">
                {(['turning', 'milling', 'drilling', 'reaming'] as const).map(op => {
                  const labels: Record<string, string> = {
                    turning: t('cpOperationTurning'),
                    milling: t('cpOperationMilling'),
                    drilling: t('cpOperationDrilling'),
                    reaming: t('cpOperationReaming'),
                  }
                  return (
                    <button
                      key={op}
                      onClick={() => setOperation(op)}
                      className={[
                        'py-2 px-3 rounded text-sm font-medium transition-colors',
                        operation === op
                          ? 'bg-[var(--tp-accent)] text-white'
                          : 'bg-[var(--tp-surface-2)] text-[var(--tp-text-2)] hover:text-[var(--tp-text)]',
                      ].join(' ')}
                    >
                      {labels[op]}
                    </button>
                  )
                })}
              </div>

              <SectionLabel>{t('cpSelectIsoGroup')}</SectionLabel>
              <div className="grid grid-cols-3 gap-2 mb-4">
                {(['P', 'M', 'K', 'N', 'S', 'H'] as const).map(g => {
                  const labels: Record<string, string> = {
                    P: t('cpIsoP'), M: t('cpIsoM'), K: t('cpIsoK'),
                    N: t('cpIsoN'), S: t('cpIsoS'), H: t('cpIsoH'),
                  }
                  return (
                    <button
                      key={g}
                      onClick={() => setIsoGroup(g)}
                      title={labels[g]}
                      className={[
                        'py-2 px-2 rounded text-sm font-mono font-semibold transition-colors',
                        isoGroup === g
                          ? 'bg-[var(--tp-accent)] text-white'
                          : 'bg-[var(--tp-surface-2)] text-[var(--tp-text-2)] hover:text-[var(--tp-text)]',
                      ].join(' ')}
                    >
                      {g}
                    </button>
                  )
                })}
              </div>
              {/* ISO description */}
              {schema && (
                <p className="text-xs text-[var(--tp-text-3)] mb-4">
                  {schema.iso_material_labels[isoGroup] ?? isoGroup}
                </p>
              )}

              <SectionLabel>{t('cpSelectToolMaterial')}</SectionLabel>
              <select
                value={toolMaterial}
                onChange={e => setToolMaterial(e.target.value)}
                className="w-full bg-[var(--tp-surface-2)] border border-[var(--tp-border)] rounded px-3 py-2 text-sm text-[var(--tp-text)] focus:outline-none focus:border-[var(--tp-accent)]"
              >
                <option value="">{t('cpAnyToolMaterial')}</option>
                {(schema?.tool_materials ?? ['carbide', 'HSS', 'cermet', 'ceramic', 'CBN', 'PCD']).map(tm => (
                  <option key={tm} value={tm}>{TOOL_MATERIAL_LABELS[tm] ?? tm}</option>
                ))}
              </select>

              <button
                onClick={handleQuery}
                disabled={queryLoading}
                className="mt-4 w-full py-2.5 rounded bg-[var(--tp-accent)] hover:opacity-90 disabled:opacity-50 text-white text-sm font-medium transition-opacity"
              >
                {queryLoading ? '…' : t('cpQueryButton')}
              </button>

              {queryError && (
                <p className="mt-2 text-xs text-[var(--tp-error)]">{queryError}</p>
              )}
            </div>

            {/* Calculation panel */}
            {result?.matched && (
              <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4">
                <SectionLabel>{t('cpCalcTitle')}</SectionLabel>

                {vcRecord && (
                  <p className="text-xs text-[var(--tp-text-3)] mb-3">
                    {t('cpCalcEnterVc')}: {vcRecord.min_value}–{vcRecord.max_value} {t('cpUnitMmin')}
                  </p>
                )}

                <div className="flex flex-col gap-2 mb-3">
                  <label className="text-xs text-[var(--tp-text-2)]">{t('cpSelectedVc')} ({t('cpUnitMmin')})</label>
                  <input
                    type="number"
                    value={selectedVc}
                    onChange={e => setSelectedVc(e.target.value)}
                    placeholder={vcRecord ? `${vcRecord.min_value}–${vcRecord.max_value}` : '150'}
                    className="bg-[var(--tp-surface-2)] border border-[var(--tp-border)] rounded px-3 py-2 text-sm text-[var(--tp-text)] focus:outline-none focus:border-[var(--tp-accent)]"
                  />
                </div>

                <div className="flex flex-col gap-2 mb-3">
                  <label className="text-xs text-[var(--tp-text-2)]">{t('cpDiameterMm')}</label>
                  <input
                    type="number"
                    value={diameter}
                    onChange={e => setDiameter(e.target.value)}
                    placeholder="20"
                    className="bg-[var(--tp-surface-2)] border border-[var(--tp-border)] rounded px-3 py-2 text-sm text-[var(--tp-text)] focus:outline-none focus:border-[var(--tp-accent)]"
                  />
                </div>

                {operation !== 'milling' && (
                  <div className="flex flex-col gap-2 mb-3">
                    <label className="text-xs text-[var(--tp-text-2)]">{t('cpFeedRange')} ({t('cpUnitMmRev')})</label>
                    <input
                      type="number"
                      value={feedPerRev}
                      onChange={e => setFeedPerRev(e.target.value)}
                      placeholder="0.20"
                      className="bg-[var(--tp-surface-2)] border border-[var(--tp-border)] rounded px-3 py-2 text-sm text-[var(--tp-text)] focus:outline-none focus:border-[var(--tp-accent)]"
                    />
                  </div>
                )}

                {operation === 'milling' && (
                  <div className="flex flex-col gap-2 mb-3">
                    <label className="text-xs text-[var(--tp-text-2)]">{t('cpToothCount')}</label>
                    <input
                      type="number"
                      value={toothCount}
                      onChange={e => setToothCount(e.target.value)}
                      placeholder="4"
                      className="bg-[var(--tp-surface-2)] border border-[var(--tp-border)] rounded px-3 py-2 text-sm text-[var(--tp-text)] focus:outline-none focus:border-[var(--tp-accent)]"
                    />
                  </div>
                )}

                <button
                  onClick={handleCalculate}
                  disabled={calcLoading || !diameter || !selectedVc}
                  className="w-full py-2 rounded bg-[var(--tp-surface-3)] hover:bg-[var(--tp-surface-2)] disabled:opacity-40 text-[var(--tp-text)] text-sm font-medium transition-colors"
                >
                  {calcLoading ? '…' : t('cpRpmResult')}
                </button>

                {calcError && (
                  <p className="mt-2 text-xs text-[var(--tp-error)]">{calcError}</p>
                )}

                {calcResult && (
                  <div className="mt-3 bg-[var(--tp-surface-2)] rounded p-3">
                    <FieldRow label={t('cpRpmResult')} value={`${calcResult.rpm.toLocaleString()} ${t('cpUnitRpm')}`} />
                    <FieldRow label={t('cpRpmFormula')} value={calcResult.rpm_formula} />
                    {calcResult.feed_rate_mm_min !== null && calcResult.feed_rate_mm_min !== undefined && (
                      <>
                        <FieldRow label={t('cpFeedRateResult')} value={`${calcResult.feed_rate_mm_min.toFixed(1)} ${t('cpUnitMmMin')}`} />
                        {calcResult.feed_rate_formula && (
                          <FieldRow label={t('cpFeedFormula')} value={calcResult.feed_rate_formula} />
                        )}
                      </>
                    )}
                    <p className="mt-2 text-[10px] text-[var(--tp-text-3)]">{t('cpMachineLimitNote')}</p>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* ---- RIGHT COLUMN: Results ---- */}
          <div className="flex flex-col gap-4">

            {/* No query yet */}
            {!result && !queryLoading && !queryError && (
              <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-5 text-center">
                <p className="text-sm text-[var(--tp-text-3)]">
                  Select operation, material group, and click <em>Query Reference Library</em>.
                </p>
              </div>
            )}

            {/* Loading */}
            {queryLoading && (
              <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-5 text-center">
                <p className="text-sm text-[var(--tp-text-3)]">Querying reference library…</p>
              </div>
            )}

            {/* No match */}
            {result && !result.matched && (
              <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Badge label={t('cpMatchNoMatch')} variant="nomatch" />
                </div>
                <p className="text-sm text-[var(--tp-text-2)]">{t('cpNoMatchHint')}</p>
              </div>
            )}

            {/* Matched result */}
            {result?.matched && (
              <>
                {/* Match status */}
                <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4">
                  <div className="flex flex-wrap items-center gap-2 mb-3">
                    <Badge label={t('cpMatchIsoGroup')} variant="match" />
                    <Badge label={t('cpEvidenceReferenceOnly').split('—')[0].trim()} variant="ref" />
                  </div>
                  <div className="text-xs text-[var(--tp-text-3)]">
                    {result.match_reason}
                  </div>
                </div>

                {/* Parameters */}
                <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4">
                  <SectionLabel>Parameters</SectionLabel>
                  {sortedParams.length === 0 ? (
                    <p className="text-sm text-[var(--tp-text-3)]">{t('cpMissingParam')}</p>
                  ) : (
                    <div>
                      {sortedParams.map(p => (
                        <FieldRow
                          key={p.parameter_type}
                          label={paramLabel(p.parameter_type)}
                          value={`${p.min_value} – ${p.max_value} ${p.unit}`}
                        />
                      ))}
                    </div>
                  )}
                </div>

                {/* Provenance & authority */}
                <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4">
                  <SectionLabel>{t('cpSource')}</SectionLabel>
                  <div className="space-y-1 text-sm">
                    <FieldRow
                      label={t('cpAuthorityLabel')}
                      value={result.authority_label}
                    />
                    {result.provenance?.source_reference && (
                      <FieldRow
                        label={t('cpSource')}
                        value={result.provenance.source_reference}
                      />
                    )}
                    {result.provenance?.page_section && (
                      <FieldRow
                        label={t('cpScopeLabel')}
                        value={result.provenance.page_section}
                      />
                    )}
                    <FieldRow
                      label={t('cpAuthorityLabel')}
                      value={result.evidence_status}
                    />
                  </div>
                  <div className="mt-3 bg-[var(--tp-warn-muted)] rounded px-3 py-2">
                    <p className="text-xs text-[var(--tp-warn)]">{t('cpLimitation')}: {result.limitation_note}</p>
                  </div>
                </div>

                {/* Reference guidance */}
                <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4">
                  <SectionLabel>{t('cpEvidenceReferenceOnly')}</SectionLabel>
                  <p className="text-xs text-[var(--tp-text-3)]">{t('cpReferenceGuidanceNote')}</p>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
