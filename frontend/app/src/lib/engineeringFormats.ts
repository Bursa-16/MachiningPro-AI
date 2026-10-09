/**
 * Client-side engineering format catalog.
 *
 * Mirrors the backend universal adapter registry so the UI can perform fast
 * extension-based routing without a server round-trip.  The canonical format
 * information (format_id, family, import_status) is authoritative only when
 * it comes from the /api/import endpoint; this table is used only for
 * immediate routing decisions (which API to call, what preview to show).
 *
 * Proprietary optional-adapter formats (DWG, Parasolid, ACIS, JT, SolidWorks,
 * CATIA, NX, Creo) are intentionally absent from NATIVE_ACCEPT so they are
 * never offered in the file chooser.
 */

export type FormatRoute =
  | 'DRAWING_PDF'     // PDF → existing /api/drawings drawing-analysis pipeline
  | 'DRAWING_IMAGE'   // PNG/JPG/TIFF/BMP/SVG → /api/import, show image preview
  | 'DRAWING_VECTOR'  // DXF → /api/import, 2D geometry
  | 'CAD_GEOMETRY'    // STEP/IGES → /api/import, neutral exchange CAD
  | 'MESH_GEOMETRY'   // STL/OBJ/3MF → /api/import, triangle mesh
  | 'NC_PROGRAM'      // NC/GCODE/TAP → /api/import, CNC program
  | 'UNKNOWN'

export interface FormatEntry {
  readonly ext: string
  readonly formatId: string
  readonly canonicalName: string
  readonly familyLabel: string
  readonly route: FormatRoute
  readonly mimeTypes: readonly string[]
}

const T: Record<string, FormatEntry> = {
  pdf:   { ext: 'pdf',   formatId: 'PDF',          canonicalName: 'PDF Document',       familyLabel: 'Engineering Document',       route: 'DRAWING_PDF',    mimeTypes: ['application/pdf'] },
  png:   { ext: 'png',   formatId: 'RASTER-IMAGE',  canonicalName: 'PNG Image',          familyLabel: 'Raster / Vector Image',      route: 'DRAWING_IMAGE',  mimeTypes: ['image/png'] },
  jpg:   { ext: 'jpg',   formatId: 'RASTER-IMAGE',  canonicalName: 'JPEG Image',         familyLabel: 'Raster / Vector Image',      route: 'DRAWING_IMAGE',  mimeTypes: ['image/jpeg'] },
  jpeg:  { ext: 'jpeg',  formatId: 'RASTER-IMAGE',  canonicalName: 'JPEG Image',         familyLabel: 'Raster / Vector Image',      route: 'DRAWING_IMAGE',  mimeTypes: ['image/jpeg'] },
  tif:   { ext: 'tif',   formatId: 'RASTER-IMAGE',  canonicalName: 'TIFF Image',         familyLabel: 'Raster / Vector Image',      route: 'DRAWING_IMAGE',  mimeTypes: ['image/tiff'] },
  tiff:  { ext: 'tiff',  formatId: 'RASTER-IMAGE',  canonicalName: 'TIFF Image',         familyLabel: 'Raster / Vector Image',      route: 'DRAWING_IMAGE',  mimeTypes: ['image/tiff'] },
  bmp:   { ext: 'bmp',   formatId: 'RASTER-IMAGE',  canonicalName: 'Bitmap Image',       familyLabel: 'Raster / Vector Image',      route: 'DRAWING_IMAGE',  mimeTypes: ['image/bmp'] },
  svg:   { ext: 'svg',   formatId: 'SVG',           canonicalName: 'SVG Vector Image',   familyLabel: 'Raster / Vector Image',      route: 'DRAWING_IMAGE',  mimeTypes: ['image/svg+xml'] },
  dxf:   { ext: 'dxf',   formatId: 'DXF',           canonicalName: 'AutoCAD DXF',        familyLabel: '2D Engineering Drawing',     route: 'DRAWING_VECTOR', mimeTypes: ['image/vnd.dxf', 'application/dxf'] },
  step:  { ext: 'step',  formatId: 'STEP-GENERIC',  canonicalName: 'STEP (AP203/214/242)',familyLabel: 'CAD Neutral Exchange',       route: 'CAD_GEOMETRY',   mimeTypes: ['model/step', 'application/step'] },
  stp:   { ext: 'stp',   formatId: 'STEP-GENERIC',  canonicalName: 'STEP (AP203/214/242)',familyLabel: 'CAD Neutral Exchange',       route: 'CAD_GEOMETRY',   mimeTypes: ['model/step', 'application/step'] },
  iges:  { ext: 'iges',  formatId: 'IGES',          canonicalName: 'IGES',               familyLabel: 'CAD Neutral Exchange',       route: 'CAD_GEOMETRY',   mimeTypes: ['model/iges', 'application/iges'] },
  igs:   { ext: 'igs',   formatId: 'IGES',          canonicalName: 'IGES',               familyLabel: 'CAD Neutral Exchange',       route: 'CAD_GEOMETRY',   mimeTypes: ['model/iges', 'application/iges'] },
  stl:   { ext: 'stl',   formatId: 'STL',           canonicalName: 'STL Mesh',           familyLabel: 'Mesh Geometry',              route: 'MESH_GEOMETRY',  mimeTypes: ['model/stl', 'application/sla'] },
  obj:   { ext: 'obj',   formatId: 'OBJ',           canonicalName: 'Wavefront OBJ',      familyLabel: 'Mesh Geometry',              route: 'MESH_GEOMETRY',  mimeTypes: ['model/obj'] },
  '3mf': { ext: '3mf',   formatId: '3MF',           canonicalName: '3D Manufacturing Format', familyLabel: 'Mesh Geometry',         route: 'MESH_GEOMETRY',  mimeTypes: ['model/3mf'] },
  nc:    { ext: 'nc',    formatId: 'NC-GCODE',      canonicalName: 'NC / G-code',        familyLabel: 'NC / G-code Program',        route: 'NC_PROGRAM',     mimeTypes: ['text/plain'] },
  gcode: { ext: 'gcode', formatId: 'NC-GCODE',      canonicalName: 'G-code',             familyLabel: 'NC / G-code Program',        route: 'NC_PROGRAM',     mimeTypes: ['text/plain'] },
  tap:   { ext: 'tap',   formatId: 'NC-GCODE',      canonicalName: 'NC Tape / G-code',   familyLabel: 'NC / G-code Program',        route: 'NC_PROGRAM',     mimeTypes: ['text/plain'] },
}

/** Comma-separated accept string for the file input (19 native formats, no proprietary). */
export const NATIVE_ACCEPT =
  '.pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.svg,.dxf,.step,.stp,.iges,.igs,.stl,.obj,.3mf,.nc,.gcode,.tap'

/**
 * Detect format from a File object (extension-based, instant, client-side only).
 * Returns the FormatEntry for the extension, or null for unrecognized formats.
 */
export function detectFormatByFile(file: File): FormatEntry | null {
  const dot = file.name.lastIndexOf('.')
  if (dot < 0) return null
  const ext = file.name.slice(dot + 1).toLowerCase()
  return T[ext] ?? null
}
