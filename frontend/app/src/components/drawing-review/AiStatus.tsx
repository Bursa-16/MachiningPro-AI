import { AlertTriangle, Info, LoaderCircle } from 'lucide-react'
import { useLocale } from '../../i18n'
import type { TranslationDictionary } from '../../i18n/types'
import { ANALYSIS_PHASES, phaseIndex } from '../../lib/drawingReview.ts'
import type { AiAnalysisState, AiFailureKind, AnalysisPhase } from '../../types/drawingReview.ts'

const FAILURE_KEY: Record<AiFailureKind, keyof TranslationDictionary> = {
  DISABLED: 'drStateDisabled',
  OLLAMA_UNAVAILABLE: 'drStateOllama',
  MODEL_UNAVAILABLE: 'drStateModel',
  TIMEOUT: 'drStateTimeout',
  VALIDATION_FAILED: 'drStateValidation',
  INVALID_DRAWING: 'drStateInvalidDrawing',
  INVALID_REGION: 'drStateInvalidRegion',
  NOT_CONNECTED: 'drStateNotConnected',
  UNKNOWN: 'drStateUnknown',
}

const PHASE_KEY: Record<AnalysisPhase, keyof TranslationDictionary> = {
  QUEUED: 'drPhaseQueued',
  PREPARING_DRAWING: 'drPhasePreparing',
  AI_IN_PROGRESS: 'drPhaseAi',
  VALIDATING_RESPONSE: 'drPhaseValidating',
}

/**
 * Renders every non-review AI state. Running state is an indeterminate spinner plus a
 * step list: there is no real progress metric, so no percentage is ever shown.
 */
export default function AiStatus({ state }: { state: AiAnalysisState }) {
  const { t } = useLocale()

  if (state.kind === 'RUNNING') {
    const current = phaseIndex(state.phase)
    return (
      <div
        role="status"
        aria-live="polite"
        data-testid="ai-status"
        data-state="RUNNING"
        className="rounded-md border border-tp-ai/60 bg-tp-ai-muted p-3"
      >
        <div className="mb-2 flex items-center gap-2 text-sm font-medium text-tp-text">
          <LoaderCircle size={16} className="animate-spin text-tp-ai-light" aria-hidden="true" />
          {t(PHASE_KEY[state.phase])}
        </div>
        <ol className="space-y-1 text-xs">
          {ANALYSIS_PHASES.map((phase, index) => (
            <li
              key={phase}
              data-done={index < current}
              data-current={index === current}
              className={
                index < current
                  ? 'text-tp-text-2'
                  : index === current
                    ? 'font-medium text-tp-text'
                    : 'text-tp-text-3'
              }
            >
              {index < current ? '✓ ' : index === current ? '● ' : '○ '}
              {t(PHASE_KEY[phase])}
            </li>
          ))}
        </ol>
        <p className="mt-2 text-xs text-tp-text-2">{t('drSlowNote')}</p>
      </div>
    )
  }

  if (state.kind === 'FAILED') {
    return (
      <div
        role="alert"
        data-testid="ai-status"
        data-state="FAILED"
        data-failure={state.failure}
        className="rounded-md border border-tp-warn bg-tp-warn-muted p-3"
      >
        <div className="flex items-start gap-2 text-sm text-tp-text">
          <AlertTriangle size={16} className="mt-0.5 shrink-0 text-tp-warn" aria-hidden="true" />
          <div>
            <div>{t(FAILURE_KEY[state.failure])}</div>
            <div className="mt-1 text-xs text-tp-text-2">{t('drDeterministicStillAvailable')}</div>
          </div>
        </div>
      </div>
    )
  }

  const message =
    state.kind === 'IDLE' ? t('drStateIdle') : t('drNoFindings')
  return (
    <div
      role="status"
      data-testid="ai-status"
      data-state={state.kind === 'IDLE' ? 'IDLE' : 'NO_FINDINGS'}
      className="flex items-start gap-2 rounded-md border border-tp-border bg-tp-surface-2 p-3
                 text-sm text-tp-text-2"
    >
      <Info size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
      {message}
    </div>
  )
}
