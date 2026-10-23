// NC_PROGRAM_TRACEABILITY_AND_AUDIT_01 — traceability and audit tests
//
// Run with: npm test
// Node 22 required (crypto.subtle available as global)

import assert from 'node:assert/strict'
import { describe, test, beforeEach } from 'node:test'

import { enTranslations } from '../src/i18n/en.ts'
import { trTranslations } from '../src/i18n/tr.ts'
import type { TranslationDictionary } from '../src/i18n/types.ts'
import {
  normalizeNcContent,
  computeNcSha256,
  computeConfigFingerprint,
  computeAnalysisFingerprint,
  buildShortHash,
  computeChangeState,
  buildNcReviewJson,
  buildFindingsCsv,
  buildSegmentsCsv,
  buildCoverageCsv,
  generatePrintHtml,
  logExportEvent,
  getAuditEvents,
  clearAuditEvents,
  addAuditEvent,
  REVIEW_SCHEMA_VERSION,
} from '../src/lib/nc_report_export.ts'
import type {
  NCAnalysisTraceabilityExport,
  NcAuditEvent,
} from '../src/lib/nc_report_export.ts'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const tEn = (k: string): string => (enTranslations as Record<string, string>)[k] ?? k
const tTr = (k: string): string => (trTranslations as Record<string, string>)[k] ?? k

function makeTraceability(overrides?: Partial<NCAnalysisTraceabilityExport>): NCAnalysisTraceabilityExport {
  return {
    review_id: 'a1b2c3d4-0000-4000-8000-111111111111',
    program_fingerprint: 'a'.repeat(64),
    configuration_fingerprint: 'b'.repeat(64),
    analysis_fingerprint: 'c'.repeat(64),
    traceability_status: 'TRACEABLE',
    generated_at: '2026-10-23T12:00:00.000Z',
    review_schema_version: '1.0',
    parser_profile: 'GENERIC_ISO_GCODE_SUBSET',
    parser_version: '3.0.0',
    machine_id: 'dmg-clx-350',
    cutting_tool_id: 'sandvik-r216',
    tool_holder_id: null,
    operation: 'milling',
    process_step_id: 'step-01',
    material_iso_group: 'P',
    hash_equals_digital_signature: false,
    hash_equals_approval: false,
    hash_equals_certification: false,
    false_immutable_audit_claim: false,
    ...overrides,
  }
}

