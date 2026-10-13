/**
 * CAD Import — universal engineering file import workspace.
 *
 * Accepts all formats supported by the universal adapter registry
 * (DXF, STEP/STP, IGES/IGS, STL, OBJ, 3MF, NC/G-code/TAP, PNG/JPG/TIFF/BMP/SVG, PDF).
 *
 * Each file's metadata, capability level, and format family come exclusively
 * from the real /api/import endpoint — no synthetic or sample data is ever shown.
 *
 * Preview policy:
 *   DRAWING_IMAGE (PNG/JPG/TIFF/BMP/SVG) — real image preview via URL.createObjectURL
 *   DRAWING_VECTOR (DXF) — real raster render via /api/import/dxf-as-pdf, displayed in iframe
 *   All others — PREVIEW_UNAVAILABLE (no 3D/PDF renderer present in this build)
 *
 * Technical Drawing Intelligence remains a separate workflow for PDF/drawing AI analysis.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { FolderOpen, LoaderCircle, RefreshCw, X } from 'lucide-react'
import Panel from '../components/ui/Panel'
import EngineeringFileInfo from '../components/drawing-review/EngineeringFileInfo'
import MeshViewer from '../components/cad-viewer/MeshViewer'
import { useLocale } from '../i18n'
import { detectFormatByFile, NATIVE_ACCEPT } from '../lib/engineeringFormats'
import type { FormatRoute } from '../lib/engineeringFormats'
import { detectAndImport, fetchDxfAsPdf, ImportApiError } from '../services/engineeringImport'
import type { ImportResult } from '../services/engineeringImport'

const BUTTON =
  'inline-flex min-h-11 items-center justify-center gap-1.5 rounded border px-3 text-sm ' +
  'font-medium transition-colors sm:min-h-9 focus-visible:outline-2 ' +
  'focus-visible:outline-tp-accent-light disabled:cursor-not-allowed disabled:opacity-50'

export default function CadImportPage() {
  const { t } = useLocale()
  const fileInput = useRef<HTMLInputElement>(null)

  const [fileName, setFileName] = useState<string>('')
  const [importRoute, setImportRoute] = useState<FormatRoute | null>(null)
  const [importResult, setImportResult] = useState<ImportResult | null>(null)
  const [importLoading, setImportLoading] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null)
  const [dxfPreviewUrl, setDxfPreviewUrl] = useState<string | null>(null)
  const [dxfPreviewError, setDxfPreviewError] = useState<string | null>(null)
  const [hasFile, setHasFile] = useState(false)
  const [currentFile, setCurrentFile] = useState<File | null>(null)
  const [importFormatId, setImportFormatId] = useState<string | null>(null)

  // Revoke object URLs on unmount to avoid memory leaks
  useEffect(() => {
    return () => {
      if (imagePreviewUrl) URL.revokeObjectURL(imagePreviewUrl)
      if (dxfPreviewUrl) URL.revokeObjectURL(dxfPreviewUrl)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const revokeAll = useCallback(() => {
    if (imagePreviewUrl) URL.revokeObjectURL(imagePreviewUrl)
    if (dxfPreviewUrl) URL.revokeObjectURL(dxfPreviewUrl)
    setImagePreviewUrl(null)
    setDxfPreviewUrl(null)
  }, [imagePreviewUrl, dxfPreviewUrl])

  const handleFile = useCallback(
    (file: File) => {
      revokeAll()

      const detected = detectFormatByFile(file)
      const route = detected?.route ?? 'UNKNOWN'

      setFileName(file.name)
      setImportRoute(route)
      setImportFormatId(detected?.formatId ?? null)
      setImportResult(null)
      setImportError(null)
      setDxfPreviewError(null)
      setImportLoading(true)
      setHasFile(true)
      setCurrentFile(file)

      if (route === 'DRAWING_IMAGE') {
        setImagePreviewUrl(URL.createObjectURL(file))
      }

      if (route === 'DRAWING_VECTOR') {
        // DXF: run metadata parse and render in parallel; both can succeed independently
        const capturedFile = file
        void Promise.allSettled([
          detectAndImport(capturedFile),
          fetchDxfAsPdf(capturedFile),
        ]).then(([importRes, pdfRes]) => {
          if (importRes.status === 'fulfilled') {
            setImportResult(importRes.value)
            setImportError(null)
          } else {
            setImportError(errorMessage(importRes.reason, t))
          }
          if (pdfRes.status === 'fulfilled') {
            setDxfPreviewUrl(URL.createObjectURL(pdfRes.value))
          } else {
            setDxfPreviewError(t('ciErrRenderFailed'))
          }
          setImportLoading(false)
        })
        return
      }

      detectAndImport(file)
        .then(r => {
          setImportResult(r)
          setImportLoading(false)
        })
        .catch(err => {
          setImportError(errorMessage(err, t))
          setImportLoading(false)
        })
    },
    [revokeAll, t],
  )

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (file) handleFile(file)
  }

  const handleClear = () => {
    revokeAll()
    setFileName('')
    setImportRoute(null)
    setImportResult(null)
    setImportError(null)
    setDxfPreviewError(null)
    setImportLoading(false)
    setHasFile(false)
    setCurrentFile(null)
    setImportFormatId(null)
  }

  // 3D viewer: STL only, SUCCESS status, renderable geometry confirmed (HARD RULE 06)
  const showMeshViewer =
    currentFile !== null &&
    importResult !== null &&
    importRoute === 'MESH_GEOMETRY' &&
    importFormatId === 'STL' &&
    importResult.import_status === 'SUCCESS' &&
    importResult.has_renderable_geometry

  // Static "Preview Unavailable" panel for CAD/NC and any route without a dedicated viewer
  const showPreviewUnavailable =
    importResult !== null &&
    importRoute !== null &&
    importRoute !== 'DRAWING_IMAGE' &&
    importRoute !== 'DRAWING_VECTOR' &&
    importRoute !== 'MESH_GEOMETRY' &&
    importRoute !== 'UNKNOWN'

  const showDxfPreviewSection =
    importRoute === 'DRAWING_VECTOR' &&
    (dxfPreviewUrl !== null || dxfPreviewError !== null || importLoading)

  return (
    <div className="h-full overflow-y-auto p-4 sm:p-6">
      <div className="mb-4 max-w-3xl">
        <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light">
          MachiningPro AI
        </div>
        <h1 className="text-lg font-semibold text-tp-text">{t('cadImport')}</h1>
        <p className="text-sm text-tp-text-2">{t('ciPageSubtitle')}</p>
      </div>

      <div className="max-w-3xl space-y-4">
        {/* Primary action panel */}
        <Panel title={t('cadImport')}>
          <div className="space-y-3">
            <input
              ref={fileInput}
              type="file"
              accept={NATIVE_ACCEPT}
              className="hidden"
              onChange={handleChange}
              aria-label={t('drUploadDrawing')}
            />

            {/* Button row */}
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                disabled={importLoading}
                onClick={() => fileInput.current?.click()}
                className={`${BUTTON} border-tp-border-strong text-tp-text hover:bg-tp-surface-2`}
              >
                {importLoading ? (
                  <LoaderCircle size={14} className="animate-spin" aria-hidden="true" />
                ) : (
                  <FolderOpen size={14} aria-hidden="true" />
                )}
                {importLoading ? t('drImportUploading') : t('drUploadDrawing')}
              </button>

              {hasFile && (
                <>
                  <button
                    type="button"
                    disabled={importLoading}
                    onClick={() => fileInput.current?.click()}
                    className={`${BUTTON} border-tp-border text-tp-text-2 hover:bg-tp-surface-2`}
                  >
                    <RefreshCw size={14} aria-hidden="true" />
                    {t('ciLoadAnother')}
                  </button>
                  <button
                    type="button"
                    disabled={importLoading}
                    onClick={handleClear}
                    className={`${BUTTON} border-tp-border text-tp-text-3 hover:bg-tp-surface-2`}
                  >
                    <X size={14} aria-hidden="true" />
                    {t('close')}
                  </button>
                </>
              )}
            </div>

            {/* Empty state */}
            {!hasFile && (
              <p className="text-sm text-tp-text-3">{t('ciSelectPrompt')}</p>
            )}

            {/* Import error */}
            {importError && !importLoading && (
              <div role="alert" className="rounded-md border border-tp-error-muted bg-tp-error-muted px-3 py-2 text-sm text-tp-error">
                {importError}
              </div>
            )}

            {/* Structured import metadata — reuses the existing EngineeringFileInfo component */}
            {importRoute && importRoute !== 'UNKNOWN' && (
              <EngineeringFileInfo
                fileName={fileName}
                route={importRoute}
                result={importLoading ? null : importResult}
                error={importError}
                previewUrl={imagePreviewUrl}
              />
            )}

            {/* Unknown format */}
            {importRoute === 'UNKNOWN' && !importLoading && (
              <div className="mt-3 rounded-md border border-tp-border bg-tp-surface p-3 text-sm text-tp-text-2">
                <div className="font-medium text-tp-text mb-0.5">{fileName}</div>
                <div>{t('drImportError')}</div>
              </div>
            )}

            {/* PDF guidance note */}
            {importRoute === 'DRAWING_PDF' && !importLoading && (
              <p className="text-xs text-tp-text-3 mt-1">{t('ciPdfNote')}</p>
            )}

            {/* Fidelity events */}
            {importResult && importResult.fidelity_events && importResult.fidelity_events.length > 0 && (
              <details className="mt-2">
                <summary className="cursor-pointer text-xs text-tp-text-3 hover:text-tp-text">
                  {t('ciFidelityEvents')} ({importResult.fidelity_events.length})
                </summary>
                <ul className="mt-1 space-y-1">
                  {importResult.fidelity_events.map((ev, i) => (
                    <li key={i} className="flex gap-2 text-xs text-tp-text-3">
                      <span className="shrink-0 font-medium text-tp-text-2">{ev.class}</span>
                      <span>{ev.description}</span>
                    </li>
                  ))}
                </ul>
              </details>
            )}

            {/* Adapter ID */}
            {importResult?.adapter_id && (
              <div className="mt-1 text-[11px] text-tp-text-3">
                {t('ciAdapterUsed')}: <span className="font-mono">{importResult.adapter_id}</span>
              </div>
            )}
          </div>
        </Panel>

        {/* DXF Preview panel — real render via /api/import/dxf-as-pdf */}
        {showDxfPreviewSection && (
          <Panel title={t('ciDxfPreview')}>
            {importLoading && (
              <div className="flex items-center gap-2 text-sm text-tp-text-2">
                <LoaderCircle size={14} className="animate-spin" aria-hidden="true" />
                {t('drImportUploading')}
              </div>
            )}
            {dxfPreviewUrl && !importLoading && (
              <iframe
                src={dxfPreviewUrl}
                title={t('ciDxfPreview')}
                className="w-full rounded border border-tp-border"
                style={{ height: '420px' }}
              />
            )}
            {dxfPreviewError && !importLoading && (
              <p className="text-sm text-tp-text-3">{dxfPreviewError}</p>
            )}
          </Panel>
        )}

        {/* 3D Mesh Viewer panel — real geometry from the uploaded file */}
        {showMeshViewer && currentFile && (
          <Panel title={t('ciMeshPreview')}>
            <MeshViewer
              key={`${currentFile.name}-${currentFile.lastModified}`}
              file={currentFile}
            />
          </Panel>
        )}

        {/* Preview unavailable panel for STEP/IGES/NC */}
        {showPreviewUnavailable && (
          <Panel title={t('ciPreviewUnavailable')}>
            <p className="text-sm text-tp-text-3">{t('ciPreviewUnavailableHint')}</p>
          </Panel>
        )}
      </div>
    </div>
  )
}

/** Map an import API error to a user-facing i18n string key. */
function errorMessage(
  err: unknown,
  t: (key: Parameters<ReturnType<typeof useLocale>['t']>[0]) => string,
): string {
  if (err instanceof ImportApiError) {
    if (err.status === 413 || err.code === 'FILE_TOO_LARGE') return t('ciErrFileTooLarge')
    if (err.status === 401 || err.code === 'UNAUTHENTICATED') return t('ciErrAuth')
    if (err.code === 'RENDER_FAILED') return t('ciErrRenderFailed')
    if (err.code === 'PARSE_ERROR') return t('ciErrInvalidFile')
    return t('ciErrImportFailed')
  }
  return t('ciErrRequestFailed')
}
