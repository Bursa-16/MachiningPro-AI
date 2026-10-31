import type { LucideIcon } from 'lucide-react'
import type { TranslationDictionary } from '../i18n/types'

export interface NavItem {
  id: string
  path: string
  labelKey: keyof TranslationDictionary
  icon: LucideIcon
  badge?: string | number
}

export interface NavGroup {
  id: string
  domainKey: string
  labelKey: keyof TranslationDictionary
  items: NavItem[]
  adminOnly?: boolean
}
