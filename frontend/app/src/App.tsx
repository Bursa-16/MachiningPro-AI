import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import AppShell from './layouts/AppShell'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import TechnicalDrawingIntelligencePage from './pages/TechnicalDrawingIntelligencePage'

function CapabilityPendingPage({ title }: { title: string }) {
  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-3xl">
        <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light mb-2">
          MachiningPro AI
        </div>
        <h1 className="text-xl font-semibold text-tp-text mb-3">{title}</h1>
        <div className="bg-tp-surface border border-tp-border rounded-lg p-5">
          <div className="text-sm font-medium text-tp-text mb-1">
            Backend capability available
          </div>
          <div className="text-sm text-tp-text-2">
            UI integration is pending. This public engineering preview does not expose
            an unverified or cross-project workflow.
          </div>
        </div>
      </div>
    </div>
  )
}

const capability = (title: string) => <CapabilityPendingPage title={title} />

function ProtectedRoutes() {
  const { isAuthenticated, user, role, login, logout } = useAuth()
  if (!isAuthenticated) return <LoginPage onLogin={login} />

  return (
    <Routes>
      <Route element={<AppShell user={user} role={role} onLogout={logout} />}>
        <Route path="app" element={<DashboardPage />} />

        {/* Engineering */}
        <Route path="app/engineering/machining-analysis" element={capability('Machining Analysis')} />
        <Route path="app/engineering/cutting-parameters" element={capability('Cutting Parameters')} />
        <Route path="app/engineering/tool-life" element={capability('Tool Life')} />
        <Route path="app/engineering/surface-roughness" element={capability('Surface Roughness')} />

        {/* Processes */}
        <Route path="app/processes/turning" element={capability('Turning')} />
        <Route path="app/processes/milling" element={capability('Milling')} />
        <Route path="app/processes/drilling" element={capability('Drilling')} />
        <Route path="app/processes/threading" element={capability('Threading')} />
        <Route path="app/processes/hole-finishing" element={capability('Hole Finishing')} />
        <Route path="app/processes/honing" element={capability('Honing')} />
        <Route path="app/processes/lapping" element={capability('Lapping')} />

        {/* Resources */}
        <Route path="app/resources/machines" element={capability('Machines')} />
        <Route path="app/resources/materials" element={capability('Materials')} />
        <Route path="app/resources/cutting-tools" element={capability('Cutting Tools')} />
        <Route path="app/resources/libraries" element={capability('Libraries')} />

        {/* CAD & Drawing */}
        <Route path="app/cad-drawing/cad-import" element={capability('CAD Import')} />
        <Route
          path="app/cad-drawing/technical-drawing-intelligence"
          element={<TechnicalDrawingIntelligencePage reviewer={user} />}
        />

        {/* Planning & Quality */}
        <Route path="app/planning-quality/process-planning" element={capability('Process Planning')} />
        <Route path="app/planning-quality/dfm" element={capability('DFM')} />
        <Route path="app/planning-quality/machine-capability" element={capability('Machine Capability')} />
        <Route path="app/planning-quality/validation" element={capability('Validation')} />

        <Route index element={<Navigate to="/app" replace />} />
        <Route path="*" element={<Navigate to="/app" replace />} />
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/*" element={<ProtectedRoutes />} />
      </Routes>
    </BrowserRouter>
  )
}
