import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import { useLocale } from './i18n'
import AppShell from './layouts/AppShell'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import TechnicalDrawingIntelligencePage from './pages/TechnicalDrawingIntelligencePage'
import CadImportPage from './pages/CadImportPage'
import CuttingParametersPage from './pages/CuttingParametersPage'
import ToolLifePage from './pages/ToolLifePage'
import MachineCatalogPage from './pages/MachineCatalogPage'
import CuttingToolCatalogPage from './pages/CuttingToolCatalogPage'
import CompatibilityPage from './pages/CompatibilityPage'
import SelectionPage from './pages/SelectionPage'
import ToolHolderCatalogPage from './pages/ToolHolderCatalogPage'
import ProcessPlanningPage from './pages/ProcessPlanningPage'
import DrawingToProcessPage from './pages/DrawingToProcessPage'
import MaterialLibraryPage from './pages/MaterialLibraryPage'

function CapabilityPendingPage({ title }: { title: string }) {
  const { t } = useLocale()
  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-3xl">
        <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light mb-2">
          {t('capPreviewBadge')}
        </div>
        <h1 className="text-xl font-semibold text-tp-text mb-3">{title}</h1>
        <div className="bg-tp-surface border border-tp-border rounded-lg p-5">
          <div className="text-sm font-medium text-tp-text mb-1">
            {t('capPreviewTitle')}
          </div>
          <div className="text-sm text-tp-text-2">
            {t('capPreviewDesc')}
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
        <Route path="app/engineering/cutting-parameters" element={<CuttingParametersPage />} />
        <Route path="app/engineering/tool-life" element={<ToolLifePage />} />
        <Route path="app/engineering/compatibility" element={<CompatibilityPage />} />
        <Route path="app/engineering/configuration-selection" element={<SelectionPage />} />
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
        <Route path="app/resources/machines" element={<MachineCatalogPage />} />
        <Route path="app/resources/materials" element={<MaterialLibraryPage />} />
        <Route path="app/resources/cutting-tools" element={<CuttingToolCatalogPage />} />
        <Route path="app/resources/tool-holders" element={<ToolHolderCatalogPage />} />
        <Route path="app/resources/libraries" element={capability('Libraries')} />

        {/* CAD & Drawing */}
        <Route path="app/cad-drawing/cad-import" element={<CadImportPage />} />
        <Route
          path="app/cad-drawing/technical-drawing-intelligence"
          element={<TechnicalDrawingIntelligencePage reviewer={user} />}
        />

        {/* Planning & Quality */}
        <Route path="app/planning-quality/process-planning" element={<ProcessPlanningPage />} />
        <Route path="app/planning-quality/drawing-to-process" element={<DrawingToProcessPage />} />
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
