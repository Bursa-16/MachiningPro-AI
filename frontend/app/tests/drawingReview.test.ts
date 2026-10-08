// HUMAN_CONFIRMATION_UI_01 tests. Run with `npm test` (Node's built-in runner, no new
// dependencies). Rendering tests bundle the real components with Vite's SSR build and
// render them to static HTML. No real AI service is ever contacted.

import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { before, after, describe, test } from 'node:test'
import { build } from 'vite'

import { enTranslations } from '../src/i18n/en.ts'
import { trTranslations } from '../src/i18n/tr.ts'
import {
  ANALYSIS_PHASES,
  MAX_REVIEW_VALUE_CHARS,
  boxBasisLabelKey,
  claimsExactLocalization,
  classifyAiFailure,
  confirmedValue,
  countByStatus,
  createReviewState,
  reviewReducer,
  validateEditedValue,
} from '../src/lib/drawingReview.ts'
import {
  PREVIEW_STATE_KEYS,
  SAMPLE_DETERMINISTIC,
  SAMPLE_FINDINGS,
  SAMPLE_REGION,
  previewState,
} from '../src/data/sampleDrawingReview.ts'
import type { ReviewAction } from '../src/types/drawingReview.ts'

const here = dirname(fileURLToPath(import.meta.url))
const appRoot = join(here, '..')
const NOW = '2026-10-08T12:00:00.000Z'
const [FIRST, SECOND] = SAMPLE_FINDINGS

const act = (type: 'ACCEPT' | 'REJECT', id = FIRST.evidence_id): ReviewAction => ({
  type,
  evidence_id: id,
  reviewed_by: 'engineer-1',
  reviewed_at: NOW,
})
const edit = (value: string, id = FIRST.evidence_id): ReviewAction => ({
  type: 'EDIT',
  evidence_id: id,
  value,
  reviewed_by: 'engineer-1',
  reviewed_at: NOW,
})

// ---------------------------------------------------------------------------
// Rendering harness: bundle the real components once, import the bundle.
// ---------------------------------------------------------------------------

type Renderers = typeof import('./render-entry.tsx')
let render: Renderers
let workDir = ''

before(async () => {
  workDir = mkdtempSync(join(tmpdir(), 'mp-ui01-'))
  const result = await build({
    root: appRoot,
    logLevel: 'silent',
    configFile: join(appRoot, 'vite.config.ts'),
    build: {
      ssr: join(appRoot, 'tests', 'render-entry.tsx'),
      write: false,
      minify: false,
      rollupOptions: { output: { format: 'esm' } },
    },
    ssr: { noExternal: true },
  })
  const outputs = Array.isArray(result) ? result : [result]
  const chunk = (outputs[0] as { output: { code?: string; type: string }[] }).output.find(
    item => item.type === 'chunk',
  )
  assert.ok(chunk?.code, 'SSR bundle produced')
  const file = join(workDir, 'render.mjs')
  writeFileSync(file, chunk.code)
  render = (await import(pathToFileURL(file).href)) as Renderers
})

after(() => {
  if (workDir) rmSync(workDir, { recursive: true, force: true })
})

const pending = (id = FIRST.evidence_id) => createReviewState(SAMPLE_FINDINGS)[id]

// ---------------------------------------------------------------------------
// Review logic
// ---------------------------------------------------------------------------

