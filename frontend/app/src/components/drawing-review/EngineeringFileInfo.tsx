/**
 * EngineeringFileInfo — shows structured import metadata after any engineering
 * file is selected.
 *
 * Displayed for all non-PDF formats (and optionally for PDF before the drawing
 * analysis result arrives).  Provides FILE_NAME, DETECTED_FORMAT, FORMAT_FAMILY,
 * IMPORT_STATUS, ENTITY_COUNT and a family-specific note.
 */

import { LoaderCircle } from 'lucide-react'
import { useLocale } from '../../i18n'
import type { ImportResult } from '../../services/engineeringImport'
import type { FormatRoute } from '../../lib/engineeringFormats'

interface Props {
  fileName: string
  route: FormatRoute
  result: ImportResult | null   // null = loading
  error: string | null
  /** For IMAGE routes: object URL for preview (caller manages lifecycle) */
  previewUrl?: string | null
}

const ROW = 'flex flex-wrap gap-x-4 gap-y-0.5 text-sm'
const LABEL = 'w-36 shrink-0 text-tp-text-3'
const VALUE = 'font-medium text-tp-text break-all'

function StatusChip({ status }: { status: ImportResult['import_status'] }) {
  const colors: Record<string, string> = {
    SUCCESS:           'bg-tp-accent-muted text-tp-accent-light border-tp-accent-muted',
    PARTIAL:           'bg-tp-warn-muted   text-tp-warn       border-tp-warn-muted',
    FAILED:            'bg-tp-error-muted  text-tp-error      border-tp-error-muted',
    UNSUPPORTED:       'bg-tp-surface-2    text-tp-text-2     border-tp-border',
    INSUFFICIENT_DATA: 'bg-tp-surface-2    text-tp-text-2     border-tp-border',
    UNRECOGNIZED:      'bg-tp-surface-2    text-tp-text-2     border-tp-border',
    PARSE_ERROR:       'bg-tp-error-muted  text-tp-error      border-tp-error-muted',
    UNKNOWN:           'bg-tp-surface-2    text-tp-text-2     border-tp-border',
  }
  const cls = colors[status] ?? colors.UNKNOWN
  return (
    <span className={`rounded border px-1.5 py-0.5 text-xs font-semibold uppercase tracking-wide ${cls}`}>
      {status}
    </span>
  )
}

export default function EngineeringFileInfo({ fileName, route, result, error, previewUrl }: Props) {
  const { t } = useLocale()

  const familyNote = () => {
    if (!result) return null
    switch (route) {
      case 'DRAWING_IMAGE':
        return t('drNonPdfNote')
      case 'DRAWING_VECTOR':
        return t('drDrawingAnalysisNote')
      case 'CAD_GEOMETRY':
        return t('drCadNote')
      case 'MESH_GEOMETRY':
        return t('drMeshNote')
      case 'NC_PROGRAM':
        return t('drNcNote')
      default:
        return null
    }
  }

  return (
    <div
      data-testid="engineering-file-info"
      className="mt-3 rounded-md border border-tp-border bg-tp-surface p-3 space-y-2"
    >
      <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light">
        {t('drImportInfoTitle')}
      </div>

      {/* Loading state */}
      {!result && !error && (
        <div className="flex items-center gap-2 text-sm text-tp-text-2">
          <LoaderCircle size={14} className="animate-spin" aria-hidden="true" />
          {t('drImportUploading')}
        </div>
      )}

      {/* Error state */}
      {error && (
        <div role="alert" className="text-sm text-tp-error">
          {t('drImportError')}
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="space-y-1.5">
          <div className={ROW}>
            <span className={LABEL}>{t('drFileName')}</span>
            <span className={VALUE}>{result.file_name}</span>
          </div>
          <div className={ROW}>
            <span className={LABEL}>{t('drDetectedFormat')}</span>
            <span className={VALUE}>{result.format_id}</span>
          </div>
          <div className={ROW}>
            <span className={LABEL}>{t('drFormatFamily')}</span>
            <span className={VALUE}>{result.format_family_label}</span>
          </div>
          <div className={ROW}>
            <span className={LABEL}>{t('drImportStatus')}</span>
            <StatusChip status={result.import_status} />
          </div>
          {result.entity_count > 0 && (
            <div className={ROW}>
              <span className={LABEL}>{t('drEntityCount')}</span>
              <span className={VALUE}>{result.entity_count}</span>
            </div>
          )}
          <div className={ROW}>
            <span className={LABEL}>{t('drCapabilityLevel')}</span>
            <span className="text-xs text-tp-text-3">{result.capability_level}</span>
          </div>

          {/* Format-specific metadata (key-value from first entity) */}
          {Object.keys(result.metadata).length > 0 && (
            <div className="mt-1 border-t border-tp-border pt-1.5 space-y-1">
              {Object.entries(result.metadata).map(([k, v]) => (
                <div key={k} className={ROW}>
                  <span className={LABEL + ' text-[11px]'}>{k.replace(/_/g, ' ')}</span>
                  <span className="text-[11px] text-tp-text-2">{String(v ?? '')}</span>
                </div>
              ))}
            </div>
          )}

          {/* Family-specific guidance note */}
          {familyNote() && (
            <p className="mt-1 text-xs text-tp-text-3 border-t border-tp-border pt-1.5">
              {familyNote()}
            </p>
          )}
        </div>
      )}

      {/* Image preview for DRAWING_IMAGE route */}
      {route === 'DRAWING_IMAGE' && previewUrl && (
        <div className="mt-2">
          <img
            data-testid="image-preview"
            src={previewUrl}
            alt={fileName}
            className="max-h-48 max-w-full rounded border border-tp-border object-contain"
          />
        </div>
      )}
    </div>
  )
}
