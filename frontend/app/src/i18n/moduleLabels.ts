/**
 * MachiningPro AI — Canonical Module Label Map
 *
 * SINGLE SOURCE OF TRUTH for all 22 module IDs and navigation group labels.
 *
 * All UI surfaces (sidebar, breadcrumb, page titles, command palette,
 * module guides, related modules, onboarding, global help) MUST consume
 * this map — never hardcode English module names in individual components.
 *
 * Route IDs and URL paths are unchanged.
 */

import type { Locale } from './types'

// ── Module labels ──────────────────────────────────────────────────────────

export const MODULE_LABELS: Record<string, Record<Locale, string>> = {
  'dashboard': { en: 'Dashboard', tr: 'Ana Panel' },
  'machining-analysis': { en: 'Machining Analysis', tr: 'Talaşlı İmalat Analizi' },
  'cutting-parameters': { en: 'Cutting Parameters', tr: 'Kesme Parametreleri' },
  'tool-life': { en: 'Tool Life', tr: 'Takım Ömrü' },
  'surface-roughness': { en: 'Surface Roughness', tr: 'Yüzey Pürüzlülüğü' },
  'turning': { en: 'Turning', tr: 'Tornalama' },
  'milling': { en: 'Milling', tr: 'Frezeleme' },
  'drilling': { en: 'Drilling', tr: 'Delme' },
  'threading': { en: 'Threading', tr: 'Diş Açma' },
  'hole-finishing': { en: 'Hole Finishing', tr: 'Delik Son İşleme' },
  'honing': { en: 'Honing', tr: 'Honlama' },
  'lapping': { en: 'Lapping', tr: 'Lepleme' },
  'machines': { en: 'Machines', tr: 'Tezgâhlar' },
  'materials': { en: 'Materials', tr: 'Malzemeler' },
  'cutting-tools': { en: 'Cutting Tools', tr: 'Kesici Takımlar' },
  'libraries': { en: 'Libraries', tr: 'Kütüphaneler' },
  'cad-import': { en: 'CAD Import', tr: 'CAD İçe Aktarma' },
  'technical-drawing-intelligence': { en: 'Technical Drawing Intelligence', tr: 'Teknik Resim Zekâsı' },
  'process-planning': { en: 'Process Planning', tr: 'Proses Planlama' },
  'dfm': { en: 'DFM', tr: 'Üretilebilirlik Analizi (DFM)' },
  'machine-capability': { en: 'Machine Capability', tr: 'Tezgâh Yeterliliği' },
  'validation': { en: 'Validation', tr: 'Doğrulama' },
}

// ── Navigation group labels ────────────────────────────────────────────────

export const NAV_GROUP_LABELS: Record<string, Record<Locale, string>> = {
  'engineering': { en: 'Engineering', tr: 'Mühendislik' },
  'processes': { en: 'Processes', tr: 'Prosesler' },
  'resources': { en: 'Resources', tr: 'Kaynaklar' },
  'cad-drawing': { en: 'CAD & Drawing', tr: 'CAD ve Teknik Resim' },
  'planning-quality': { en: 'Planning & Quality', tr: 'Planlama ve Kalite' },
}

// ── Helpers ────────────────────────────────────────────────────────────────

/** Returns the localized label for a module ID, falling back to EN. */
export function getModuleLabel(moduleId: string, locale: Locale): string {
  const entry = MODULE_LABELS[moduleId]
  if (!entry) return moduleId
  return entry[locale] ?? entry['en']
}

/** Returns the localized label for a nav group ID, falling back to EN. */
export function getNavGroupLabel(groupId: string, locale: Locale): string {
  const entry = NAV_GROUP_LABELS[groupId]
  if (!entry) return groupId
  return entry[locale] ?? entry['en']
}
