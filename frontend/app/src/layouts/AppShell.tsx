import { useMemo } from 'react'
import { Outlet, Link, useLocation } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import Sidebar from './Sidebar'
import { BREADCRUMB_MAP } from '../lib/navigation'
import { useLocale } from '../i18n'
import { LanguageToggle } from '../components/LanguageToggle'

// AI provider status stays hidden until a verified runtime source exists.
function AiStatusBadge() {
  return null
}

function Breadcrumb({ pathname }: { pathname: string }) {
  const entry = useMemo(() => BREADCRUMB_MAP[pathname] ?? null, [pathname])
  const { t } = useLocale()

  if (!entry) return <span className="text-xs text-tp-text-3">MachiningPro AI</span>

  return (
    <nav className="flex items-center gap-1.5 text-xs">
      {entry.domainKey ? (
        <>
          <span className="text-tp-text-3">{t(entry.domainKey)}</span>
          <ChevronRight size={11} className="text-tp-text-3 shrink-0" />
          <span className="text-tp-text-2 font-medium">{t(entry.pageKey)}</span>
        </>
      ) : (
        <span className="text-tp-text-2 font-medium">{t(entry.pageKey)}</span>
      )}
    </nav>
  )
}

export default function AppShell({ user, role, onLogout }: {
  user: string | null; role: string | null; onLogout: () => void
}) {
  const location = useLocation()
  const { t } = useLocale()

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <header className="h-12 shrink-0 bg-tp-surface border-b border-tp-border
                         flex items-center px-4 gap-4">
        <Link
          to="/app"
          className="flex items-center gap-2 shrink-0 hover:opacity-90 transition-opacity"
        >
          <img
            src="/branding/machiningpro-ai-symbol.png"
            alt=""
            aria-hidden="true"
            className="h-[28px] w-auto shrink-0"
          />
          <span className="text-base font-bold text-tp-accent-light tracking-tight">
            MachiningPro AI
          </span>
          <span className="text-tp-text-3 font-normal text-[10px]">alpha</span>
        </Link>

        <div className="flex-1 min-w-0 truncate">
          <Breadcrumb pathname={location.pathname} />
        </div>

        <div className="shrink-0 flex items-center gap-3">
          <AiStatusBadge />
          <LanguageToggle />
          <div className="hidden items-center gap-2 text-xs sm:flex">
            <span className="text-tp-text-2">{user}</span>
            <span className="text-tp-text-3 text-[10px]">({role})</span>
          </div>
          <button
            onClick={onLogout}
            className="text-xs text-tp-text-3 hover:text-tp-error transition-colors px-2 py-1
                       rounded hover:bg-tp-error-muted"
          >
            {t('logout')}
          </button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <Sidebar role={role} />
        <main className="flex-1 overflow-hidden flex flex-col">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
