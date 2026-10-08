import type { ReactNode } from 'react'
import { useLocale } from '../../i18n'
import {
  PREVIEW_STATE_KEYS,
  SAMPLE_DETERMINISTIC,
  SAMPLE_REGION,
  previewState,
  type PreviewStateKey,
} from '../../data/sampleDrawingReview.ts'
import type { AiAnalysisState, DeterministicItem, SourceRegion } from '../../types/drawingReview.ts'

export interface SamplePreview {
  ai: AiAnalysisState
  deterministic: readonly DeterministicItem[]
  region: SourceRegion
  art: ReactNode
}

function SampleArt() {
  return (
    <>
      <g fill="none" stroke="#1b2133" strokeWidth="2">
        <rect x="40" y="60" width="320" height="192" />
        <circle cx="200" cy="156" r="32" />
      </g>
      <g stroke="#1b2133" strokeWidth="1" fill="none">
        <line x1="40" y1="48" x2="360" y2="48" />
        <line x1="40" y1="44" x2="40" y2="60" />
        <line x1="360" y1="44" x2="360" y2="60" />
        <line x1="372" y1="60" x2="372" y2="252" />
        <line x1="360" y1="60" x2="376" y2="60" />
        <line x1="360" y1="252" x2="376" y2="252" />
      </g>
      <g fill="#1b2133" fontFamily="monospace" fontSize="16">
        <text x="165" y="40">100 MM</text>
        <text x="384" y="160">60 MM</text>
        <text x="150" y="214">HOLE 20 MM</text>
      </g>
    </>
  )
}

/**
 * Development-only state previewer. The page loads this module with a dynamic import that is
 * guarded by import.meta.env.DEV, so production builds contain none of the sample data.
 */
export default function DevPreview({ onSelect }: { onSelect: (preview: SamplePreview) => void }) {
  const { t } = useLocale()
  return (
    <div className="space-y-2 border-t border-tp-border pt-2">
      <label className="block text-xs text-tp-text-3">
        {t('drPreviewStates')}
        <select
          data-testid="preview-state"
          className="mt-1 block min-h-9 w-full rounded border border-tp-border bg-tp-bg px-2
                     text-sm text-tp-text"
          defaultValue=""
          onChange={e => {
            if (!e.target.value) return
            onSelect({
              ai: previewState(e.target.value as PreviewStateKey),
              deterministic: SAMPLE_DETERMINISTIC,
              region: SAMPLE_REGION,
              art: <SampleArt />,
            })
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
    </div>
  )
}
