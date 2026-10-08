// Bundled by tests/drawingReview.test.ts (via Vite SSR build) and rendered to static HTML.
// No browser, no network and no model is involved.

import { renderToStaticMarkup } from 'react-dom/server'
import AiStatus from '../src/components/drawing-review/AiStatus'
import DrawingViewer from '../src/components/drawing-review/DrawingViewer'
import FindingCard from '../src/components/drawing-review/FindingCard'
import AuthorityBadge, { type BadgeKind } from '../src/components/drawing-review/AuthorityBadge'
import { LocaleProvider } from '../src/i18n'
import TechnicalDrawingIntelligencePage from '../src/pages/TechnicalDrawingIntelligencePage'
import type {
  AdvisoryFinding,
  AiAnalysisState,
  ReviewRecord,
  SourceRegion,
} from '../src/types/drawingReview.ts'

const wrap = (node: React.ReactNode) =>
  renderToStaticMarkup(<LocaleProvider>{node}</LocaleProvider>)

const noop = () => {}

export const renderFindingCard = (finding: AdvisoryFinding, record: ReviewRecord, selected = false) =>
  wrap(
    <FindingCard
      finding={finding}
      record={record}
      selected={selected}
      onSelect={noop}
      onAccept={noop}
      onReject={noop}
      onEdit={noop}
    />,
  )

export const renderAiStatus = (state: AiAnalysisState) => wrap(<AiStatus state={state} />)

export const renderBadge = (kind: BadgeKind) => wrap(<AuthorityBadge kind={kind} />)

export const renderViewer = (loaded: boolean, region: SourceRegion | null, showRegion: boolean) =>
  wrap(<DrawingViewer loaded={loaded} region={region} showRegion={showRegion} />)

export const renderPage = (reviewer: string | null) =>
  wrap(<TechnicalDrawingIntelligencePage reviewer={reviewer} />)
