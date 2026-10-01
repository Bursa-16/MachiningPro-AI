import {
  LayoutDashboard, Zap, Wrench, Microscope,
  CheckSquare, TrendingUp, Settings2,
  Search, ClipboardList, Puzzle, SearchCode,
  Archive, FileText, Ruler, ShieldCheck,
} from 'lucide-react'
import type { NavGroup } from '../types/navigation'

export const HOME_ITEM = {
  id: 'dashboard',
  path: '/app',
  label: 'Dashboard',
  icon: LayoutDashboard,
}

export const NAV_GROUPS: NavGroup[] = [
  {
    id: 'engineering', domainKey: 'calculation', label: 'Engineering',
    items: [
      { id: 'machining-analysis', path: '/app/engineering/machining-analysis', label: 'Machining Analysis', icon: Microscope },
      { id: 'cutting-parameters', path: '/app/engineering/cutting-parameters', label: 'Cutting Parameters', icon: Settings2 },
      { id: 'tool-life', path: '/app/engineering/tool-life', label: 'Tool Life', icon: TrendingUp },
      { id: 'surface-roughness', path: '/app/engineering/surface-roughness', label: 'Surface Roughness', icon: Ruler },
    ],
  },
  {
    id: 'processes', domainKey: 'validation', label: 'Processes',
    items: [
      { id: 'turning', path: '/app/processes/turning', label: 'Turning', icon: Wrench },
      { id: 'milling', path: '/app/processes/milling', label: 'Milling', icon: Settings2 },
      { id: 'drilling', path: '/app/processes/drilling', label: 'Drilling', icon: SearchCode },
      { id: 'threading', path: '/app/processes/threading', label: 'Threading', icon: Puzzle },
      { id: 'hole-finishing', path: '/app/processes/hole-finishing', label: 'Hole Finishing', icon: CheckSquare },
      { id: 'honing', path: '/app/processes/honing', label: 'Honing', icon: Microscope },
      { id: 'lapping', path: '/app/processes/lapping', label: 'Lapping', icon: Zap },
    ],
  },
  {
    id: 'resources', domainKey: 'production', label: 'Resources',
    items: [
      { id: 'machines', path: '/app/resources/machines', label: 'Machines', icon: Settings2 },
      { id: 'materials', path: '/app/resources/materials', label: 'Materials', icon: Archive },
      { id: 'cutting-tools', path: '/app/resources/cutting-tools', label: 'Cutting Tools', icon: Wrench },
      { id: 'libraries', path: '/app/resources/libraries', label: 'Libraries', icon: ClipboardList },
    ],
  },
  {
    id: 'cad-drawing', domainKey: 'knowledge', label: 'CAD & Drawing',
    items: [
      { id: 'cad-import', path: '/app/cad-drawing/cad-import', label: 'CAD Import', icon: FileText },
      {
        id: 'technical-drawing-intelligence',
        path: '/app/cad-drawing/technical-drawing-intelligence',
        label: 'Technical Drawing Intelligence',
        icon: Search,
      },
    ],
  },
  {
    id: 'planning-quality', domainKey: 'traceability', label: 'Planning & Quality',
    items: [
      { id: 'process-planning', path: '/app/planning-quality/process-planning', label: 'Process Planning', icon: ClipboardList },
      { id: 'dfm', path: '/app/planning-quality/dfm', label: 'DFM', icon: Puzzle },
      { id: 'machine-capability', path: '/app/planning-quality/machine-capability', label: 'Machine Capability', icon: TrendingUp },
      { id: 'validation', path: '/app/planning-quality/validation', label: 'Validation', icon: ShieldCheck },
    ],
  },
]

export type BreadcrumbEntry = { domain: string; page: string }

export const BREADCRUMB_MAP: Record<string, BreadcrumbEntry> = {
  '/app': { domain: '', page: 'Dashboard' },
}

NAV_GROUPS.forEach(group => {
  group.items.forEach(item => {
    BREADCRUMB_MAP[item.path] = { domain: group.label, page: item.label }
  })
})
