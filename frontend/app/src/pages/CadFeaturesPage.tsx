import { useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLocale } from '../i18n/index'
import { PipelineBreadcrumb } from '../components/PipelineBreadcrumb'
import {
  analyzeCad,
  getCadFeatures,
  getCadPatterns,
  getFusionStatus,
  confirmFeature,
  rejectFeature,
  type ManufacturingFeatureOut,
  type PatternOut,
  type FusionStatusResponse,
  type FeaturesResponse,
} from '../services/cadFeatures'
import { usePipeline } from '../context/PipelineContext'

// ---------------------------------------------------------------------------
// Small UI helpers
// ---------------------------------------------------------------------------

function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4 ${className}`}>
      {children}
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

function Badge({ label, color = 'gray' }: { label: string; color?: 'gray' | 'green' | 'yellow' | 'blue' | 'red' }) {
  const map: Record<string, string> = {
    gray: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300',
    green: 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300',
    yellow: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300',
    blue: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300',
    red: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300',
  }
  return (
    <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold ${map[color]}`}>
      {label}
    </span>
  )
}

function ConfidenceBadge({ confidence }: { confidence: string }) {
  const high = ['EXACT_BREP', 'TOPOLOGY_RULE', 'GEOMETRY_RULE']
  const mid = ['PATTERN_RECOGNIZED', 'INFERRED']
  const color = high.includes(confidence) ? 'green' : mid.includes(confidence) ? 'yellow' : 'red'
  return <Badge label={confidence.replace(/_/g, ' ')} color={color} />
}

function FeatureTypeBadge({ type }: { type: string }) {
  const holeTypes = ['THROUGH_HOLE', 'BLIND_HOLE', 'COUNTERBORE', 'COUNTERSINK', 'STEPPED_HOLE', 'HOLE']
  const turningTypes = ['OUTER_DIAMETER', 'GROOVE', 'BOSS']
  const millingTypes = ['CLOSED_POCKET', 'OPEN_SLOT']
  const finishTypes = ['CHAMFER', 'FILLET', 'PLANAR_FACE']
  if (holeTypes.includes(type)) return <Badge label={type.replace(/_/g, ' ')} color="blue" />
  if (turningTypes.includes(type)) return <Badge label={type.replace(/_/g, ' ')} color="green" />
  if (millingTypes.includes(type)) return <Badge label={type.replace(/_/g, ' ')} color="yellow" />
  if (finishTypes.includes(type)) return <Badge label={type.replace(/_/g, ' ')} color="gray" />
  return <Badge label={type.replace(/_/g, ' ')} color="gray" />
}

function DimValue({ label, value, unit = 'mm' }: { label: string; value: number | null; unit?: string }) {
  if (value == null) return null
  return (
    <span className="text-xs text-[var(--tp-text-2)]">
      <span className="text-[var(--tp-text-3)]">{label}:</span>{' '}
      <span className="font-mono font-medium text-[var(--tp-text)]">{value.toFixed(3)}</span>{' '}
      <span className="text-[var(--tp-text-3)]">{unit}</span>
    </span>
  )
}

// ---------------------------------------------------------------------------
// Feature tree panel
// ---------------------------------------------------------------------------

interface FeatureTreePanelProps {
  features: ManufacturingFeatureOut[]
  patterns: PatternOut[]
  onConfirm: (featureId: string) => void
  onReject: (featureId: string) => void
  busy: boolean
  t: (key: string) => string
}