describe('review state machine', () => {
  test('UI01-T03 every finding starts pending and nothing is accepted automatically', () => {
    const state = createReviewState(SAMPLE_FINDINGS)
    assert.deepEqual(countByStatus(state), {
      PENDING_REVIEW: 2,
      ACCEPTED: 0,
      REJECTED: 0,
      EDITED: 0,
    })
    for (const record of Object.values(state)) {
      assert.equal(confirmedValue(record), null)
      assert.equal(record.reviewed_by, null)
      assert.equal(record.history.length, 0)
    }
  })

  test('UI01-T16 there is no bulk or automatic acceptance action', () => {
    const source = readFileSync(join(appRoot, 'src', 'lib', 'drawingReview.ts'), 'utf8')
    assert.doesNotMatch(source, /ACCEPT_ALL|BULK|AUTO_ACCEPT|autoAccept/i)
    const state = createReviewState(SAMPLE_FINDINGS)
    const unknown = { type: 'ACCEPT_ALL' } as unknown as ReviewAction
    assert.equal(reviewReducer(state, unknown), state)
  })

  test('UI01-T04 accept confirms the AI value without changing it', () => {
    const state = reviewReducer(createReviewState(SAMPLE_FINDINGS), act('ACCEPT'))
    const record = state[FIRST.evidence_id]
    assert.equal(record.status, 'ACCEPTED')
    assert.equal(record.original_ai_value, '100 MM')
    assert.equal(record.reviewed_value, null)
    assert.equal(confirmedValue(record), '100 MM')
    assert.equal(record.reviewed_by, 'engineer-1')
    assert.equal(record.reviewed_at, NOW)
    assert.equal(state[SECOND.evidence_id].status, 'PENDING_REVIEW')
  })

  test('UI01-T05 / T09 reject is recorded and the original stays auditable', () => {
    const state = reviewReducer(createReviewState(SAMPLE_FINDINGS), act('REJECT'))
    const record = state[FIRST.evidence_id]
    assert.equal(record.status, 'REJECTED')
    assert.equal(record.original_ai_value, '100 MM')
    assert.equal(confirmedValue(record), null)
    assert.equal(record.history.length, 1)
    assert.equal(record.history[0].status, 'REJECTED')
  })

  test('UI01-T06 / T07 edit stores the human value separately from the AI value', () => {
    const state = reviewReducer(createReviewState(SAMPLE_FINDINGS), edit('  100 mm  '))
    const record = state[FIRST.evidence_id]
    assert.equal(record.status, 'EDITED')
    assert.equal(record.original_ai_value, '100 MM')
    assert.equal(record.reviewed_value, '100 mm')
    assert.equal(confirmedValue(record), '100 mm')
    assert.equal(FIRST.original_value, '100 MM', 'the AI finding itself is untouched')
  })

  test('invalid edits change nothing', () => {
    const state = createReviewState(SAMPLE_FINDINGS)
    for (const bad of ['', '   ', '100 MM', 'x'.repeat(MAX_REVIEW_VALUE_CHARS + 1), 'a\u0000b', 'a\nb']) {
      assert.equal(reviewReducer(state, edit(bad)), state, JSON.stringify(bad))
    }
    assert.deepEqual(validateEditedValue('', 'x'), { ok: false, reason: 'BLANK' })
    assert.deepEqual(validateEditedValue('x', 'x'), { ok: false, reason: 'UNCHANGED' })
    assert.deepEqual(validateEditedValue('y', 'x'), { ok: true, value: 'y' })
  })

  test('unknown evidence ids are ignored', () => {
    const state = createReviewState(SAMPLE_FINDINGS)
    assert.equal(reviewReducer(state, act('ACCEPT', 'nope')), state)
  })

  test('the reducer is pure and history is append-only', () => {
    const initial = createReviewState(SAMPLE_FINDINGS)
    const snapshot = JSON.stringify(initial)
    const one = reviewReducer(initial, act('ACCEPT'))
    const two = reviewReducer(one, edit('100 mm'))
    const three = reviewReducer(two, act('REJECT'))
    assert.equal(JSON.stringify(initial), snapshot)
    assert.deepEqual(
      three[FIRST.evidence_id].history.map(event => event.status),
      ['ACCEPTED', 'EDITED', 'REJECTED'],
    )
    assert.equal(three[FIRST.evidence_id].status, 'REJECTED')
    assert.equal(three[FIRST.evidence_id].reviewed_value, null)
    assert.equal(two[FIRST.evidence_id].history.length, 2)
  })

  test('UI01-T08 accepting AI never touches the deterministic result', () => {
    const deterministic = JSON.stringify(SAMPLE_DETERMINISTIC)
    let state = createReviewState(SAMPLE_FINDINGS)
    state = reviewReducer(state, act('ACCEPT'))
    state = reviewReducer(state, edit('999 mm', SECOND.evidence_id))
    assert.equal(JSON.stringify(SAMPLE_DETERMINISTIC), deterministic)
    assert.equal(SAMPLE_DETERMINISTIC[0].value, '100 mm')
    assert.ok(!('deterministic' in state[FIRST.evidence_id]))
    const reducerSource = readFileSync(join(appRoot, 'src', 'lib', 'drawingReview.ts'), 'utf8')
    assert.doesNotMatch(reducerSource, /DeterministicItem|SAMPLE_DETERMINISTIC/)
  })
})

