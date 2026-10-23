// NC Program Change Management — Export utilities and audit helpers
// NC_PROGRAM_CHANGE_MANAGEMENT_01
//
// CHANGE_REVIEW_REUSED_FOR_EXPORT=YES
// EXPORT_RECOMPUTATION_DUPLICATED=NO
// PRIVATE_LOCAL_PATH_EXPORTED=NO
// CREDENTIAL_EXPORTED=NO

import type {
  NCProgramChangeReview,
  NcBlockChange,
  NcSegmentChange,
  NcFindingChange,
  ConfigFieldChange,
} from '../services/nc_path'
import {
  addAuditEvent,
  type NcAuditEventType,
} from './nc_report_export'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const CHANGE_REVIEW_SCHEMA_VERSION = '1.0'
export const CHANGE_REVIEW_REPORT_TYPE = 'NC_PROGRAM_CHANGE_REVIEW' as const

// ---------------------------------------------------------------------------
// JSON export
// ---------------------------------------------------------------------------

export interface NcChangeReviewExportJson {
  schema_version: string
  report_type: typeof CHANGE_REVIEW_REPORT_TYPE
  generated_at: string
  change_review_id: string
  comparison_schema_version: string
  comparison_fingerprint: string | null
  baseline_review_id: string | null
  current_review_id: string | null
  baseline_analysis_fingerprint: string | null
  current_analysis_fingerprint: string | null
  overall_change_status: string
  change_severity: string
  comparability_status: string
  program_change_status: string
  configuration_change_status: string
  version_change_status: string
  review_required: boolean
  review_required_reasons: string[]
  change_summary: NCProgramChangeReview['change_summary']
  block_changes: NCProgramChangeReview['block_changes']
  segment_changes: NCProgramChangeReview['segment_changes']
  finding_changes: NCProgramChangeReview['finding_changes']
  coverage_changes: NCProgramChangeReview['coverage_changes']
  configuration_changes: NCProgramChangeReview['configuration_changes']
  feed_spindle_changes: NCProgramChangeReview['feed_spindle_changes']
  cycle_time_changes: NCProgramChangeReview['cycle_time_changes']
  comparability_notes: string[]
  limitations: string[]
  // Immutable safety flags
  false_change_approval_claim: false
  false_safe_change_claim: false
  false_controller_certification_claim: false
  nc_change_review_is_not_approval: true
  nc_change_review_is_not_safety_certification: true
}

export function buildNcChangeReviewJson(cr: NCProgramChangeReview): NcChangeReviewExportJson {
  return {
    schema_version: CHANGE_REVIEW_SCHEMA_VERSION,
    report_type: CHANGE_REVIEW_REPORT_TYPE,
    generated_at: new Date().toISOString(),
    change_review_id: cr.change_review_id,
    comparison_schema_version: cr.comparison_schema_version,
    comparison_fingerprint: cr.comparison_fingerprint,
    baseline_review_id: cr.baseline_review_id,
    current_review_id: cr.current_review_id,
    baseline_analysis_fingerprint: cr.baseline_analysis_fingerprint,
    current_analysis_fingerprint: cr.current_analysis_fingerprint,
    overall_change_status: cr.overall_change_status,
    change_severity: cr.change_severity,
    comparability_status: cr.comparability_status,
    program_change_status: cr.program_change_status,
    configuration_change_status: cr.configuration_change_status,
    version_change_status: cr.version_change_status,
    review_required: cr.review_required,
    review_required_reasons: cr.review_required_reasons,
    change_summary: cr.change_summary,
    block_changes: cr.block_changes,
    segment_changes: cr.segment_changes,
    finding_changes: cr.finding_changes,
    coverage_changes: cr.coverage_changes,
    configuration_changes: cr.configuration_changes,
    feed_spindle_changes: cr.feed_spindle_changes,
    cycle_time_changes: cr.cycle_time_changes,
    comparability_notes: cr.comparability_notes,
    limitations: cr.limitations,
    false_change_approval_claim: false,
    false_safe_change_claim: false,
    false_controller_certification_claim: false,
    nc_change_review_is_not_approval: true,
    nc_change_review_is_not_safety_certification: true,
  }
}

