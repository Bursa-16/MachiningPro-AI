import { useState } from 'react'
import { Check, Pencil, X } from 'lucide-react'
import { useLocale } from '../../i18n'
import type { TranslationDictionary } from '../../i18n/types'
import {
  boxBasisLabelKey,
  confidenceLabel,
  confirmedValue,
  validateEditedValue,
} from '../../lib/drawingReview.ts'
import type { AdvisoryFinding, Reconciliation, ReviewRecord } from '../../types/drawingReview.ts'
import AuthorityBadge, { type BadgeKind } from './AuthorityBadge'

const EDIT_ERROR: Record<string, keyof TranslationDictionary> = {
  BLANK: 'drEditBlank',
  TOO_LONG: 'drEditTooLong',
  CONTROL_CHARACTERS: 'drEditControl',
  UNCHANGED: 'drEditUnchanged',
}

const RECONCILIATION: Record<Reconciliation, keyof TranslationDictionary> = {
  CORROBORATED: 'drCorroborated',
  CONFLICT: 'drConflict',
  ADVISORY_ONLY: 'drAdvisoryOnly',
  RECOVERY_CANDIDATE: 'drAdvisoryOnly',
  AMBIGUOUS: 'drOtherComparison',
  NOT_COMPARABLE: 'drOtherComparison',
}

const STATUS_BADGE: Record<ReviewRecord['status'], BadgeKind> = {
  PENDING_REVIEW: 'PENDING',
  ACCEPTED: 'CONFIRMED',
  EDITED: 'EDITED',
  REJECTED: 'REJECTED',
}

const BORDER: Record<ReviewRecord['status'], string> = {
  PENDING_REVIEW: 'border-tp-ai/60',
  ACCEPTED: 'border-tp-valid',
  EDITED: 'border-tp-warn',
  REJECTED: 'border-tp-error',
}

const ACTION =
  'inline-flex min-h-11 items-center justify-center gap-1.5 rounded border px-3 text-sm ' +
  'font-medium transition-colors sm:min-h-9 focus-visible:outline-2 ' +
  'focus-visible:outline-tp-accent-light'

export interface FindingCardProps {
  finding: AdvisoryFinding
  record: ReviewRecord
  selected: boolean
  onSelect: () => void
  onAccept: () => void
  onReject: () => void
  onEdit: (value: string) => void
}

