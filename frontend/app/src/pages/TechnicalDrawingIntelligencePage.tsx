import { useMemo, useReducer, useState } from 'react'
import { ShieldCheck } from 'lucide-react'
import Panel from '../components/ui/Panel'
import AiStatus from '../components/drawing-review/AiStatus'
import AuthorityBadge from '../components/drawing-review/AuthorityBadge'
import DrawingViewer from '../components/drawing-review/DrawingViewer'
import FindingCard from '../components/drawing-review/FindingCard'
import { useLocale } from '../i18n'
import { countByStatus, createReviewState, reviewReducer } from '../lib/drawingReview.ts'
import {
  PREVIEW_STATE_KEYS,
  SAMPLE_DETERMINISTIC,
  SAMPLE_REGION,
  previewState,
  type PreviewStateKey,
} from '../data/sampleDrawingReview.ts'
import type { AiAnalysisState, ReviewAction } from '../types/drawingReview.ts'

type Action = ReviewAction | { type: 'RESET'; state: ReturnType<typeof createReviewState> }

function reducer(state: ReturnType<typeof createReviewState>, action: Action) {
  return action.type === 'RESET' ? action.state : reviewReducer(state, action)
}

/**
 * Human-review workspace for advisory AI drawing findings.
 *
 * The backend exposes no drawing-analysis or review endpoint yet, so this build works on
 * a clearly labelled synthetic sample and keeps decisions in the browser session. The
 * deterministic panel is independent of the AI state and is always rendered.
 */
export default function TechnicalDrawingIntelligencePage({
  reviewer,
}: {
  reviewer: string | null
}) {
  const { t } = useLocale()
  const [sampleLoaded, setSampleLoaded] = useState(false)
  const [ai, setAi] = useState<AiAnalysisState>({ kind: 'FAILED', failure: 'NOT_CONNECTED' })
  const [review, dispatch] = useReducer(reducer, {})
  const [selected, setSelected] = useState<string | null>(null)

  const findings = ai.kind === 'READY' ? ai.findings : []
  const counts = useMemo(() => countByStatus(review), [review])

  const applyAiState = (next: AiAnalysisState) => {
    setAi(next)
    setSelected(null)
    dispatch({
      type: 'RESET',
      state: createReviewState(next.kind === 'READY' ? next.findings : []),
    })
  }

  const loadSample = () => {
    setSampleLoaded(true)
    applyAiState(previewState('READY'))
  }

  const stamp = () => new Date().toISOString()
  const selectedFinding = findings.find(f => f.evidence_id === selected) ?? null

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
          <Panel title={t('drDrawing')} subtitle={sampleLoaded ? t('drSampleNote') : undefined}>
            <DrawingViewer
              loaded={sampleLoaded}
              region={sampleLoaded ? SAMPLE_REGION : null}
              showRegion={selectedFinding !== null}
            />
            {!sampleLoaded && (
              <button
                type="button"
                onClick={loadSample}
                className="mt-3 inline-flex min-h-11 items-center rounded border
                           border-tp-accent-muted bg-tp-surface-2 px-3 text-sm font-medium
                           text-tp-accent-light hover:bg-tp-surface-3 sm:min-h-9
                           focus-visible:outline-2 focus-visible:outline-tp-accent-light"
              >
                {t('drLoadSample')}
              </button>
            )}
          </Panel>

          <Panel title={t('drDeterministicResult')} subtitle={t('drDeterministicHint')}>
            {sampleLoaded ? (
              <ul className="space-y-2" data-testid="deterministic-list">
                {SAMPLE_DETERMINISTIC.map(item => (
                  <li
                    key={item.id}
                    data-testid="deterministic-item"
                    className="rounded-md border border-tp-accent-muted bg-tp-surface-2 p-3"
                  >
                    <div className="mb-1">
                      <AuthorityBadge kind="DETERMINISTIC" />
                    </div>
                    <div className="font-mono text-lg font-semibold tabular-nums">
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
                  {findings.map(finding => (
                    <FindingCard
                      key={finding.evidence_id}
                      finding={finding}
                      record={review[finding.evidence_id]}
                      selected={selected === finding.evidence_id}
                      onSelect={() => setSelected(finding.evidence_id)}
                      onAccept={() =>
                        dispatch({
                          type: 'ACCEPT',
                          evidence_id: finding.evidence_id,
                          reviewed_by: reviewer,
                          reviewed_at: stamp(),
                        })
                      }
                      onReject={() =>
                        dispatch({
                          type: 'REJECT',
                          evidence_id: finding.evidence_id,
                          reviewed_by: reviewer,
                          reviewed_at: stamp(),
                        })
                      }
                      onEdit={value =>
                        dispatch({
                          type: 'EDIT',
                          evidence_id: finding.evidence_id,
                          value,
                          reviewed_by: reviewer,
                          reviewed_at: stamp(),
                        })
                      }
                    />
                  ))}
                  <p className="text-xs text-tp-text-3">{t('drSessionNote')}</p>
                </>
              ) : (
                <AiStatus state={ai} />
              )}

              {import.meta.env.DEV && (
                <label className="block text-xs text-tp-text-3">
                  {t('drPreviewStates')}
                  <select
                    data-testid="preview-state"
                    className="mt-1 block min-h-9 w-full rounded border border-tp-border
                               bg-tp-bg px-2 text-sm text-tp-text"
                    defaultValue=""
                    onChange={e => {
                      if (!e.target.value) return
                      setSampleLoaded(true)
                      applyAiState(previewState(e.target.value as PreviewStateKey))
                    }}
                  >
                    <option value="">—</option>
                    {PREVIEW_STATE_KEYS.map(key => (
                      <option key={key} value={key}>
                        {key}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </div>
          </Panel>
        </aside>
      </div>
    </div>
  )
}
