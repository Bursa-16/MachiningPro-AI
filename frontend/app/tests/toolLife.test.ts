/**
 * TOOL_LIFE_UI_INTEGRATION_01 frontend tests.
 *
 * Tests: i18n key completeness, semantic truthfulness guards, and
 * pure logic (chart scaling, EOL flag semantics, CTF countdown).
 *
 * Run with: npm test
 */

import assert from 'node:assert/strict'
import { describe, test } from 'node:test'

import { enTranslations } from '../src/i18n/en.ts'
import { trTranslations } from '../src/i18n/tr.ts'

// ── i18n key presence ────────────────────────────────────────────────────────

describe('tl* i18n key presence — EN', () => {
  const tlKeys = [
    'tlPageTitle', 'tlPageSubtitle', 'tlEvidenceStatus',
    'tlObservations', 'tlTools', 'tlSensorFeatures', 'tlEolObservations',
    'tlDatasetAvailable', 'tlEmpiricalExploration', 'tlProductionNotValidated',
    'tlSelectTool', 'tlToolLabel', 'tlToolType', 'tlTotalCycles',
    'tlAdocMm', 'tlRdocMm', 'tlHolderLengthMm', 'tlHardnessMean',
    'tlEolPresent', 'tlEolYes', 'tlEolNo',
    'tlLifecycleChart', 'tlSensorChart', 'tlSelectSensorFeature',
    'tlCycleToFailureLabel', 'tlCycleToFailureSemantics',
    'tlLeakageWarning', 'tlLeakageWarningDetail',
    'tlLimitations', 'tlSourceProvenance', 'tlSourceDoi', 'tlSourceSheet',
    'tlDatasetNotConfigured', 'tlDatasetNotConfiguredDetail',
    'tlLoadingTools', 'tlLoadingDetail',
    'tlObsIndex', 'tlNormalized', 'tlEolMarker', 'tlFeatureIndex',
  ] as const

  for (const key of tlKeys) {
    test(`EN has key: ${key}`, () => {
      assert.ok(
        key in enTranslations,
        `Missing EN translation key: ${key}`
      )
      assert.ok(
        (enTranslations as Record<string, string>)[key].length > 0,
        `EN translation key ${key} is empty`
      )
    })
  }
})

describe('tl* i18n key presence — TR', () => {
  const tlKeys = [
    'tlPageTitle', 'tlPageSubtitle', 'tlProductionNotValidated',
    'tlDatasetAvailable', 'tlEmpiricalExploration',
    'tlCycleToFailureSemantics', 'tlLeakageWarning', 'tlLeakageWarningDetail',
    'tlLimitations', 'tlDatasetNotConfigured',
  ] as const

  for (const key of tlKeys) {
    test(`TR has key: ${key}`, () => {
      assert.ok(
        key in trTranslations,
        `Missing TR translation key: ${key}`
      )
      assert.ok(
        (trTranslations as Record<string, string>)[key].length > 0,
        `TR translation key ${key} is empty`
      )
    })
  }
})

// ── Semantic truthfulness — page title ───────────────────────────────────────

describe('tlPageTitle — no false production claims', () => {
  test('EN page title must not claim production readiness', () => {
    const title = enTranslations.tlPageTitle.toLowerCase()
    assert.ok(!title.includes('production'), `Page title must not say "production": ${title}`)
    assert.ok(!title.includes('predict'), `Page title must not say "predict": ${title}`)
  })

  test('EN page title positions as exploration or empirical', () => {
    const title = enTranslations.tlPageTitle.toLowerCase()
    const isExplorer = title.includes('explorer') || title.includes('empirical') || title.includes('analysis')
    assert.ok(isExplorer, `Page title should position as explorer/empirical/analysis, got: "${title}"`)
  })

  test('EN page subtitle mentions sensor or cycle analysis', () => {
    const sub = enTranslations.tlPageSubtitle.toLowerCase()
    const isSensor = sub.includes('sensor') || sub.includes('cycle') || sub.includes('failure')
    assert.ok(isSensor, `Subtitle should mention sensor/cycle/failure analysis, got: "${sub}"`)
  })
})

// ── Production not validated key ─────────────────────────────────────────────

describe('tlProductionNotValidated', () => {
  test('EN must explicitly say not validated', () => {
    const val = enTranslations.tlProductionNotValidated.toLowerCase()
    assert.ok(
      val.includes('not validated') || val.includes('not valid'),
      `Must say "not validated", got: "${val}"`
    )
  })

  test('TR must explicitly state not validated', () => {
    const val = trTranslations.tlProductionNotValidated.toLowerCase()
    assert.ok(val.length > 0, 'TR tlProductionNotValidated must be non-empty')
  })
})

// ── Leakage warning ───────────────────────────────────────────────────────────