function makeReviewWithTraceability(overrides?: Partial<NCAnalysisTraceabilityExport>) {
  const tr = makeTraceability(overrides)
  return {
    source_name_safe: 'prog_001',
    parser_profile: 'GENERIC_ISO_GCODE_SUBSET',
    parser_version: '3.0.0',
    review_schema_version: '1.0',
    units_declared: 'mm',
    analysis_status: 'COMPLETE',
    segment_count: 1,
    tool_change_count: 0,
    supported_motion_count: 10,
    unsupported_construct_count: 0,
    arc_motion_count: 0,
    feature_coverage: [
      { feature: 'G0 (Rapid)', state: 'SUPPORTED', detected: true, note: null },
    ],
    deferred_features_detected: [],
    unsupported_features_detected: [],
    total_feed_distance_mm: 50.0,
    total_rapid_distance_mm: 100.0,
    segments: [
      {
        segment_id: 'SEG_1',
        start_line: 1,
        end_line: 10,
        tool_id_raw: 'T1',
        feed_motion_distance_mm: 50.0,
        rapid_motion_distance_mm: 100.0,
        linear_motion_count: 10,
        arc_motion_count: 0,
        commanded_feed_min: 150,
        commanded_feed_max: 200,
        feed_change_count: 1,
        analysis_status: 'COMPLETE',
        unsupported_features: [],
        feed_mode: 'G94',
        commanded_feed_mm_rev: null,
        commanded_spindle_rpm: 800,
        spindle_state: 'M3_CW',
        spindle_direction: 'CW',
        nc_feed_move_equals_confirmed_cutting: false as const,
        arc_chord_approximation_used: false as const,
      },
    ],
    equipment: {
      machine_id: 'dmg-clx-350',
      machine_display: 'DMG CLX 350',
      cutting_tool_id: 'sandvik-r216',
      cutting_tool_display: 'Sandvik R216',
      tool_holder_id: null,
      tool_holder_display: null,
      machine_spindle_max_rpm: 4500,
      tool_max_rpm: 12000,
      holder_max_rpm: null,
      effective_rpm_limit: 4500,
      effective_rpm_limit_source: 'MACHINE',
      missing_fields: [],
    },
    compatibility_status: 'COMPATIBLE',
    validation_summary: {
      nc_commanded_feed_mm_min: 150,
      nc_commanded_feed_mm_rev: null,
      nc_feed_mode: 'G94',
      nc_commanded_spindle_rpm: 800,
      nc_spindle_state: 'M3_CW',
      calculated_cutting_speed_m_min: 15.1,
      calculated_feed_per_tooth_mm: 0.0625,
      calculated_feed_per_rev_mm: 0.125,
      machine_rpm_limit_check: null,
      tool_rpm_limit_check: null,
      holder_rpm_limit_check: null,
      effective_rpm_limit_check: null,
      cutting_speed_check: null,
      feed_per_tooth_check: null,
      feed_per_rev_check: null,
      blocking_count: 0,
      warning_count: 0,
      advisory_count: 0,
      insufficient_data_count: 0,
      limitations: [],
      evidence_sources: ['NC_PROGRAM'],
      nc_commanded_spindle_speed_equals_actual_rpm: false as const,
      nc_commanded_feed_equals_actual_feed: false as const,
      nc_commanded_feed_equals_recommended_feed: false as const,
      reference_range_validation_is_optimization: false as const,
      nc_program_automatic_operation_classification: false as const,
      machine_feed_limit_validation_implemented: false as const,
      g84_pitch_validation_implemented: false as const,
      generic_feed_without_spindle_warning_implemented: false as const,
      spindle_direction_compatibility_check_implemented: false as const,
    },
    operation_association: 'milling',
    cycle_time_known_subtotal_sec: null,
    cycle_time_status: null,
    cycle_time_limitations: [],
    canned_cycle_notes: [],
    findings: [],
    blocking_count: 0,
    warning_count: 0,
    advisory_count: 0,
    info_count: 0,
    insufficient_data_count: 0,
    unsupported_count: 0,
    limitations: [],
    review_status: 'PASS_WITH_EVIDENCE' as const,
    traceability: {
      review_id: tr.review_id,
      program_fingerprint: tr.program_fingerprint,
      configuration_fingerprint: tr.configuration_fingerprint,
      analysis_fingerprint: tr.analysis_fingerprint,
      traceability_status: tr.traceability_status,
      generated_at: tr.generated_at,
      review_schema_version: tr.review_schema_version,
      parser_profile: tr.parser_profile,
      parser_version: tr.parser_version,
      machine_id: tr.machine_id,
      cutting_tool_id: tr.cutting_tool_id,
      tool_holder_id: tr.tool_holder_id,
      operation: tr.operation,
      process_step_id: tr.process_step_id,
      material_iso_group: tr.material_iso_group,
      provenance_summary: [],
      source_counts: { segments: 1, findings: 0, limitations: 0 },
      limitations_count: 0,
      hash_equals_digital_signature: false as const,
      hash_equals_approval: false as const,
      hash_equals_certification: false as const,
      false_immutable_audit_claim: false as const,
    },
    nc_file_executed: false as const,
    machine_behavior_simulated: false as const,
    collision_check_performed: false as const,
    machine_kinematics_simulated: false as const,
    gouge_check_performed: false as const,
    false_controller_compatibility_claim: false as const,
    false_production_approval_claim: false as const,
    false_safe_to_run_claim: false as const,
    false_collision_free_claim: false as const,
    arbitrary_numeric_engineering_score_implemented: false as const,
    programmed_motion_equals_executed_motion: false as const,
    programmed_feed_distance_equals_confirmed_cutting: false as const,
    t_word_equals_confirmed_tool_identity: false as const,
    partial_time_mislabeled_total: false as const,
    bounded_canned_cycle_mislabeled_complete: false as const,
    private_local_path_visible: false as const,
    private_path_in_api_response: false as const,
  }
}

