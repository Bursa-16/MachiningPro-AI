// NC Program Engineering Review — Export DTO, Utilities, and Print Report
// NC_PROGRAM_REPORTING_AND_EXPORT_01
//
// ENGINEERING_REVIEW_REUSED_FOR_EXPORT=YES
// EXPORT_RECOMPUTATION_DUPLICATED=NO
// PRIVATE_LOCAL_PATH_EXPORTED=NO
// CREDENTIAL_EXPORTED=NO
// ENVIRONMENT_VALUE_EXPORTED=NO

import type {
  NCProgramEngineeringReview,
  NCAnalysisTraceability,
  NCValidationFinding,
  NcMotionSegment,
  ParserFeatureCoverage,
  CannedCycleNote,
  EngReviewFinding,
} from '../services/nc_path'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const EXPORT_SCHEMA_VERSION = '1.0'
export const EXPORT_REPORT_TYPE = 'NC_PROGRAM_ENGINEERING_REVIEW' as const
export const EXPORT_APPLICATION_NAME = 'MachiningPro AI'
export const EXPORT_APPLICATION_VERSION = '0.1.0-alpha.10'
// NC_PROGRAM_TRACEABILITY_AND_AUDIT_01 — aligns with backend REVIEW_SCHEMA_VERSION
export const REVIEW_SCHEMA_VERSION = '1.0'

// Provenance categories — safe descriptive strings, no filesystem paths
const PROVENANCE: Record<string, string> = {
  NC_PROGRAM: 'User-supplied NC program text',
  MACHINE_CATALOG: 'MachiningPro AI machine catalog',
  CUTTING_TOOL_CATALOG: 'MachiningPro AI cutting tool catalog',
  TOOL_HOLDER_CATALOG: 'MachiningPro AI tool holder catalog',
  CUTTING_PARAMETER_REFERENCE: 'Catalog-backed reference ranges',
  DERIVED_FORMULA: 'Effective RPM = min(machine_max, tool_max, holder_max)',
  CYCLE_TIME_FOUNDATION: 'feed_distance / commanded_feed_rate',
  COMPATIBILITY_ENGINE: 'MachiningPro AI compatibility engine',
}

// ---------------------------------------------------------------------------
// Export DTO types
// ---------------------------------------------------------------------------

export interface NcReviewExportMeta {
  schema_version: string
  report_type: typeof EXPORT_REPORT_TYPE
  generated_at: string
  application: string
  application_version: string
  parser_profile: string
  parser_version: string
  language: string
  units: string
  nc_content_sha256: string | null
}

export interface NcReviewFindingExport {
  finding_code: string
  category: string
  severity: string
  title: string
  message: string
  observed_value: number | null
  limit_value: number | null
  unit: string | null
  source: string | null
  evidence_type: string | null
  segment_id: string | null
  limitation: string | null
}

export interface NcReviewSegmentExport {
  segment_id: string
  tool_id_raw: string | null
  t_word_equals_confirmed_tool_identity: false
  nc_feed_move_equals_confirmed_cutting: false
  feed_motion_distance_mm: number
  rapid_motion_distance_mm: number
  linear_motion_count: number
  arc_motion_count: number
  commanded_feed_min_mm_min: number | null
  commanded_feed_max_mm_min: number | null
  feed_mode: string | null
  commanded_spindle_rpm: number | null
  spindle_state: string | null
  analysis_status: string
  unsupported_features: string[]
}

// NC_PROGRAM_TRACEABILITY_AND_AUDIT_01 — export DTO types
export type TraceabilityStatusExport =
  | 'TRACEABLE'
  | 'PARTIALLY_TRACEABLE'
  | 'INSUFFICIENT_TRACEABILITY_DATA'

export type TraceabilityChangeState =
  | 'UNCHANGED'
  | 'PROGRAM_CHANGED'
  | 'CONFIGURATION_CHANGED'
  | 'PROGRAM_AND_CONFIGURATION_CHANGED'
  | 'VERSION_CHANGED'
  | 'UNKNOWN'

export interface NCAnalysisTraceabilityExport {
  review_id: string | null
  program_fingerprint: string | null
  configuration_fingerprint: string | null
  analysis_fingerprint: string | null
  traceability_status: TraceabilityStatusExport
  generated_at: string
  review_schema_version: string
  parser_profile: string
  parser_version: string
  machine_id: string | null
  cutting_tool_id: string | null
  tool_holder_id: string | null
  operation: string | null
  process_step_id: string | null
  material_iso_group: string | null
  // Immutable safety flags — always false
  hash_equals_digital_signature: false
  hash_equals_approval: false
  hash_equals_certification: false
  false_immutable_audit_claim: false
}

export type NcAuditEventType =
  | 'NC_ANALYSIS_CREATED'
  | 'NC_REVIEW_GENERATED'
  | 'NC_JSON_EXPORTED'
  | 'NC_CSV_EXPORTED'
  | 'NC_PRINT_OPENED'
  | 'NC_REVIEWED'
  // NC_PROGRAM_CHANGE_MANAGEMENT_01
  | 'NC_CHANGE_REVIEW_CREATED'
  | 'NC_BASELINE_SELECTED'
  | 'NC_CURRENT_SELECTED'
  | 'NC_CHANGE_REPORT_JSON_EXPORTED'
  | 'NC_CHANGE_REPORT_CSV_EXPORTED'
  | 'NC_CHANGE_REPORT_PRINT_OPENED'

export interface NcAuditEvent {
  event_id: string
  event_type: NcAuditEventType
  timestamp: string
  review_id: string | null
  analysis_fingerprint: string | null
  export_format: string | null
}

// Module-level session audit log (in-memory, not persisted)
const _sessionAuditLog: NcAuditEvent[] = []

export function getAuditEvents(): Readonly<NcAuditEvent[]> {
  return _sessionAuditLog
}

export function clearAuditEvents(): void {
  _sessionAuditLog.length = 0
}

export function addAuditEvent(event: NcAuditEvent): void {
  _sessionAuditLog.push(event)
}

