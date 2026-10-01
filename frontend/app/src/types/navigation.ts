import type { LucideIcon } from 'lucide-react'

export interface NavItem {
  id: string
  path: string
  label: string
  icon: LucideIcon
  badge?: string | number
}

export interface NavGroup {
  id: string
  domainKey: string
  label: string
  items: NavItem[]
  adminOnly?: boolean
}