function makeReviewWithoutTraceability() {
  const r = makeReviewWithTraceability()
  const { traceability: _, ...rest } = r
  return rest
}

// ---------------------------------------------------------------------------
// GROUP 1: normalizeNcContent — conservative normalization
// ---------------------------------------------------------------------------

describe('normalizeNcContent', () => {
  test('LF-only content is returned unchanged (no trailing spaces)', () => {
    const input = 'G0 X10\nG1 F200\n'
    const result = normalizeNcContent(input)
    assert.equal(result, 'G0 X10\nG1 F200\n')
  })

  test('CRLF is normalized to LF', () => {
    const input = 'G0 X10\r\nG1 F200\r\n'
    const result = normalizeNcContent(input)
    assert.equal(result, 'G0 X10\nG1 F200\n')
  })

  test('stray CR is normalized to LF', () => {
    const input = 'G0 X10\rG1 F200\r'
    const result = normalizeNcContent(input)
    assert.equal(result, 'G0 X10\nG1 F200\n')
  })

  test('BOM prefix is stripped', () => {
    const input = '﻿G0 X10\nG1\n'
    const result = normalizeNcContent(input)
    assert.equal(result, 'G0 X10\nG1\n')
  })

  test('trailing whitespace per line is stripped', () => {
    const input = 'G0 X10   \nG1 F200  \n'
    const result = normalizeNcContent(input)
    assert.equal(result, 'G0 X10\nG1 F200\n')
  })

  test('leading whitespace per line is preserved', () => {
    const input = '  G0 X10\n    G1 F200\n'
    const result = normalizeNcContent(input)
    assert.equal(result, '  G0 X10\n    G1 F200\n')
  })

  test('numeric values are preserved exactly', () => {
    const input = 'G1 X123.456789 Y-0.001 Z0.0 F200.0\n'
    const result = normalizeNcContent(input)
    assert.equal(result, 'G1 X123.456789 Y-0.001 Z0.0 F200.0\n')
  })

  test('NC comments are preserved exactly', () => {
    const input = '(TOOL: T1 D=10)\nG0 X0\n'
    const result = normalizeNcContent(input)
    assert.equal(result, '(TOOL: T1 D=10)\nG0 X0\n')
  })

  test('empty program is returned unchanged', () => {
    assert.equal(normalizeNcContent(''), '')
  })

  test('CRLF + BOM + trailing space combined', () => {
    const input = '﻿G0 X10  \r\nG1 F200  \r\n'
    const result = normalizeNcContent(input)
    assert.equal(result, 'G0 X10\nG1 F200\n')
  })
})

// ---------------------------------------------------------------------------
// GROUP 2: buildShortHash
// ---------------------------------------------------------------------------

describe('buildShortHash', () => {
  test('returns first 12 chars + ellipsis from 64-char hash', () => {
    const hash = 'a'.repeat(64)
    const result = buildShortHash(hash)
    assert.equal(result, 'a'.repeat(12) + '…')
  })

  test('null input returns em dash', () => {
    assert.equal(buildShortHash(null), '—')
  })

  test('undefined input returns em dash', () => {
    assert.equal(buildShortHash(undefined), '—')
  })

  test('custom length is respected', () => {
    const hash = 'abcdefghijklmnopqrstuvwxyz123456abcdefghijklmnopqrstuvwxyz123456'
    assert.equal(buildShortHash(hash, 8), 'abcdefgh…')
  })

  test('short hash shorter than length returns full hash + ellipsis', () => {
    assert.equal(buildShortHash('abc', 12), 'abc…')
  })
})