function FeatureTreePanel({ features, patterns, onConfirm, onReject, busy, t }: FeatureTreePanelProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const toggle = (id: string) =>
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  const patternFeatureIds = new Set(patterns.flatMap(p => p.feature_ids))

  return (
    <div className="space-y-1">
      {features.length === 0 && (
        <div className="text-sm text-[var(--tp-text-3)] text-center py-6">{t('cfNoFeatures')}</div>
      )}
      {features.map(feat => {
        const isOpen = expanded.has(feat.feature_id)
        const inPattern = patternFeatureIds.has(feat.feature_id)
        return (
          <div key={feat.feature_id} className="border border-[var(--tp-border)] rounded-md overflow-hidden">
            <button
              className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-[var(--tp-surface-hover)] transition-colors"
              onClick={() => toggle(feat.feature_id)}
            >
              <span className="text-[var(--tp-text-3)] text-xs select-none">{isOpen ? '▼' : '▶'}</span>
              <FeatureTypeBadge type={feat.feature_type} />
              {inPattern && <Badge label={t('cfPattern')} color="blue" />}
              <span className="ml-auto">
                <ConfidenceBadge confidence={feat.confidence} />
              </span>
            </button>
            {isOpen && (
              <div className="px-4 py-2 border-t border-[var(--tp-border)] bg-[var(--tp-bg)] space-y-2">
                <div className="text-[10px] font-mono text-[var(--tp-text-3)] truncate">{feat.feature_id}</div>
                <div className="flex flex-wrap gap-3">
                  <DimValue label="Ø" value={feat.diameter_mm} />
                  <DimValue label="R" value={feat.radius_mm} />
                  <DimValue label={t('cfDepth')} value={feat.depth_mm} />
                </div>
                {feat.axis_count && (
                  <div className="text-xs text-[var(--tp-text-2)]">
                    <span className="text-[var(--tp-text-3)]">{t('cfAxis')}:</span> {feat.axis_count.replace(/_/g, ' ')}
                  </div>
                )}
                <div className="text-xs text-[var(--tp-text-2)]">
                  <span className="text-[var(--tp-text-3)]">{t('cfMethod')}:</span> {feat.method}
                </div>
                {feat.warnings?.length > 0 && (
                  <div className="text-xs text-yellow-700 dark:text-yellow-400">
                    {feat.warnings.join(' · ')}
                  </div>
                )}
                <div className="flex gap-2 pt-1">
                  <button
                    className="text-[11px] px-2 py-0.5 rounded border border-green-500 text-green-600 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/20 disabled:opacity-40"
                    disabled={busy}
                    onClick={() => onConfirm(feat.feature_id)}
                  >
                    {t('cfConfirm')}
                  </button>
                  <button
                    className="text-[11px] px-2 py-0.5 rounded border border-red-400 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 disabled:opacity-40"
                    disabled={busy}
                    onClick={() => onReject(feat.feature_id)}
                  >
                    {t('cfReject')}
                  </button>
                </div>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ---------------------------------------------------------------------------
// 3D viewer stub
// ---------------------------------------------------------------------------

function ViewerStub({ faceCount, bodyCount, t }: { faceCount: number; bodyCount: number; t: (k: string) => string }) {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[200px] border-2 border-dashed border-[var(--tp-border)] rounded-lg text-center p-6 gap-3">
      <div className="text-4xl text-[var(--tp-text-3)]">⬡</div>
      <div className="text-sm font-medium text-[var(--tp-text-2)]">{t('cfViewerStubTitle')}</div>
      <div className="text-xs text-[var(--tp-text-3)]">{t('cfViewerStubDesc')}</div>
      <div className="flex gap-4 text-xs text-[var(--tp-text-2)] mt-2">
        <span><span className="text-[var(--tp-text-3)]">{t('cfFaceCount')}:</span> <strong>{faceCount}</strong></span>
        <span><span className="text-[var(--tp-text-3)]">{t('cfBodyCount')}:</span> <strong>{bodyCount}</strong></span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Fusion status panel
// ---------------------------------------------------------------------------

function FusionPanel({ fusion, t }: { fusion: FusionStatusResponse; t: (k: string) => string }) {
  if (!fusion.fusion_available) {
    return (
      <div className="text-sm text-[var(--tp-text-3)] py-2">{fusion.message}</div>
    )
  }
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div>
          <span className="text-[var(--tp-text-3)]">{t('cfCompleteness')}:</span>{' '}
          <Badge
            label={fusion.completeness ?? '—'}
            color={fusion.completeness === 'FULL' ? 'green' : fusion.completeness === 'PARTIAL' ? 'yellow' : 'gray'}
          />
        </div>
        <div>
          <span className="text-[var(--tp-text-3)]">{t('cfUnresolved')}:</span>{' '}
          <strong>{fusion.unresolved_count ?? 0}</strong>
        </div>
        <div>
          <span className="text-[var(--tp-text-3)]">{t('cfAutoMatched')}:</span>{' '}
          <strong>{fusion.auto_matched_count ?? 0}</strong>
        </div>
        <div>
          <span className="text-[var(--tp-text-3)]">{t('cfCadOnly')}:</span>{' '}
          <strong>{fusion.cad_only_count ?? 0}</strong>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function CadFeaturesPage() {
  const { t } = useLocale()
  const navigate = useNavigate()
  const { drawingParserSessionId, setCadSessionId } = usePipeline()
  const fileRef = useRef<HTMLInputElement>(null)

  const [sessionId, setSessionId] = useState<string | null>(null)
  const [faceCount, setFaceCount] = useState(0)
  const [bodyCount, setBodyCount] = useState(0)
  const [featureCount, setFeatureCount] = useState(0)
  const [featuresData, setFeaturesData] = useState<FeaturesResponse | null>(null)
  const [patterns, setPatterns] = useState<PatternOut[]>([])
  const [fusion, setFusion] = useState<FusionStatusResponse | null>(null)
  const [warnings, setWarnings] = useState<string[]>([])
  const [uploading, setUploading] = useState(false)
  const [actionBusy, setActionBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'features' | 'patterns' | 'fusion'>('features')

  const reset = () => {
    setSessionId(null)
    setFaceCount(0)
    setBodyCount(0)
    setFeatureCount(0)
    setFeaturesData(null)
    setPatterns([])
    setFusion(null)
    setWarnings([])
    setError(null)
  }

  const loadSession = useCallback(async (sid: string) => {
    const [featsRes, patsRes, fusRes] = await Promise.all([
      getCadFeatures(sid),
      getCadPatterns(sid),
      getFusionStatus(sid),
    ])
    setFeaturesData(featsRes)
    setPatterns(patsRes.patterns)
    setFusion(fusRes)
  }, [])

  const handleFile = useCallback(async (file: File) => {
    reset()
    setUploading(true)
    setError(null)
    try {
      const ab = await file.arrayBuffer()
      const b64 = btoa(String.fromCharCode(...new Uint8Array(ab)))
      const res = await analyzeCad({
        file_name: file.name,
        content_b64: b64,
        source_id: `upload-${Date.now()}`,
      })
      setSessionId(res.session_id)
      setFaceCount(res.face_count)
      setBodyCount(res.body_count)
      setFeatureCount(res.feature_count)
      setWarnings(res.warnings ?? [])
      await loadSession(res.session_id)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setUploading(false)
    }
  }, [loadSession])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [handleFile])

  const handleConfirm = async (featureId: string) => {
    if (!sessionId) return
    setActionBusy(true)
    try {
      await confirmFeature(sessionId, featureId, 'engineer')
    } catch { /* ignore */ } finally {
      setActionBusy(false)
    }
  }

  const handleReject = async (featureId: string) => {
    if (!sessionId) return
    setActionBusy(true)
    try {
      await rejectFeature(sessionId, featureId)
    } catch { /* ignore */ } finally {
      setActionBusy(false)
    }
  }

  const features = featuresData?.features ?? []

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-6xl mx-auto space-y-4">

        {/* Pipeline navigation */}
        <PipelineBreadcrumb />

        {/* Header */}
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--tp-accent-light)] mb-1">
            {t('cfPreviewBadge')}
          </div>
          <h1 className="text-xl font-semibold text-[var(--tp-text)]">{t('cfPageTitle')}</h1>
          <p className="text-sm text-[var(--tp-text-2)] mt-1">{t('cfPageSubtitle')}</p>
        </div>

        {/* Pipeline requirements banner */}
        {drawingParserSessionId && (
          <div className="p-2 rounded bg-blue-100 dark:bg-blue-900 border border-blue-400 text-blue-800 dark:text-blue-200 text-xs">
            {t('pipeline_requirementsLoadedFrom')}: <span className="font-mono">{drawingParserSessionId}</span>
          </div>
        )}

        {/* Disclaimer */}
        <Card className="border-amber-300 dark:border-amber-700 bg-amber-50/60 dark:bg-amber-900/10">
          <div className="text-xs font-semibold text-amber-800 dark:text-amber-300 mb-1">{t('cfDisclaimerTitle')}</div>
          <div className="text-xs text-amber-700 dark:text-amber-400">{t('cfDisclaimerText')}</div>
        </Card>

        {/* Upload zone + session info */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Upload */}
          <Card className="lg:col-span-1">
            <SectionLabel>{t('cfUploadLabel')}</SectionLabel>
            <div
              className="border-2 border-dashed border-[var(--tp-border)] rounded-lg p-6 text-center cursor-pointer hover:border-[var(--tp-accent)] transition-colors"
              onDrop={handleDrop}
              onDragOver={e => e.preventDefault()}
              onClick={() => fileRef.current?.click()}
            >
              <div className="text-3xl text-[var(--tp-text-3)] mb-2">📂</div>
              <div className="text-sm text-[var(--tp-text-2)]">{t('cfDropHint')}</div>
              <div className="text-xs text-[var(--tp-text-3)] mt-1">{t('cfSupportedFormats')}</div>
            </div>
            <input
              ref={fileRef}
              type="file"
              accept=".dxf,.step,.stp,.igs,.iges"
              className="hidden"
              onChange={e => {
                const f = e.target.files?.[0]
                if (f) handleFile(f)
                e.target.value = ''
              }}
            />
            {uploading && (
              <div className="mt-3 text-sm text-[var(--tp-text-2)] text-center">{t('cfAnalyzing')}</div>
            )}
            {error && (
              <div className="mt-3 text-xs text-red-600 dark:text-red-400 p-2 bg-red-50 dark:bg-red-900/20 rounded">
                {error}
              </div>
            )}
          </Card>

          {/* Session summary */}
          <Card className="lg:col-span-2">
            <SectionLabel>{t('cfSessionLabel')}</SectionLabel>
            {!sessionId ? (
              <div className="text-sm text-[var(--tp-text-3)] py-4 text-center">{t('cfNoSession')}</div>
            ) : (
              <div className="space-y-3">
                <div className="font-mono text-xs text-[var(--tp-text-3)] truncate">{sessionId}</div>
                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-[var(--tp-bg)] rounded p-3 text-center">
                    <div className="text-2xl font-bold text-[var(--tp-text)]">{featureCount}</div>
                    <div className="text-[10px] text-[var(--tp-text-3)] uppercase tracking-wide mt-0.5">{t('cfFeatureCount')}</div>
                  </div>
                  <div className="bg-[var(--tp-bg)] rounded p-3 text-center">
                    <div className="text-2xl font-bold text-[var(--tp-text)]">{faceCount}</div>
                    <div className="text-[10px] text-[var(--tp-text-3)] uppercase tracking-wide mt-0.5">{t('cfFaceCount')}</div>
                  </div>
                  <div className="bg-[var(--tp-bg)] rounded p-3 text-center">
                    <div className="text-2xl font-bold text-[var(--tp-text)]">{bodyCount}</div>
                    <div className="text-[10px] text-[var(--tp-text-3)] uppercase tracking-wide mt-0.5">{t('cfBodyCount')}</div>
                  </div>
                </div>
                {warnings.length > 0 && (
                  <div className="text-xs text-yellow-700 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-900/20 rounded p-2 space-y-0.5">
                    {warnings.map((w, i) => <div key={i}>⚠ {w}</div>)}
                  </div>
                )}
                <button
                  className="text-xs text-[var(--tp-text-3)] hover:text-[var(--tp-text)] underline"
                  onClick={reset}
                >
                  {t('cfClearSession')}
                </button>
              </div>
            )}
          </Card>
        </div>

        {/* Main content — feature tree + viewer */}
        {sessionId && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Left: feature tree + tabs */}
            <Card>
              {/* Tabs */}
              <div className="flex gap-1 mb-3">
                {(['features', 'patterns', 'fusion'] as const).map(tab => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`text-[11px] px-2.5 py-1 rounded font-medium transition-colors ${
                      activeTab === tab
                        ? 'bg-[var(--tp-accent)] text-white'
                        : 'text-[var(--tp-text-2)] hover:bg-[var(--tp-surface-hover)]'
                    }`}
                  >
                    {tab === 'features' && `${t('cfTabFeatures')} (${features.length})`}
                    {tab === 'patterns' && `${t('cfTabPatterns')} (${patterns.length})`}
                    {tab === 'fusion' && t('cfTabFusion')}
                  </button>
                ))}
              </div>

              {activeTab === 'features' && (
                <FeatureTreePanel
                  features={features}
                  patterns={patterns}
                  onConfirm={handleConfirm}
                  onReject={handleReject}
                  busy={actionBusy}
                  t={t}
                />
              )}

              {activeTab === 'patterns' && (
                <div className="space-y-2">
                  {patterns.length === 0 && (
                    <div className="text-sm text-[var(--tp-text-3)] text-center py-6">{t('cfNoPatterns')}</div>
                  )}
                  {patterns.map(p => (
                    <div key={p.pattern_id} className="border border-[var(--tp-border)] rounded-md p-3">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge label={p.pattern_type.replace(/_/g, ' ')} color="blue" />
                        <span className="text-xs text-[var(--tp-text-2)]">{p.count}×</span>
                      </div>
                      <div className="text-xs text-[var(--tp-text-3)]">{p.description}</div>
                    </div>
                  ))}
                </div>
              )}

              {activeTab === 'fusion' && fusion && (
                <FusionPanel fusion={fusion} t={t} />
              )}
            </Card>

            {/* Right: 3D viewer stub */}
            <Card>
              <SectionLabel>{t('cfViewerLabel')}</SectionLabel>
              <ViewerStub faceCount={faceCount} bodyCount={bodyCount} t={t} />
            </Card>
          </div>
        )}

        {/* Pipeline handoff: Continue to Route Generation */}
        {sessionId && (
          <div className="flex items-center gap-3 pt-2 border-t border-[var(--tp-border)]">
            <button
              onClick={() => {
                setCadSessionId(sessionId)
                navigate('/app/planning-quality/process-routes')
              }}
              className="px-3 py-1.5 text-xs font-semibold rounded bg-green-600 text-white hover:bg-green-700 transition-colors"
            >
              {t('pipeline_continueToRouteGeneration')} →
            </button>
          </div>
        )}

      </div>
    </div>
  )
}
