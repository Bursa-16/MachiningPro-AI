import { useMemo } from 'react'
import { Outlet, Link, useLocation } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import Sidebar from './Sidebar'
import { BREADCRUMB_MAP } from '../lib/navigation'

// AI provider status stays hidden until a verified runtime source exists.
function AiStatusBadge() {
  return null
}

function Breadcrumb({ pathname }: { pathname: string }) {
  const entry = useMemo(() => BREADCRUMB_MAP[pathname] ?? null, [pathname])

  if (!entry) return <span className="text-xs text-tp-text-3">MachiningPro AI</span>

  return (
    <nav className="flex items-center gap-1.5 text-xs">
      {entry.domain ? (
        <>
          <span className="text-tp-text-3">{entry.domain}</span>
          <ChevronRight size={11} className="text-tp-text-3 shrink-0" />
          <span className="text-tp-text-2 font-medium">{entry.page}</span>
        </>
      ) : (
        <span className="text-tp-text-2 font-medium">{entry.page}</span>
      )}
    </nav>
  )
}

export default function AppShell({ user, role, onLogout }: {
  user: string | null; role: string | null; onLogout: () => void
}) {
  const location = useLocation()

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <header className="h-12 shrink-0 bg-tp-surface border-b border-tp-border
                         flex items-center px-4 gap-4">
        <Link
          to="/app"
          className="text-base font-bold text-tp-accent-light tracking-tight shrink-0
                     hover:text-tp-accent transition-colors"
        >
          MachiningPro AI
          <span className="text-tp-text-3 font-normal text-[10px] ml-1.5">alpha</span>
        </Link>

        <div className="flex-1 min-w-0 truncate">
          <Breadcrumb pathname={location.pathname} />
        </div>

        <div className="shrink-0 flex items-center gap-3">
          <AiStatusBadge />
          <div className="hidden items-center gap-2 text-xs sm:flex">
            <span className="text-tp-text-2">{user}</span>
            <span className="text-tp-text-3 text-[10px]">({role})</span>
          </div>
          <button
            onClick={onLogout}
            className="text-xs text-tp-text-3 hover:text-tp-error transition-colors px-2 py-1
                       rounded hover:bg-tp-error-muted"
          >
            Çıkış
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