describe('provenance and wording', () => {
  test('UI01-T01 / T17 sample findings are ADVISORY with provider and model provenance', () => {
    for (const finding of SAMPLE_FINDINGS) {
      assert.equal(finding.authority, 'ADVISORY')
      assert.equal(finding.provider_id, 'ollama.chat')
      assert.equal(finding.model_id, 'granite3.2-vision:2b')
      assert.equal(finding.box_basis, 'REGION_EXTENT')
    }
  })

  test('UI01-T10 REGION_EXTENT is a Source Region, never an exact localization', () => {
    assert.equal(boxBasisLabelKey('REGION_EXTENT'), 'drSourceRegion')
    assert.equal(claimsExactLocalization('REGION_EXTENT'), false)
    assert.equal(claimsExactLocalization('MODEL_PIXEL_BOX'), true)
    assert.equal(enTranslations.drSourceRegion, 'Source Region')
    for (const dictionary of [enTranslations, trTranslations]) {
      const text = Object.entries(dictionary)
        .filter(([key]) => key.startsWith('dr'))
        .map(([, value]) => value)
        .join(' ')
      assert.doesNotMatch(text, /exact (ai )?(detection|text) box/i)
    }
    assert.match(enTranslations.drSourceRegionNote, /not with an exact text position/)
  })

  test('required review wording matches the product terms', () => {
    assert.equal(enTranslations.drDeterministicResult, 'Deterministic Result')
    assert.equal(enTranslations.drAiSuggestion, 'AI Suggestion')
    assert.equal(enTranslations.drHumanConfirmed, 'Human Confirmed')
    assert.equal(enTranslations.drReviewRequired, 'AI suggestions require human review before use.')
  })

  test('every new English key has a non-empty Turkish translation and vice versa', () => {
    const en = Object.keys(enTranslations).filter(key => key.startsWith('dr'))
    const tr = Object.keys(trTranslations).filter(key => key.startsWith('dr'))
    assert.deepEqual(en.sort(), tr.sort())
    assert.ok(en.length >= 60)
    for (const key of en) {
      assert.ok((enTranslations as Record<string, string>)[key].trim(), key)
      assert.ok((trTranslations as Record<string, string>)[key].trim(), key)
    }
  })
})

describe('AI failure mapping and states', () => {
  test('backend diagnostics map to UI failure kinds', () => {
    assert.equal(classifyAiFailure(['VLM_DISABLED']), 'DISABLED')
    assert.equal(classifyAiFailure(['VLM_UNAVAILABLE']), 'OLLAMA_UNAVAILABLE')
    assert.equal(classifyAiFailure(['VLM_TIMEOUT']), 'TIMEOUT')
    assert.equal(classifyAiFailure(['VLM_BUDGET_EXHAUSTED']), 'TIMEOUT')
    assert.equal(classifyAiFailure(['VLM_REQUEST_REJECTED']), 'MODEL_UNAVAILABLE')
    assert.equal(classifyAiFailure(['VLM_RESPONSE_BOX']), 'VALIDATION_FAILED')
    assert.equal(classifyAiFailure(['VLM_RESPONSE_UNKNOWN_FIELD']), 'VALIDATION_FAILED')
    assert.equal(classifyAiFailure(['something else']), 'UNKNOWN')
    assert.equal(classifyAiFailure([]), 'UNKNOWN')
  })

  test('every preview state is defined and running phases are the four real steps', () => {
    for (const key of PREVIEW_STATE_KEYS) assert.ok(previewState(key).kind)
    assert.equal(ANALYSIS_PHASES.length, 4)
  })
})

// ---------------------------------------------------------------------------
// Rendered components
// ---------------------------------------------------------------------------

