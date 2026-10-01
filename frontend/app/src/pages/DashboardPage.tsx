import { useEffect, useState } from 'react'
import Panel from '../components/ui/Panel'
import { getHealth } from '../services/admin'

export default function DashboardPage() {
  const [health, setHealth] = useState<any>(null)

  useEffect(() => {
    getHealth().then(setHealth).catch(() => {})
  }, [])

  return (
    <div className="h-full overflow-y-auto p-6">
      <h1 className="text-lg font-semibold mb-1">Dashboard</h1>
      <div className="text-sm text-tp-text-3 mb-5">
        MachiningPro AI engineering workspace
      </div>

      <div className="grid grid-cols-4 gap-3 mb-5">
        {[
          {
            label: 'API Status',
            value: health?.status || '—',
            color: health?.database_ok ? 'text-tp-valid' : 'text-tp-error',
          },
          {
            label: 'Version',
            value: health?.version || '—',
            color: 'text-tp-accent-light',
          },
          {
            label: 'Database',
            value: health?.database_ok ? 'Connected' : 'Unavailable',
            color: health?.database_ok ? 'text-tp-valid' : 'text-tp-error',
          },
          {
            label: 'Server Date',
            value: health?.server_time?.split('T')[0] || '—',
            color: 'text-tp-text',
          },
        ].map(status => (
          <Panel key={status.label}>
            <div className="text-xs text-tp-text-3 mb-1">{status.label}</div>
            <div className={`text-xl font-bold tabular-nums ${status.color}`}>
              {status.value}
            </div>
          </Panel>
        ))}
      </div>

      <Panel title="Engineering Workspace" subtitle="Machining capabilities organized by domain">
        <div className="text-sm text-tp-text-2">
          Use the left navigation for Engineering, Processes, Resources, CAD & Drawing,
          and Planning & Quality. Capabilities without a verified frontend integration
          are explicitly marked as pending rather than routed to unrelated workflows.
        </div>
      </Panel>
    </div>
  )
}