// ---------------------------------------------------------------------------
// CSV helpers
// ---------------------------------------------------------------------------

function escapeCsv(value: string | number | boolean | null | undefined): string {
  if (value === null || value === undefined) return ''
  const s = String(value)
  if (s.includes(',') || s.includes('"') || s.includes('\n')) {
    return '"' + s.replace(/"/g, '""') + '"'
  }
  return s
}

function csvRow(cells: (string | number | boolean | null | undefined)[]): string {
  return cells.map(escapeCsv).join(',')
}

export function buildBlockChangesCsv(cr: NCProgramChangeReview): string {
  const header = csvRow([
    'change_type',
    'semantic_change_type',
    'block_classification',
    'baseline_line_index',
    'current_line_index',
    'baseline_text',
    'current_text',
  ])
  if (!cr.block_changes || cr.block_changes.length === 0) return header + '\n'
  const rows = cr.block_changes.map((b: NcBlockChange) =>
    csvRow([
      b.change_type,
      b.semantic_change_type,
      b.block_classification,
      b.baseline_line_index,
      b.current_line_index,
      b.baseline_text,
      b.current_text,
    ])
  )
  return header + '\n' + rows.join('\n') + '\n'
}

export function buildFindingChangesCsv(cr: NCProgramChangeReview): string {
  const header = csvRow([
    'finding_code',
    'category',
    'change_type',
    'baseline_severity',
    'current_severity',
    'baseline_observed_value',
    'current_observed_value',
    'baseline_limit_value',
    'current_limit_value',
    'unit',
    'source_changed',
  ])
  if (!cr.finding_changes || cr.finding_changes.length === 0) return header + '\n'
  const rows = cr.finding_changes.map((f: NcFindingChange) =>
    csvRow([
      f.finding_code,
      f.category,
      f.change_type,
      f.baseline_severity,
      f.current_severity,
      f.baseline_observed_value,
      f.current_observed_value,
      f.baseline_limit_value,
      f.current_limit_value,
      f.unit,
      f.source_changed,
    ])
  )
  return header + '\n' + rows.join('\n') + '\n'
}

export function buildSegmentChangesCsv(cr: NCProgramChangeReview): string {
  const header = csvRow([
    'baseline_segment_id',
    'current_segment_id',
    'change_type',
    'tool_id_raw_changed',
    'baseline_tool_id_raw',
    'current_tool_id_raw',
    'feed_distance_delta_mm',
    'commanded_feed_changed',
    'commanded_spindle_changed',
    'analysis_status_changed',
  ])
  if (!cr.segment_changes || cr.segment_changes.length === 0) return header + '\n'
  const rows = cr.segment_changes.map((s: NcSegmentChange) =>
    csvRow([
      s.baseline_segment_id,
      s.current_segment_id,
      s.change_type,
      s.tool_id_raw_changed,
      s.baseline_tool_id_raw,
      s.current_tool_id_raw,
      s.feed_distance_delta_mm,
      s.commanded_feed_changed,
      s.commanded_spindle_changed,
      s.analysis_status_changed,
    ])
  )
  return header + '\n' + rows.join('\n') + '\n'
}

export function buildConfigChangesCsv(cr: NCProgramChangeReview): string {
  const header = csvRow(['field_name', 'baseline_value', 'current_value', 'changed'])
  if (!cr.configuration_changes || cr.configuration_changes.length === 0) return header + '\n'
  const rows = cr.configuration_changes.map((c: ConfigFieldChange) =>
    csvRow([c.field_name, c.baseline_value, c.current_value, c.changed])
  )
  return header + '\n' + rows.join('\n') + '\n'
}

// ---------------------------------------------------------------------------
// Print HTML
// ---------------------------------------------------------------------------

export function buildChangeReviewPrintHtml(cr: NCProgramChangeReview, locale: string): string {
  const now = new Date()
  const nowStr = now.toLocaleString(locale === 'tr' ? 'tr-TR' : 'en-US')
  const s = cr.change_summary

  const safeStr = (v: string | null | undefined) => v ?? '—'
  const numStr = (v: number | null | undefined) => (v !== null && v !== undefined ? String(v) : '—')

  const blockRows = (cr.block_changes ?? [])
    .filter(b => b.change_type !== 'UNCHANGED')
    .slice(0, 200)
    .map(b => `
      <tr>
        <td>${b.change_type}</td>
        <td>${b.semantic_change_type}</td>
        <td>${b.block_classification}</td>
        <td>${numStr(b.baseline_line_index)}</td>
        <td>${numStr(b.current_line_index)}</td>
        <td class="mono">${safeStr(b.baseline_text)}</td>
        <td class="mono">${safeStr(b.current_text)}</td>
      </tr>`)
    .join('')

  const findingRows = cr.finding_changes
    .filter(f => f.change_type !== 'FINDING_UNCHANGED')
    .map(f => `
      <tr>
        <td>${f.finding_code}</td>
        <td>${f.change_type}</td>
        <td>${safeStr(f.baseline_severity)}</td>
        <td>${safeStr(f.current_severity)}</td>
        <td>${numStr(f.baseline_observed_value)}</td>
        <td>${numStr(f.current_observed_value)}</td>
        <td>${safeStr(f.unit)}</td>
      </tr>`)
    .join('')

  const configRows = cr.configuration_changes
    .filter(c => c.changed)
    .map(c => `
      <tr>
        <td>${c.field_name}</td>
        <td>${safeStr(c.baseline_value)}</td>
        <td>${safeStr(c.current_value)}</td>
      </tr>`)
    .join('')

  return `<!DOCTYPE html>
<html lang="${locale === 'tr' ? 'tr' : 'en'}">
<head>
<meta charset="UTF-8">
<title>NC Change Review — ${cr.change_review_id}</title>
<style>
  body { font-family: system-ui, sans-serif; font-size: 12px; color: #111; margin: 2rem; }
  h1 { font-size: 1.2rem; font-weight: 700; margin-bottom: 0.25rem; }
  h2 { font-size: 0.9rem; font-weight: 700; margin: 1.5rem 0 0.5rem; border-bottom: 1px solid #ccc; padding-bottom: 0.25rem; }
  table { border-collapse: collapse; width: 100%; margin-bottom: 1rem; font-size: 11px; }
  th, td { border: 1px solid #ddd; padding: 3px 6px; text-align: left; vertical-align: top; }
  th { background: #f5f5f5; font-weight: 600; }
  .mono { font-family: monospace; font-size: 10px; }
  .meta { font-size: 11px; color: #666; margin-bottom: 1rem; }
  .badge { display: inline-block; padding: 1px 6px; border-radius: 3px; font-weight: 600; font-size: 10px; text-transform: uppercase; letter-spacing: 0.04em; }
  .status-review { background: #fef3c7; color: #92400e; }
  .status-change { background: #fee2e2; color: #991b1b; }
  .status-no-change { background: #d1fae5; color: #065f46; }
  .status-incomplete { background: #e0e7ff; color: #3730a3; }
  .warning { background: #fffbeb; border: 1px solid #fcd34d; padding: 0.5rem; border-radius: 4px; margin: 1rem 0; font-size: 11px; }
  @media print { body { margin: 0.5cm; } }
</style>
</head>
<body>
<h1>NC Program Change Review</h1>
<div class="meta">
  ID: ${cr.change_review_id} &nbsp;|&nbsp; Generated: ${nowStr} &nbsp;|&nbsp; Schema: ${cr.comparison_schema_version}
</div>
<div class="warning">
  <strong>NOT AN APPROVAL DOCUMENT.</strong> This report does not approve, certify, or authorize the use of any NC program. Engineering judgment and qualified review are required before production use.
</div>

<h2>Change Status</h2>
<table>
  <tr><th>Field</th><th>Value</th></tr>
  <tr><td>Overall Status</td><td>${cr.overall_change_status}</td></tr>
  <tr><td>Change Severity</td><td>${cr.change_severity}</td></tr>
  <tr><td>Comparability</td><td>${cr.comparability_status}</td></tr>
  <tr><td>Program Change</td><td>${cr.program_change_status}</td></tr>
  <tr><td>Configuration Change</td><td>${cr.configuration_change_status}</td></tr>
  <tr><td>Version Change</td><td>${cr.version_change_status}</td></tr>
  <tr><td>Review Required</td><td>${cr.review_required ? 'YES' : 'NO'}</td></tr>
</table>

${cr.review_required ? `<h2>Review Required Reasons</h2><ul>${cr.review_required_reasons.map(r => `<li>${r}</li>`).join('')}</ul>` : ''}

<h2>Change Summary</h2>
<table>
  <tr><th>Metric</th><th>Value</th></tr>
  <tr><td>Blocks Added</td><td>${numStr(s.blocks_added)}</td></tr>
  <tr><td>Blocks Removed</td><td>${numStr(s.blocks_removed)}</td></tr>
  <tr><td>Blocks Modified</td><td>${numStr(s.blocks_modified)}</td></tr>
  <tr><td>Segments Added</td><td>${s.segments_added}</td></tr>
  <tr><td>Segments Removed</td><td>${s.segments_removed}</td></tr>
  <tr><td>Segments Modified</td><td>${s.segments_modified}</td></tr>
  <tr><td>New Findings</td><td>${s.new_findings}</td></tr>
  <tr><td>Resolved Findings</td><td>${s.resolved_findings}</td></tr>
  <tr><td>New Blocking</td><td>${s.new_blocking_findings}</td></tr>
  <tr><td>Coverage Changes</td><td>${s.coverage_changes}</td></tr>
  <tr><td>Configuration Changes</td><td>${s.configuration_changes}</td></tr>
  <tr><td>Feed Changed</td><td>${s.feed_changed ? 'YES' : 'NO'}</td></tr>
  <tr><td>Spindle Changed</td><td>${s.spindle_changed ? 'YES' : 'NO'}</td></tr>
</table>

${blockRows ? `<h2>Block Changes (non-unchanged, max 200)</h2>
<table>
  <tr><th>Type</th><th>Semantic</th><th>Class</th><th>Base Line</th><th>Curr Line</th><th>Baseline Text</th><th>Current Text</th></tr>
  ${blockRows}
</table>` : ''}

${findingRows ? `<h2>Finding Changes</h2>
<table>
  <tr><th>Code</th><th>Change</th><th>Base Severity</th><th>Curr Severity</th><th>Base Value</th><th>Curr Value</th><th>Unit</th></tr>
  ${findingRows}
</table>` : ''}

${configRows ? `<h2>Configuration Changes</h2>
<table>
  <tr><th>Field</th><th>Baseline</th><th>Current</th></tr>
  ${configRows}
</table>` : ''}

${cr.limitations.length > 0 ? `<h2>Limitations</h2><ul>${cr.limitations.map(l => `<li>${l}</li>`).join('')}</ul>` : ''}

<div class="meta" style="margin-top:2rem">
  Baseline fingerprint: ${safeStr(cr.baseline_analysis_fingerprint)} &nbsp;|&nbsp;
  Current fingerprint: ${safeStr(cr.current_analysis_fingerprint)} &nbsp;|&nbsp;
  Comparison fingerprint: ${safeStr(cr.comparison_fingerprint)}
</div>
</body>
</html>`
}

// ---------------------------------------------------------------------------
// Audit helpers
// ---------------------------------------------------------------------------

export function logChangeReviewEvent(
  eventType: NcAuditEventType,
  changeReviewId: string | null,
  analysisFingerprint: string | null,
  exportFormat?: string
): void {
  addAuditEvent({
    event_id: crypto.randomUUID(),
    event_type: eventType,
    timestamp: new Date().toISOString(),
    review_id: changeReviewId,
    analysis_fingerprint: analysisFingerprint,
    export_format: exportFormat ?? null,
  })
}