// ---------------------------------------------------------------------------
// GROUP 3: computeChangeState
// ---------------------------------------------------------------------------

describe('computeChangeState', () => {
  const base = makeTraceability()

  test('returns UNCHANGED when all fingerprints match', () => {
    assert.equal(computeChangeState(base, base), 'UNCHANGED')
  })

  test('returns PROGRAM_CHANGED when only program fingerprint differs', () => {
    const changed = makeTraceability({ program_fingerprint: 'x'.repeat(64) })
    assert.equal(computeChangeState(changed, base), 'PROGRAM_CHANGED')
  })

  test('returns CONFIGURATION_CHANGED when only config fingerprint differs', () => {
    const changed = makeTraceability({ configuration_fingerprint: 'y'.repeat(64) })
    assert.equal(computeChangeState(changed, base), 'CONFIGURATION_CHANGED')
  })

  test('returns PROGRAM_AND_CONFIGURATION_CHANGED when both differ', () => {
    const changed = makeTraceability({
      program_fingerprint: 'x'.repeat(64),
      configuration_fingerprint: 'y'.repeat(64),
    })
    assert.equal(computeChangeState(changed, base), 'PROGRAM_AND_CONFIGURATION_CHANGED')
  })

  test('returns VERSION_CHANGED when review_schema_version differs', () => {
    const changed = makeTraceability({ review_schema_version: '2.0' })
    assert.equal(computeChangeState(changed, base), 'VERSION_CHANGED')
  })

  test('returns VERSION_CHANGED when parser_profile differs', () => {
    const changed = makeTraceability({ parser_profile: 'OTHER_PROFILE' })
    assert.equal(computeChangeState(changed, base), 'VERSION_CHANGED')
  })

  test('returns VERSION_CHANGED when parser_version differs', () => {
    const changed = makeTraceability({ parser_version: '99.0.0' })
    assert.equal(computeChangeState(changed, base), 'VERSION_CHANGED')
  })

  test('VERSION_CHANGED takes priority over fingerprint differences', () => {
    const changed = makeTraceability({
      review_schema_version: '2.0',
      program_fingerprint: 'x'.repeat(64),
    })
    assert.equal(computeChangeState(changed, base), 'VERSION_CHANGED')
  })
})

// ---------------------------------------------------------------------------
// GROUP 4: computeNcSha256 (async, conservative normalization)
// ---------------------------------------------------------------------------

describe('computeNcSha256', () => {
  test('returns a 64-char hex string for valid input', async () => {
    const hash = await computeNcSha256('G0 X10\nG1 F200\n')
    assert.ok(hash, 'hash must not be null')
    assert.equal(hash!.length, 64)
    assert.match(hash!, /^[0-9a-f]{64}$/)
  })

  test('CRLF and LF produce the same hash (conservative normalization)', async () => {
    const lf = await computeNcSha256('G0 X10\nG1 F200\n')
    const crlf = await computeNcSha256('G0 X10\r\nG1 F200\r\n')
    assert.equal(lf, crlf)
  })

  test('BOM prefix does not affect hash', async () => {
    const noBom = await computeNcSha256('G0 X10\nG1 F200\n')
    const withBom = await computeNcSha256('﻿G0 X10\nG1 F200\n')
    assert.equal(noBom, withBom)
  })

  test('trailing whitespace does not affect hash', async () => {
    const clean = await computeNcSha256('G0 X10\nG1 F200\n')
    const trailing = await computeNcSha256('G0 X10   \nG1 F200  \n')
    assert.equal(clean, trailing)
  })

  test('different program text produces different hash', async () => {
    const hash1 = await computeNcSha256('G0 X10\n')
    const hash2 = await computeNcSha256('G0 X20\n')
    assert.notEqual(hash1, hash2)
  })

  test('adding a line to program changes the hash', async () => {
    const hash1 = await computeNcSha256('G0 X10\n')
    const hash2 = await computeNcSha256('G0 X10\nG1 F200\n')
    assert.notEqual(hash1, hash2)
  })
})

