import { useLocale } from '../../i18n'
import type { SourceRegion } from '../../types/drawingReview.ts'

const WIDTH = 480
const HEIGHT = 320

/**
 * Viewer for the synthetic sample drawing. The dashed overlay is the deterministic
 * "Source Region" the AI suggestion is associated with. It is never drawn as an exact
 * detection box, because the model supplied no coordinates.
 */
export default function DrawingViewer({
  loaded,
  region,
  showRegion,
}: {
  loaded: boolean
  region: SourceRegion | null
  showRegion: boolean
}) {
  const { t } = useLocale()

  if (!loaded) {
    return (
      <div
        data-testid="drawing-empty"
        className="flex aspect-[3/2] w-full items-center justify-center rounded-md border
                   border-dashed border-tp-border-strong bg-tp-surface-2 p-4 text-center
                   text-sm text-tp-text-3"
      >
        {t('drNoDrawing')}
      </div>
    )
  }

  const overlay = showRegion && region
  return (
    <figure className="m-0">
      <svg
        data-testid="drawing-svg"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={t('drSampleNote')}
        className="block h-auto w-full rounded-md border border-tp-border bg-[#f4f6fb]"
      >
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
        {overlay && (
          <g data-testid="source-region-overlay">
            <rect
              x={region.x0 + 2}
              y={region.top + 2}
              width={region.x1 - region.x0 - 4}
              height={region.bottom - region.top - 4}
              fill="rgba(124,92,191,0.08)"
              stroke="#7c5cbf"
              strokeWidth="2"
              strokeDasharray="8 5"
            />
            <rect x="8" y="8" width="104" height="22" rx="3" fill="#2a1e40" />
            <text x="16" y="23" fill="#d9ccf5" fontSize="12" fontFamily="sans-serif">
              {t('drSourceRegion')}
            </text>
          </g>
        )}
      </svg>
      <figcaption className="mt-1.5 text-xs text-tp-text-3">
        {overlay ? t('drSourceRegionNote') : t('drSelectFinding')}
      </figcaption>
    </figure>
  )
}