export default function FindingCard({
  finding,
  record,
  selected,
  onSelect,
  onAccept,
  onReject,
  onEdit,
}: FindingCardProps) {
  const { t } = useLocale()
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<keyof TranslationDictionary | null>(null)

  const confidence = confidenceLabel(finding.confidence)
  const confirmed = confirmedValue(record)
  const rejected = record.status === 'REJECTED'
  const inputId = `edit-${finding.evidence_id}`

  const startEdit = () => {
    setDraft(record.reviewed_value ?? finding.original_value)
    setError(null)
    setEditing(true)
  }
  const save = () => {
    const checked = validateEditedValue(draft, finding.original_value)
    if (!checked.ok) {
      setError(EDIT_ERROR[checked.reason])
      return
    }
    onEdit(checked.value)
    setEditing(false)
  }

  return (
    <article
      data-testid="finding-card"
      data-status={record.status}
      aria-label={finding.original_value}
      className={`rounded-md border bg-tp-surface p-3 ${BORDER[record.status]}
                  ${selected ? 'ring-1 ring-tp-accent-light' : ''}`}
      onClick={onSelect}
    >
      <div className="mb-2 flex flex-wrap items-center gap-1.5">
        <AuthorityBadge kind="AI" />
        <AuthorityBadge kind={STATUS_BADGE[record.status]} testId="status-badge" />
      </div>

      <div className="mb-2">
        <div className="text-[11px] uppercase tracking-wide text-tp-text-3">
          {t('drAiOriginalValue')}
        </div>
        <div
          data-testid="ai-original-value"
          className={`font-mono text-lg font-semibold tabular-nums break-words ${
            rejected || record.status === 'EDITED' ? 'text-tp-text-2 line-through' : 'text-tp-text'
          }`}
        >
          {finding.original_value}
        </div>
      </div>

      {record.status === 'EDITED' && (
        <div className="mb-2">
          <div className="text-[11px] uppercase tracking-wide text-tp-text-3">
            {t('drHumanValue')}
          </div>
          <div data-testid="human-value" className="font-mono text-lg font-semibold break-words">
            {record.reviewed_value}
          </div>
        </div>
      )}
      {record.status === 'ACCEPTED' && confirmed !== null && (
        <div className="mb-2 text-xs text-tp-text-2" data-testid="confirmed-value">
          {t('drHumanConfirmed')}: <span className="font-mono text-tp-text">{confirmed}</span>
        </div>
      )}

      <dl className="mb-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
        <dt className="text-tp-text-3">{t('drFindingType')}</dt>
        <dd className="text-tp-text-2">{finding.candidate_type}</dd>
        <dt className="text-tp-text-3">{t('drConfidence')}</dt>
        <dd className="text-tp-text-2">{confidence ?? t('drNoConfidence')}</dd>
        <dt className="text-tp-text-3">{t('drProvider')}</dt>
        <dd className="text-tp-text-2 break-all" data-testid="provider">{finding.provider_id}</dd>
        <dt className="text-tp-text-3">{t('drModel')}</dt>
        <dd className="text-tp-text-2 break-all" data-testid="model">{finding.model_id}</dd>
        <dt className="text-tp-text-3">{t('drRegion')}</dt>
        <dd className="text-tp-text-2 break-all" data-testid="region-basis">
          {t(boxBasisLabelKey(finding.box_basis))} · {finding.region_id}
        </dd>
        {finding.reconciliation && (
          <>
            <dt className="text-tp-text-3">{t('drCompared')}</dt>
            <dd className="text-tp-text-2">{t(RECONCILIATION[finding.reconciliation])}</dd>
          </>
        )}
      </dl>

      {editing ? (
        <div className="mt-2 space-y-2" onClick={e => e.stopPropagation()}>
          <label htmlFor={inputId} className="block text-xs text-tp-text-2">
            {t('drEditValueLabel')}
          </label>
          <input
            id={inputId}
            value={draft}
            onChange={e => {
              setDraft(e.target.value)
              setError(null)
            }}
            onKeyDown={e => {
              if (e.key === 'Enter') save()
              if (e.key === 'Escape') setEditing(false)
            }}
            autoFocus
            aria-invalid={error !== null}
            aria-describedby={error ? `${inputId}-error` : undefined}
            className="min-h-11 w-full rounded border border-tp-border-strong bg-tp-bg px-2
                       font-mono text-sm text-tp-text sm:min-h-9
                       focus-visible:outline-2 focus-visible:outline-tp-accent-light"
          />
          {error && (
            <div id={`${inputId}-error`} role="alert" className="text-xs text-tp-error">
              {t(error)}
            </div>
          )}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={save}
              className={`${ACTION} border-tp-warn bg-tp-warn-muted text-tp-text hover:bg-tp-warn/30`}
            >
              <Check size={14} aria-hidden="true" />
              {t('drSaveEdit')}
            </button>
            <button
              type="button"
              onClick={() => setEditing(false)}
              className={`${ACTION} border-tp-border-strong text-tp-text-2 hover:bg-tp-surface-2`}
            >
              {t('drCancel')}
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-2 flex flex-wrap gap-2" onClick={e => e.stopPropagation()}>
          <button
            type="button"
            onClick={onAccept}
            aria-pressed={record.status === 'ACCEPTED'}
            className={`${ACTION} border-tp-valid text-tp-text hover:bg-tp-valid-muted`}
          >
            <Check size={14} aria-hidden="true" />
            {t('drAccept')}
          </button>
          <button
            type="button"
            onClick={startEdit}
            aria-pressed={record.status === 'EDITED'}
            className={`${ACTION} border-tp-warn text-tp-text hover:bg-tp-warn-muted`}
          >
            <Pencil size={14} aria-hidden="true" />
            {t('drEdit')}
          </button>
          <button
            type="button"
            onClick={onReject}
            aria-pressed={rejected}
            className={`${ACTION} border-tp-error text-tp-text hover:bg-tp-error-muted`}
          >
            <X size={14} aria-hidden="true" />
            {t('drReject')}
          </button>
        </div>
      )}

      {record.history.length > 0 && (
        <details className="mt-2 text-xs text-tp-text-2" onClick={e => e.stopPropagation()}>
          <summary className="cursor-pointer text-tp-text-3">{t('drReviewHistory')}</summary>
          <ol className="mt-1 space-y-1" data-testid="review-history">
            {record.history.map((event, index) => (
              <li key={index}>
                {event.status}
                {event.reviewed_value !== null && ` → ${event.reviewed_value}`} ·{' '}
                {t('drReviewedBy')} {event.reviewed_by ?? t('drNotRecorded')} · {event.reviewed_at}
              </li>
            ))}
          </ol>
        </details>
      )}
    </article>
  )
}
