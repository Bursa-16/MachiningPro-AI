import type { ReactNode } from 'react'
import { useLocale } from '../../i18n'
import type { SourceRegion } from '../../types/drawingReview.ts'

const SAMPLE_WIDTH = 480
const SAMPLE_HEIGHT = 320

/** The real uploaded page: size in PDF points and the backend-rendered preview image. */
export interface LivePage {
  widthPt: number
  heightPt: number
  imageUrl: string | null
}

/**
 * Viewer for the uploaded drawing (live) or the development sample. The dashed overlay is
 * the deterministic "Source Region" the AI suggestion is associated with, in the page's own
 * point coordinates. It is never drawn as an exact detection box: the model supplied none.
 */
export default function DrawingViewer({
  loaded,
  region,
  showRegion,
  live = null,
  art = null,
}: {
  loaded: boolean
  region: SourceRegion | null
  showRegion: boolean
  live?: LivePage | null
  /** Development sample artwork (injected so production builds never contain it). */
  art?: ReactNode
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

  const width = live ? live.widthPt : SAMPLE_WIDTH
  const height = live ? live.heightPt : SAMPLE_HEIGHT
  const unit = width / SAMPLE_WIDTH // keeps the label legible at any page size
  const overlay = showRegion && region

  return (
    <figure className="m-0">
      <svg
        data-testid={live ? 'drawing-live' : 'drawing-svg'}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={t('drDrawing')}
        className="block h-auto w-full rounded-md border border-tp-border bg-[#f4f6fb]"
      >
        {live ? (
          live.imageUrl && (
            <image href={live.imageUrl} x="0" y="0" width={width} height={height} />
          )
        ) : (
          art
        )}
        {overlay && (
          <g data-testid="source-region-overlay">
            <rect
              x={region.x0}
              y={region.top}
              width={region.x1 - region.x0}
              height={region.bottom - region.top}
              fill="rgba(124,92,191,0.08)"
              stroke="#7c5cbf"
              strokeWidth={2 * unit}
              strokeDasharray={`${8 * unit} ${5 * unit}`}
            />
            <rect
              x={region.x0 + 8 * unit}
              y={region.top + 8 * unit}
              width={104 * unit}
              height={22 * unit}
              rx={3 * unit}
              fill="#2a1e40"
            />
            <text
              x={region.x0 + 16 * unit}
              y={region.top + 23 * unit}
              fill="#d9ccf5"
              fontSize={12 * unit}
              fontFamily="sans-serif"
            >
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
