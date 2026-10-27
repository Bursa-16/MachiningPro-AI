import { useState, useRef, useCallback } from 'react'
import { useLocale } from '../i18n/index'
import {
  analyzeDrawing,
  getDetections,
  confirmDetection,
  editDetection,
  rejectDetection,
  associateDetection,
  type DetectionOut,
  type DetectionsResponse,
  type AnalyzeResponse,
} from '../services/drawingParser'

// ---------------------------------------------------------------------------
// Small reusable UI helpers
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

function ConfidenceBadge({ confidence, method }: { confidence: number; method: string }) {
  const pct = Math.round(confidence * 100)
  let color = 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300'
  if (confidence < 0.85) color = 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300'
  if (confidence < 0.70) color = 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300'
  return (
    <span title={method} className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold ${color}`}>
      {pct}%
    </span>
  )
}

function ReviewBadge({ state }: { state: string }) {
  const colors: Record<string, string> = {
    PENDING: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300',
    CONFIRMED: 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300',
    EDITED: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300',
    REJECTED: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300',
  }
  return (
    <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold ${colors[state] ?? colors.PENDING}`}>
      {state}
    </span>
  )
}

function TypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    DIMENSION: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300',
    TOLERANCE: 'bg-teal-100 text-teal-800 dark:bg-teal-900/40 dark:text-teal-300',
    FIT: 'bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300',
    THREAD: 'bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300',
    SURFACE_FINISH: 'bg-pink-100 text-pink-800 dark:bg-pink-900/40 dark:text-pink-300',
    GDT_FCF: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300',
    DATUM: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-300',
    NOTE: 'bg-gray-100 text-gray-800 dark:bg-gray-700/40 dark:text-gray-300',
    TITLE_FIELD: 'bg-slate-100 text-slate-800 dark:bg-slate-700/40 dark:text-slate-300',
    GENERAL_TOLERANCE: 'bg-teal-100 text-teal-800 dark:bg-teal-900/40 dark:text-teal-300',
  }
  return (
    <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold ${colors[type] ?? colors.NOTE}`}>
      {type.replace(/_/g, ' ')}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Detection row
// ---------------------------------------------------------------------------

interface DetectionRowProps {
  detection: DetectionOut
  onConfirm: (id: string) => void
  onEdit: (id: string, current: string) => void
  onReject: (id: string) => void
  loading: boolean
}

function DetectionRow({ detection: d, onConfirm, onEdit, onReject, loading }: DetectionRowProps) {
  const isRejected = d.review_state === 'REJECTED'
  return (
    <div className={`p-3 border-b border-[var(--tp-border)] last:border-0 ${isRejected ? 'opacity-40' : ''}`}>
      <div className="flex flex-wrap items-center gap-1.5 mb-1">
        <TypeBadge type={d.normalized_type} />
        <ConfidenceBadge confidence={d.confidence} method={d.confidence_method} />
        <ReviewBadge state={d.review_state} />
        {d.review_required && d.review_state === 'PENDING' && (
          <span className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
            REVIEW
          </span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <span className="text-sm font-mono text-[var(--tp-text)]">
          {d.normalized_value ?? d.raw_text ?? '—'}
        </span>
        {d.unit && (
          <span className="text-xs text-[var(--tp-text-3)]">{d.unit}</span>
        )}
        {d.association_feature_id && (
          <span className="text-xs text-[var(--tp-text-3)]">→ {d.association_feature_id}</span>
        )}
      </div>
      {d.raw_text && d.raw_text !== d.normalized_value && (
        <div className="text-[10px] text-[var(--tp-text-3)] mt-0.5 font-mono">
          raw: {d.raw_text}
        </div>
      )}
      {d.ambiguities.length > 0 && (
        <div className="mt-1 text-[10px] text-amber-700 dark:text-amber-400">
          ⚠ {d.ambiguities.map(a => a.kind).join(', ')}
        </div>
      )}
      {!isRejected && (
        <div className="flex gap-1.5 mt-2">
          {d.review_state !== 'CONFIRMED' && (
            <button
              onClick={() => onConfirm(d.detection_id)}
              disabled={loading}
              className="px-2 py-1 text-[10px] font-semibold rounded bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
            >
              CONFIRM
            </button>
          )}
          <button
            onClick={() => onEdit(d.detection_id, d.normalized_value ?? '')}
            disabled={loading}
            className="px-2 py-1 text-[10px] font-semibold rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
          >
            EDIT
          </button>
          <button
            onClick={() => onReject(d.detection_id)}
            disabled={loading}
            className="px-2 py-1 text-[10px] font-semibold rounded bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
          >
            REJECT
          </button>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Filter bar
// ---------------------------------------------------------------------------

const FILTER_TYPES = [
  'ALL', 'DIMENSION', 'TOLERANCE', 'FIT', 'THREAD',
  'SURFACE_FINISH', 'GDT_FCF', 'DATUM', 'NOTE', 'TITLE_FIELD',
]

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function DrawingParserPage() {
  const { t } = useLocale()

  // Upload state
  const fileRef = useRef<HTMLInputElement>(null)
  const [notes, setNotes] = useState('')
  const [materialRaw, setMaterialRaw] = useState('')
  const [titleUnit, setTitleUnit] = useState('')

  // Session state
  const [analyzing, setAnalyzing] = useState(false)
  const [analyzeResult, setAnalyzeResult] = useState<AnalyzeResponse | null>(null)
  const [detections, setDetections] = useState<DetectionsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState(false)
  const [editTarget, setEditTarget] = useState<{ id: string; value: string } | null>(null)
  const [editValue, setEditValue] = useState('')
  const [filterType, setFilterType] = useState('ALL')

  const reload = useCallback(async (sid: string) => {
    const d = await getDetections(sid)
    setDetections(d)
  }, [])

  const handleAnalyze = useCallback(async () => {
    const file = fileRef.current?.files?.[0]
    if (!file) { setError(t('dpUploadRequired')); return }
    setError(null)
    setAnalyzing(true)
    try {
      const buf = await file.arrayBuffer()
      const bytes = new Uint8Array(buf)
      const b64 = btoa(String.fromCharCode(...bytes))
      const result = await analyzeDrawing({
        source_id: `upload-${Date.now()}`,
        file_name: file.name,
        content_b64: b64,
        title_block_unit: titleUnit || undefined,
        material_raw: materialRaw || undefined,
        notes: notes ? notes.split('\n').filter(Boolean) : [],
      })
      setAnalyzeResult(result)
      await reload(result.session_id)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setAnalyzing(false)
    }
  }, [t, notes, materialRaw, titleUnit, reload])

  const handleConfirm = useCallback(async (id: string) => {
    if (!analyzeResult) return
    setActionLoading(true)
    try { await confirmDetection(analyzeResult.session_id, id) }
    catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setActionLoading(false); await reload(analyzeResult.session_id) }
  }, [analyzeResult, reload])

  const handleEditOpen = useCallback((id: string, current: string) => {
    setEditTarget({ id, value: current })
    setEditValue(current)
  }, [])

  const handleEditSubmit = useCallback(async () => {
    if (!analyzeResult || !editTarget) return
    setActionLoading(true)
    try { await editDetection(analyzeResult.session_id, editTarget.id, editValue) }
    catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)) }
    finally {
      setActionLoading(false)
      setEditTarget(null)
      await reload(analyzeResult.session_id)
    }
  }, [analyzeResult, editTarget, editValue, reload])

  const handleReject = useCallback(async (id: string) => {
    if (!analyzeResult) return
    setActionLoading(true)
    try { await rejectDetection(analyzeResult.session_id, id) }
    catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setActionLoading(false); await reload(analyzeResult.session_id) }
  }, [analyzeResult, reload])

  const visibleDetections = detections?.detections.filter(d =>
    filterType === 'ALL' || d.normalized_type === filterType
  ) ?? []

  return (
    <div className="h-full overflow-y-auto p-4 md:p-6">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="mb-5">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light mb-1">
            {t('dpBadge')}
          </div>
          <h1 className="text-xl font-semibold text-tp-text">{t('dpTitle')}</h1>
          <p className="text-sm text-tp-text-2 mt-1">{t('dpSubtitle')}</p>
        </div>

        {/* Upload panel */}
        <Card className="mb-4">
          <SectionLabel>{t('dpUploadSection')}</SectionLabel>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-tp-text-2 block mb-1">{t('dpFileLabel')}</label>
              <input
                ref={fileRef}
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.tiff,.tif,.bmp,.dxf,.step,.stp,.iges,.igs"
                className="text-sm text-tp-text file:mr-2 file:py-1 file:px-3 file:rounded file:border-0 file:text-xs file:font-semibold file:bg-tp-accent file:text-white hover:file:bg-tp-accent/90"
              />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label className="text-xs text-tp-text-2 block mb-1">{t('dpUnitLabel')}</label>
                <input
                  value={titleUnit}
                  onChange={e => setTitleUnit(e.target.value)}
                  placeholder="mm / inch"
                  className="w-full px-2 py-1.5 text-sm border border-tp-border rounded bg-tp-bg text-tp-text"
                />
              </div>
              <div>
                <label className="text-xs text-tp-text-2 block mb-1">{t('dpMaterialLabel')}</label>
                <input
                  value={materialRaw}
                  onChange={e => setMaterialRaw(e.target.value)}
                  placeholder="e.g. 42CrMo4"
                  className="w-full px-2 py-1.5 text-sm border border-tp-border rounded bg-tp-bg text-tp-text"
                />
              </div>
              <div>
                <label className="text-xs text-tp-text-2 block mb-1">{t('dpNotesLabel')}</label>
                <input
                  value={notes}
                  onChange={e => setNotes(e.target.value)}
                  placeholder="Notes (one per line)"
                  className="w-full px-2 py-1.5 text-sm border border-tp-border rounded bg-tp-bg text-tp-text"
                />
              </div>
            </div>
            <button
              onClick={handleAnalyze}
              disabled={analyzing}
              className="px-4 py-2 text-sm font-semibold rounded bg-tp-accent text-white hover:bg-tp-accent/90 disabled:opacity-50"
            >
              {analyzing ? t('dpAnalyzing') : t('dpAnalyzeBtn')}
            </button>
          </div>
        </Card>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700 dark:bg-red-900/20 dark:border-red-800 dark:text-red-400">
            {error}
          </div>
        )}

        {/* Session summary */}
        {analyzeResult && (
          <Card className="mb-4">
            <SectionLabel>{t('dpSessionSection')}</SectionLabel>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="text-center">
                <div className="text-xl font-semibold text-tp-text">{analyzeResult.detection_count}</div>
                <div className="text-xs text-tp-text-3">{t('dpDetectionsLabel')}</div>
              </div>
              <div className="text-center">
                <div className="text-xl font-semibold text-amber-600">{analyzeResult.review_required_count}</div>
                <div className="text-xs text-tp-text-3">{t('dpReviewRequiredLabel')}</div>
              </div>
              <div className="text-center">
                <div className="text-xl font-semibold text-tp-text">{analyzeResult.detected_unit ?? t('dpUnitUnknown')}</div>
                <div className="text-xs text-tp-text-3">{t('dpDetectedUnit')}</div>
              </div>
              <div className="text-center">
                <div className={`text-xl font-semibold ${analyzeResult.ocr_available ? 'text-green-600' : 'text-amber-600'}`}>
                  {analyzeResult.ocr_available ? t('dpOcrOn') : t('dpOcrOff')}
                </div>
                <div className="text-xs text-tp-text-3">{t('dpOcrStatus')}</div>
              </div>
            </div>
            {analyzeResult.warnings.length > 0 && (
              <div className="mt-3 text-xs text-amber-700 dark:text-amber-400">
                ⚠ {analyzeResult.warnings.join(' · ')}
              </div>
            )}
            <div className="mt-2 text-[10px] text-tp-text-3 italic">{analyzeResult.disclaimer}</div>
          </Card>
        )}

        {/* Edit modal */}
        {editTarget && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
            <div className="bg-tp-surface border border-tp-border rounded-lg p-5 w-80 shadow-xl">
              <div className="text-sm font-semibold text-tp-text mb-3">{t('dpEditTitle')}</div>
              <input
                value={editValue}
                onChange={e => setEditValue(e.target.value)}
                className="w-full px-2 py-1.5 text-sm border border-tp-border rounded bg-tp-bg text-tp-text mb-3"
                autoFocus
              />
              <div className="flex gap-2 justify-end">
                <button onClick={() => setEditTarget(null)} className="px-3 py-1.5 text-xs rounded border border-tp-border text-tp-text-2 hover:bg-tp-surface">
                  {t('dpCancelBtn')}
                </button>
                <button
                  onClick={handleEditSubmit}
                  disabled={actionLoading || !editValue.trim()}
                  className="px-3 py-1.5 text-xs font-semibold rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  {t('dpSaveBtn')}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Detections panel */}
        {detections && (
          <Card>
            <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
              <SectionLabel>{t('dpDetectionsSection')} ({detections.total})</SectionLabel>
              <div className="flex flex-wrap gap-1">
                {FILTER_TYPES.map(ft => (
                  <button
                    key={ft}
                    onClick={() => setFilterType(ft)}
                    className={`px-2 py-0.5 text-[10px] rounded font-semibold ${
                      filterType === ft
                        ? 'bg-tp-accent text-white'
                        : 'bg-tp-surface border border-tp-border text-tp-text-2 hover:bg-tp-border'
                    }`}
                  >
                    {ft === 'ALL' ? t('dpFilterAll') : ft.replace(/_/g, ' ')}
                  </button>
                ))}
              </div>
            </div>

            {visibleDetections.length === 0 ? (
              <div className="text-sm text-tp-text-3 py-4 text-center">
                {t('dpNoDetections')}
              </div>
            ) : (
              <div className="rounded border border-tp-border">
                {visibleDetections.map(d => (
                  <DetectionRow
                    key={d.detection_id}
                    detection={d}
                    onConfirm={handleConfirm}
                    onEdit={handleEditOpen}
                    onReject={handleReject}
                    loading={actionLoading}
                  />
                ))}
              </div>
            )}

            <div className="mt-3 flex items-center gap-4 text-xs text-tp-text-3">
              <span>{t('dpConfirmedCount')}: <strong>{detections.confirmed_count}</strong></span>
              <span>{t('dpReviewPending')}: <strong>{detections.review_required_count}</strong></span>
            </div>
            <div className="mt-1 text-[10px] text-tp-text-3 italic">{detections.disclaimer}</div>
          </Card>
        )}
      </div>
    </div>
  )
}