describe('rendered review card', () => {
  test('UI01-T01 / T03 / T17 AI card is labelled AI Suggestion, pending, with provenance', () => {
    const html = render.renderFindingCard(FIRST, pending())
    assert.match(html, /data-badge="AI"/)
    assert.match(html, /AI Suggestion/)
    assert.match(html, /data-status="PENDING_REVIEW"/)
    assert.match(html, /Pending Review/)
    assert.match(html, /ollama\.chat/)
    assert.match(html, /granite3\.2-vision:2b/)
    assert.match(html, /100 MM/)
    assert.doesNotMatch(html, /Human Confirmed/)
  })

  test('review actions are present and keyboard-reachable buttons', () => {
    const html = render.renderFindingCard(FIRST, pending())
    for (const label of ['Accept', 'Edit', 'Reject']) {
      assert.match(html, new RegExp(`<button[^>]*type="button"[\\s\\S]*?${label}`))
    }
  })

  test('UI01-T10 the region is shown as Source Region, not as an exact box', () => {
    const html = render.renderFindingCard(FIRST, pending())
    assert.match(html, /Source Region · vlm-region-1/)
    assert.doesNotMatch(html, /exact/i)
  })

  test('UI01-T04 accepted card shows Human Confirmed and keeps the AI value', () => {
    const record = reviewReducer(createReviewState(SAMPLE_FINDINGS), act('ACCEPT'))[FIRST.evidence_id]
    const html = render.renderFindingCard(FIRST, record)
    assert.match(html, /data-status="ACCEPTED"/)
    assert.match(html, /data-badge="CONFIRMED"/)
    assert.match(html, /data-badge="AI"/, 'the AI provenance badge stays')
    assert.match(html, /AI original value/)
    assert.match(html, /engineer-1/)
  })

  test('UI01-T06 / T07 edited card shows both values, struck-through original', () => {
    const record = reviewReducer(createReviewState(SAMPLE_FINDINGS), edit('100 mm'))[FIRST.evidence_id]
    const html = render.renderFindingCard(FIRST, record)
    assert.match(html, /data-badge="EDITED"/)
    assert.match(html, /Edited by Human/)
    assert.match(html, /data-testid="ai-original-value"[^>]*line-through[^>]*>100 MM</)
    assert.match(html, /data-testid="human-value"[^>]*>100 mm</)
  })

  test('UI01-T05 / T09 rejected card stays visible with its original value', () => {
    const record = reviewReducer(createReviewState(SAMPLE_FINDINGS), act('REJECT'))[FIRST.evidence_id]
    const html = render.renderFindingCard(FIRST, record)
    assert.match(html, /data-status="REJECTED"/)
    assert.match(html, /data-badge="REJECTED"/)
    assert.match(html, />100 MM</)
    assert.doesNotMatch(html, /Human Confirmed/)
  })

  test('the review history is rendered for audit', () => {
    let state = reviewReducer(createReviewState(SAMPLE_FINDINGS), act('ACCEPT'))
    state = reviewReducer(state, edit('100 mm'))
    const html = render.renderFindingCard(FIRST, state[FIRST.evidence_id])
    assert.match(html, /data-testid="review-history"/)
    assert.match(html, /ACCEPTED/)
    assert.match(html, /EDITED → 100 mm/)
  })

  test('badges are distinct for deterministic, AI, human, rejected, edited and pending', () => {
    const kinds = ['DETERMINISTIC', 'AI', 'CONFIRMED', 'REJECTED', 'EDITED', 'PENDING'] as const
    const labels = kinds.map(kind => render.renderBadge(kind).replace(/<[^>]+>/g, ''))
    assert.deepEqual(labels, [
      'Deterministic Result',
      'AI Suggestion',
      'Human Confirmed',
      'Rejected',
      'Edited by Human',
      'Pending Review',
    ])
  })
})

