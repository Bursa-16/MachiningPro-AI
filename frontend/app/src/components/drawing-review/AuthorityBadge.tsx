import { Check, Pencil, ShieldCheck, Sparkles, X, Clock } from 'lucide-react'
import { useLocale } from '../../i18n'
import type { TranslationDictionary } from '../../i18n/types'

export type BadgeKind = 'DETERMINISTIC' | 'AI' | 'CONFIRMED' | 'REJECTED' | 'EDITED' | 'PENDING'

const STYLE: Record<
  BadgeKind,
  { key: keyof TranslationDictionary; className: string; Icon: typeof Check }
> = {
  DETERMINISTIC: {
    key: 'drDeterministicResult',
    className: 'border-tp-accent-muted bg-tp-surface-2 text-tp-accent-light',
    Icon: ShieldCheck,
  },
  AI: {
    key: 'drAiSuggestion',
    className: 'border-tp-ai bg-tp-ai-muted text-tp-ai-light',
    Icon: Sparkles,
  },
  CONFIRMED: {
    key: 'drHumanConfirmed',
    className: 'border-tp-valid bg-tp-valid-muted text-tp-text',
    Icon: Check,
  },
  EDITED: {
    key: 'drEditedByHuman',
    className: 'border-tp-warn bg-tp-warn-muted text-tp-text',
    Icon: Pencil,
  },
  REJECTED: {
    key: 'drRejected',
    className: 'border-tp-error bg-tp-error-muted text-tp-text',
    Icon: X,
  },
  PENDING: {
    key: 'drPendingReview',
    className: 'border-tp-border-strong bg-tp-surface-2 text-tp-text-2',
    Icon: Clock,
  },
}

/** A labelled badge. Meaning is always carried by the icon and text, never by colour alone. */
export default function AuthorityBadge({ kind, testId }: { kind: BadgeKind; testId?: string }) {
  const { t } = useLocale()
  const { key, className, Icon } = STYLE[kind]
  return (
    <span
      data-testid={testId}
      data-badge={kind}
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px]
                  font-semibold uppercase tracking-wide ${className}`}
    >
      <Icon size={11} aria-hidden="true" />
      {t(key)}
    </span>
  )
}