export interface NcReviewExportJson {
  schema_version: string
  report_type: typeof EXPORT_REPORT_TYPE
  traceability: NCAnalysisTraceabilityExport | null
  metadata: NcReviewExportMeta
  program_identity: {
    source_name_safe: string | null
    parser_profile: string
    parser_version: string
    units_declared: string | null
    analysis_status: string
    segment_count: number
    tool_change_count: number
    supported_motion_count: number
    unsupported_construct_count: number
    arc_motion_count: number
  }
  review_status: string
  review_status_label: string
  executive_summary: {
    blocking_count: number
    warning_count: number
    advisory_count: number
    info_count: number
    insufficient_data_count: number
    unsupported_count: number
    total_feed_distance_mm: number
    total_rapid_distance_mm: number
    cycle_time_known_subtotal_sec: number | null
    cycle_time_status: string | null
    cycle_time_limitations: string[]
  }
  equipment: {
    machine_id: string | null
    machine_display: string | null
    cutting_tool_id: string | null
    cutting_tool_display: string | null
    tool_holder_id: string | null
    tool_holder_display: string | null
    machine_spindle_max_rpm: number | null
    tool_max_rpm: number | null
    holder_max_rpm: number | null
    effective_rpm_limit: number | null
    effective_rpm_limit_source: string | null
    missing_fields: string[]
    compatibility_status: string | null
    operation_association: string | null
  }
  feed_spindle_validation: {
    nc_feed_mode: string | null
    nc_commanded_feed_mm_min: number | null
    nc_commanded_feed_mm_rev: number | null
    nc_commanded_spindle_rpm: number | null
    nc_spindle_state: string | null
    calculated_cutting_speed_m_min: number | null
    calculated_feed_per_tooth_mm: number | null
    calculated_feed_per_rev_mm: number | null
    machine_rpm_limit_check: NCValidationFinding | null
    tool_rpm_limit_check: NCValidationFinding | null
    holder_rpm_limit_check: NCValidationFinding | null
    effective_rpm_limit_check: NCValidationFinding | null
    cutting_speed_check: NCValidationFinding | null
    feed_per_tooth_check: NCValidationFinding | null
    feed_per_rev_check: NCValidationFinding | null
    evidence_sources: string[]
    limitations: string[]
    safety_flags: {
      nc_commanded_spindle_speed_equals_actual_rpm: false
      nc_commanded_feed_equals_actual_feed: false
      reference_range_validation_is_optimization: false
    }
  }
  parser_coverage: ParserFeatureCoverage[]
  deferred_features_detected: string[]
  unsupported_features_detected: string[]
  motion_summary: {
    total_feed_distance_mm: number
    total_rapid_distance_mm: number
    safety_flags: {
      programmed_motion_equals_executed_motion: false
      programmed_feed_distance_equals_confirmed_cutting: false
    }
  }
  segments: NcReviewSegmentExport[]
  canned_cycles: Array<{
    cycle_code_str: string
    state: string
    bounded_reason: string | null
    detected_limitations: string[]
    bounded_canned_cycle_mislabeled_complete: false
  }>
  findings: NcReviewFindingExport[]
  limitations: string[]
  provenance: Record<string, string>
  safety_flags: {
    nc_file_executed: false
    machine_behavior_simulated: false
    collision_check_performed: false
    false_controller_compatibility_claim: false
    false_production_approval_claim: false
    false_safe_to_run_claim: false
    false_collision_free_claim: false
    partial_time_mislabeled_total: false
    private_path_in_api_response: false
    t_word_equals_confirmed_tool_identity: false
    programmed_motion_equals_executed_motion: false
    programmed_feed_distance_equals_confirmed_cutting: false
  }
  disclaimer: string
}

// ---------------------------------------------------------------------------
// Filename utility
// ---------------------------------------------------------------------------

export function buildExportFilename(
  sourceNameSafe: string | null | undefined,
  date: Date,
  ext: string,
): string {
  const rawName = (sourceNameSafe ?? '').replace(/[^a-zA-Z0-9_-]/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '')
  const safeName = rawName.length > 0 ? rawName.slice(0, 40) : 'Unnamed'
  const y = date.getUTCFullYear()
  const m = String(date.getUTCMonth() + 1).padStart(2, '0')
  const d = String(date.getUTCDate()).padStart(2, '0')
  return `MachiningPro_NC_Engineering_Review_${safeName}_${y}${m}${d}.${ext}`
}

export function buildExportFilenameSuffix(
  sourceNameSafe: string | null | undefined,
  date: Date,
  suffix: string,
  ext: string,
): string {
  const rawName = (sourceNameSafe ?? '').replace(/[^a-zA-Z0-9_-]/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '')
  const safeName = rawName.length > 0 ? rawName.slice(0, 40) : 'Unnamed'
  const y = date.getUTCFullYear()
  const m = String(date.getUTCMonth() + 1).padStart(2, '0')
  const d = String(date.getUTCDate()).padStart(2, '0')
  return `MachiningPro_NC_Engineering_Review_${safeName}_${y}${m}${d}_${suffix}.${ext}`
}

// ---------------------------------------------------------------------------
// Browser download trigger
// ---------------------------------------------------------------------------

export function triggerBrowserDownload(
  content: string,
  filename: string,
  mimeType: string,
): void {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  try {
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  } finally {
    URL.revokeObjectURL(url)
  }
}

// ---------------------------------------------------------------------------
// Export audit event — safe lightweight logging
// Do NOT log raw NC content, credentials, or filesystem paths.
// ---------------------------------------------------------------------------

export function logExportEvent(
  format: string,
  reviewStatus: string,
  reviewId?: string | null,
  analysisFingerprint?: string | null,
): void {
  const eventTypeMap: Record<string, NcAuditEventType> = {
    json: 'NC_JSON_EXPORTED',
    csv_findings: 'NC_CSV_EXPORTED',
    csv_segments: 'NC_CSV_EXPORTED',
    csv_coverage: 'NC_CSV_EXPORTED',
    print: 'NC_PRINT_OPENED',
  }
  const eventType: NcAuditEventType = eventTypeMap[format] ?? 'NC_REVIEW_GENERATED'
  const event: NcAuditEvent = {
    event_id: crypto.randomUUID(),
    event_type: eventType,
    timestamp: new Date().toISOString(),
    review_id: reviewId ?? null,
    analysis_fingerprint: analysisFingerprint ?? null,
    export_format: format,
  }
  addAuditEvent(event)
  console.info('[nc-export]', { event: 'nc_review_exported', format, review_status: reviewStatus, timestamp: event.timestamp, review_id: event.review_id })
}

// ---------------------------------------------------------------------------
// NC content normalization and fingerprinting
// NC_NORMALIZATION_POLICY=CONSERVATIVE
// NC_NORMALIZATION_SEMANTIC_RISK=LOW
// ---------------------------------------------------------------------------

export function normalizeNcContent(ncText: string): string {
  let s = ncText.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
  if (s.startsWith('﻿')) s = s.slice(1)
  return s.split('\n').map(line => line.trimEnd()).join('\n')
}

export async function computeNcSha256(ncText: string): Promise<string | null> {
  try {
    const encoder = new TextEncoder()
    const normalized = normalizeNcContent(ncText)
    const data = encoder.encode(normalized)
    const hashBuffer = await crypto.subtle.digest('SHA-256', data)
    const hashArray = Array.from(new Uint8Array(hashBuffer))
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('')
  } catch {
    return null
  }
}

export async function computeConfigFingerprint(config: {
  machine_id?: string | null
  cutting_tool_id?: string | null
  tool_holder_id?: string | null
  operation?: string | null
  material_iso_group?: string | null
  process_step_id?: string | null
}): Promise<string | null> {
  try {
    const stable = {
      cutting_tool_id: config.cutting_tool_id ?? null,
      machine_id: config.machine_id ?? null,
      material_iso_group: config.material_iso_group ?? null,
      operation: config.operation ? config.operation.toLowerCase() : null,
      process_step_id: config.process_step_id ?? null,
      tool_holder_id: config.tool_holder_id ?? null,
    }
    const json = JSON.stringify(stable, Object.keys(stable).sort())
    const encoder = new TextEncoder()
    const data = encoder.encode(json)
    const hashBuffer = await crypto.subtle.digest('SHA-256', data)
    const hashArray = Array.from(new Uint8Array(hashBuffer))
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('')
  } catch {
    return null
  }
}