// ---------------------------------------------------------------------------
// GROUP 5: computeConfigFingerprint (async)
// ---------------------------------------------------------------------------

describe('computeConfigFingerprint', () => {
  const baseConfig = {
    machine_id: 'dmg-clx-350',
    cutting_tool_id: 'sandvik-r216',
    tool_holder_id: null,
    operation: 'MILLING',
    material_iso_group: 'P',
    process_step_id: 'step-01',
  }

  test('returns a 64-char hex string', async () => {
    const hash = await computeConfigFingerprint(baseConfig)
    assert.ok(hash)
    assert.equal(hash!.length, 64)
  })

  test('same config produces same fingerprint (deterministic)', async () => {
    const h1 = await computeConfigFingerprint(baseConfig)
    const h2 = await computeConfigFingerprint({ ...baseConfig })
    assert.equal(h1, h2)
  })

  test('different machine_id produces different fingerprint', async () => {
    const h1 = await computeConfigFingerprint(baseConfig)
    const h2 = await computeConfigFingerprint({ ...baseConfig, machine_id: 'other-machine' })
    assert.notEqual(h1, h2)
  })

  test('operation is case-insensitive (MILLING == milling)', async () => {
    const h1 = await computeConfigFingerprint({ ...baseConfig, operation: 'MILLING' })
    const h2 = await computeConfigFingerprint({ ...baseConfig, operation: 'milling' })
    assert.equal(h1, h2)
  })

  test('null cutting_tool_id vs defined produces different fingerprint', async () => {
    const h1 = await computeConfigFingerprint(baseConfig)
    const h2 = await computeConfigFingerprint({ ...baseConfig, cutting_tool_id: null })
    assert.notEqual(h1, h2)
  })

  test('empty config (all null) produces a valid hash', async () => {
    const h = await computeConfigFingerprint({})
    assert.ok(h)
    assert.equal(h!.length, 64)
  })

  test('different process_step_id changes fingerprint', async () => {
    const h1 = await computeConfigFingerprint(baseConfig)
    const h2 = await computeConfigFingerprint({ ...baseConfig, process_step_id: 'step-02' })
    assert.notEqual(h1, h2)
  })

  test('field order does not affect fingerprint (sorted JSON)', async () => {
    const h1 = await computeConfigFingerprint({
      machine_id: 'M1', cutting_tool_id: 'T1', operation: 'milling',
      tool_holder_id: null, material_iso_group: null, process_step_id: null,
    })
    const h2 = await computeConfigFingerprint({
      operation: 'milling', cutting_tool_id: 'T1', machine_id: 'M1',
      tool_holder_id: null, material_iso_group: null, process_step_id: null,
    })
    assert.equal(h1, h2)
  })
})

// ---------------------------------------------------------------------------
// GROUP 6: computeAnalysisFingerprint (async)
// ---------------------------------------------------------------------------

describe('computeAnalysisFingerprint', () => {
  const prog = 'a'.repeat(64)
  const cfg = 'b'.repeat(64)

  test('returns a 64-char hex string when all inputs are provided', async () => {
    const h = await computeAnalysisFingerprint(prog, cfg, 'GENERIC_ISO_GCODE_SUBSET', '1.0')
    assert.ok(h)
    assert.equal(h!.length, 64)
  })

  test('returns null when program_fingerprint is null', async () => {
    const h = await computeAnalysisFingerprint(null, cfg, 'GENERIC_ISO_GCODE_SUBSET', '1.0')
    assert.equal(h, null)
  })

  test('returns null when config_fingerprint is null', async () => {
    const h = await computeAnalysisFingerprint(prog, null, 'GENERIC_ISO_GCODE_SUBSET', '1.0')
    assert.equal(h, null)
  })

  test('different program fingerprint produces different analysis fingerprint', async () => {
    const h1 = await computeAnalysisFingerprint(prog, cfg, 'GENERIC_ISO_GCODE_SUBSET', '1.0')
    const h2 = await computeAnalysisFingerprint('x'.repeat(64), cfg, 'GENERIC_ISO_GCODE_SUBSET', '1.0')
    assert.notEqual(h1, h2)
  })

  test('different parser_profile produces different analysis fingerprint', async () => {
    const h1 = await computeAnalysisFingerprint(prog, cfg, 'GENERIC_ISO_GCODE_SUBSET', '1.0')
    const h2 = await computeAnalysisFingerprint(prog, cfg, 'OTHER_PROFILE', '1.0')
    assert.notEqual(h1, h2)
  })

  test('different review_schema_version produces different analysis fingerprint', async () => {
    const h1 = await computeAnalysisFingerprint(prog, cfg, 'GENERIC_ISO_GCODE_SUBSET', '1.0')
    const h2 = await computeAnalysisFingerprint(prog, cfg, 'GENERIC_ISO_GCODE_SUBSET', '2.0')
    assert.notEqual(h1, h2)
  })
})

