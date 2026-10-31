import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import { getHealth } from '../services/admin'
import { useLocale } from '../i18n'

const WORKFLOW_STEPS = [
  { n: '01', key: 'dbStep1' as const, path: '/app/planning-quality/drawing-parser' },
  { n: '02', key: 'dbStep2' as const, path: '/app/planning-quality/gdt-intelligence' },
  { n: '03', key: 'dbStep3' as const, path: '/app/cad-drawing/cad-features' },
  { n: '04', key: 'dbStep4' as const, path: '/app/planning-quality/process-routes' },
  { n: '05', key: 'dbStep5' as const, path: '/app/planning-quality/manufacturing-plan' },
  { n: '06', key: 'dbStep6' as const, path: '/app/planning-quality/manufacturing-plan' },
  { n: '07', key: 'dbStep7' as const, path: '/app/planning-quality/manufacturing-plan' },
  { n: '08', key: 'dbStep8' as const, path: '/app/planning-quality/manufacturing-plan' },
]

const CAPABILITIES = [
  { labelKey: 'dbCapMachines' as const, path: '/app/resources/machines' },
  { labelKey: 'dbCapCuttingTools' as const, path: '/app/resources/cutting-tools' },
  { labelKey: 'dbCapToolHolders' as const, path: '/app/resources/tool-holders' },
  { labelKey: 'dbCapCuttingParameters' as const, path: '/app/engineering/cutting-parameters' },
  { labelKey: 'dbCapCompatibilityCheck' as const, path: '/app/engineering/compatibility' },
  { labelKey: 'dbCapConfigurationSelection' as const, path: '/app/engineering/configuration-selection' },
  { labelKey: 'dbCapDrawingSemanticExtraction' as const, path: '/app/planning-quality/drawing-parser' },
  { labelKey: 'dbCapGdtIntelligence' as const, path: '/app/planning-quality/gdt-intelligence' },
  { labelKey: 'dbCapCadFeatureRecognition' as const, path: '/app/cad-drawing/cad-features' },
  { labelKey: 'dbCapRouteOptimization' as const, path: '/app/planning-quality/process-routes' },
  { labelKey: 'dbCapManufacturingPlan' as const, path: '/app/planning-quality/manufacturing-plan' },
  { labelKey: 'dbCapInspectionControlPlan' as const, path: '/app/planning-quality/manufacturing-plan' },
  { labelKey: 'dbCapProcessCapability' as const, path: '/app/planning-quality/process-capability' },
  { labelKey: 'dbCapTraceability' as const, path: '/app/planning-quality/manufacturing-plan' },
  { labelKey: 'dbCapToolLifeExplorer' as const, path: '/app/engineering/tool-life' },
]

export default function DashboardPage() {
  const { t } = useLocale()
  const navigate = useNavigate()
  const [health, setHealth] = useState<Record<string, unknown> | null>(null)

  useEffect(() => { getHealth().then(setHealth).catch(() => {}) }, [])

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6">

      {/* Identity + value prop */}
      <div>
        <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light mb-2">
          {t('dbAlpha')} · v0.5.0-demo
        </div>
        <h1 className="text-xl font-semibold text-tp-text mb-1">MachiningPro AI</h1>
        <p className="text-sm text-tp-text-2 max-w-xl">{t('dbValueProp')}</p>
      </div>

      {/* One-click demo card */}
      <div className="bg-tp-surface border border-tp-accent-light/30 rounded-lg p-5">
        <div className="mb-3">
          <div className="text-sm font-semibold text-tp-text">{t('dbDemoCardTitle')}</div>
          <div className="text-xs text-tp-text-3 mt-0.5">
            {t('dbDemoCardSubtitle')}
          </div>
        </div>
        <button
          onClick={() => navigate('/app/planning-quality/manufacturing-plan?demo=1')}
          className="px-4 py-2 bg-tp-accent-light text-white text-sm font-semibold rounded hover:opacity-90 transition-opacity"
        >
          {t('demo_startDemo')} →
        </button>
      </div>

      {/* Demo workflow */}
      <div className="bg-tp-surface border border-tp-border rounded-lg p-5">
        <div className="mb-3">
          <div className="text-sm font-semibold text-tp-text">{t('dbWorkflowTitle')}</div>
          <div className="text-xs text-tp-text-3 mt-0.5">{t('dbWorkflowDesc')}</div>
        </div>
        <div className="space-y-1.5">
          {WORKFLOW_STEPS.map(step => (
            <button
              key={step.n}
              onClick={() => navigate(step.path)}
              className="w-full flex items-center gap-3 px-3 py-2 rounded hover:bg-tp-surface-2 transition-colors text-left group"
            >
              <span className="shrink-0 text-[10px] font-mono font-semibold text-tp-accent-light w-5 text-right">
                {step.n}
              </span>
              <span className="text-sm text-tp-text-2 group-hover:text-tp-text transition-colors flex-1">
                {t(step.key)}
              </span>
              <ChevronRight size={12} className="shrink-0 text-tp-text-3 opacity-0 group-hover:opacity-100 transition-opacity" />
            </button>
          ))}
        </div>
      </div>

      {/* Available capabilities grid */}
      <div>
        <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-text-3 mb-2">
          {t('dbCapabilitiesTitle')}
        </div>
        <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-3 lg:grid-cols-5">
          {CAPABILITIES.map(cap => (
            <button
              key={cap.path}
              onClick={() => navigate(cap.path)}
              className="text-left px-3 py-2.5 rounded border border-tp-border bg-tp-surface hover:bg-tp-surface-2 hover:border-tp-border-2 transition-colors group"
            >
              <span className="text-xs font-medium text-tp-text-2 group-hover:text-tp-text transition-colors">
                {t(cap.labelKey)}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* System status — compact */}
      {health && (
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-text-3 mb-2">
            {t('dbStatusTitle')}
          </div>
          <div className="flex flex-wrap gap-2">
            {[
              { k: 'apiStatus', v: t('connected') },
              { k: 'version', v: String(health.version ?? '—') },
              { k: 'database', v: health.database ? t('connected') : '—' },
              { k: 'serverDate', v: health.server_date ? String(health.server_date).split('T')[0] : '—' },
            ].map(item => (
              <div key={item.k} className="text-xs text-tp-text-3 bg-tp-surface border border-tp-border rounded px-2 py-1">
                <span className="text-tp-text-2">{t(item.k as Parameters<typeof t>[0])}</span>
                <span className="mx-1 text-tp-border">·</span>
                <span className="font-mono">{item.v}</span>
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  )
}