export async function computeAnalysisFingerprint(
  programFingerprint: string | null,
  configFingerprint: string | null,
  parserProfile: string,
  reviewSchemaVersion: string,
): Promise<string | null> {
  if (!programFingerprint || !configFingerprint) return null
  try {
    const combined = `${programFingerprint}|${configFingerprint}|${parserProfile}|${reviewSchemaVersion}`
    const encoder = new TextEncoder()
    const data = encoder.encode(combined)
    const hashBuffer = await crypto.subtle.digest('SHA-256', data)
    const hashArray = Array.from(new Uint8Array(hashBuffer))
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('')
  } catch {
    return null
  }
}

export function buildShortHash(fullHash: string | null | undefined, length = 12): string {
  if (!fullHash) return '—'
  return fullHash.slice(0, length) + '…'
}

export function computeChangeState(
  current: NCAnalysisTraceabilityExport,
  prior: NCAnalysisTraceabilityExport,
): TraceabilityChangeState {
  if (
    current.review_schema_version !== prior.review_schema_version ||
    current.parser_profile !== prior.parser_profile ||
    current.parser_version !== prior.parser_version
  ) {
    return 'VERSION_CHANGED'
  }
  const progSame = current.program_fingerprint === prior.program_fingerprint
  const cfgSame = current.configuration_fingerprint === prior.configuration_fingerprint
  if (progSame && cfgSame) return 'UNCHANGED'
  if (!progSame && !cfgSame) return 'PROGRAM_AND_CONFIGURATION_CHANGED'
  if (!progSame) return 'PROGRAM_CHANGED'
  if (!cfgSame) return 'CONFIGURATION_CHANGED'
  return 'UNKNOWN'
}

function _buildTraceabilityExport(
  tr: NCAnalysisTraceability,
): NCAnalysisTraceabilityExport {
  return {
    review_id: tr.review_id,
    program_fingerprint: tr.program_fingerprint,
    configuration_fingerprint: tr.configuration_fingerprint,
    analysis_fingerprint: tr.analysis_fingerprint,
    traceability_status: tr.traceability_status as TraceabilityStatusExport,
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
    hash_equals_digital_signature: false,
    hash_equals_approval: false,
    hash_equals_certification: false,
    false_immutable_audit_claim: false,
  }
}

// ---------------------------------------------------------------------------
// JSON export
// ---------------------------------------------------------------------------

export function buildNcReviewJson(
  er: NCProgramEngineeringReview,
  t: (key: string) => string,
  locale: string,
  ncContentSha256?: string | null,
): NcReviewExportJson {
  const now = new Date().toISOString()
  const units = er.units_declared ?? 'mm'
  const disclaimer = t('ncErExportDisclaimer')

  const meta: NcReviewExportMeta = {
    schema_version: EXPORT_SCHEMA_VERSION,
    report_type: EXPORT_REPORT_TYPE,
    generated_at: now,
    application: EXPORT_APPLICATION_NAME,
    application_version: EXPORT_APPLICATION_VERSION,
    parser_profile: er.parser_profile,
    parser_version: er.parser_version,
    language: locale,
    units,
    nc_content_sha256: ncContentSha256 ?? null,
  }

  const findings: NcReviewFindingExport[] = er.findings.map((f: EngReviewFinding) => ({
    finding_code: f.finding_code,
    category: f.category,
    severity: f.severity,
    title: t(f.title_key) || f.title_key,
    message: t(f.message_key) || f.message_key,
    observed_value: f.observed_value,
    limit_value: f.limit_value,
    unit: f.unit,
    source: f.source,
    evidence_type: f.evidence_type,
    segment_id: f.segment_id,
    limitation: f.limitation,
  }))

  const segments: NcReviewSegmentExport[] = er.segments.map((s: NcMotionSegment) => ({
    segment_id: s.segment_id,
    tool_id_raw: s.tool_id_raw,
    t_word_equals_confirmed_tool_identity: false,
    nc_feed_move_equals_confirmed_cutting: false,
    feed_motion_distance_mm: s.feed_motion_distance_mm,
    rapid_motion_distance_mm: s.rapid_motion_distance_mm,
    linear_motion_count: s.linear_motion_count,
    arc_motion_count: s.arc_motion_count,
    commanded_feed_min_mm_min: s.commanded_feed_min,
    commanded_feed_max_mm_min: s.commanded_feed_max,
    feed_mode: s.feed_mode,
    commanded_spindle_rpm: s.commanded_spindle_rpm,
    spindle_state: s.spindle_state,
    analysis_status: s.analysis_status,
    unsupported_features: s.unsupported_features,
  }))

  const canned_cycles = er.canned_cycle_notes.map((c: CannedCycleNote) => ({
    cycle_code_str: c.cycle_code_str,
    state: c.state,
    bounded_reason: c.bounded_reason,
    detected_limitations: c.detected_limitations,
    bounded_canned_cycle_mislabeled_complete: false as const,
  }))

  const statusLabels: Record<string, string> = {
    PASS_WITH_EVIDENCE: t('ncErStatusPassWithEvidence'),
    PASS_WITH_ADVISORIES: t('ncErStatusPassWithAdvisories'),
    REVIEW_REQUIRED: t('ncErStatusReviewRequired'),
    BLOCKED_BY_KNOWN_LIMIT: t('ncErStatusBlockedByKnownLimit'),
    INSUFFICIENT_DATA: t('ncErStatusInsufficientData'),
    UNSUPPORTED_FEATURES_PRESENT: t('ncErStatusUnsupportedFeaturesPresent'),
  }

  const traceabilityExport: NCAnalysisTraceabilityExport | null =
    er.traceability ? _buildTraceabilityExport(er.traceability) : null

  return {
    schema_version: EXPORT_SCHEMA_VERSION,
    report_type: EXPORT_REPORT_TYPE,
    traceability: traceabilityExport,
    metadata: meta,
    program_identity: {
      source_name_safe: er.source_name_safe,
      parser_profile: er.parser_profile,
      parser_version: er.parser_version,
      units_declared: er.units_declared,
      analysis_status: er.analysis_status,
      segment_count: er.segment_count,
      tool_change_count: er.tool_change_count,
      supported_motion_count: er.supported_motion_count,
      unsupported_construct_count: er.unsupported_construct_count,
      arc_motion_count: er.arc_motion_count,
    },
    review_status: er.review_status,
    review_status_label: statusLabels[er.review_status] ?? er.review_status,
    executive_summary: {
      blocking_count: er.blocking_count,
      warning_count: er.warning_count,
      advisory_count: er.advisory_count,
      info_count: er.info_count,
      insufficient_data_count: er.insufficient_data_count,
      unsupported_count: er.unsupported_count,
      total_feed_distance_mm: er.total_feed_distance_mm,
      total_rapid_distance_mm: er.total_rapid_distance_mm,
      cycle_time_known_subtotal_sec: er.cycle_time_known_subtotal_sec,
      cycle_time_status: er.cycle_time_status,
      cycle_time_limitations: er.cycle_time_limitations,
    },
    equipment: {
      machine_id: er.equipment.machine_id,
      machine_display: er.equipment.machine_display,
      cutting_tool_id: er.equipment.cutting_tool_id,
      cutting_tool_display: er.equipment.cutting_tool_display,
      tool_holder_id: er.equipment.tool_holder_id,
      tool_holder_display: er.equipment.tool_holder_display,
      machine_spindle_max_rpm: er.equipment.machine_spindle_max_rpm,
      tool_max_rpm: er.equipment.tool_max_rpm,
      holder_max_rpm: er.equipment.holder_max_rpm,
      effective_rpm_limit: er.equipment.effective_rpm_limit,
      effective_rpm_limit_source: er.equipment.effective_rpm_limit_source,
      missing_fields: er.equipment.missing_fields,
      compatibility_status: er.compatibility_status,
      operation_association: er.operation_association,
    },
    feed_spindle_validation: {
      nc_feed_mode: er.validation_summary.nc_feed_mode,
      nc_commanded_feed_mm_min: er.validation_summary.nc_commanded_feed_mm_min,
      nc_commanded_feed_mm_rev: er.validation_summary.nc_commanded_feed_mm_rev,
      nc_commanded_spindle_rpm: er.validation_summary.nc_commanded_spindle_rpm,
      nc_spindle_state: er.validation_summary.nc_spindle_state,
      calculated_cutting_speed_m_min: er.validation_summary.calculated_cutting_speed_m_min,
      calculated_feed_per_tooth_mm: er.validation_summary.calculated_feed_per_tooth_mm,
      calculated_feed_per_rev_mm: er.validation_summary.calculated_feed_per_rev_mm,
      machine_rpm_limit_check: er.validation_summary.machine_rpm_limit_check,
      tool_rpm_limit_check: er.validation_summary.tool_rpm_limit_check,
      holder_rpm_limit_check: er.validation_summary.holder_rpm_limit_check,
      effective_rpm_limit_check: er.validation_summary.effective_rpm_limit_check,
      cutting_speed_check: er.validation_summary.cutting_speed_check,
      feed_per_tooth_check: er.validation_summary.feed_per_tooth_check,
      feed_per_rev_check: er.validation_summary.feed_per_rev_check,
      evidence_sources: er.validation_summary.evidence_sources,
      limitations: er.validation_summary.limitations,
      safety_flags: {
        nc_commanded_spindle_speed_equals_actual_rpm: false,
        nc_commanded_feed_equals_actual_feed: false,
        reference_range_validation_is_optimization: false,
      },
    },
    parser_coverage: er.feature_coverage,
    deferred_features_detected: er.deferred_features_detected,
    unsupported_features_detected: er.unsupported_features_detected,
    motion_summary: {
      total_feed_distance_mm: er.total_feed_distance_mm,
      total_rapid_distance_mm: er.total_rapid_distance_mm,
      safety_flags: {
        programmed_motion_equals_executed_motion: false,
        programmed_feed_distance_equals_confirmed_cutting: false,
      },
    },
    segments,
    canned_cycles,
    findings,
    limitations: er.limitations,
    provenance: PROVENANCE,
    safety_flags: {
      nc_file_executed: false,
      machine_behavior_simulated: false,
      collision_check_performed: false,
      false_controller_compatibility_claim: false,
      false_production_approval_claim: false,
      false_safe_to_run_claim: false,
      false_collision_free_claim: false,
      partial_time_mislabeled_total: false,
      private_path_in_api_response: false,
      t_word_equals_confirmed_tool_identity: false,
      programmed_motion_equals_executed_motion: false,
      programmed_feed_distance_equals_confirmed_cutting: false,
    },
    disclaimer,
  }
}