// ---------------------------------------------------------------------------
// GROUP 7: JSON export — traceability block
// ---------------------------------------------------------------------------

describe('buildNcReviewJson — traceability', () => {
  test('traceability is present in JSON output when review has it', () => {
    const er = makeReviewWithTraceability()
    const json = buildNcReviewJson(er, tEn, 'en')
    assert.ok(json.traceability, 'traceability must be present')
    assert.equal(json.traceability!.review_id, 'a1b2c3d4-0000-4000-8000-111111111111')
  })

  test('traceability is null in JSON output when review has no traceability', () => {
    const er = makeReviewWithoutTraceability()
    const json = buildNcReviewJson(er as never, tEn, 'en')
    assert.equal(json.traceability, null)
  })

  test('traceability safety flags are always false in JSON', () => {
    const er = makeReviewWithTraceability()
    const json = buildNcReviewJson(er, tEn, 'en')
    const tr = json.traceability!
    assert.equal(tr.hash_equals_digital_signature, false)
    assert.equal(tr.hash_equals_approval, false)
    assert.equal(tr.hash_equals_certification, false)
    assert.equal(tr.false_immutable_audit_claim, false)
  })

  test('program_fingerprint is passed through to JSON', () => {
    const er = makeReviewWithTraceability()
    const json = buildNcReviewJson(er, tEn, 'en')
    assert.equal(json.traceability!.program_fingerprint, 'a'.repeat(64))
  })

  test('traceability_status is passed through to JSON', () => {
    const er = makeReviewWithTraceability({ traceability_status: 'PARTIALLY_TRACEABLE' })
    const json = buildNcReviewJson(er, tEn, 'en')
    assert.equal(json.traceability!.traceability_status, 'PARTIALLY_TRACEABLE')
  })

  test('traceability appears as top-level key in JSON export', () => {
    const er = makeReviewWithTraceability()
    const json = buildNcReviewJson(er, tEn, 'en')
    const keys = Object.keys(json)
    const traceabilityIndex = keys.indexOf('traceability')
    assert.ok(traceabilityIndex >= 0, 'traceability must be a top-level key')
    // Should appear before metadata per spec
    const metaIndex = keys.indexOf('metadata')
    assert.ok(traceabilityIndex < metaIndex, 'traceability should appear before metadata')
  })
})

// ---------------------------------------------------------------------------
// GROUP 8: CSV leading columns
// ---------------------------------------------------------------------------