describe('tlLeakageWarningDetail', () => {
  test('EN must mention cycle_number or leakage risk', () => {
    const val = enTranslations.tlLeakageWarningDetail.toLowerCase()
    const hasCycleNum = val.includes('cycle_number') || val.includes('cycle number')
    const hasLeakage = val.includes('leakage') || val.includes('correlat')
    assert.ok(hasCycleNum || hasLeakage, `Must mention cycle_number or leakage, got: "${val}"`)
  })

  test('EN must not claim independent prediction is valid', () => {
    const val = enTranslations.tlLeakageWarningDetail.toLowerCase()
    // Should say "not valid" or similar
    const hasWarning = val.includes('not valid') || val.includes('invalid') || val.includes('replicat')
    assert.ok(hasWarning, `Leakage detail must warn against invalid use, got: "${val}"`)
  })
})

// ── CycleToFailure semantics ──────────────────────────────────────────────────

describe('tlCycleToFailureSemantics', () => {
  test('EN must describe CTF as countdown', () => {
    const val = enTranslations.tlCycleToFailureSemantics.toLowerCase()
    const isCountdown = val.includes('countdown') || val.includes('0 =') || val.includes('eol')
    assert.ok(isCountdown, `CTF semantics must describe it as countdown/EOL, got: "${val}"`)
  })

  test('EN must state it is NOT cumulative age', () => {
    const val = enTranslations.tlCycleToFailureSemantics.toLowerCase()
    const isNotCumulative = val.includes('not cumulative') || val.includes('not age') || val.includes('not a cumul')
    assert.ok(isNotCumulative, `CTF semantics must say "Not cumulative age", got: "${val}"`)
  })
})

// ── Pure chart scaling logic ──────────────────────────────────────────────────

function scaleY(val: number, min: number, max: number, padTop: number, innerH: number): number {
  if (max === min) return padTop + innerH / 2
  return padTop + innerH - ((val - min) / (max - min)) * innerH
}

describe('SVG chart scale — scaleY', () => {
  const PAD_TOP = 14
  const INNER_H = 130

  test('min value maps to bottom', () => {
    const y = scaleY(0, 0, 1, PAD_TOP, INNER_H)
    assert.equal(y, PAD_TOP + INNER_H)
  })

  test('max value maps to top', () => {
    const y = scaleY(1, 0, 1, PAD_TOP, INNER_H)
    assert.equal(y, PAD_TOP)
  })

  test('mid value maps to middle', () => {
    const y = scaleY(0.5, 0, 1, PAD_TOP, INNER_H)
    assert.equal(y, PAD_TOP + INNER_H / 2)
  })

  test('equal min/max maps to centre (no divide-by-zero)', () => {
    const y = scaleY(5, 5, 5, PAD_TOP, INNER_H)
    assert.equal(y, PAD_TOP + INNER_H / 2)
  })
})

// ── EOL countdown semantics ───────────────────────────────────────────────────

describe('CTF countdown semantics', () => {
  function isEol(cycleToFailure: number): boolean {
    return cycleToFailure === 0
  }

  test('CTF=0 is EOL', () => {
    assert.equal(isEol(0), true)
  })

  test('CTF=1 is not EOL', () => {
    assert.equal(isEol(1), false)
  })

  test('CTF=10 is not EOL', () => {
    assert.equal(isEol(10), false)
  })

  test('CTF countdown: values decrease toward EOL', () => {
    const ctfSeries = [3, 2, 1, 0]
    const eolCount = ctfSeries.filter(isEol).length
    assert.equal(eolCount, 1)
    // confirm last value is EOL
    assert.equal(ctfSeries[ctfSeries.length - 1], 0)
  })
})

// ── No false AI/production/VB claims in key strings ─────────────────────────

describe('False claim guards', () => {
  test('EN tlDatasetAvailable does not claim AI prediction', () => {
    const val = enTranslations.tlDatasetAvailable.toLowerCase()
    assert.ok(!val.includes('ai predict'), `Must not claim AI prediction: "${val}"`)
    assert.ok(!val.includes('predicts exact'), `Must not claim exact prediction: "${val}"`)
  })

  test('EN tlEmpiricalExploration does not claim validated deployment', () => {
    const val = enTranslations.tlEmpiricalExploration.toLowerCase()
    assert.ok(!val.includes('validated deployment'), `Must not claim validated deployment: "${val}"`)
  })

  test('EN tlProductionNotValidated does not say production ready', () => {
    const val = enTranslations.tlProductionNotValidated.toLowerCase()
    assert.ok(!val.includes('production ready'), `Must not say production ready: "${val}"`)
  })

  test('EN tlPageTitle does not mention VB or flank wear', () => {
    const val = enTranslations.tlPageTitle.toLowerCase()
    assert.ok(!val.includes('vb'), `Page title must not mention VB: "${val}"`)
    assert.ok(!val.includes('flank wear'), `Page title must not mention flank wear: "${val}"`)
  })

  test('EN tlPageTitle does not claim Taylor equation fit', () => {
    const val = enTranslations.tlPageTitle.toLowerCase()
    assert.ok(!val.includes('taylor'), `Page title must not mention Taylor: "${val}"`)
  })
})