// ---------------------------------------------------------------------------
// CSV utilities
// ---------------------------------------------------------------------------

function csvField(v: string | number | null | undefined | boolean): string {
  if (v === null || v === undefined) return ''
  // Numbers are always safe — cannot be formula prefixes
  if (typeof v === 'number') return String(v)
  const s = String(v).replace(/\n/g, ' ').replace(/\r/g, '')
  const trimmed = s.trimStart()
  // OWASP CSV formula injection guard: strings starting with =, +, -, @ that are
  // not pure numeric (e.g. G-code values like "+1.5" are numeric, not formulas)
  const isFormulaPrefix = trimmed.length > 0 && /^[=+\-@]/.test(trimmed)
  const isPureNumber = /^[+-]?\d+(\.\d+)?([eE][+-]?\d+)?$/.test(trimmed)
  const needsFormulaGuard = isFormulaPrefix && !isPureNumber
  const needsQuote = s.includes(',') || s.includes('"') || s.includes('\n') || needsFormulaGuard
  if (needsQuote) {
    const content = needsFormulaGuard ? '\t' + s : s
    return '"' + content.replace(/"/g, '""') + '"'
  }
  return s
}

function csvRow(fields: (string | number | null | undefined | boolean)[]): string {
  return fields.map(csvField).join(',')
}

// UTF-8 BOM prefix for Excel compatibility with Turkish/Unicode characters
const CSV_BOM = '﻿'

export function buildFindingsCsv(
  er: NCProgramEngineeringReview,
  t: (key: string) => string,
): string {
  const reviewId = er.traceability?.review_id ?? null
  const analysisFingerprint = er.traceability?.analysis_fingerprint ?? null
  const programFingerprint = er.traceability?.program_fingerprint ?? null
  const header = csvRow([
    'review_id', 'analysis_fingerprint', 'program_fingerprint',
    'finding_code', 'category', 'severity', 'title', 'message',
    'observed_value', 'limit_value', 'unit', 'source', 'evidence_type',
    'segment_id', 'limitation',
  ])
  const rows = er.findings.map((f: EngReviewFinding) =>
    csvRow([
      reviewId,
      analysisFingerprint,
      programFingerprint,
      f.finding_code,
      f.category,
      f.severity,
      t(f.title_key) || f.title_key,
      t(f.message_key) || f.message_key,
      f.observed_value,
      f.limit_value,
      f.unit,
      f.source,
      f.evidence_type,
      f.segment_id,
      f.limitation,
    ])
  )
  return CSV_BOM + [header, ...rows].join('\r\n')
}

export function buildSegmentsCsv(er: NCProgramEngineeringReview): string {
  const reviewId = er.traceability?.review_id ?? null
  const analysisFingerprint = er.traceability?.analysis_fingerprint ?? null
  const programFingerprint = er.traceability?.program_fingerprint ?? null
  const header = csvRow([
    'review_id', 'analysis_fingerprint', 'program_fingerprint',
    'segment_id', 'tool_id_raw_nc_t_word', 't_word_equals_confirmed_tool_identity',
    'feed_motion_distance_mm', 'rapid_motion_distance_mm',
    'linear_motion_count', 'arc_motion_count',
    'commanded_feed_min_mm_min', 'commanded_feed_max_mm_min',
    'feed_mode', 'commanded_spindle_rpm', 'spindle_state',
    'analysis_status', 'unsupported_features',
  ])
  const rows = er.segments.map((s: NcMotionSegment) =>
    csvRow([
      reviewId,
      analysisFingerprint,
      programFingerprint,
      s.segment_id,
      s.tool_id_raw,
      false,
      s.feed_motion_distance_mm,
      s.rapid_motion_distance_mm,
      s.linear_motion_count,
      s.arc_motion_count,
      s.commanded_feed_min,
      s.commanded_feed_max,
      s.feed_mode,
      s.commanded_spindle_rpm,
      s.spindle_state,
      s.analysis_status,
      s.unsupported_features.join('|'),
    ])
  )
  return CSV_BOM + [header, ...rows].join('\r\n')
}

export function buildCoverageCsv(
  er: NCProgramEngineeringReview,
  t: (key: string) => string,
): string {
  const reviewId = er.traceability?.review_id ?? null
  const analysisFingerprint = er.traceability?.analysis_fingerprint ?? null
  const programFingerprint = er.traceability?.program_fingerprint ?? null
  const header = csvRow(['review_id', 'analysis_fingerprint', 'program_fingerprint', 'feature', 'state', 'detected', 'note'])
  void header
  const stateLabel: Record<string, string> = {
    SUPPORTED: t('ncErStateSupported'),
    BOUNDED: t('ncErStateBounded'),
    DEFERRED: t('ncErStateDeferred'),
    UNSUPPORTED: t('ncErStateUnsupported'),
    INSUFFICIENT_SEMANTICS: t('ncErStateInsufficientSemantics'),
  }
  const rows = er.feature_coverage.map((fc: ParserFeatureCoverage) =>
    csvRow([
      fc.feature,
      fc.state,
      fc.detected,
      fc.note,
    ])
  )
  // Include state label column and leading traceability columns
  const headerWithLabel = csvRow([
    'review_id', 'analysis_fingerprint', 'program_fingerprint',
    'feature', 'state', 'state_label', 'detected', 'note',
  ])
  const rowsWithLabel = er.feature_coverage.map((fc: ParserFeatureCoverage) =>
    csvRow([
      reviewId,
      analysisFingerprint,
      programFingerprint,
      fc.feature,
      fc.state,
      stateLabel[fc.state] ?? fc.state,
      fc.detected,
      fc.note,
    ])
  )
  void rows
  return CSV_BOM + [headerWithLabel, ...rowsWithLabel].join('\r\n')
}

// ---------------------------------------------------------------------------
// Print-ready HTML report generator
// ---------------------------------------------------------------------------

const STATUS_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  PASS_WITH_EVIDENCE: { bg: '#dcfce7', text: '#15803d', border: '#86efac' },
  PASS_WITH_ADVISORIES: { bg: '#dbeafe', text: '#1d4ed8', border: '#93c5fd' },
  REVIEW_REQUIRED: { bg: '#fef3c7', text: '#92400e', border: '#fcd34d' },
  BLOCKED_BY_KNOWN_LIMIT: { bg: '#fee2e2', text: '#991b1b', border: '#fca5a5' },
  INSUFFICIENT_DATA: { bg: '#f3f4f6', text: '#374151', border: '#d1d5db' },
  UNSUPPORTED_FEATURES_PRESENT: { bg: '#ffedd5', text: '#9a3412', border: '#fdba74' },
}

