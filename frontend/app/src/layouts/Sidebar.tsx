import { useState, useEffect, useCallback } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import * as Collapsible from '@radix-ui/react-collapsible'
import { ChevronDown, ChevronRight, ChevronLeft, Pin, PinOff } from 'lucide-react'
import { NAV_GROUPS, HOME_ITEM } from '../lib/navigation'
import type { LucideIcon } from 'lucide-react'

// ── Persistence ──────────────────────────────────────────────────────────────
interface SidebarPrefs { collapsed: boolean; pinned: boolean; openGroups: string[] }

const SIDEBAR_KEY = 'machiningpro_sidebar_state'

function loadPrefs(): SidebarPrefs {
  try {
    // Canonical key
    const raw = localStorage.getItem(SIDEBAR_KEY)
    if (raw) return JSON.parse(raw)
  } catch { /* ignore */ }
  // First visit on a phone-width screen: start collapsed so content keeps its width.
  const narrow = typeof window !== 'undefined' && window.matchMedia?.('(max-width: 767px)').matches
  return { collapsed: !!narrow, pinned: true, openGroups: ['engineering'] }
}

function savePrefs(p: SidebarPrefs) {
  try { localStorage.setItem(SIDEBAR_KEY, JSON.stringify(p)) } catch { /* ignore */ }
}

// ── Icon helper ───────────────────────────────────────────────────────────────
function Icon({ icon: Ic, size = 16 }: { icon: LucideIcon; size?: number }) {
  return <Ic size={size} strokeWidth={1.6} />
}