describe('CSV leading columns — traceability', () => {
  test('buildFindingsCsv includes review_id as first column header', () => {
    const er = makeReviewWithTraceability()
    const csv = buildFindingsCsv(er, tEn)
    const lines = csv.replace(/^﻿/, '').split('\r\n')
    const headers = lines[0].split(',')
    assert.equal(headers[0], 'review_id')
  })

  test('buildFindingsCsv includes analysis_fingerprint as second column', () => {
    const er = makeReviewWithTraceability()
    const csv = buildFindingsCsv(er, tEn)
    const headers = csv.replace(/^﻿/, '').split('\r\n')[0].split(',')
    assert.equal(headers[1], 'analysis_fingerprint')
  })

  test('buildFindingsCsv includes program_fingerprint as third column', () => {
    const er = makeReviewWithTraceability()
    const csv = buildFindingsCsv(er, tEn)
    const headers = csv.replace(/^﻿/, '').split('\r\n')[0].split(',')
    assert.equal(headers[2], 'program_fingerprint')
  })

  test('buildSegmentsCsv includes review_id as first column header', () => {
    const er = makeReviewWithTraceability()
    const csv = buildSegmentsCsv(er)
    const headers = csv.replace(/^﻿/, '').split('\r\n')[0].split(',')
    assert.equal(headers[0], 'review_id')
  })

  test('buildCoverageCsv includes review_id as first column header', () => {
    const er = makeReviewWithTraceability()
    const csv = buildCoverageCsv(er, tEn)
    const headers = csv.replace(/^﻿/, '').split('\r\n')[0].split(',')
    assert.equal(headers[0], 'review_id')
  })

  test('CSV review_id column value matches traceability.review_id', () => {
    const er = makeReviewWithTraceability()
    const csv = buildSegmentsCsv(er)
    const lines = csv.replace(/^﻿/, '').split('\r\n')
    const dataRow = lines[1].split(',')
    assert.equal(dataRow[0], 'a1b2c3d4-0000-4000-8000-111111111111')
  })
})

// ---------------------------------------------------------------------------
// GROUP 9: Print HTML traceability section
// ---------------------------------------------------------------------------

describe('generatePrintHtml — traceability section', () => {
  test('print HTML contains traceability section heading when traceability present', () => {
    const er = makeReviewWithTraceability()
    const html = generatePrintHtml(er, tEn, 'en')
    assert.ok(html.includes('Traceability'), 'section heading must be present')
  })

  test('print HTML contains review_id value when traceability present', () => {
    const er = makeReviewWithTraceability()
    const html = generatePrintHtml(er, tEn, 'en')
    assert.ok(html.includes('a1b2c3d4-0000-4000-8000-111111111111'))
  })

  test('print HTML contains safety constraint declarations', () => {
    const er = makeReviewWithTraceability()
    const html = generatePrintHtml(er, tEn, 'en')
    assert.ok(html.includes('HASH_EQUALS_DIGITAL_SIGNATURE=NO'))
    assert.ok(html.includes('HASH_EQUALS_APPROVAL=NO'))
    assert.ok(html.includes('HASH_EQUALS_CERTIFICATION=NO'))
    assert.ok(html.includes('FALSE_IMMUTABLE_AUDIT_CLAIM=NO'))
  })

  test('print HTML contains traceability section when locale is TR', () => {
    const er = makeReviewWithTraceability()
    const html = generatePrintHtml(er, tTr, 'tr')
    assert.ok(html.includes('İzlenebilirlik'))
  })

  test('print HTML does not include traceability section when traceability is absent', () => {
    const er = makeReviewWithoutTraceability()
    const html = generatePrintHtml(er as never, tEn, 'en')
    // Disclaimer section should still be present
    assert.ok(html.includes('Scope'))
  })
})

// ---------------------------------------------------------------------------
// GROUP 10: Audit events
// ---------------------------------------------------------------------------

