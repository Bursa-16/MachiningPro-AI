import { Suspense, lazy, useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react'
import { LoaderCircle, ShieldCheck, Upload } from 'lucide-react'
import Panel from '../components/ui/Panel'
import AiStatus from '../components/drawing-review/AiStatus'
import AuthorityBadge from '../components/drawing-review/AuthorityBadge'
import DrawingViewer from '../components/drawing-review/DrawingViewer'
import EngineeringFileInfo from '../components/drawing-review/EngineeringFileInfo'
import FindingCard from '../components/drawing-review/FindingCard'
import { useLocale } from '../i18n'
import { useAnalysisController } from '../hooks/useAnalysisController'
import { aiStateFor, isJobActive } from '../lib/analysisController.ts'
import { countByStatus, createReviewState, reviewReducer } from '../lib/drawingReview.ts'
import { detectFormatByFile, NATIVE_ACCEPT } from '../lib/engineeringFormats'
import type { FormatRoute } from '../lib/engineeringFormats'
import { detectAndImport, fetchDxfAsPdf } from '../services/engineeringImport'
import type { ImportResult } from '../services/engineeringImport'
import { drawingAnalysisApi } from '../services/drawingAnalysis'
import type { SamplePreview } from '../components/drawing-review/DevPreview'
import type {
  AiAnalysisState,
  DeterministicItem,
  ReviewAction,
  ReviewState,
  SourceRegion,
} from '../types/drawingReview.ts'

// Development-only: the dynamic import sits behind a compile-time constant, so production
// builds drop the sample data and the previewer entirely.
const DevPreview = import.meta.env.DEV
  ? lazy(() => import('../components/drawing-review/DevPreview'))
  : null

type LocalAction = ReviewAction | { type: 'RESET'; state: ReviewState }

function localReducer(state: ReviewState, action: LocalAction): ReviewState {
  return action.type === 'RESET' ? action.state : reviewReducer(state, action)
}

const BUTTON =
  'inline-flex min-h-11 items-center justify-center gap-1.5 rounded border px-3 text-sm ' +
  'font-medium transition-colors sm:min-h-9 focus-visible:outline-2 ' +
  'focus-visible:outline-tp-accent-light disabled:cursor-not-allowed disabled:opacity-50'

/**
 * Human-review workspace for advisory AI drawing findings.
 *
 * Production data comes from the authenticated drawing-analysis API: upload (deterministic
 * ingestion), an explicit "Analyze with Local AI" job that is polled for real states, and
 * server-side review decisions. The development sample below is reachable only in dev
 * builds. The deterministic panel is independent of the AI state and is always rendered.
 */
export default function TechnicalDrawingIntelligencePage({
  reviewer,
}: {
  reviewer: string | null
}) {
  const { t } = useLocale()
  const { controller, state } = useAnalysisController(drawingAnalysisApi)
  const fileInput = useRef<HTMLInputElement>(null)

  // Development-only sample mode; null in production builds.
  const [sample, setSample] = useState<SamplePreview | null>(null)
  const [localReview, dispatch] = useReducer(localReducer, {})
  const [selected, setSelected] = useState<string | null>(null)

  // Universal engineering import state (non-PDF files)
  const [importRoute, setImportRoute] = useState<FormatRoute | null>(null)
  const [importFileName, setImportFileName] = useState<string>('')
  const [importResult, setImportResult] = useState<ImportResult | null>(null)
  const [importLoading, setImportLoading] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null)

  // Revoke previous object URL when a new file is selected
  const revokePreview = useCallback(() => {
    if (imagePreviewUrl) {
      URL.revokeObjectURL(imagePreviewUrl)
      setImagePreviewUrl(null)
    }
  }, [imagePreviewUrl])

  useEffect(() => {
    return () => {
      if (imagePreviewUrl) URL.revokeObjectURL(imagePreviewUrl)
    }
  }, [imagePreviewUrl])

  const sampleMode = sample !== null
  const ai: AiAnalysisState = sample?.ai ?? aiStateFor(state)
  const findings = ai.kind === 'READY' ? ai.findings : []
  const records: ReviewState = sampleMode ? localReview : (state.job?.reviews ?? {})
  const counts = useMemo(() => countByStatus(records), [records])
  const active = isJobActive(state.job)

  const deterministic: readonly DeterministicItem[] = sample
    ? sample.deterministic
    : (state.drawing?.deterministic.items ?? [])
  const drawingLoaded = sampleMode || state.drawing !== null
  const region: SourceRegion | null = sample ? sample.region : (state.job?.region ?? null)
  const firstPage = state.drawing?.pages[0] ?? null
  const live =
    !sampleMode && firstPage
      ? { widthPt: firstPage.width_pt, heightPt: firstPage.height_pt, imageUrl: state.previewUrl }
      : null
  const selectedFinding = findings.find(f => f.evidence_id === selected) ?? null

  const stamp = () => new Date().toISOString()
  const applySample = (next: SamplePreview) => {
    setSample(next)
    setSelected(null)
    dispatch({
      type: 'RESET',
      state: createReviewState(next.ai.kind === 'READY' ? next.ai.findings : []),
    })
  }

  const decide = (evidenceId: string, action: 'ACCEPT' | 'REJECT' | { value: string }) => {
    if (sampleMode) {
      const base = { evidence_id: evidenceId, reviewed_by: reviewer, reviewed_at: stamp() }
      dispatch(
        typeof action === 'string'
          ? { type: action, ...base }
          : { type: 'EDIT', value: action.value, ...base },
      )
      return
    }
    void controller.review(
      evidenceId,
      typeof action === 'string' ? { action } : { action: 'EDIT', value: action.value },
    )
  }

  const canAnalyze = !sampleMode && state.drawing !== null && !state.uploading && !state.starting && !active && !importLoading

  return (
    <div className="h-full overflow-y-auto p-4 sm:p-6">
      <div className="mb-4 max-w-3xl">
        <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light">
          MachiningPro AI
        </div>
        <h1 className="text-lg font-semibold text-tp-text">{t('drPageTitle')}</h1>
        <p className="text-sm text-tp-text-2">{t('drPageSubtitle')}</p>
      </div>

      <div
        data-testid="review-required-note"
        className="mb-4 flex items-start gap-2 rounded-md border border-tp-ai/60 bg-tp-ai-muted
                   px-3 py-2 text-sm text-tp-text"
      >
        <ShieldCheck size={16} className="mt-0.5 shrink-0 text-tp-ai-light" aria-hidden="true" />
        <span>{t('drReviewRequired')}</span>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_400px]">
        <div className="min-w-0 space-y-4">
          <Panel title={t('drDrawing')} subtitle={sampleMode ? t('drSampleNote') : undefined}>
            <DrawingViewer
              loaded={drawingLoaded}
              region={region}
              showRegion={selectedFinding !== null && region !== null}
              live={live}
              art={sample?.art}
            />
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <input
                ref={fileInput}
                data-testid="upload-input"
                type="file"
                accept={NATIVE_ACCEPT}
                className="hidden"
                onChange={e => {
                  const file = e.target.files?.[0]
                  e.target.value = ''
                  if (!file) return
                  const detected = detectFormatByFile(file)
                  const route = detected?.route ?? 'UNKNOWN'
                  if (route === 'DRAWING_PDF') {
                    // PDF → existing drawing-analysis pipeline
                    setImportRoute(null)
                    setImportResult(null)
                    setImportError(null)
                    revokePreview()
                    setSample(null)
                    setSelected(null)
                    void controller.upload(file)
                  } else {
                    // All other formats → universal import endpoint
                    setImportRoute(route)
                    setImportFileName(file.name)
                    setImportResult(null)
                    setImportError(null)
                    setImportLoading(true)
                    revokePreview()
                    setSample(null)
                    setSelected(null)
                    if (route === 'DRAWING_IMAGE') {
                      setImagePreviewUrl(URL.createObjectURL(file))
                    }
                    if (route === 'DRAWING_VECTOR') {
                      // DXF: parse metadata AND render to PDF for AI pipeline in parallel
                      const capturedFile = file
                      void Promise.allSettled([
                        detectAndImport(capturedFile),
                        fetchDxfAsPdf(capturedFile),
                      ]).then(([importRes, pdfRes]) => {
                        if (importRes.status === 'fulfilled') {
                          setImportResult(importRes.value)
                        } else {
                          setImportError('import_failed')
                        }
                        setImportLoading(false)
                        // Feed the rendered DXF PDF into the drawing-analysis pipeline
                        // only when both import metadata and render succeeded
                        if (
                          importRes.status === 'fulfilled' &&
                          pdfRes.status === 'fulfilled' &&
                          (importRes.value.import_status === 'SUCCESS' ||
                            importRes.value.import_status === 'PARTIAL')
                        ) {
                          const pdfFile = new File(
                            [pdfRes.value],
                            capturedFile.name + '.pdf',
                            { type: 'application/pdf' },
                          )
                          void controller.uploadDxfRender(pdfFile)
                        }
                      })
                    } else {
                      detectAndImport(file)
                        .then(r => {
                          setImportResult(r)
                          setImportLoading(false)
                        })
                        .catch(() => {
                          setImportError('import_failed')
                          setImportLoading(false)
                        })
                    }
                  }
                }}
              />
              <button
                type="button"
                data-testid="upload-button"
                disabled={state.uploading || importLoading || active}
                onClick={() => fileInput.current?.click()}
                className={`${BUTTON} border-tp-border-strong text-tp-text hover:bg-tp-surface-2`}
              >
                {(state.uploading || importLoading) ? (
                  <LoaderCircle size={14} className="animate-spin" aria-hidden="true" />
                ) : (
                  <Upload size={14} aria-hidden="true" />
                )}
                {state.uploading ? t('drUploading') : importLoading ? t('drImportUploading') : t('drUploadDrawing')}
              </button>
              <button
                type="button"
                data-testid="analyze-button"
                disabled={!canAnalyze}
                onClick={() => void controller.startAnalysis()}
                className={`${BUTTON} border-tp-ai bg-tp-ai-muted text-tp-text hover:bg-tp-ai/30`}
              >
                {active || state.starting
                  ? t('drAnalysisActive')
                  : state.job
                    ? t('drAnalyzeAgain')
                    : t('drAnalyze')}
              </button>
            </div>
            {state.uploadFailed && (
              <div role="alert" data-testid="upload-error" className="mt-2 text-xs text-tp-error">
                {t('drUploadFailed')}
              </div>
            )}
            {state.drawing && !sampleMode && (
              <p className="mt-2 text-xs text-tp-text-3">{t('drWholeImageNote')}</p>
            )}
            {/* Universal import info panel for non-PDF files */}
            {importRoute && importRoute !== 'DRAWING_PDF' && (
              <EngineeringFileInfo
                fileName={importFileName}
                route={importRoute}
                result={importLoading ? null : importResult}
                error={importError}
                previewUrl={imagePreviewUrl}
              />
            )}
          </Panel>

          <Panel title={t('drDeterministicResult')} subtitle={t('drDeterministicHint')}>
            {deterministic.length > 0 ? (
              <ul className="space-y-2" data-testid="deterministic-list">
                {deterministic.map(item => (
                  <li
                    key={item.id}
                    data-testid="deterministic-item"
                    className="rounded-md border border-tp-accent-muted bg-tp-surface-2 p-3"
                  >
                    <div className="mb-1">
                      <AuthorityBadge kind="DETERMINISTIC" />
                    </div>
                    <div className="font-mono text-lg font-semibold tabular-nums break-words">
                      {item.value}
                    </div>
                    <div className="text-xs text-tp-text-3">
                      {item.label} · {t('drSource')}: {item.source}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="text-sm text-tp-text-3">{t('drNoDeterministic')}</div>
            )}
          </Panel>
        </div>

        <aside aria-label={t('drPanelTitle')} className="min-w-0">
          <Panel title={t('drPanelTitle')}>
            <div className="space-y-3">
              {sampleMode && (
                <div className="text-[11px] uppercase tracking-wide text-tp-warn">
                  {t('drSampleBadge')}
                </div>
              )}
              {ai.kind === 'READY' && findings.length > 0 ? (
                <>
                  <div
                    data-testid="review-counts"
                    className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-tp-text-2"
                  >
                    <span>{counts.PENDING_REVIEW} {t('drCountPending')}</span>
                    <span>{counts.ACCEPTED} {t('drCountAccepted')}</span>
                    <span>{counts.EDITED} {t('drCountEdited')}</span>
                    <span>{counts.REJECTED} {t('drCountRejected')}</span>
                  </div>
                  {findings.map(finding => {
                    const record = records[finding.evidence_id]
                    return record ? (
                      <FindingCard
                        key={finding.evidence_id}
                        finding={finding}
                        record={record}
                        selected={selected === finding.evidence_id}
                        onSelect={() => setSelected(finding.evidence_id)}
                        onAccept={() => decide(finding.evidence_id, 'ACCEPT')}
                        onReject={() => decide(finding.evidence_id, 'REJECT')}
                        onEdit={value => decide(finding.evidence_id, { value })}
                      />
                    ) : null
                  })}
                  {state.reviewFailed && (
                    <div role="alert" data-testid="review-error" className="text-xs text-tp-error">
                      {t('drReviewSaveFailed')}
                    </div>
                  )}
                  <p className="text-xs text-tp-text-3">
                    {sampleMode ? t('drSessionNote') : t('drServerSessionNote')}
                  </p>
                </>
              ) : (
                <AiStatus state={ai} />
              )}

              {DevPreview && (
                <Suspense fallback={null}>
                  <DevPreview onSelect={applySample} />
                </Suspense>
              )}
            </div>
          </Panel>
        </aside>
      </div>
    </div>
  )
}