// ── Tooltip for collapsed mode ────────────────────────────────────────────────
function CollapseTooltip({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="relative group/tip">
      {children}
      <div className="pointer-events-none absolute left-full top-1/2 -translate-y-1/2 ml-2 z-50
                      bg-tp-surface-3 border border-tp-border text-tp-text text-xs px-2 py-1 rounded
                      whitespace-nowrap opacity-0 group-hover/tip:opacity-100 transition-opacity duration-100">
        {label}
      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
export default function Sidebar({ role }: { role: string | null }) {
  const location = useLocation()
  const navigate = useNavigate()
  const isAdmin = role === 'admin'

  const [prefs, setPrefs] = useState<SidebarPrefs>(loadPrefs)
  const [hovered, setHovered] = useState(false)

  const isCollapsed = prefs.collapsed
  const isPinned = prefs.pinned
  // Unpinned + collapsed: expand on hover
  const effectivelyExpanded = !isCollapsed || (!isPinned && hovered)

  const updatePrefs = useCallback((patch: Partial<SidebarPrefs>) => {
    setPrefs(prev => {
      const next = { ...prev, ...patch }
      savePrefs(next)
      return next
    })
  }, [])

  // Auto-open group containing the current route
  useEffect(() => {
    const activeGroup = NAV_GROUPS.find(g =>
      g.items.some(i => i.path === location.pathname)
    )
    if (activeGroup && !prefs.openGroups.includes(activeGroup.id)) {
      updatePrefs({ openGroups: [...prefs.openGroups, activeGroup.id] })
    }
  }, [location.pathname])

  const toggleGroup = (groupId: string) => {
    const next = prefs.openGroups.includes(groupId)
      ? prefs.openGroups.filter(id => id !== groupId)
      : [...prefs.openGroups, groupId]
    updatePrefs({ openGroups: next })
  }

  const visibleGroups = NAV_GROUPS.filter(g => !g.adminOnly || isAdmin)

  const sidebarWidth = effectivelyExpanded ? '280px' : '48px'

  return (
    <aside
      style={{ width: sidebarWidth, minWidth: sidebarWidth, transition: 'width 150ms ease, min-width 150ms ease' }}
      className="bg-tp-surface border-r border-tp-border flex flex-col overflow-hidden shrink-0 h-full"
      onMouseEnter={() => !isPinned && setHovered(true)}
      onMouseLeave={() => !isPinned && setHovered(false)}
    >
      {/* Home / Dashboard — always visible */}
      <div className="shrink-0 pt-2 pb-1 px-1.5">
        <button
          onClick={() => navigate('/app')}
          className={`w-full flex items-center gap-2.5 px-2 py-1.5 rounded text-[13px] transition-colors
            ${location.pathname === '/app'
              ? 'text-tp-accent-light bg-tp-accent/10 border border-tp-accent/20'
              : 'text-tp-text-2 hover:text-tp-text hover:bg-tp-surface-2 border border-transparent'
            }`}
        >
          <span className="shrink-0 w-4 flex justify-center">
            <Icon icon={HOME_ITEM.icon} />
          </span>
          {effectivelyExpanded && <span className="truncate font-medium">{HOME_ITEM.label}</span>}
        </button>
      </div>

      <div className="w-full h-px bg-tp-border mx-0 shrink-0" />

      {/* Navigation groups */}
      <nav className="flex-1 overflow-y-auto py-1 px-1.5 space-y-0.5">
        {visibleGroups.map(group => {
          const isOpen = prefs.openGroups.includes(group.id)
          const hasActive = group.items.some(i => i.path === location.pathname)

          if (!effectivelyExpanded) {
            // Collapsed: show icons only, no group labels
            return (
              <div key={group.id} className="space-y-0.5 pb-2">
                {group.items.map(item => {
                  const isActive = location.pathname === item.path
                  return (
                    <CollapseTooltip key={item.id} label={item.label}>
                      <button
                        onClick={() => navigate(item.path)}
                        className={`w-full flex items-center justify-center p-2 rounded transition-colors
                          ${isActive
                            ? 'text-tp-accent-light bg-tp-accent/10'
                            : 'text-tp-text-3 hover:text-tp-text hover:bg-tp-surface-2'
                          }`}
                      >
                        <Icon icon={item.icon} size={16} />
                      </button>
                    </CollapseTooltip>
                  )
                })}
              </div>
            )
          }

          return (
            <Collapsible.Root key={group.id} open={isOpen} onOpenChange={() => toggleGroup(group.id)}>
              {/* Group heading */}
              <Collapsible.Trigger asChild>
                <button className={`w-full flex items-center justify-between px-2 py-1.5 rounded
                    text-[10px] font-semibold uppercase tracking-widest transition-colors
                    ${hasActive ? 'text-tp-accent-light' : 'text-tp-text-3 hover:text-tp-text-2'}`}>
                  <span>{group.label}</span>
                  <span className="text-tp-text-3">
                    {isOpen ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                  </span>
                </button>
              </Collapsible.Trigger>

              <Collapsible.Content
                style={{ overflow: 'hidden' }}
                className="data-[state=open]:[animation:tp-nav-slide-down_150ms_ease_both] data-[state=closed]:[animation:tp-nav-slide-up_150ms_ease_both]"
              >
                <div className="pb-1">
                  {group.items.map(item => {
                    const isActive = location.pathname === item.path
                    return (
                      <button
                        key={item.id}
                        onClick={() => navigate(item.path)}
                        className={`w-full flex items-center gap-2.5 px-2 py-[5px] rounded text-[13px] transition-colors
                          ${isActive
                            ? 'text-tp-accent-light bg-tp-accent/10 border-l-2 border-tp-accent font-medium'
                            : 'text-tp-text-2 hover:text-tp-text hover:bg-tp-surface-2 border-l-2 border-transparent'
                          }`}
                      >
                        <span className="shrink-0 w-4 flex justify-center">
                          <Icon icon={item.icon} size={14} />
                        </span>
                        <span className="truncate">{item.label}</span>
                      </button>
                    )
                  })}
                </div>
              </Collapsible.Content>
            </Collapsible.Root>
          )
        })}
      </nav>

      {/* Footer: pin + collapse controls */}
      <div className="shrink-0 border-t border-tp-border p-1.5 flex items-center gap-1">
        {/* Pin/unpin — only shown when expanded */}
        {effectivelyExpanded && (
          <button
            onClick={() => updatePrefs({ pinned: !isPinned })}
            title={isPinned ? 'Sabitlemeyi kaldır' : 'Sabitle'}
            className="flex-1 flex items-center gap-1.5 px-2 py-1.5 rounded text-[11px]
                       text-tp-text-3 hover:text-tp-text-2 hover:bg-tp-surface-2 transition-colors"
          >
            {isPinned ? <Pin size={12} /> : <PinOff size={12} />}
            <span>{isPinned ? 'Sabitlendi' : 'Sabit değil'}</span>
          </button>
        )}
        {/* Collapse/expand toggle */}
        <button
          onClick={() => updatePrefs({ collapsed: !isCollapsed, pinned: true })}
          title={isCollapsed ? 'Genişlet' : 'Daralt'}
          className="flex items-center justify-center w-7 h-7 rounded
                     text-tp-text-3 hover:text-tp-text-2 hover:bg-tp-surface-2 transition-colors"
        >
          {isCollapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        </button>
      </div>
    </aside>
  )
}
