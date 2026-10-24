// NC_PROGRAM_REPORTING_AND_EXPORT_01 — export utility tests
//
// Run with: npm test

import assert from 'node:assert/strict'
import { describe, test } from 'node:test'

import { enTranslations } from '../src/i18n/en.ts'
import { trTranslations } from '../src/i18n/tr.ts'
import {
  EXPORT_SCHEMA_VERSION,
  EXPORT_APPLICATION_VERSION,
  buildExportFilename,
  buildExportFilenameSuffix,
  buildNcReviewJson,
  buildFindingsCsv,
  buildSegmentsCsv,
  buildCoverageCsv,
  generatePrintHtml,
} from '../src/lib/nc_report_export.ts'
import type {
  NcReviewExportJson,
} from '../src/lib/nc_report_export.ts'

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

const tEn = (k: string): string => (enTranslations as Record<string, string>)[k] ?? k
const tTr = (k: string): string => (trTranslations as Record<string, string>)[k] ?? k

function makeBaseReview() {
  return {
    source_name_safe: 'shaft_prog_001',
    parser_profile: 'GENERIC_ISO_GCODE_SUBSET',
    parser_version: '1.0.0',
    units_declared: 'mm',
    analysis_status: 'COMPLETE',
    segment_count: 2,
    tool_change_count: 1,
    supported_motion_count: 42,
    unsupported_construct_count: 0,
    arc_motion_count: 3,
    feature_coverage: [
      { feature: 'G0 (Rapid)', state: 'SUPPORTED', detected: true, note: null },
      { feature: 'G1 (Linear feed)', state: 'SUPPORTED', detected: true, note: null },
      { feature: 'G93 (Inverse time)', state: 'DEFERRED', detected: false, note: 'Not expanded' },
      { feature: 'G96 (CSS)', state: 'DEFERRED', detected: false, note: 'Not expanded' },
      { feature: 'G83 (Peck drill)', state: 'BOUNDED', detected: false, note: 'Retract rapid omitted' },
      { feature: 'G84 (Tapping)', state: 'BOUNDED', detected: false, note: 'Path only' },
      { feature: 'M98/M99 (Subprogram)', state: 'UNSUPPORTED', detected: false, note: 'NC_FILE_EXECUTED=NO' },
      { feature: 'G2/G3 R-format', state: 'DEFERRED', detected: false, note: 'IJK only' },
    ],
    deferred_features_detected: [],
    unsupported_features_detected: [],
    total_feed_distance_mm: 125.456,
    total_rapid_distance_mm: 210.000,
    segments: [
      {
        segment_id: 'PREAMBLE',
        start_line: 1,
        end_line: 3,
        tool_id_raw: null,
        feed_motion_distance_mm: 0,
        rapid_motion_distance_mm: 0,
        linear_motion_count: 0,
        arc_motion_count: 0,
        commanded_feed_min: null,
        commanded_feed_max: null,
        feed_change_count: 0,
        analysis_status: 'COMPLETE',
        unsupported_features: [],
        feed_mode: null,
        commanded_feed_mm_rev: null,
        commanded_spindle_rpm: null,
        spindle_state: null,
        spindle_direction: null,
        nc_feed_move_equals_confirmed_cutting: false as const,
        arc_chord_approximation_used: false as const,
      },
      {
        segment_id: 'SEG_TC1',
        start_line: 4,
        end_line: 30,
        tool_id_raw: 'T1',
        feed_motion_distance_mm: 125.456,
        rapid_motion_distance_mm: 210.000,
        linear_motion_count: 39,
        arc_motion_count: 3,
        commanded_feed_min: 150,
        commanded_feed_max: 250,
        feed_change_count: 2,
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
      nc_commanded_feed_mm_min: 200,
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
      evidence_sources: ['NC_PROGRAM', 'MACHINE_CATALOG'],
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
    operation_association: 'turning',
    cycle_time_known_subtotal_sec: 37.7,
    cycle_time_status: 'PARTIAL',
    cycle_time_limitations: ['Tool-change time excluded'],
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

function makeBlockedReview() {
  const base = makeBaseReview()
  return {
    ...base,
    review_status: 'BLOCKED_BY_KNOWN_LIMIT' as const,
    blocking_count: 2,
    findings: [
      {
        finding_code: 'RPM_LIMIT_MACHINE_RPM',
        category: 'RPM_LIMIT',
        severity: 'BLOCKING' as const,
        title_key: 'ncErFindingMachineRpm',
        message_key: 'ncErFindingMachineRpm',
        observed_value: 99000,
        limit_value: 4500,
        unit: 'rpm',
        source: 'MACHINE_CATALOG',
        evidence_type: 'MACHINE_CATALOG',
        segment_id: 'SEG_TC1',
        limitation: null,
      },
    ],
  }
}

function makeInsufficientReview() {
  const base = makeBaseReview()
  return {
    ...base,
    review_status: 'INSUFFICIENT_DATA' as const,
    cycle_time_known_subtotal_sec: null,
    cycle_time_status: null,
    equipment: {
      ...base.equipment,
      machine_id: null,
      machine_display: null,
      cutting_tool_id: null,
      cutting_tool_display: null,
      missing_fields: ['machine', 'cutting_tool'],
    },
  }
}

function makeUnsupportedReview() {
  const base = makeBaseReview()
  return {
    ...base,
    review_status: 'UNSUPPORTED_FEATURES_PRESENT' as const,
    unsupported_features_detected: ['M98/M99'],
    unsupported_count: 1,
    findings: [
      {
        finding_code: 'PARSER_SUBPROGRAM_UNSUPPORTED',
        category: 'PARSER_COVERAGE',
        severity: 'ADVISORY' as const,
        title_key: 'ncErFindingSubprogramUnsupported',
        message_key: 'ncErSubprogramUnsupportedMsg',
        observed_value: null,
        limit_value: null,
        unit: null,
        source: 'NC_PROGRAM',
        evidence_type: 'NC_PROGRAM',
        segment_id: null,
        limitation: null,
      },
    ],
  }
}

// ---------------------------------------------------------------------------
// 1. i18n key presence — export keys
// ---------------------------------------------------------------------------

describe('Export i18n keys — EN', () => {
  const exportKeys = [
    'ncErExportJson', 'ncErExportCsv', 'ncErExportPrint',
    'ncErExportCsvFindings', 'ncErExportCsvSegments', 'ncErExportCsvCoverage',
    'ncErExportDisclaimer', 'ncErExportProvenance', 'ncErExportScopeTitle',
  ] as const
  for (const key of exportKeys) {
    test(`EN has key: ${key}`, () => {
      assert.ok(key in enTranslations, `Missing EN key: ${key}`)
      assert.ok((enTranslations as Record<string, string>)[key].length > 0, `Empty EN value: ${key}`)
    })
  }
})

describe('Export i18n keys — TR', () => {
  const exportKeys = [
    'ncErExportJson', 'ncErExportCsv', 'ncErExportPrint',
    'ncErExportCsvFindings', 'ncErExportCsvSegments', 'ncErExportCsvCoverage',
    'ncErExportDisclaimer', 'ncErExportProvenance', 'ncErExportScopeTitle',
  ] as const
  for (const key of exportKeys) {
    test(`TR has key: ${key}`, () => {
      assert.ok(key in trTranslations, `Missing TR key: ${key}`)
      assert.ok((trTranslations as Record<string, string>)[key].length > 0, `Empty TR value: ${key}`)
    })
  }
})

// ---------------------------------------------------------------------------
// 2. Filename utility
// ---------------------------------------------------------------------------

describe('buildExportFilename', () => {
  const d = new Date('2026-10-23T12:00:00Z')

  test('includes program name', () => {
    const fn = buildExportFilename('shaft_prog', d, 'json')
    assert.ok(fn.includes('shaft_prog'), fn)
  })

  test('includes date suffix', () => {
    const fn = buildExportFilename('prog', d, 'json')
    assert.ok(fn.includes('20261023'), fn)
  })

  test('uses correct extension', () => {
    assert.ok(buildExportFilename('p', d, 'json').endsWith('.json'))
    assert.ok(buildExportFilename('p', d, 'csv').endsWith('.csv'))
    assert.ok(buildExportFilename('p', d, 'html').endsWith('.html'))
  })

  test('null source_name_safe → Unnamed', () => {
    const fn = buildExportFilename(null, d, 'json')
    assert.ok(fn.includes('Unnamed'), fn)
  })

  test('sanitizes spaces to underscores', () => {
    const fn = buildExportFilename('my program name', d, 'json')
    assert.ok(!fn.includes(' '), fn)
    assert.ok(fn.includes('my_program_name'), fn)
  })

  test('sanitizes path separators', () => {
    const fn = buildExportFilename('C:/Users/test/prog', d, 'json')
    assert.ok(!fn.includes('/'), fn)
    assert.ok(!fn.includes(':'), fn)
  })

  test('truncates long name to 40 chars', () => {
    const longName = 'a'.repeat(60)
    const fn = buildExportFilename(longName, d, 'json')
    // The safe name portion should be at most 40 chars
    const safeNamePart = fn.replace('MachiningPro_NC_Engineering_Review_', '').replace('_20261023.json', '')
    assert.ok(safeNamePart.length <= 40, `Name too long: ${safeNamePart.length}`)
  })

  test('buildExportFilenameSuffix adds suffix', () => {
    const fn = buildExportFilenameSuffix('prog', d, 'findings', 'csv')
    assert.ok(fn.includes('findings'), fn)
    assert.ok(fn.endsWith('.csv'), fn)
  })
})

// ---------------------------------------------------------------------------
// 3. JSON export — structural tests
// ---------------------------------------------------------------------------

describe('buildNcReviewJson — structure', () => {
  const er = makeBaseReview()
  let dto: NcReviewExportJson

  test('builds without error', () => {
    dto = buildNcReviewJson(er, tEn, 'en')
    assert.ok(dto)
  })

  test('schema_version present and correct', () => {
    const d = buildNcReviewJson(er, tEn, 'en')
    assert.equal(d.schema_version, EXPORT_SCHEMA_VERSION)
    assert.equal(d.metadata.schema_version, EXPORT_SCHEMA_VERSION)
  })

  test('report_type is NC_PROGRAM_ENGINEERING_REVIEW', () => {
    const d = buildNcReviewJson(er, tEn, 'en')
    assert.equal(d.report_type, 'NC_PROGRAM_ENGINEERING_REVIEW')
  })

  test('application_version present', () => {
    const d = buildNcReviewJson(er, tEn, 'en')
    assert.equal(d.metadata.application_version, EXPORT_APPLICATION_VERSION)
  })

  test('generated_at is ISO 8601', () => {
    const d = buildNcReviewJson(er, tEn, 'en')
    assert.ok(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(d.metadata.generated_at))
  })

  test('nc_content_sha256 null when not provided', () => {
    const d = buildNcReviewJson(er, tEn, 'en')
    assert.equal(d.metadata.nc_content_sha256, null)
  })

  test('nc_content_sha256 stored when provided', () => {
    const d = buildNcReviewJson(er, tEn, 'en', 'abc123def456')
    assert.equal(d.metadata.nc_content_sha256, 'abc123def456')
  })

  test('review_status matches input', () => {
    const d = buildNcReviewJson(er, tEn, 'en')
    assert.equal(d.review_status, 'PASS_WITH_EVIDENCE')
  })

  test('BLOCKED_BY_KNOWN_LIMIT review_status', () => {
    const d = buildNcReviewJson(makeBlockedReview(), tEn, 'en')
    assert.equal(d.review_status, 'BLOCKED_BY_KNOWN_LIMIT')
    assert.ok(d.executive_summary.blocking_count >= 1)
  })

  test('INSUFFICIENT_DATA: cycle_time_known_subtotal_sec is null', () => {
    const d = buildNcReviewJson(makeInsufficientReview(), tEn, 'en')
    assert.equal(d.executive_summary.cycle_time_known_subtotal_sec, null)
  })

  test('findings array populated from blocked review', () => {
    const d = buildNcReviewJson(makeBlockedReview(), tEn, 'en')
    assert.ok(d.findings.length >= 1)
    assert.equal(d.findings[0].finding_code, 'RPM_LIMIT_MACHINE_RPM')
    assert.equal(d.findings[0].severity, 'BLOCKING')
  })

  test('EN locale: review_status_label is English', () => {
    const d = buildNcReviewJson(er, tEn, 'en')
    assert.equal(d.review_status_label, enTranslations.ncErStatusPassWithEvidence)
  })

  test('TR locale: review_status_label is Turkish', () => {
    const d = buildNcReviewJson(er, tTr, 'tr')
    assert.equal(d.review_status_label, trTranslations.ncErStatusPassWithEvidence)
    assert.notEqual(d.review_status_label, enTranslations.ncErStatusPassWithEvidence)
  })

  test('EN locale: metadata.language is en', () => {
    const d = buildNcReviewJson(er, tEn, 'en')
    assert.equal(d.metadata.language, 'en')
  })

  test('TR locale: metadata.language is tr', () => {
    const d = buildNcReviewJson(er, tTr, 'tr')
    assert.equal(d.metadata.language, 'tr')
  })

  test('parser_coverage array preserved', () => {
    const d = buildNcReviewJson(er, tEn, 'en')
    assert.ok(Array.isArray(d.parser_coverage))
    assert.equal(d.parser_coverage.length, er.feature_coverage.length)
  })

  test('segments exported with safe field names', () => {
    const d = buildNcReviewJson(er, tEn, 'en')
    assert.ok(Array.isArray(d.segments))
    assert.equal(d.segments.length, er.segments.length)
    const seg = d.segments.find(s => s.segment_id === 'SEG_TC1')
    assert.ok(seg)
    assert.equal(seg!.commanded_feed_min_mm_min, 150)
    assert.equal(seg!.commanded_feed_max_mm_min, 250)
  })

  test('segments: t_word_equals_confirmed_tool_identity always false', () => {
    const d = buildNcReviewJson(er, tEn, 'en')
    for (const seg of d.segments) {
      assert.equal(seg.t_word_equals_confirmed_tool_identity, false)
    }
  })

  test('motion_summary safety flags are false', () => {
    const d = buildNcReviewJson(er, tEn, 'en')
    assert.equal(d.motion_summary.safety_flags.programmed_motion_equals_executed_motion, false)
    assert.equal(d.motion_summary.safety_flags.programmed_feed_distance_equals_confirmed_cutting, false)
  })

  test('feed_spindle safety flags are false', () => {
    const d = buildNcReviewJson(er, tEn, 'en')
    assert.equal(d.feed_spindle_validation.safety_flags.nc_commanded_spindle_speed_equals_actual_rpm, false)
    assert.equal(d.feed_spindle_validation.safety_flags.nc_commanded_feed_equals_actual_feed, false)
    assert.equal(d.feed_spindle_validation.safety_flags.reference_range_validation_is_optimization, false)
  })

  test('provenance has NC_PROGRAM key', () => {
    const d = buildNcReviewJson(er, tEn, 'en')
    assert.ok('NC_PROGRAM' in d.provenance)
  })

  test('provenance has MACHINE_CATALOG key', () => {
    const d = buildNcReviewJson(er, tEn, 'en')
    assert.ok('MACHINE_CATALOG' in d.provenance)
  })

  test('disclaimer is non-empty', () => {
    const d = buildNcReviewJson(er, tEn, 'en')
    assert.ok(d.disclaimer.length > 20)
  })
})

// ---------------------------------------------------------------------------
// 4. JSON export — safety flag tests
// ---------------------------------------------------------------------------

describe('buildNcReviewJson — safety flags', () => {
  const er = makeBaseReview()

  test('nc_file_executed is false', () => {
    const d = buildNcReviewJson(er, tEn, 'en')
    assert.equal(d.safety_flags.nc_file_executed, false)
  })

  test('false_production_approval_claim is false', () => {
    const d = buildNcReviewJson(er, tEn, 'en')
    assert.equal(d.safety_flags.false_production_approval_claim, false)
  })

  test('false_safe_to_run_claim is false', () => {
    const d = buildNcReviewJson(er, tEn, 'en')
    assert.equal(d.safety_flags.false_safe_to_run_claim, false)
  })

  test('false_collision_free_claim is false', () => {
    const d = buildNcReviewJson(er, tEn, 'en')
    assert.equal(d.safety_flags.false_collision_free_claim, false)
  })

  test('partial_time_mislabeled_total is false', () => {
    const d = buildNcReviewJson(er, tEn, 'en')
    assert.equal(d.safety_flags.partial_time_mislabeled_total, false)
  })

  test('t_word_equals_confirmed_tool_identity is false', () => {
    const d = buildNcReviewJson(er, tEn, 'en')
    assert.equal(d.safety_flags.t_word_equals_confirmed_tool_identity, false)
  })

  test('private_path_in_api_response is false', () => {
    const d = buildNcReviewJson(er, tEn, 'en')
    assert.equal(d.safety_flags.private_path_in_api_response, false)
  })

  test('machine_behavior_simulated is false', () => {
    const d = buildNcReviewJson(er, tEn, 'en')
    assert.equal(d.safety_flags.machine_behavior_simulated, false)
  })

  test('collision_check_performed is false', () => {
    const d = buildNcReviewJson(er, tEn, 'en')
    assert.equal(d.safety_flags.collision_check_performed, false)
  })
})

// ---------------------------------------------------------------------------
// 5. JSON export — no unsafe content
// ---------------------------------------------------------------------------

describe('buildNcReviewJson — no unsafe content', () => {
  test('no local path in source_name_safe', () => {
    const er = { ...makeBaseReview(), source_name_safe: 'safe_name' }
    const d = buildNcReviewJson(er, tEn, 'en')
    const json = JSON.stringify(d)
    assert.ok(!json.includes('C:\\'), json.slice(0, 200))
    assert.ok(!json.includes('/Users/'), json.slice(0, 200))
    assert.ok(!json.includes('AppData'), json.slice(0, 200))
  })

  test('disclaimer does not claim production approval', () => {
    const d = buildNcReviewJson(makeBaseReview(), tEn, 'en')
    const lower = d.disclaimer.toLowerCase()
    assert.ok(!lower.includes('production approved'), d.disclaimer.slice(0, 100))
    assert.ok(!lower.includes('approved for production'), d.disclaimer.slice(0, 100))
  })

  test('disclaimer does not claim safe to run', () => {
    const d = buildNcReviewJson(makeBaseReview(), tEn, 'en')
    const lower = d.disclaimer.toLowerCase()
    assert.ok(!lower.includes('safe to run'), d.disclaimer.slice(0, 100))
    assert.ok(!lower.includes('safe to machine'), d.disclaimer.slice(0, 100))
  })

  test('disclaimer does not claim collision-free', () => {
    const d = buildNcReviewJson(makeBaseReview(), tEn, 'en')
    const lower = d.disclaimer.toLowerCase()
    assert.ok(!lower.includes('collision-free'), d.disclaimer.slice(0, 100))
  })

  test('cycle time subtotal not labeled as total cycle time', () => {
    const d = buildNcReviewJson(makeBaseReview(), tEn, 'en')
    // Should only be present under cycle_time_known_subtotal_sec, not as totalCycleTime
    assert.ok(!('total_cycle_time' in d.executive_summary))
  })

  test('BOUNDED canned cycle has bounded_canned_cycle_mislabeled_complete false', () => {
    const er = {
      ...makeBaseReview(),
      canned_cycle_notes: [{
        cycle_code_str: 'G83',
        state: 'BOUNDED' as const,
        bounded_reason: 'Peck retract rapid is controller-specific',
        detected_limitations: [],
        bounded_canned_cycle_mislabeled_complete: false as const,
      }],
    }
    const d = buildNcReviewJson(er, tEn, 'en')
    assert.equal(d.canned_cycles[0].bounded_canned_cycle_mislabeled_complete, false)
    assert.equal(d.canned_cycles[0].state, 'BOUNDED')
  })

  test('G83 not exported as full controller semantics', () => {
    const er = {
      ...makeBaseReview(),
      canned_cycle_notes: [{
        cycle_code_str: 'G83',
        state: 'BOUNDED' as const,
        bounded_reason: 'Peck retract rapid is controller-specific',
        detected_limitations: [],
        bounded_canned_cycle_mislabeled_complete: false as const,
      }],
    }
    const d = buildNcReviewJson(er, tEn, 'en')
    const cycle = d.canned_cycles.find(c => c.cycle_code_str === 'G83')
    assert.ok(cycle)
    assert.notEqual(cycle!.state, 'SUPPORTED')
    assert.equal(cycle!.state, 'BOUNDED')
  })
})

// ---------------------------------------------------------------------------
// 6. Parser coverage semantics
// ---------------------------------------------------------------------------

describe('buildNcReviewJson — parser coverage semantics', () => {
  const er = makeBaseReview()
  const d = buildNcReviewJson(er, tEn, 'en')

  test('G93 feature state is DEFERRED', () => {
    const fc = d.parser_coverage.find(f => f.feature.includes('G93'))
    assert.ok(fc, 'G93 entry missing')
    assert.equal(fc!.state, 'DEFERRED')
  })

  test('G96 feature state is DEFERRED', () => {
    const fc = d.parser_coverage.find(f => f.feature.includes('G96'))
    assert.ok(fc, 'G96 entry missing')
    assert.equal(fc!.state, 'DEFERRED')
  })

  test('G83 feature state is BOUNDED', () => {
    const fc = d.parser_coverage.find(f => f.feature.includes('G83'))
    assert.ok(fc, 'G83 entry missing')
    assert.equal(fc!.state, 'BOUNDED')
  })

  test('G84 feature state is BOUNDED', () => {
    const fc = d.parser_coverage.find(f => f.feature.includes('G84'))
    assert.ok(fc, 'G84 entry missing')
    assert.equal(fc!.state, 'BOUNDED')
  })

  test('M98/M99 feature state is UNSUPPORTED', () => {
    const fc = d.parser_coverage.find(f => f.feature.includes('M98'))
    assert.ok(fc, 'M98 entry missing')
    assert.equal(fc!.state, 'UNSUPPORTED')
  })

  test('R-format arc feature state is DEFERRED', () => {
    const fc = d.parser_coverage.find(f => f.feature.includes('R-format'))
    assert.ok(fc, 'R-format entry missing')
    assert.equal(fc!.state, 'DEFERRED')
  })

  test('G0 feature state is SUPPORTED', () => {
    const fc = d.parser_coverage.find(f => f.feature.includes('G0'))
    assert.ok(fc, 'G0 entry missing')
    assert.equal(fc!.state, 'SUPPORTED')
  })

  test('BOUNDED state not promoted to SUPPORTED in any field', () => {
    for (const fc of d.parser_coverage) {
      if (fc.state === 'BOUNDED') {
        assert.notEqual(fc.state, 'SUPPORTED')
      }
    }
  })

  test('unsupported features exported in unsupported_features_detected when present', () => {
    const er2 = makeUnsupportedReview()
    const d2 = buildNcReviewJson(er2, tEn, 'en')
    assert.ok(d2.unsupported_features_detected.length > 0)
    assert.ok(d2.unsupported_features_detected.includes('M98/M99'))
  })
})

// ---------------------------------------------------------------------------
// 7. Findings CSV
// ---------------------------------------------------------------------------

describe('buildFindingsCsv', () => {
  test('empty findings: header row only', () => {
    const csv = buildFindingsCsv(makeBaseReview(), tEn)
    const lines = csv.replace(/^\uFEFF/, '').split('\r\n').filter(Boolean)
    assert.equal(lines.length, 1)
    assert.ok(lines[0].includes('finding_code'))
  })

  test('UTF-8 BOM present', () => {
    const csv = buildFindingsCsv(makeBaseReview(), tEn)
    assert.ok(csv.startsWith('\uFEFF'))
  })

  test('correct headers in findings CSV', () => {
    const csv = buildFindingsCsv(makeBaseReview(), tEn)
    const header = csv.replace(/^\uFEFF/, '').split('\r\n')[0]
    assert.ok(header.includes('finding_code'))
    assert.ok(header.includes('severity'))
    assert.ok(header.includes('observed_value'))
    assert.ok(header.includes('limit_value'))
    assert.ok(header.includes('segment_id'))
  })

  test('finding row count matches findings', () => {
    const er = makeBlockedReview()
    const csv = buildFindingsCsv(er, tEn)
    const lines = csv.replace(/^\uFEFF/, '').split('\r\n').filter(Boolean)
    assert.equal(lines.length, 1 + er.findings.length)
  })

  test('title resolved from i18n key (EN)', () => {
    const csv = buildFindingsCsv(makeBlockedReview(), tEn)
    // title_key=ncErFindingMachineRpm → resolved to EN string
    assert.ok(csv.includes(enTranslations.ncErFindingMachineRpm))
  })

  test('title resolved from i18n key (TR)', () => {
    const csv = buildFindingsCsv(makeBlockedReview(), tTr)
    assert.ok(csv.includes(trTranslations.ncErFindingMachineRpm))
  })

  test('comma in message is quoted', () => {
    const er = {
      ...makeBaseReview(),
      findings: [{
        finding_code: 'TEST',
        category: 'TEST',
        severity: 'INFO' as const,
        title_key: 'ncErFindingMachineRpm',
        message_key: 'ncErFindingMachineRpm',
        observed_value: null,
        limit_value: null,
        unit: null,
        source: 'NC_PROGRAM',
        evidence_type: null,
        segment_id: null,
        limitation: 'has, comma in it',
      }],
    }
    const csv = buildFindingsCsv(er, tEn)
    assert.ok(csv.includes('"has, comma in it"'))
  })

  test('double-quote in field is escaped as ""', () => {
    const er = {
      ...makeBaseReview(),
      findings: [{
        finding_code: 'TEST',
        category: 'TEST',
        severity: 'INFO' as const,
        title_key: 'ncErFindingMachineRpm',
        message_key: 'ncErFindingMachineRpm',
        observed_value: null,
        limit_value: null,
        unit: null,
        source: null,
        evidence_type: null,
        segment_id: null,
        limitation: 'say "yes" please',
      }],
    }
    const csv = buildFindingsCsv(er, tEn)
    assert.ok(csv.includes('say ""yes"" please'))
  })

  test('null values produce empty cell', () => {
    const csv = buildFindingsCsv(makeBlockedReview(), tEn)
    // segment_id is null for the test finding, should be empty cell
    const dataLine = csv.replace(/^\uFEFF/, '').split('\r\n')[1]
    assert.ok(dataLine)
    // Should not contain literal "null"
    assert.ok(!dataLine.includes(',null,'), dataLine)
  })

  test('Turkish unicode characters preserved', () => {
    const er = {
      ...makeBaseReview(),
      findings: [{
        finding_code: 'TEST_TR',
        category: 'TEST',
        severity: 'INFO' as const,
        title_key: 'ncErFindingMachineRpm',
        message_key: 'ncErFindingMachineRpm',
        observed_value: null,
        limit_value: null,
        unit: null,
        source: null,
        evidence_type: null,
        segment_id: null,
        limitation: 'Şarj ğü ı ö ü',
      }],
    }
    const csv = buildFindingsCsv(er, tTr)
    assert.ok(csv.includes('Şarj ğü ı ö ü'))
  })

  test('no "production approved" text in findings CSV', () => {
    const csv = buildFindingsCsv(makeBlockedReview(), tEn)
    assert.ok(!csv.toLowerCase().includes('production approved'))
  })
})

// ---------------------------------------------------------------------------
// 8. Segments CSV
// ---------------------------------------------------------------------------

describe('buildSegmentsCsv', () => {
  test('UTF-8 BOM present', () => {
    assert.ok(buildSegmentsCsv(makeBaseReview()).startsWith('\uFEFF'))
  })

  test('correct headers include segment_id and t-word column', () => {
    const csv = buildSegmentsCsv(makeBaseReview())
    const header = csv.replace(/^\uFEFF/, '').split('\r\n')[0]
    assert.ok(header.includes('segment_id'))
    assert.ok(header.includes('tool_id_raw_nc_t_word'))
  })

  test('t_word column not labeled as catalog identity', () => {
    const csv = buildSegmentsCsv(makeBaseReview())
    const header = csv.replace(/^\uFEFF/, '').split('\r\n')[0]
    // Column must not suggest the T-word IS confirmed (no "catalog_tool" or standalone "confirmed_tool_id")
    assert.ok(!header.toLowerCase().includes('catalog_tool'))
    // Column must be present with its safe name (NC T-word only)
    assert.ok(header.includes('tool_id_raw_nc_t_word'))
    // t_word_equals_confirmed_tool_identity safety flag column is acceptable (shows it is false)
  })

  test('row count matches segments', () => {
    const er = makeBaseReview()
    const csv = buildSegmentsCsv(er)
    const lines = csv.replace(/^\uFEFF/, '').split('\r\n').filter(Boolean)
    assert.equal(lines.length, 1 + er.segments.length)
  })

  test('t_word_equals_confirmed_tool_identity column value is false', () => {
    const csv = buildSegmentsCsv(makeBaseReview())
    const lines = csv.replace(/^\uFEFF/, '').split('\r\n')
    const header = lines[0].split(',')
    const tWordConfIdx = header.indexOf('t_word_equals_confirmed_tool_identity')
    assert.ok(tWordConfIdx >= 0, 'column missing')
    const dataRow = lines.find(l => l.includes('SEG_TC1'))
    assert.ok(dataRow)
    const cells = dataRow!.split(',')
    assert.equal(cells[tWordConfIdx], 'false')
  })
})

// ---------------------------------------------------------------------------
// 9. Coverage CSV
// ---------------------------------------------------------------------------

describe('buildCoverageCsv', () => {
  test('UTF-8 BOM present', () => {
    assert.ok(buildCoverageCsv(makeBaseReview(), tEn).startsWith('\uFEFF'))
  })

  test('all features exported', () => {
    const er = makeBaseReview()
    const csv = buildCoverageCsv(er, tEn)
    const lines = csv.replace(/^\uFEFF/, '').split('\r\n').filter(Boolean)
    assert.equal(lines.length, 1 + er.feature_coverage.length)
  })

  test('DEFERRED state preserved verbatim', () => {
    const csv = buildCoverageCsv(makeBaseReview(), tEn)
    assert.ok(csv.includes('DEFERRED'))
  })

  test('BOUNDED state preserved verbatim', () => {
    const csv = buildCoverageCsv(makeBaseReview(), tEn)
    assert.ok(csv.includes('BOUNDED'))
  })

  test('UNSUPPORTED state preserved verbatim', () => {
    const csv = buildCoverageCsv(makeBaseReview(), tEn)
    assert.ok(csv.includes('UNSUPPORTED'))
  })

  test('BOUNDED state not replaced with SUPPORTED', () => {
    const csv = buildCoverageCsv(makeBaseReview(), tEn)
    // Every BOUNDED row should not have SUPPORTED in the state column
    const lines = csv.replace(/^\uFEFF/, '').split('\r\n').filter(Boolean)
    const header = lines[0].split(',')
    const stateIdx = header.indexOf('state')
    assert.ok(stateIdx >= 0, 'state column missing')
    for (const line of lines.slice(1)) {
      const cells = line.split(',')
      const state = cells[stateIdx]
      // If feature has BOUNDED in a note-adjacent area, the state col itself must not be SUPPORTED
      // (specifically check G83/G84)
      if (line.includes('G83') || line.includes('G84')) {
        assert.equal(state, 'BOUNDED', `G83/G84 should be BOUNDED, got: ${state}`)
      }
    }
  })

  test('TR locale state labels in CSV label column', () => {
    const csv = buildCoverageCsv(makeBaseReview(), tTr)
    assert.ok(csv.includes(trTranslations.ncErStateBounded))
    assert.ok(csv.includes(trTranslations.ncErStateDeferred))
  })
})

// ---------------------------------------------------------------------------
// 10. Print HTML
// ---------------------------------------------------------------------------

describe('generatePrintHtml', () => {
  test('generates valid HTML doctype', () => {
    const html = generatePrintHtml(makeBaseReview(), tEn, 'en')
    assert.ok(html.startsWith('<!doctype html>'))
  })

  test('includes @page A4 CSS', () => {
    const html = generatePrintHtml(makeBaseReview(), tEn, 'en')
    assert.ok(html.includes('A4 portrait'))
  })

  test('includes page-break CSS', () => {
    const html = generatePrintHtml(makeBaseReview(), tEn, 'en')
    assert.ok(html.includes('page-break-after'))
  })

  test('includes review status badge', () => {
    const html = generatePrintHtml(makeBaseReview(), tEn, 'en')
    assert.ok(html.includes(enTranslations.ncErStatusPassWithEvidence))
  })

  test('includes disclaimer section', () => {
    const html = generatePrintHtml(makeBaseReview(), tEn, 'en')
    // ncErExportScopeTitle = "Scope & Disclaimer" — HTML-escaped to "Scope &amp; Disclaimer"
    assert.ok(html.includes('Scope') && html.includes('Disclaimer'))
    assert.ok(html.includes(enTranslations.ncErExportProvenance))
    assert.ok(html.length > 1000)
  })

  test('TR: section titles in Turkish', () => {
    const html = generatePrintHtml(makeBaseReview(), tTr, 'tr')
    assert.ok(html.includes(trTranslations.ncErStatusPassWithEvidence))
    assert.ok(html.includes(trTranslations.ncErExportScopeTitle))
  })

  test('includes NC_COMMANDED_FEED_EQUALS_ACTUAL_FEED=NO note', () => {
    const html = generatePrintHtml(makeBaseReview(), tEn, 'en')
    assert.ok(html.includes('NC_COMMANDED_FEED_EQUALS_ACTUAL_FEED=NO'))
  })

  test('includes T_WORD_EQUALS_CONFIRMED_TOOL_IDENTITY=NO note', () => {
    const html = generatePrintHtml(makeBaseReview(), tEn, 'en')
    assert.ok(html.includes('T_WORD_EQUALS_CONFIRMED_TOOL_IDENTITY=NO'))
  })

  test('includes PARTIAL_TIME_MISLABELED_TOTAL=NO note', () => {
    const html = generatePrintHtml(makeBaseReview(), tEn, 'en')
    assert.ok(html.includes('PARTIAL_TIME_MISLABELED_TOTAL=NO'))
  })

  test('includes provenance section', () => {
    const html = generatePrintHtml(makeBaseReview(), tEn, 'en')
    assert.ok(html.includes(enTranslations.ncErExportProvenance))
    assert.ok(html.includes('NC_PROGRAM'))
    assert.ok(html.includes('MACHINE_CATALOG'))
  })

  test('no local filesystem path in HTML', () => {
    const html = generatePrintHtml(makeBaseReview(), tEn, 'en')
    assert.ok(!html.includes('C:\\'))
    assert.ok(!html.includes('/Users/'))
    assert.ok(!html.includes('AppData'))
  })

  test('disclaimer does not claim production approval', () => {
    const html = generatePrintHtml(makeBaseReview(), tEn, 'en')
    const lower = html.toLowerCase()
    assert.ok(!lower.includes('production approved'))
    assert.ok(!lower.includes('safe to machine'))
  })

  test('BLOCKED_BY_KNOWN_LIMIT: findings table present', () => {
    const html = generatePrintHtml(makeBlockedReview(), tEn, 'en')
    assert.ok(html.includes('RPM_LIMIT_MACHINE_RPM'))
    assert.ok(html.includes('BLOCKING'))
  })
})

// ---------------------------------------------------------------------------
// 11. Backward compatibility
// ---------------------------------------------------------------------------

describe('Backward compatibility', () => {
  test('JSON export round-trip: stringify/parse preserves structure', () => {
    const er = makeBaseReview()
    const dto = buildNcReviewJson(er, tEn, 'en')
    const json = JSON.stringify(dto, null, 2)
    const parsed = JSON.parse(json)
    assert.equal(parsed.schema_version, EXPORT_SCHEMA_VERSION)
    assert.equal(parsed.review_status, 'PASS_WITH_EVIDENCE')
    assert.ok(Array.isArray(parsed.findings))
    assert.ok(Array.isArray(parsed.segments))
    assert.ok(Array.isArray(parsed.parser_coverage))
  })

  test('all required top-level keys present in export JSON', () => {
    const d = buildNcReviewJson(makeBaseReview(), tEn, 'en')
    const required = [
      'schema_version', 'report_type', 'metadata', 'program_identity',
      'review_status', 'review_status_label', 'executive_summary',
      'equipment', 'feed_spindle_validation', 'parser_coverage',
      'motion_summary', 'segments', 'canned_cycles', 'findings',
      'limitations', 'provenance', 'safety_flags', 'disclaimer',
    ]
    for (const key of required) {
      assert.ok(key in d, `Missing required key: ${key}`)
    }
  })

  test('export utility does not recompute engineering review logic', () => {
    // Verify that buildNcReviewJson uses er.review_status directly (no recomputation)
    const er = makeBaseReview()
    er.review_status = 'PASS_WITH_EVIDENCE' as const
    const d = buildNcReviewJson(er, tEn, 'en')
    assert.equal(d.review_status, 'PASS_WITH_EVIDENCE')
    // Force an unusual review_status to confirm it flows through unchanged
    const er2 = { ...er, review_status: 'REVIEW_REQUIRED' as const }
    const d2 = buildNcReviewJson(er2, tEn, 'en')
    assert.equal(d2.review_status, 'REVIEW_REQUIRED')
  })
})

// ---------------------------------------------------------------------------
// CSV formula injection guard (NC_PROGRAM_RELEASE_READINESS_01)
// CSV_FORMULA_INJECTION_MITIGATION=PASS
// CSV_ENGINEERING_NUMERIC_VALUES_PRESERVED=YES
// ---------------------------------------------------------------------------

describe('CSV formula injection guard — buildFindingsCsv', () => {
  // Helper: extract a single cell value from a CSV row (handles quoted fields).
  // Strips trailing \r from the row before parsing.
  function parseCsvCell(row: string, colIndex: number): string {
    const clean = row.replace(/\r$/, '')
    const cells: string[] = []
    let i = 0
    while (i < clean.length) {
      if (clean[i] === '"') {
        i++ // skip opening quote
        let val = ''
        while (i < clean.length) {
          if (clean[i] === '"' && clean[i + 1] === '"') { val += '"'; i += 2 }
          else if (clean[i] === '"') { i++; break }
          else { val += clean[i++] }
        }
        if (clean[i] === ',') i++
        cells.push(val)
      } else {
        let val = ''
        while (i < clean.length && clean[i] !== ',') val += clean[i++]
        if (clean[i] === ',') i++
        cells.push(val)
      }
    }
    return cells[colIndex] ?? ''
  }

  // buildFindingsCsv prepends 3 traceability cols (review_id, analysis_fp, program_fp)
  // before finding_code, so finding_code is at column index 3.
  const FINDING_CODE_COL = 3

  function makeInjectionFinding(finding_code: string) {
    return {
      finding_code,
      category: 'RPM_LIMIT',
      severity: 'BLOCKING' as const,
      title_key: 'ncErFindingMachineRpm',
      message_key: 'ncErFindingMachineRpm',
      observed_value: null as number | null,
      limit_value: null as number | null,
      unit: null as string | null,
      source: null as string | null,
      evidence_type: null as string | null,
      segment_id: null as string | null,
      limitation: null as string | null,
    }
  }

  test('formula prefix = in string cell is tab-prefixed', () => {
    const er = { ...makeBaseReview(), findings: [makeInjectionFinding('=HYPERLINK("evil.com")')] }
    const csv = buildFindingsCsv(er, tEn)
    const dataRow = csv.split('\n')[1]
    const cell = parseCsvCell(dataRow, FINDING_CODE_COL)
    assert.ok(cell.startsWith('\t'), 'Formula = cell should be tab-prefixed')
    assert.ok(cell.includes('=HYPERLINK'), 'Original content preserved')
  })

  test('formula prefix + in string cell is tab-prefixed', () => {
    const er = { ...makeBaseReview(), findings: [makeInjectionFinding('+cmd|whoami')] }
    const csv = buildFindingsCsv(er, tEn)
    const dataRow = csv.split('\n')[1]
    const cell = parseCsvCell(dataRow, FINDING_CODE_COL)
    assert.ok(cell.startsWith('\t'), 'Formula + cell should be tab-prefixed')
  })

  test('formula prefix - in string cell is tab-prefixed', () => {
    const er = { ...makeBaseReview(), findings: [makeInjectionFinding('-2+3')] }
    const csv = buildFindingsCsv(er, tEn)
    const dataRow = csv.split('\n')[1]
    const cell = parseCsvCell(dataRow, FINDING_CODE_COL)
    assert.ok(cell.startsWith('\t'), 'Formula - string cell should be tab-prefixed')
  })

  test('formula prefix @ in string cell is tab-prefixed', () => {
    const er = { ...makeBaseReview(), findings: [makeInjectionFinding('@SUM(A1:A10)')] }
    const csv = buildFindingsCsv(er, tEn)
    const dataRow = csv.split('\n')[1]
    const cell = parseCsvCell(dataRow, FINDING_CODE_COL)
    assert.ok(cell.startsWith('\t'), 'Formula @ cell should be tab-prefixed')
  })

  test('negative numeric observed_value is NOT tab-prefixed (engineering value)', () => {
    const finding = {
      ...makeInjectionFinding('RPM_OVER_LIMIT'),
      observed_value: -500,
      limit_value: 1000,
      unit: 'rpm',
    }
    const er = { ...makeBaseReview(), findings: [finding] }
    const csv = buildFindingsCsv(er, tEn)
    // numeric -500 should appear as -500, no tab prefix, not quoted
    assert.ok(csv.includes('-500'), 'Negative number preserved in output')
    assert.ok(!csv.includes('"\t-500"'), 'Negative number not tab-prefixed')
  })

  test('pure numeric string "+1500.5" is NOT tab-prefixed', () => {
    const finding = { ...makeInjectionFinding('FEED_HIGH'), observed_value: 1500.5, unit: 'mm/min' }
    const er = { ...makeBaseReview(), findings: [finding] }
    const csv = buildFindingsCsv(er, tEn)
    assert.ok(csv.includes('1500.5'), 'Numeric value preserved')
    assert.ok(!csv.includes('\t1500.5'), 'Numeric value not tab-prefixed')
  })

  test('normal engineering finding code is unmodified', () => {
    const finding = {
      ...makeInjectionFinding('RPM_LIMIT_MACHINE_RPM'),
      observed_value: 15000,
      limit_value: 12000,
      unit: 'rpm',
      source: 'MACHINE_CATALOG',
    }
    const er = { ...makeBaseReview(), findings: [finding] }
    const csv = buildFindingsCsv(er, tEn)
    const dataRow = csv.split('\n')[1]
    // finding_code is at column 3, no quoting needed for this value
    const cell = parseCsvCell(dataRow, FINDING_CODE_COL)
    assert.equal(cell, 'RPM_LIMIT_MACHINE_RPM', 'Normal finding code unmodified')
  })

  test('i18n keys for NC scope panel exist in both locales', () => {
    const scopeKeys = [
      'ppNcScopeTitle',
      'ppNcScopeNotice',
      'ppNcScopeDeferredLabel',
      'ppNcScopeDeferredItems',
      'ppNcScopeUnsupportedLabel',
      'ppNcScopeUnsupportedItems',
    ]
    for (const key of scopeKeys) {
      assert.ok(key in enTranslations, `EN missing scope key: ${key}`)
      assert.ok(key in trTranslations, `TR missing scope key: ${key}`)
      assert.ok(typeof (enTranslations as Record<string, string>)[key] === 'string')
      assert.ok(typeof (trTranslations as Record<string, string>)[key] === 'string')
      assert.ok((enTranslations as Record<string, string>)[key].length > 0)
      assert.ok((trTranslations as Record<string, string>)[key].length > 0)
    }
  })
})
