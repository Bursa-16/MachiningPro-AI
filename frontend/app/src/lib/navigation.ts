import {
  LayoutDashboard, Zap, Wrench, Microscope,
  CheckSquare, TrendingUp, Settings2,
  Search, ClipboardList, Puzzle, SearchCode,
  Archive, FileText, Ruler, ShieldCheck, GitBranch,
  BarChart2, ClipboardCheck,
} from 'lucide-react'
import type { NavGroup } from '../types/navigation'
import type { TranslationDictionary } from '../i18n/types'

export const HOME_ITEM = {
  id: 'dashboard',
  path: '/app',
  labelKey: 'nav_dashboard' as keyof TranslationDictionary,
  icon: LayoutDashboard,
}

export const NAV_GROUPS: NavGroup[] = [
  {
    id: 'engineering', domainKey: 'calculation', labelKey: 'nav_engineering',
    items: [
      { id: 'machining-analysis', path: '/app/engineering/machining-analysis', labelKey: 'nav_machiningAnalysis', icon: Microscope, badge: 'preview' },
      { id: 'cutting-parameters', path: '/app/engineering/cutting-parameters', labelKey: 'nav_cuttingParameters', icon: Settings2 },
      { id: 'tool-life', path: '/app/engineering/tool-life', labelKey: 'nav_toolLife', icon: TrendingUp },
      { id: 'compatibility', path: '/app/engineering/compatibility', labelKey: 'nav_compatibilityCheck', icon: ShieldCheck },
      { id: 'configuration-selection', path: '/app/engineering/configuration-selection', labelKey: 'nav_configurationSelection', icon: GitBranch },
      { id: 'surface-roughness', path: '/app/engineering/surface-roughness', labelKey: 'nav_surfaceRoughness', icon: Ruler, badge: 'preview' },
    ],
  },
  {
    id: 'processes', domainKey: 'validation', labelKey: 'nav_processes',
    items: [
      { id: 'turning', path: '/app/processes/turning', labelKey: 'nav_turning', icon: Wrench, badge: 'preview' },
      { id: 'milling', path: '/app/processes/milling', labelKey: 'nav_milling', icon: Settings2, badge: 'preview' },
      { id: 'drilling', path: '/app/processes/drilling', labelKey: 'nav_drilling', icon: SearchCode, badge: 'preview' },
      { id: 'threading', path: '/app/processes/threading', labelKey: 'nav_threading', icon: Puzzle, badge: 'preview' },
      { id: 'hole-finishing', path: '/app/processes/hole-finishing', labelKey: 'nav_holeFinishing', icon: CheckSquare, badge: 'preview' },
      { id: 'honing', path: '/app/processes/honing', labelKey: 'nav_honing', icon: Microscope, badge: 'preview' },
      { id: 'lapping', path: '/app/processes/lapping', labelKey: 'nav_lapping', icon: Zap, badge: 'preview' },
    ],
  },
  {
    id: 'resources', domainKey: 'production', labelKey: 'nav_resources',
    items: [
      { id: 'machines', path: '/app/resources/machines', labelKey: 'nav_machines', icon: Settings2 },
      { id: 'materials', path: '/app/resources/materials', labelKey: 'nav_materials', icon: Archive, badge: 'preview' },
      { id: 'cutting-tools', path: '/app/resources/cutting-tools', labelKey: 'nav_cuttingTools', icon: Wrench },
      { id: 'tool-holders', path: '/app/resources/tool-holders', labelKey: 'nav_toolHolders', icon: Settings2 },
      { id: 'libraries', path: '/app/resources/libraries', labelKey: 'nav_libraries', icon: ClipboardList, badge: 'preview' },
    ],
  },
  {
    id: 'cad-drawing', domainKey: 'knowledge', labelKey: 'nav_cadDrawing',
    items: [
      { id: 'cad-import', path: '/app/cad-drawing/cad-import', labelKey: 'nav_cadImport', icon: FileText },
      {
        id: 'technical-drawing-intelligence',
        path: '/app/cad-drawing/technical-drawing-intelligence',
        labelKey: 'nav_technicalDrawingIntelligence',
        icon: Search,
      },
      {
        id: 'cad-features',
        path: '/app/cad-drawing/cad-features',
        labelKey: 'nav_cadFeatureRecognition',
        icon: SearchCode,
        badge: 'preview' as const,
      },
    ],
  },
  {
    id: 'planning-quality', domainKey: 'traceability', labelKey: 'nav_planningQuality',
    items: [
      { id: 'process-planning', path: '/app/planning-quality/process-planning', labelKey: 'nav_processPlanning', icon: ClipboardList },
      { id: 'drawing-parser', path: '/app/planning-quality/drawing-parser', labelKey: 'nav_drawingParser', icon: Search },
      { id: 'gdt-intelligence', path: '/app/planning-quality/gdt-intelligence', labelKey: 'nav_gdtIntelligence', icon: Ruler },
      { id: 'process-routes', path: '/app/planning-quality/process-routes', labelKey: 'nav_routeOptimization', icon: GitBranch },
      { id: 'process-capability', path: '/app/planning-quality/process-capability', labelKey: 'nav_processCapability', icon: BarChart2 },
      { id: 'manufacturing-plan', path: '/app/planning-quality/manufacturing-plan', labelKey: 'nav_manufacturingPlan', icon: ClipboardCheck },
      { id: 'dfm', path: '/app/planning-quality/dfm', labelKey: 'nav_dfm', icon: Puzzle, badge: 'preview' },
      { id: 'machine-capability', path: '/app/planning-quality/machine-capability', labelKey: 'nav_machineCapability', icon: TrendingUp, badge: 'preview' },
      { id: 'validation', path: '/app/planning-quality/validation', labelKey: 'nav_validationPage', icon: ShieldCheck, badge: 'preview' },
    ],
  },
]

export type BreadcrumbEntry = {
  domainKey: keyof TranslationDictionary | ''
  pageKey: keyof TranslationDictionary
}

export const BREADCRUMB_MAP: Record<string, BreadcrumbEntry> = {
  '/app': { domainKey: '', pageKey: 'nav_dashboard' },
}

NAV_GROUPS.forEach(group => {
  group.items.forEach(item => {
    BREADCRUMB_MAP[item.path] = { domainKey: group.labelKey, pageKey: item.labelKey }
  })
})