describe('rendered states', () => {
  test('UI01-T13 running state shows steps and a spinner but no percentage', () => {
    for (const key of ['RUNNING_1', 'RUNNING_2', 'RUNNING_3', 'RUNNING_4'] as const) {
      const html = render.renderAiStatus(previewState(key))
      assert.match(html, /data-state="RUNNING"/)
      assert.match(html, /animate-spin/)
      assert.match(html, /Preparing drawing\.\.\./)
      assert.match(html, /Validating AI response\.\.\./)
      assert.match(html, /several minutes/)
      assert.doesNotMatch(html, /\d\s?%/)
      assert.doesNotMatch(html, /<progress|role="progressbar"|aria-valuenow/)
    }
    const running = render.renderAiStatus(previewState('RUNNING_3'))
    assert.match(running, /data-current="true"[^>]*>● AI analysis in progress/)
    assert.doesNotMatch(running, /cancel/i)
  })

  test('UI01-T11 / T14 / T15 every failure keeps deterministic results available', () => {
    const expected: [Parameters<typeof previewState>[0], RegExp][] = [
      ['TIMEOUT', /AI analysis timed out/],
      ['OLLAMA', /Ollama\) is unavailable/],
      ['MODEL', /model is unavailable or was rejected/],
      ['VALIDATION', /failed validation and was discarded/],
      ['DISABLED', /AI analysis is disabled/],
      ['NOT_CONNECTED', /not connected in this build/],
    ]
    for (const [key, pattern] of expected) {
      const html = render.renderAiStatus(previewState(key))
      assert.match(html, /data-state="FAILED"/)
      assert.match(html, pattern)
      assert.match(html, /Deterministic results remain available/)
    }
  })

  test('UI01-T12 no-findings state', () => {
    const html = render.renderAiStatus(previewState('EMPTY'))
    assert.match(html, /data-state="NO_FINDINGS"/)
    assert.match(html, /no items in the analysed region/)
  })

  test('UI01-T10 the viewer labels the overlay Source Region and explains it', () => {
    const on = render.renderViewer(true, SAMPLE_REGION, true)
    assert.match(on, /data-testid="source-region-overlay"/)
    assert.match(on, />Source Region</)
    assert.match(on, /not with an exact text position/)
    const off = render.renderViewer(true, SAMPLE_REGION, false)
    assert.doesNotMatch(off, /source-region-overlay/)
    assert.match(render.renderViewer(false, null, false), /No drawing loaded/)
  })
})

describe('rendered page', () => {
  test('UI01-T11 without AI the page still renders and says so honestly', () => {
    const html = render.renderPage('engineer-1')
    assert.match(html, /Technical Drawing Intelligence/)
    assert.match(html, /AI suggestions require human review before use\./)
    assert.match(html, /AI analysis is not connected in this build/)
    assert.match(html, /Deterministic results remain available/)
    assert.match(html, /Load synthetic sample/)
    assert.match(html, /No deterministic results for this drawing/)
    assert.doesNotMatch(html, /finding-card/)
  })

  test('UI01-T18 the layout is responsive and avoids horizontal overflow classes', () => {
    const html = render.renderPage(null)
    assert.match(html, /grid-cols-1[^"]*lg:grid-cols-\[minmax\(0,1fr\)_400px\]/)
    assert.match(html, /min-w-0/)
    assert.doesNotMatch(html, /overflow-x-scroll|min-w-\[\d{4,}px\]/)
    const card = render.renderFindingCard(FIRST, pending())
    assert.match(card, /min-h-11/, 'touch-sized actions below the sm breakpoint')
    assert.match(card, /break-words|break-all/)
  })

  test('the page source never auto-accepts and has no cancel for inference', () => {
    const page = readFileSync(join(appRoot, 'src', 'pages', 'TechnicalDrawingIntelligencePage.tsx'), 'utf8')
    assert.doesNotMatch(page, /type: 'ACCEPT'[\s\S]{0,200}useEffect/)
    assert.doesNotMatch(page, /useEffect/)
    assert.doesNotMatch(page, /fetch\(|axios|XMLHttpRequest/, 'no network from this slice')
  })
})

test('UI01 the frontend logic and sample data contain no AI service endpoint', () => {
  for (const file of [
    join('src', 'data', 'sampleDrawingReview.ts'),
    join('src', 'lib', 'drawingReview.ts'),
  ]) {
    const source = readFileSync(join(appRoot, file), 'utf8')
    assert.doesNotMatch(source, /11434|api\.openai|api\.anthropic|http:\/\/|https:\/\//, file)
  }
})