const SEV_COLORS: Record<string, { bg: string; text: string }> = {
  BLOCKING: { bg: '#fee2e2', text: '#991b1b' },
  WARNING: { bg: '#fef3c7', text: '#92400e' },
  ADVISORY: { bg: '#dbeafe', text: '#1d4ed8' },
  INFO: { bg: '#f3f4f6', text: '#374151' },
  INSUFFICIENT_DATA: { bg: '#f3f4f6', text: '#6b7280' },
  NOT_APPLICABLE: { bg: '#f3f4f6', text: '#9ca3af' },
}

function esc(s: string | null | undefined): string {
  if (s == null) return ''
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function fmtNum(v: number | null | undefined, dp: number): string {
  if (v == null) return '—'
  return v.toFixed(dp)
}

function statusBadge(status: string, label: string): string {
  const col = STATUS_COLORS[status] ?? { bg: '#f3f4f6', text: '#374151', border: '#d1d5db' }
  return `<span style="display:inline-block;padding:3px 10px;border-radius:4px;font-weight:600;font-size:11pt;background:${col.bg};color:${col.text};border:1px solid ${col.border}">${esc(label)}</span>`
}

function sevBadge(sev: string): string {
  const col = SEV_COLORS[sev] ?? SEV_COLORS.INFO
  return `<span style="display:inline-block;padding:1px 6px;border-radius:3px;font-size:9pt;font-weight:600;background:${col.bg};color:${col.text}">${esc(sev)}</span>`
}

function sectionTitle(text: string): string {
  return `<h2 style="font-size:13pt;font-weight:700;color:#1e293b;border-bottom:2px solid #e2e8f0;padding-bottom:4pt;margin:0 0 10pt 0">${esc(text)}</h2>`
}

function kv(label: string, value: string | number | null | undefined, unit?: string): string {
  const valStr = value == null ? '<span style="color:#9ca3af">—</span>' : `<strong>${esc(String(value))}</strong>${unit ? ` <span style="color:#6b7280;font-size:9pt">${esc(unit)}</span>` : ''}`
  return `<tr><td style="color:#6b7280;padding:2pt 8pt 2pt 0;width:45%">${esc(label)}</td><td style="padding:2pt 0">${valStr}</td></tr>`
}

function tableHead(...cols: string[]): string {
  return `<tr style="background:#f8fafc">${cols.map(c => `<th style="text-align:left;padding:4pt 8pt;border-bottom:1px solid #e2e8f0;font-size:9pt;font-weight:600;color:#475569">${esc(c)}</th>`).join('')}</tr>`
}

function tableCellRow(...cells: string[]): string {
  return `<tr style="border-bottom:1px solid #f1f5f9">${cells.map(c => `<td style="padding:3pt 8pt;font-size:9pt;color:#374151;vertical-align:top">${c}</td>`).join('')}</tr>`
}

export function generatePrintHtml(
  er: NCProgramEngineeringReview,
  t: (key: string) => string,
  locale: string,
): string {
  const now = new Date()
  const genAt = now.toISOString().replace('T', ' ').replace(/\.\d+Z$/, ' UTC')
  const disclaimer = t('ncErExportDisclaimer')

  const statusLabels: Record<string, string> = {
    PASS_WITH_EVIDENCE: t('ncErStatusPassWithEvidence'),
    PASS_WITH_ADVISORIES: t('ncErStatusPassWithAdvisories'),
    REVIEW_REQUIRED: t('ncErStatusReviewRequired'),
    BLOCKED_BY_KNOWN_LIMIT: t('ncErStatusBlockedByKnownLimit'),
    INSUFFICIENT_DATA: t('ncErStatusInsufficientData'),
    UNSUPPORTED_FEATURES_PRESENT: t('ncErStatusUnsupportedFeaturesPresent'),
  }
  const stateLabels: Record<string, string> = {
    SUPPORTED: t('ncErStateSupported'),
    BOUNDED: t('ncErStateBounded'),
    DEFERRED: t('ncErStateDeferred'),
    UNSUPPORTED: t('ncErStateUnsupported'),
    INSUFFICIENT_SEMANTICS: t('ncErStateInsufficientSemantics'),
  }
  const statusLabel = statusLabels[er.review_status] ?? er.review_status
  const programName = er.source_name_safe ?? '—'

  // ---- Cover ----
  const cover = `
<div class="page-break">
  <div style="text-align:center;padding:40pt 0">
    <div style="font-size:10pt;color:#64748b;font-weight:600;letter-spacing:0.15em;text-transform:uppercase;margin-bottom:8pt">${esc(EXPORT_APPLICATION_NAME)}</div>
    <h1 style="font-size:22pt;font-weight:700;color:#0f172a;margin:0 0 16pt 0">${esc(t('ncEngineeringReview'))}</h1>
    <div style="margin-bottom:16pt">${statusBadge(er.review_status, statusLabel)}</div>
    <table style="margin:0 auto;border:none">
      ${kv(t('ncErParserProfile'), er.parser_profile)}
      ${kv('Program', programName)}
      ${kv(locale === 'tr' ? 'Oluşturulma' : 'Generated', genAt)}
      ${kv(locale === 'tr' ? 'Sürüm' : 'Version', EXPORT_SCHEMA_VERSION)}
      ${kv(locale === 'tr' ? 'Dil' : 'Language', locale.toUpperCase())}
    </table>
  </div>
</div>`

  // ---- Executive Summary ----
  const exec = `
<div class="page-break">
  ${sectionTitle(t('ncErExecutiveSummary'))}
  <table style="width:100%;border-collapse:collapse;margin-bottom:12pt">
    ${kv(t('ncErSegments'), er.segment_count)}
    ${kv(t('ncErToolChanges'), er.tool_change_count)}
    ${kv(t('ncErSupportedMotions'), er.supported_motion_count)}
    ${kv(t('ncErUnsupportedConstructs'), er.unsupported_construct_count)}
    ${kv(t('ncErBlockingCount'), er.blocking_count)}
    ${kv(t('ncErWarningCount'), er.warning_count)}
    ${kv(t('ncErAdvisoryCount'), er.advisory_count)}
  </table>
  <table style="width:100%;border-collapse:collapse;margin-bottom:12pt">
    ${kv(locale === 'tr' ? 'Programlanmış İlerleme Mesafesi' : 'Programmed Feed Distance', fmtNum(er.total_feed_distance_mm, 3), 'mm')}
    ${kv(locale === 'tr' ? 'Programlanmış Hızlı Hareket' : 'Programmed Rapid Distance', fmtNum(er.total_rapid_distance_mm, 3), 'mm')}
    ${kv(t('ncErCycleTimeSubtotalLabel'), er.cycle_time_known_subtotal_sec != null ? fmtNum(er.cycle_time_known_subtotal_sec, 1) : null, er.cycle_time_known_subtotal_sec != null ? 's' : undefined)}
  </table>
  <p style="font-size:9pt;color:#6b7280;font-style:italic;margin:0">${esc(t('ncErProgrammedFeedNote'))}</p>
</div>`

  // ---- Parser Coverage ----
  const covRows = er.feature_coverage.map((fc: ParserFeatureCoverage) => {
    const stateCol = STATUS_COLORS[fc.state] ?? { text: '#374151', bg: '#f3f4f6', border: '#d1d5db' }
    const stateBadge = `<span style="font-size:9pt;font-weight:600;color:${stateCol.text}">${esc(stateLabels[fc.state] ?? fc.state)}</span>`
    return tableCellRow(
      esc(fc.feature),
      stateBadge,
      fc.detected ? (locale === 'tr' ? 'Evet' : 'Yes') : (locale === 'tr' ? 'Hayır' : 'No'),
      esc(fc.note ?? ''),
    )
  }).join('')

  const coverage = `
<div class="page-break">
  ${sectionTitle(t('ncErProgramCoverage'))}
  <div style="overflow-x:auto">
    <table style="width:100%;border-collapse:collapse;font-size:9pt">
      ${tableHead(locale === 'tr' ? 'Özellik' : 'Feature', locale === 'tr' ? 'Durum' : 'State', locale === 'tr' ? 'Tespit' : 'Detected', locale === 'tr' ? 'Not' : 'Note')}
      ${covRows}
    </table>
  </div>
  ${er.deferred_features_detected.length > 0 ? `<p style="font-size:9pt;color:#92400e;margin:8pt 0 0"><strong>${esc(t('ncErUnsupportedFeatures'))} (Deferred):</strong> ${esc(er.deferred_features_detected.join(', '))}</p>` : ''}
  ${er.unsupported_features_detected.length > 0 ? `<p style="font-size:9pt;color:#991b1b;margin:4pt 0 0"><strong>${esc(t('ncErUnsupportedFeatures'))} (Unsupported):</strong> ${esc(er.unsupported_features_detected.join(', '))}</p>` : ''}
</div>`

  // ---- Equipment / Configuration ----
  const eqp = er.equipment
  const equipment = `
<div class="page-break">
  ${sectionTitle(t('ncErMachineConfig') + ' / ' + t('ncErToolConfig') + ' / ' + t('ncErHolderConfig'))}
  <table style="width:100%;border-collapse:collapse;margin-bottom:12pt">
    ${kv(t('ncErMachineConfig'), eqp.machine_display ?? eqp.machine_id)}
    ${kv(locale === 'tr' ? 'Maks. Devir (Tezgah)' : 'Machine Max RPM', eqp.machine_spindle_max_rpm, 'rpm')}
    ${kv(t('ncErToolConfig'), eqp.cutting_tool_display ?? eqp.cutting_tool_id)}
    ${kv(locale === 'tr' ? 'Maks. Devir (Takım)' : 'Tool Max RPM', eqp.tool_max_rpm, 'rpm')}
    ${kv(t('ncErHolderConfig'), eqp.tool_holder_display ?? eqp.tool_holder_id)}
    ${kv(locale === 'tr' ? 'Maks. Devir (Tutucu)' : 'Holder Max RPM', eqp.holder_max_rpm, 'rpm')}
    ${kv(t('ncErEffectiveRpmLimit'), eqp.effective_rpm_limit, 'rpm')}
    ${kv(locale === 'tr' ? 'Efektif Limit Kaynağı' : 'Effective Limit Source', eqp.effective_rpm_limit_source)}
    ${kv(locale === 'tr' ? 'Uyumluluk' : 'Compatibility', er.compatibility_status)}
    ${kv(locale === 'tr' ? 'Operasyon' : 'Operation', er.operation_association)}
  </table>
  ${eqp.missing_fields.length > 0 ? `<p style="font-size:9pt;color:#92400e"><strong>${esc(t('ncErMissingFields'))}:</strong> ${esc(eqp.missing_fields.join(', '))}</p>` : ''}
</div>`

  // ---- Feed & Spindle Validation ----
  const vs = er.validation_summary
  const feedSpindle = `
<div class="page-break">
  ${sectionTitle(t('ncErFeedSpindleValidation'))}
  <table style="width:100%;border-collapse:collapse;margin-bottom:12pt">
    ${kv(locale === 'tr' ? 'İlerleme Modu' : 'Feed Mode', vs.nc_feed_mode)}
    ${kv(locale === 'tr' ? 'Komut Edilen İlerleme (mm/dak)' : 'NC Commanded Feed (mm/min)', vs.nc_commanded_feed_mm_min, 'mm/min')}
    ${kv(locale === 'tr' ? 'Komut Edilen İlerleme (mm/dev)' : 'NC Commanded Feed (mm/rev)', vs.nc_commanded_feed_mm_rev, 'mm/rev')}
    ${kv(locale === 'tr' ? 'Komut Edilen Devir' : 'NC Commanded Spindle', vs.nc_commanded_spindle_rpm, 'rpm')}
    ${kv(locale === 'tr' ? 'Mil Durumu' : 'Spindle State', vs.nc_spindle_state)}
    ${kv(locale === 'tr' ? 'Hesaplanan Vc' : 'Calculated Vc', vs.calculated_cutting_speed_m_min != null ? fmtNum(vs.calculated_cutting_speed_m_min, 2) : null, 'm/min')}
    ${kv(locale === 'tr' ? 'Hesaplanan fz' : 'Calculated fz', vs.calculated_feed_per_tooth_mm != null ? fmtNum(vs.calculated_feed_per_tooth_mm, 4) : null, 'mm/tooth')}
    ${kv(locale === 'tr' ? 'Hesaplanan fn' : 'Calculated fn', vs.calculated_feed_per_rev_mm != null ? fmtNum(vs.calculated_feed_per_rev_mm, 4) : null, 'mm/rev')}
  </table>
  <p style="font-size:8pt;color:#6b7280;font-style:italic;margin:0">${locale === 'tr' ? 'NC komut edilen değerler gerçek değerler değildir (NC_COMMANDED_FEED_EQUALS_ACTUAL_FEED=NO)' : 'NC commanded values are not actual machine values (NC_COMMANDED_FEED_EQUALS_ACTUAL_FEED=NO)'}</p>
</div>`

  // ---- Motion Summary ----
  const motion = `
<div>
  ${sectionTitle(t('ncErMotionSummary'))}
  <table style="width:100%;border-collapse:collapse;margin-bottom:8pt">
    ${kv(locale === 'tr' ? 'Programlanmış İlerleme Mesafesi' : 'Programmed Feed Distance', fmtNum(er.total_feed_distance_mm, 3), 'mm')}
    ${kv(locale === 'tr' ? 'Programlanmış Hızlı Hareket' : 'Programmed Rapid Distance', fmtNum(er.total_rapid_distance_mm, 3), 'mm')}
  </table>
  <p style="font-size:9pt;color:#6b7280;font-style:italic;margin:0">${esc(t('ncErProgrammedFeedNote'))}</p>
</div>`

  // ---- Segments ----
  const segRows = er.segments.map((s: NcMotionSegment) =>
    tableCellRow(
      esc(s.segment_id),
      esc(s.tool_id_raw ?? '—'),
      fmtNum(s.feed_motion_distance_mm, 3),
      fmtNum(s.rapid_motion_distance_mm, 3),
      s.commanded_spindle_rpm != null ? String(s.commanded_spindle_rpm) : '—',
      esc(s.feed_mode ?? '—'),
      esc(s.analysis_status),
    )
  ).join('')

  const segments = `
<div class="page-break">
  ${sectionTitle(locale === 'tr' ? 'Segment / Operasyon Eşleme' : 'Segment / Operation Mapping')}
  <p style="font-size:9pt;color:#6b7280;margin:0 0 6pt">${locale === 'tr' ? 'T kelimesi ham NC değeridir — katalog kimliği değil (T_WORD_EQUALS_CONFIRMED_TOOL_IDENTITY=NO)' : 'T-word is raw NC value — not confirmed catalog identity (T_WORD_EQUALS_CONFIRMED_TOOL_IDENTITY=NO)'}</p>
  <div style="overflow-x:auto">
    <table style="width:100%;border-collapse:collapse;font-size:9pt">
      ${tableHead('Segment', 'T-word (NC)', 'Feed mm', 'Rapid mm', 'Spindle rpm', 'Feed Mode', 'Status')}
      ${segRows}
    </table>
  </div>
</div>`

  // ---- Cycle Time ----
  const cycleTime = `
<div>
  ${sectionTitle(t('ncErCycleTimeEvidence'))}
  <table style="width:100%;border-collapse:collapse;margin-bottom:8pt">
    ${kv(t('ncErCycleTimeSubtotalLabel'), er.cycle_time_known_subtotal_sec != null ? fmtNum(er.cycle_time_known_subtotal_sec, 1) : null, er.cycle_time_known_subtotal_sec != null ? 's' : undefined)}
    ${kv(locale === 'tr' ? 'Durum' : 'Status', er.cycle_time_status)}
  </table>
  ${er.cycle_time_limitations.length > 0 ? `<p style="font-size:9pt;color:#92400e"><strong>${locale === 'tr' ? 'Kısıtlar' : 'Limitations'}:</strong> ${esc(er.cycle_time_limitations.join('; '))}</p>` : ''}
  <p style="font-size:8pt;color:#6b7280;font-style:italic">${locale === 'tr' ? 'Bu yalnızca bilinen alt toplamı ifade eder — takım değişimi ve kurulum süresi dahil değil (PARTIAL_TIME_MISLABELED_TOTAL=NO)' : 'This is the known subtotal only — tool-change and setup time excluded (PARTIAL_TIME_MISLABELED_TOTAL=NO)'}</p>
</div>`

  // ---- Canned Cycles ----
  const cannedRows = er.canned_cycle_notes.map((c: CannedCycleNote) => {
    const stateCol = STATUS_COLORS[c.state] ?? { text: '#374151', bg: '#f3f4f6', border: '#d1d5db' }
    return tableCellRow(
      esc(c.cycle_code_str),
      `<span style="font-weight:600;color:${stateCol.text}">${esc(stateLabels[c.state] ?? c.state)}</span>`,
      esc(c.bounded_reason ?? ''),
      esc(c.detected_limitations.join('; ')),
    )
  }).join('')

  const cannedCycles = er.canned_cycle_notes.length > 0 ? `
<div>
  ${sectionTitle(t('ncErCannedCycleReview'))}
  <div style="overflow-x:auto">
    <table style="width:100%;border-collapse:collapse;font-size:9pt">
      ${tableHead('Code', 'State', locale === 'tr' ? 'Sınır Nedeni' : 'Bounded Reason', locale === 'tr' ? 'Kısıtlar' : 'Limitations')}
      ${cannedRows}
    </table>
  </div>
</div>` : ''

  // ---- Findings ----
  const findingRows = er.findings.map((f: EngReviewFinding) =>
    tableCellRow(
      esc(f.finding_code),
      sevBadge(f.severity),
      esc(t(f.title_key) || f.title_key),
      `${fmtNum(f.observed_value, 1)}${f.unit ? ' ' + f.unit : ''}`,
      `${fmtNum(f.limit_value, 1)}${f.unit ? ' ' + f.unit : ''}`,
      esc(f.segment_id ?? ''),
    )
  ).join('')

  const findings = `
<div class="page-break">
  ${sectionTitle(t('ncErFindings'))}
  ${er.findings.length === 0
    ? `<p style="color:#6b7280;font-size:10pt">${esc(t('ncErNoFindings'))}</p>`
    : `<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:9pt">
      ${tableHead('Code', locale === 'tr' ? 'Önem' : 'Severity', locale === 'tr' ? 'Başlık' : 'Title', locale === 'tr' ? 'Gözlenen' : 'Observed', locale === 'tr' ? 'Limit' : 'Limit', 'Segment')}
      ${findingRows}
    </table></div>`
  }
</div>`

  // ---- Limitations ----
  const limitations = `
<div>
  ${sectionTitle(t('ncErLimitations'))}
  ${er.limitations.length === 0
    ? `<p style="color:#6b7280;font-size:10pt">${esc(t('ncErNoLimitations'))}</p>`
    : `<ul style="font-size:10pt;color:#374151;margin:0;padding-left:20pt">${er.limitations.map(l => `<li style="margin-bottom:4pt">${esc(l)}</li>`).join('')}</ul>`
  }
</div>`

  // ---- Provenance ----
  const provRows = Object.entries(PROVENANCE).map(([k, v]) =>
    `<tr><td style="font-family:monospace;font-size:9pt;color:#374151;padding:2pt 12pt 2pt 0;white-space:nowrap">${esc(k)}</td><td style="font-size:9pt;color:#6b7280;padding:2pt 0">${esc(v)}</td></tr>`
  ).join('')

  const provenance = `
<div>
  ${sectionTitle(t('ncErExportProvenance'))}
  <table style="width:100%;border-collapse:collapse">${provRows}</table>
</div>`

  // ---- Traceability (NC_PROGRAM_TRACEABILITY_AND_AUDIT_01) ----
  const tr = er.traceability ?? null
  const traceabilityLabels: Record<string, string> = {
    TRACEABLE: t('ncErTraceabilityTraceable'),
    PARTIALLY_TRACEABLE: t('ncErTraceabilityPartiallyTraceable'),
    INSUFFICIENT_TRACEABILITY_DATA: t('ncErTraceabilityInsufficientData'),
  }
  const traceabilitySection = tr ? `
<div>
  ${sectionTitle(t('ncErTraceabilitySection'))}
  <table style="width:100%;border-collapse:collapse;margin-bottom:12pt">
    ${kv(t('ncErReviewId'), tr.review_id)}
    ${kv(t('ncErTraceabilityStatus'), traceabilityLabels[tr.traceability_status] ?? tr.traceability_status)}
    ${kv(t('ncErProgramFingerprint'), tr.program_fingerprint ? `${tr.program_fingerprint.slice(0, 16)}…` : null)}
    ${kv(t('ncErConfigFingerprint'), tr.configuration_fingerprint ? `${tr.configuration_fingerprint.slice(0, 16)}…` : null)}
    ${kv(t('ncErAnalysisFingerprint'), tr.analysis_fingerprint ? `${tr.analysis_fingerprint.slice(0, 16)}…` : null)}
    ${kv(t('ncErReviewSchemaVersion'), tr.review_schema_version)}
    ${kv(t('ncErGeneratedAt'), tr.generated_at)}
  </table>
  <p style="font-size:8pt;color:#6b7280;font-style:italic">HASH_EQUALS_DIGITAL_SIGNATURE=NO · HASH_EQUALS_APPROVAL=NO · HASH_EQUALS_CERTIFICATION=NO · FALSE_IMMUTABLE_AUDIT_CLAIM=NO · ENGINEERING_STATUS_EQUALS_TRACEABILITY_STATUS=NO</p>
</div>` : ''

  // ---- Disclaimer ----
  const disclaimerSection = `
<div>
  ${sectionTitle(t('ncErExportScopeTitle'))}
  <p style="font-size:10pt;color:#374151;line-height:1.6;max-width:600pt">${esc(disclaimer)}</p>
  <table style="margin-top:12pt;border-collapse:collapse;font-size:9pt">
    ${['nc_file_executed', 'collision_check_performed', 'false_production_approval_claim', 'false_safe_to_run_claim', 'false_collision_free_claim'].map(flag =>
      `<tr><td style="font-family:monospace;color:#374151;padding:1pt 12pt 1pt 0">${esc(flag.toUpperCase())}</td><td style="color:#15803d;font-weight:600">NO</td></tr>`
    ).join('')}
  </table>
</div>`

  const baseCSS = `
    @page { size: A4 portrait; margin: 20mm 15mm; }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: system-ui, -apple-system, Arial, sans-serif; font-size: 10pt; color: #1e293b; line-height: 1.4; }
    h1, h2, h3 { page-break-after: avoid; }
    table { page-break-inside: avoid; }
    .page-break { page-break-after: always; }
    .no-print { display: none !important; }
    @media screen {
      body { max-width: 794px; margin: 0 auto; padding: 20px; }
      .page-break { border-bottom: 2px dashed #e2e8f0; margin-bottom: 24px; padding-bottom: 24px; }
    }
  `

  return `<!doctype html>
<html lang="${esc(locale)}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${esc(EXPORT_APPLICATION_NAME)} — ${esc(t('ncEngineeringReview'))}</title>
<style>${baseCSS}</style>
</head>
<body>
${cover}
${exec}
${coverage}
${equipment}
${feedSpindle}
${motion}
${segments}
${cycleTime}
${cannedCycles}
${findings}
${limitations}
${provenance}
${traceabilitySection}
${disclaimerSection}
</body>
</html>`
}

// ---------------------------------------------------------------------------
// Open print window
// ---------------------------------------------------------------------------

export function openPrintWindow(
  er: NCProgramEngineeringReview,
  t: (key: string) => string,
  locale: string,
): void {
  const html = generatePrintHtml(er, t, locale)
  const w = window.open('', '_blank', 'width=900,height=700')
  if (!w) return
  w.document.open()
  w.document.write(html)
  w.document.close()
  w.focus()
  // Slight delay to allow images/fonts to load before print dialog
  setTimeout(() => {
    try { w.print() } catch { /* user may have closed the window */ }
  }, 300)
}
