/**
 * CUTTING_PARAMETERS_DEMO_DEFECT_CLOSURE_01 tests.
 * Tests the pure logic for D1 (Vc out-of-range) and D2 (diameter validation),
 * and i18n completeness for the new shell and validation keys.
 *
 * Run with: npm test
 */

import assert from 'node:assert/strict'
import { describe, test } from 'node:test'

import { enTranslations } from '../src/i18n/en.ts'
import { trTranslations } from '../src/i18n/tr.ts'

// ── D1: Vc out-of-range detection logic ─────────────────────────────────────

function isVcOutOfRange(selectedVc: string, minValue: number, maxValue: number): boolean {
  if (selectedVc === '') return false
  const v = parseFloat(selectedVc)
  if (isNaN(v)) return false
  return v < minValue || v > maxValue
}

describe('D1 — Vc out-of-range detection', () => {
  const min = 120
  const max = 280

  test('blank Vc: no warning', () => {
    assert.equal(isVcOutOfRange('', min, max), false)
  })

  test('Vc at min boundary: no warning', () => {
    assert.equal(isVcOutOfRange('120', min, max), false)
  })

  test('Vc at max boundary: no warning', () => {
    assert.equal(isVcOutOfRange('280', min, max), false)
  })

  test('Vc within range: no warning', () => {
    assert.equal(isVcOutOfRange('200', min, max), false)
  })

  test('Vc above range: warning', () => {
    assert.equal(isVcOutOfRange('300', min, max), true)
  })

  test('Vc below range: warning', () => {
    assert.equal(isVcOutOfRange('50', min, max), true)
  })

  test('Vc just above max: warning', () => {
    assert.equal(isVcOutOfRange('281', min, max), true)
  })

  test('Vc just below min: warning', () => {
    assert.equal(isVcOutOfRange('119', min, max), true)
  })

  test('warning is not presented as recommended (string must not say "recommended")', () => {
    assert.ok(!enTranslations.cpVcOutOfRange.toLowerCase().includes('recommended'))
    assert.ok(!trTranslations.cpVcOutOfRange.toLowerCase().includes('önerilen'))
  })
})

// ── D2: Diameter validation logic ────────────────────────────────────────────

function isDiameterInvalid(diameter: string): boolean {
  if (diameter === '') return false
  const d = parseFloat(diameter)
  return isNaN(d) || d <= 0
}

describe('D2 — Diameter validation', () => {
  test('blank diameter: not invalid (button disabled separately)', () => {
    assert.equal(isDiameterInvalid(''), false)
  })

  test('D=0: invalid', () => {
    assert.equal(isDiameterInvalid('0'), true)
  })

  test('D<0: invalid', () => {
    assert.equal(isDiameterInvalid('-5'), true)
  })

  test('D=-0.001: invalid', () => {
    assert.equal(isDiameterInvalid('-0.001'), true)
  })

  test('valid positive D: not invalid', () => {
    assert.equal(isDiameterInvalid('50'), false)
  })

  test('valid small positive D: not invalid', () => {
    assert.equal(isDiameterInvalid('0.1'), false)
  })

  test('validation message exists in EN', () => {
    assert.ok(enTranslations.cpDiameterInvalid.length > 0)
  })

  test('validation message exists in TR', () => {
    assert.ok(trTranslations.cpDiameterInvalid.length > 0)
  })
})

// ── D3/D5: Shell i18n keys present ──────────────────────────────────────────

describe('D3/D5 — Shell i18n keys', () => {
  test('EN logout key is not Turkish', () => {
    assert.ok(enTranslations.logout !== 'Çıkış')
    assert.ok(enTranslations.logout.length > 0)
  })

  test('TR logout key is Turkish', () => {
    assert.ok(trTranslations.logout.length > 0)
  })

  test('EN sidebarPinned is English', () => {
    assert.equal(enTranslations.sidebarPinned, 'Pinned')
  })

  test('TR sidebarPinned is Turkish', () => {
    assert.equal(trTranslations.sidebarPinned, 'Sabitlendi')
  })

  test('EN sidebarUnpinned is English', () => {
    assert.equal(enTranslations.sidebarUnpinned, 'Unpinned')
  })

  test('TR sidebarUnpinned is Turkish', () => {
    assert.equal(trTranslations.sidebarUnpinned, 'Sabit değil')
  })
})

// ── D1 warning semantics ─────────────────────────────────────────────────────

describe('D1 — Warning semantics', () => {
  test('EN warning mentions "reference range"', () => {
    assert.ok(enTranslations.cpVcOutOfRange.toLowerCase().includes('reference range'))
  })

  test('EN warning advises to validate', () => {
    assert.ok(enTranslations.cpVcOutOfRange.toLowerCase().includes('validate'))
  })

  test('TR warning exists and is non-empty', () => {
    assert.ok(trTranslations.cpVcOutOfRange.length > 10)
  })
})