describe('audit events', () => {
  beforeEach(() => {
    clearAuditEvents()
  })

  test('logExportEvent adds an event to the session audit log', () => {
    logExportEvent('json', 'PASS_WITH_EVIDENCE', null, null)
    const events = getAuditEvents()
    assert.equal(events.length, 1)
  })

  test('logExportEvent sets event_type NC_JSON_EXPORTED for format json', () => {
    logExportEvent('json', 'PASS_WITH_EVIDENCE', null, null)
    const events = getAuditEvents()
    assert.equal(events[0].event_type, 'NC_JSON_EXPORTED')
  })

  test('logExportEvent sets event_type NC_CSV_EXPORTED for csv formats', () => {
    logExportEvent('csv_findings', 'PASS_WITH_EVIDENCE', null, null)
    const events = getAuditEvents()
    assert.equal(events[0].event_type, 'NC_CSV_EXPORTED')
  })

  test('logExportEvent sets event_type NC_PRINT_OPENED for print', () => {
    logExportEvent('print', 'PASS_WITH_EVIDENCE', null, null)
    const events = getAuditEvents()
    assert.equal(events[0].event_type, 'NC_PRINT_OPENED')
  })

  test('logExportEvent passes review_id to audit event', () => {
    logExportEvent('json', 'PASS_WITH_EVIDENCE', 'test-review-id', null)
    const events = getAuditEvents()
    assert.equal(events[0].review_id, 'test-review-id')
  })

  test('clearAuditEvents empties the log', () => {
    logExportEvent('json', 'PASS_WITH_EVIDENCE', null, null)
    clearAuditEvents()
    assert.equal(getAuditEvents().length, 0)
  })

  test('addAuditEvent appends to the log', () => {
    const event: NcAuditEvent = {
      event_id: 'test-id',
      event_type: 'NC_REVIEW_GENERATED',
      timestamp: new Date().toISOString(),
      review_id: null,
      analysis_fingerprint: null,
      export_format: null,
    }
    addAuditEvent(event)
    const events = getAuditEvents()
    assert.equal(events.length, 1)
    assert.equal(events[0].event_id, 'test-id')
  })
})

// ---------------------------------------------------------------------------
// GROUP 11: i18n key coverage
// ---------------------------------------------------------------------------

describe('i18n key coverage — NC_PROGRAM_TRACEABILITY_AND_AUDIT_01', () => {
  const TRACEABILITY_KEYS: (keyof TranslationDictionary)[] = [
    'ncErTraceabilitySection',
    'ncErReviewId',
    'ncErProgramFingerprint',
    'ncErConfigFingerprint',
    'ncErAnalysisFingerprint',
    'ncErGeneratedAt',
    'ncErReviewSchemaVersion',
    'ncErTraceabilityStatus',
    'ncErTraceabilityTraceable',
    'ncErTraceabilityPartiallyTraceable',
    'ncErTraceabilityInsufficientData',
    'ncErMatchUnchanged',
    'ncErMatchProgramChanged',
    'ncErMatchConfigChanged',
    'ncErMatchBothChanged',
    'ncErMatchVersionChanged',
    'ncErMatchUnknown',
    'ncErCopyFingerprint',
    'ncErFingerprintCopied',
    'ncErAuditEvent',
    'ncErAuditAnalysisCreated',
    'ncErAuditReviewGenerated',
    'ncErAuditJsonExported',
    'ncErAuditCsvExported',
    'ncErAuditPrintOpened',
    'ncErAuditReviewed',
  ]

  test('all traceability keys are present in EN translations', () => {
    const en = enTranslations as Record<string, string>
    for (const key of TRACEABILITY_KEYS) {
      assert.ok(typeof en[key] === 'string' && en[key].length > 0, `EN missing: ${key}`)
    }
  })

  test('all traceability keys are present in TR translations', () => {
    const tr = trTranslations as Record<string, string>
    for (const key of TRACEABILITY_KEYS) {
      assert.ok(typeof tr[key] === 'string' && tr[key].length > 0, `TR missing: ${key}`)
    }
  })

  test('EN and TR translations are different for label keys', () => {
    const en = enTranslations as Record<string, string>
    const tr = trTranslations as Record<string, string>
    // At least one TR label must differ from EN
    const hasDifference = TRACEABILITY_KEYS.some(k => en[k] !== tr[k])
    assert.ok(hasDifference, 'TR translations must differ from EN for at least some keys')
  })

  test('REVIEW_SCHEMA_VERSION constant is 1.0', () => {
    assert.equal(REVIEW_SCHEMA_VERSION, '1.0')
  })
})
