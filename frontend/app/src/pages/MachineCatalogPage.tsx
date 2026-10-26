import { useEffect, useState, useCallback } from 'react'
import { useLocale } from '../i18n/index'
import {
  fetchMachineSchema,
  fetchMachines,
  fetchMachineDetail,
  searchMachines,
  type MachineCatalogRecord,
  type MachineSchema,
} from '../services/machines'

// ── Tiny shared components ────────────────────────────────────────────────────

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--tp-text-3)] mb-2">
      {children}
    </div>
  )
}

function FieldRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between items-baseline py-1.5 border-b border-[var(--tp-border)] last:border-0">
      <span className="text-xs text-[var(--tp-text-2)]">{label}</span>
      <span className="text-sm font-mono text-[var(--tp-text)] ml-4 text-right">{value}</span>
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg px-4 py-3 flex flex-col gap-1 min-w-0">
      <div className="text-lg font-semibold text-[var(--tp-text)] tabular-nums">{value}</div>
      <div className="text-[11px] text-[var(--tp-text-2)] uppercase tracking-wide">{label}</div>
    </div>
  )
}

function MissingVal({ label }: { label: string }) {
  return <span className="text-[var(--tp-text-3)]">{label}</span>
}

function ProcessBadge({ name }: { name: string }) {
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-[var(--tp-surface-3)] text-[var(--tp-text-2)] mr-1 mb-1">
      {name}
    </span>
  )
}

function FeatureBadge({ label, active }: { label: string; active: boolean | null }) {
  if (active === null) return null
  const cls = active
    ? 'bg-[var(--tp-accent-muted)] text-[var(--tp-accent-light)] border-[var(--tp-accent-light)]'
    : 'bg-[var(--tp-surface-3)] text-[var(--tp-text-3)] border-[var(--tp-border)]'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded border text-[10px] font-medium mr-1 mb-1 ${cls}`}>
      {label}
    </span>
  )
}

// ── Detail panel ──────────────────────────────────────────────────────────────

function MachineDetail({
  record,
  onBack,
}: {
  record: MachineCatalogRecord
  onBack: () => void
}) {
  const { t } = useLocale()
  const mv = t('mcMissingValue')

  function num(val: number | null, unit: string) {
    if (val === null) return <MissingVal label={mv} />
    return <>{val.toLocaleString()} {unit}</>
  }

  function bool(val: boolean) {
    return val ? t('mcYes') : t('mcNo')
  }

  function boolOpt(val: boolean | null) {
    if (val === null) return <MissingVal label={mv} />
    return <>{val ? t('mcYes') : t('mcNo')}</>
  }

  function str(val: string | null) {
    if (!val) return <MissingVal label={mv} />
    return <>{val}</>
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Back */}
      <button
        onClick={onBack}
        className="self-start text-xs text-[var(--tp-accent-light)] hover:underline mb-1"
      >
        ← {t('mcBack')}
      </button>

      {/* Header */}
      <div>
        <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--tp-accent-light)] mb-1">
          {record.manufacturer}
        </div>
        <h2 className="text-xl font-semibold text-[var(--tp-text)]">{record.model}</h2>
        <div className="text-sm text-[var(--tp-text-2)] mt-1">{record.machine_type}</div>
        {record.family && (
          <div className="text-xs text-[var(--tp-text-3)]">{record.family}</div>
        )}
        {record.country_of_origin && (
          <div className="text-xs text-[var(--tp-text-3)]">{t('mcCountryOfOrigin')}: {record.country_of_origin}</div>
        )}
      </div>

      {/* Disclaimer */}
      <div className="bg-[var(--tp-warn-muted)] border border-[var(--tp-warn)] rounded-lg p-3 text-xs text-[var(--tp-warn)]">
        {t('mcCatalogBrowseOnly')}
      </div>

      {/* Capability */}
      <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4 flex flex-col gap-1">
        <SectionLabel>{t('mcMachineType')}</SectionLabel>
        <FieldRow label={t('mcMachineType')} value={record.machine_type} />
        <FieldRow label={t('mcMachineTypeCode')} value={record.machine_type_code} />
        <FieldRow label={t('mcAxisCount')} value={`${record.axis_count}`} />
        {record.simultaneous_axis_count !== null && (
          <FieldRow label={t('mcSimultaneousAxes')} value={`${record.simultaneous_axis_count}`} />
        )}
        <FieldRow label={t('mcTurningCapable')} value={bool(record.turning_capable)} />
        <FieldRow label={t('mcMillingCapable')} value={bool(record.milling_capable)} />
        <FieldRow label={t('mcDrillingCapable')} value={bool(record.drilling_capable)} />
        <div className="mt-2">
          <div className="text-xs text-[var(--tp-text-2)] mb-1">{t('mcSupportedProcesses')}</div>
          <div className="flex flex-wrap">
            {record.supported_processes.map(p => <ProcessBadge key={p} name={p} />)}
          </div>
        </div>
      </div>

      {/* Features */}
      <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4">
        <SectionLabel>{t('mcFeaturesSection')}</SectionLabel>
        <div className="flex flex-wrap">
          <FeatureBadge label={t('mcFeatureSubspindle')} active={record.has_subspindle} />
          <FeatureBadge label={t('mcFeatureYAxis')} active={record.has_y_axis} />
          <FeatureBadge label={t('mcFeatureLiveTooling')} active={record.has_live_tooling} />
          <FeatureBadge label={t('mcFeatureBAxis')} active={record.has_b_axis} />
          <FeatureBadge label={t('mcFeaturePalletChanger')} active={record.has_pallet_changer} />
          <FeatureBadge label={t('mcCapable5Axis')} active={record.capable_5axis_simultaneous} />
          <FeatureBadge label={t('mcCapable3Plus2')} active={record.capable_3plus2} />
          <FeatureBadge label={t('mcCapableTapping')} active={record.capable_tapping} />
          <FeatureBadge label={t('mcCapableBoring')} active={record.capable_boring} />
          <FeatureBadge label={t('mcCapableThreading')} active={record.capable_threading} />
          <FeatureBadge label={t('mcCapableReaming')} active={record.capable_reaming} />
        </div>
      </div>

      {/* Spindle */}
      <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4 flex flex-col gap-1">
        <SectionLabel>{t('mcSpindleSection')}</SectionLabel>
        <FieldRow label={t('mcSpindleMaxRpm')} value={num(record.spindle_max_rpm, t('mcUnitRpm'))} />
        {record.spindle_min_rpm !== null && (
          <FieldRow label={t('mcSpindleMinRpm')} value={num(record.spindle_min_rpm, t('mcUnitRpm'))} />
        )}
        <FieldRow label={t('mcSpindlePowerKw')} value={num(record.spindle_power_kw, t('mcUnitKw'))} />
        {record.spindle_power_continuous_kw !== null && (
          <FieldRow label={t('mcSpindlePowerContKw')} value={num(record.spindle_power_continuous_kw, t('mcUnitKw'))} />
        )}
        <FieldRow label={t('mcSpindleTorqueNm')} value={num(record.spindle_torque_nm, t('mcUnitNm'))} />
        <FieldRow label={t('mcSpindleInterface')} value={str(record.spindle_interface)} />
        {record.spindle_interfaces_supported.length > 0 && (
          <FieldRow label={t('mcSpindleInterfacesSupported')} value={record.spindle_interfaces_supported.join(', ')} />
        )}
        {record.max_cutting_feed_mm_min !== null && (
          <FieldRow label={t('mcMaxCuttingFeed')} value={num(record.max_cutting_feed_mm_min, t('mcUnitMmMin'))} />
        )}
      </div>

      {/* Workspace */}
      <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4 flex flex-col gap-1">
        <SectionLabel>{t('mcWorkspaceSection')}</SectionLabel>
        {record.travel_x_mm !== null && (
          <FieldRow label={t('mcTravelX')} value={num(record.travel_x_mm, t('mcUnitMm'))} />
        )}
        {record.travel_y_mm !== null && (
          <FieldRow label={t('mcTravelY')} value={num(record.travel_y_mm, t('mcUnitMm'))} />
        )}
        {record.travel_z_mm !== null && (
          <FieldRow label={t('mcTravelZ')} value={num(record.travel_z_mm, t('mcUnitMm'))} />
        )}
        {record.table_length_mm !== null && (
          <FieldRow label={t('mcTableLength')} value={num(record.table_length_mm, t('mcUnitMm'))} />
        )}
        {record.table_width_mm !== null && (
          <FieldRow label={t('mcTableWidth')} value={num(record.table_width_mm, t('mcUnitMm'))} />
        )}
        {record.table_load_kg !== null && (
          <FieldRow label={t('mcTableLoad')} value={num(record.table_load_kg, t('mcUnitKg'))} />
        )}
        {record.max_turning_diameter_mm !== null && (
          <FieldRow label={t('mcMaxTurningDia')} value={num(record.max_turning_diameter_mm, t('mcUnitMm'))} />
        )}
        {record.max_turning_length_mm !== null && (
          <FieldRow label={t('mcMaxTurningLength')} value={num(record.max_turning_length_mm, t('mcUnitMm'))} />
        )}
        {record.bar_capacity_mm !== null && (
          <FieldRow label={t('mcBarCapacity')} value={num(record.bar_capacity_mm, t('mcUnitMm'))} />
        )}
      </div>

      {/* Tool system */}
      <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4 flex flex-col gap-1">
        <SectionLabel>{t('mcToolSection')}</SectionLabel>
        <FieldRow label={t('mcMagazineCapacity')} value={
          record.tool_magazine_capacity !== null
            ? `${record.tool_magazine_capacity}`
            : <MissingVal label={mv} />
        } />
        {record.tool_magazine_type && (
          <FieldRow label={t('mcMagazineType')} value={record.tool_magazine_type} />
        )}
        <FieldRow label={t('mcToolInterface')} value={str(record.tool_interface ?? record.spindle_interface)} />
        <FieldRow label={t('mcMaxToolDia')} value={num(record.max_tool_diameter_mm, t('mcUnitMm'))} />
        <FieldRow label={t('mcMaxToolLength')} value={num(record.max_tool_length_mm, t('mcUnitMm'))} />
        {record.atc_chip_to_chip_sec !== null && (
          <FieldRow label={t('mcAtcChipToChip')} value={num(record.atc_chip_to_chip_sec, t('mcUnitSec'))} />
        )}
      </div>

      {/* Coolant */}
      <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4 flex flex-col gap-1">
        <SectionLabel>{t('mcCoolantSection')}</SectionLabel>
        <FieldRow label={t('mcFloodCoolant')} value={bool(record.flood_coolant)} />
        <FieldRow label={t('mcThroughSpindleCoolant')} value={boolOpt(record.through_spindle_coolant)} />
        {record.coolant_pressure_bar !== null && (
          <FieldRow label={t('mcCoolantPressure')} value={num(record.coolant_pressure_bar, t('mcUnitBar'))} />
        )}
        <FieldRow label={t('mcMqlSupport')} value={boolOpt(record.mql_support)} />
      </div>

      {/* Envelope & dynamics */}
      <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4 flex flex-col gap-1">
        <SectionLabel>{t('mcDynamicsSection')}</SectionLabel>
        <FieldRow label={t('mcRapidTraverse')} value={num(record.rapid_traverse_mpm, t('mcUnitMpm'))} />
        <FieldRow label={t('mcMachineWeight')} value={num(record.machine_weight_kg, t('mcUnitKg'))} />
        {record.positioning_accuracy_um !== null && (
          <FieldRow label={t('mcPositioningAccuracy')} value={num(record.positioning_accuracy_um, 'µm')} />
        )}
        {record.repeatability_um !== null && (
          <FieldRow label={t('mcRepeatability')} value={num(record.repeatability_um, 'µm')} />
        )}
      </div>

      {/* Control */}
      <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4 flex flex-col gap-1">
        <SectionLabel>{t('mcControlSection')}</SectionLabel>
        <FieldRow label={t('mcControllerFamily')} value={str(record.controller_family)} />
        {record.controller_model && (
          <FieldRow label={t('mcControllerModel')} value={record.controller_model} />
        )}
        {record.nc_dialect && (
          <FieldRow label={t('mcNcDialect')} value={record.nc_dialect} />
        )}
      </div>

      {/* Source */}
      <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4 flex flex-col gap-2">
        <SectionLabel>{t('mcSourceSection')}</SectionLabel>
        <div className="text-xs text-[var(--tp-text-2)]">
          <span className="font-medium text-[var(--tp-text)]">{t('mcEvidenceLabel')}: </span>
          {record.evidence_status}
        </div>
        <div className="text-xs text-[var(--tp-text-2)]">
          <span className="font-medium text-[var(--tp-text)]">{t('mcSourceTitle')}: </span>
          {record.source_title}
        </div>
        {record.source_note && (
          <div className="text-[11px] text-[var(--tp-text-3)] mt-1">{record.source_note}</div>
        )}
        {record.missing_fields.length > 0 && (
          <div className="mt-2">
            <div className="text-xs text-[var(--tp-text-2)] mb-1">{t('mcMissingFields')}</div>
            <div className="flex flex-wrap gap-1">
              {record.missing_fields.map(f => (
                <span key={f} className="text-[10px] font-mono bg-[var(--tp-surface-3)] text-[var(--tp-text-3)] px-1.5 py-0.5 rounded">
                  {f}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Machine list card ─────────────────────────────────────────────────────────

function MachineCard({
  record,
  onClick,
  missingVal: _missingVal,
  compareSelected,
  onToggleCompare,
}: {
  record: MachineCatalogRecord
  onClick: () => void
  missingVal: string
  compareSelected: boolean
  onToggleCompare: (id: string) => void
}) {
  return (
    <div
      className={`relative bg-[var(--tp-surface)] border rounded-lg p-4 flex flex-col gap-2 transition-colors
        ${compareSelected ? 'border-[var(--tp-accent-light)]' : 'border-[var(--tp-border)]'}`}
    >
      <button
        onClick={onClick}
        className="w-full text-left flex flex-col gap-1"
      >
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--tp-accent-light)]">
              {record.manufacturer}
            </div>
            <div className="text-base font-semibold text-[var(--tp-text)] truncate">{record.model}</div>
            <div className="text-xs text-[var(--tp-text-2)]">{record.machine_type}</div>
          </div>
          <div className="flex-shrink-0 text-right">
            <div className="text-xs font-mono text-[var(--tp-text)]">
              {record.axis_count}ax
            </div>
            {record.spindle_max_rpm && (
              <div className="text-xs text-[var(--tp-text-3)]">
                {record.spindle_max_rpm.toLocaleString()} RPM
              </div>
            )}
            {record.spindle_interface && (
              <div className="text-[10px] text-[var(--tp-text-3)]">
                {record.spindle_interface}
              </div>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-1">
          {record.supported_processes.slice(0, 4).map(p => (
            <ProcessBadge key={p} name={p} />
          ))}
          {record.supported_processes.length > 4 && (
            <span className="text-[10px] text-[var(--tp-text-3)]">+{record.supported_processes.length - 4}</span>
          )}
        </div>
      </button>
      <button
        onClick={e => { e.stopPropagation(); onToggleCompare(record.stable_id) }}
        className={`self-end text-[10px] px-2 py-0.5 rounded border transition-colors
          ${compareSelected
            ? 'border-[var(--tp-accent-light)] text-[var(--tp-accent-light)] bg-[var(--tp-accent-muted)]'
            : 'border-[var(--tp-border)] text-[var(--tp-text-3)] hover:border-[var(--tp-accent-light)]'
          }`}
      >
        {compareSelected ? '✓ Compare' : '+ Compare'}
      </button>
    </div>
  )
}

// ── Comparison panel ──────────────────────────────────────────────────────────

const COMPARE_FIELDS: Array<{ key: keyof MachineCatalogRecord; label: string; format?: (v: unknown) => string }> = [
  { key: 'machine_type', label: 'Type' },
  { key: 'axis_count', label: 'Axes' },
  { key: 'simultaneous_axis_count', label: 'Simultaneous axes' },
  { key: 'spindle_max_rpm', label: 'Spindle max RPM', format: v => v != null ? `${(v as number).toLocaleString()} rpm` : '—' },
  { key: 'spindle_power_kw', label: 'Spindle power', format: v => v != null ? `${v} kW` : '—' },
  { key: 'spindle_interface', label: 'Spindle interface' },
  { key: 'travel_x_mm', label: 'Travel X', format: v => v != null ? `${v} mm` : '—' },
  { key: 'travel_y_mm', label: 'Travel Y', format: v => v != null ? `${v} mm` : '—' },
  { key: 'travel_z_mm', label: 'Travel Z', format: v => v != null ? `${v} mm` : '—' },
  { key: 'tool_magazine_capacity', label: 'Magazine capacity' },
  { key: 'rapid_traverse_mpm', label: 'Rapid traverse', format: v => v != null ? `${v} m/min` : '—' },
  { key: 'controller_family', label: 'Controller' },
  { key: 'has_pallet_changer', label: 'Pallet changer', format: v => v ? 'Yes' : 'No' },
  { key: 'through_spindle_coolant', label: 'TSC', format: v => v === null ? '?' : v ? 'Yes' : 'No' },
  { key: 'capable_5axis_simultaneous', label: '5-axis simultaneous', format: v => v === null ? '?' : v ? 'Yes' : 'No' },
]

function ComparePanel({
  records,
  onClose,
}: {
  records: MachineCatalogRecord[]
  onClose: () => void
}) {
  return (
    <div className="overflow-x-auto">
      <div className="flex justify-between items-center mb-3">
        <div className="text-sm font-semibold text-[var(--tp-text)]">
          Comparison ({records.length} machines)
        </div>
        <button onClick={onClose} className="text-xs text-[var(--tp-text-3)] hover:text-[var(--tp-text)]">
          ✕ Close
        </button>
      </div>
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr>
            <th className="text-left py-2 pr-4 text-[var(--tp-text-3)] font-medium w-32 min-w-32">Field</th>
            {records.map(r => (
              <th key={r.stable_id} className="text-left py-2 px-2 text-[var(--tp-text)] font-medium min-w-[140px]">
                <div className="text-[10px] text-[var(--tp-accent-light)]">{r.manufacturer}</div>
                <div>{r.model}</div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {COMPARE_FIELDS.map(f => (
            <tr key={String(f.key)} className="border-t border-[var(--tp-border)]">
              <td className="py-1.5 pr-4 text-[var(--tp-text-2)]">{f.label}</td>
              {records.map(r => {
                const v = r[f.key]
                const display = f.format ? f.format(v) : (v == null ? '—' : String(v))
                return (
                  <td key={r.stable_id} className="py-1.5 px-2 font-mono text-[var(--tp-text)]">
                    {display}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function MachineCatalogPage() {
  const { t } = useLocale()

  const [schema, setSchema] = useState<MachineSchema | null>(null)
  const [machines, setMachines] = useState<MachineCatalogRecord[]>([])
  const [selectedMachine, setSelectedMachine] = useState<MachineCatalogRecord | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Filters
  const [filterManufacturer, setFilterManufacturer] = useState('')
  const [filterMachineType, setFilterMachineType] = useState('')
  const [filterProcess, setFilterProcess] = useState('')
  const [filterAxis, setFilterAxis] = useState('')
  const [filterSpindleInterface, setFilterSpindleInterface] = useState('')
  const [filter5Axis, setFilter5Axis] = useState(false)

  // Search
  const [searchQuery, setSearchQuery] = useState('')
  const [searchActive, setSearchActive] = useState(false)

  // Comparison
  const [compareIds, setCompareIds] = useState<string[]>([])
  const [showCompare, setShowCompare] = useState(false)

  // Load schema once
  useEffect(() => {
    fetchMachineSchema()
      .then(setSchema)
      .catch(() => setError(t('mcBackendError')))
  }, [])

  // Load machines whenever filters or search changes
  const loadMachines = useCallback(async () => {
    setLoading(true)
    setError(null)
    setSelectedMachine(null)
    try {
      let list: MachineCatalogRecord[]
      if (searchActive && searchQuery.trim()) {
        list = await searchMachines({
          q: searchQuery.trim(),
          manufacturer: filterManufacturer || undefined,
          machine_type: filterMachineType || undefined,
          spindle_interface: filterSpindleInterface || undefined,
          has_5axis: filter5Axis || undefined,
        })
      } else {
        const params: Record<string, string | number | boolean> = {}
        if (filterManufacturer) params.manufacturer = filterManufacturer
        if (filterMachineType) params.machine_type = filterMachineType
        if (filterProcess) params.process = filterProcess
        if (filterAxis) params.axis_count = Number(filterAxis)
        if (filterSpindleInterface) params.spindle_interface = filterSpindleInterface
        if (filter5Axis) params.has_5axis = true
        list = await fetchMachines(params)
      }
      setMachines(list)
    } catch {
      setError(t('mcBackendError'))
    } finally {
      setLoading(false)
    }
  }, [filterManufacturer, filterMachineType, filterProcess, filterAxis, filterSpindleInterface, filter5Axis, searchActive, searchQuery])

  useEffect(() => { loadMachines() }, [loadMachines])

  const handleSelectMachine = useCallback(async (id: string) => {
    try {
      const detail = await fetchMachineDetail(id)
      setSelectedMachine(detail)
    } catch {
      const found = machines.find(m => m.stable_id === id) ?? null
      setSelectedMachine(found)
    }
  }, [machines])

  const handleToggleCompare = useCallback((id: string) => {
    setCompareIds(prev => {
      if (prev.includes(id)) return prev.filter(x => x !== id)
      if (prev.length >= 4) return prev  // max 4
      return [...prev, id]
    })
  }, [])

  const compareRecords = machines.filter(m => compareIds.includes(m.stable_id))

  const selectLabel = (label: string) => `${t('mcFilterAll')} — ${label}`

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setSearchActive(!!searchQuery.trim())
  }

  const handleSearchClear = () => {
    setSearchQuery('')
    setSearchActive(false)
  }

  return (
    <div className="h-full overflow-y-auto p-4 sm:p-6">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="mb-5">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--tp-accent-light)] mb-2">
            MachiningPro AI
          </div>
          <h1 className="text-xl font-semibold text-[var(--tp-text)] mb-1">{t('mcPageTitle')}</h1>
          <p className="text-sm text-[var(--tp-text-2)]">{t('mcPageSubtitle')}</p>
        </div>

        {/* Summary cards */}
        {schema && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
            <StatCard label={t('mcMachineCount')} value={schema.machine_count} />
            <StatCard label={t('mcManufacturerCount')} value={schema.manufacturers.length} />
            <StatCard label={t('mcMachineTypeCount')} value={schema.machine_types.length} />
            <StatCard label={t('mcEvidenceLabel')} value={t('mcEvidenceStatus')} />
          </div>
        )}

        {/* Disclaimer */}
        <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-3 text-xs text-[var(--tp-text-2)] mb-5">
          <span className="font-semibold text-[var(--tp-text)]">{t('mcProductionNotValidated')}. </span>
          {t('mcCatalogBrowseOnly')}
        </div>

        {selectedMachine ? (
          <MachineDetail
            record={selectedMachine}
            onBack={() => setSelectedMachine(null)}
          />
        ) : (
          <>
            {/* Search bar */}
            <form onSubmit={handleSearchSubmit} className="flex gap-2 mb-4">
              <input
                type="text"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder={t('mcSearchPlaceholder')}
                className="flex-1 text-sm bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded px-3 py-1.5 text-[var(--tp-text)] focus:outline-none focus:border-[var(--tp-accent-light)] placeholder:text-[var(--tp-text-3)]"
              />
              <button
                type="submit"
                className="text-sm px-3 py-1.5 bg-[var(--tp-accent-muted)] border border-[var(--tp-accent-light)] text-[var(--tp-accent-light)] rounded hover:bg-[var(--tp-accent-light)] hover:text-[var(--tp-bg)] transition-colors"
              >
                {t('mcSearchBtn')}
              </button>
              {searchActive && (
                <button
                  type="button"
                  onClick={handleSearchClear}
                  className="text-sm px-3 py-1.5 border border-[var(--tp-border)] text-[var(--tp-text-2)] rounded hover:border-[var(--tp-text-2)] transition-colors"
                >
                  {t('mcSearchClear')}
                </button>
              )}
            </form>

            {/* Filters */}
            {schema && (
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-4">
                <div className="flex flex-col gap-1">
                  <label className="text-[10px] font-semibold uppercase tracking-wider text-[var(--tp-text-2)]">
                    {t('mcFilterManufacturer')}
                  </label>
                  <select
                    value={filterManufacturer}
                    onChange={e => setFilterManufacturer(e.target.value)}
                    className="text-sm bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded px-2 py-1.5 text-[var(--tp-text)] focus:outline-none focus:border-[var(--tp-accent-light)]"
                  >
                    <option value="">{selectLabel(t('mcFilterManufacturer'))}</option>
                    {schema.manufacturers.map(m => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                </div>

                <div className="flex flex-col gap-1">
                  <label className="text-[10px] font-semibold uppercase tracking-wider text-[var(--tp-text-2)]">
                    {t('mcFilterMachineType')}
                  </label>
                  <select
                    value={filterMachineType}
                    onChange={e => setFilterMachineType(e.target.value)}
                    className="text-sm bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded px-2 py-1.5 text-[var(--tp-text)] focus:outline-none focus:border-[var(--tp-accent-light)]"
                  >
                    <option value="">{selectLabel(t('mcFilterMachineType'))}</option>
                    {schema.machine_types.map(mt => (
                      <option key={mt} value={mt}>{mt}</option>
                    ))}
                  </select>
                </div>

                <div className="flex flex-col gap-1">
                  <label className="text-[10px] font-semibold uppercase tracking-wider text-[var(--tp-text-2)]">
                    {t('mcFilterProcess')}
                  </label>
                  <select
                    value={filterProcess}
                    onChange={e => setFilterProcess(e.target.value)}
                    className="text-sm bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded px-2 py-1.5 text-[var(--tp-text)] focus:outline-none focus:border-[var(--tp-accent-light)]"
                  >
                    <option value="">{selectLabel(t('mcFilterProcess'))}</option>
                    {schema.processes.map(p => (
                      <option key={p} value={p}>{p}</option>
                    ))}
                  </select>
                </div>

                <div className="flex flex-col gap-1">
                  <label className="text-[10px] font-semibold uppercase tracking-wider text-[var(--tp-text-2)]">
                    {t('mcFilterAxisCount')}
                  </label>
                  <select
                    value={filterAxis}
                    onChange={e => setFilterAxis(e.target.value)}
                    className="text-sm bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded px-2 py-1.5 text-[var(--tp-text)] focus:outline-none focus:border-[var(--tp-accent-light)]"
                  >
                    <option value="">{selectLabel(t('mcFilterAxisCount'))}</option>
                    {schema.axis_count_options.map(n => (
                      <option key={n} value={n}>{n}</option>
                    ))}
                  </select>
                </div>

                <div className="flex flex-col gap-1">
                  <label className="text-[10px] font-semibold uppercase tracking-wider text-[var(--tp-text-2)]">
                    {t('mcFilterSpindleInterface')}
                  </label>
                  <input
                    type="text"
                    value={filterSpindleInterface}
                    onChange={e => setFilterSpindleInterface(e.target.value)}
                    placeholder="e.g. HSK-A63"
                    className="text-sm bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded px-2 py-1.5 text-[var(--tp-text)] focus:outline-none focus:border-[var(--tp-accent-light)] placeholder:text-[var(--tp-text-3)]"
                  />
                </div>

                <div className="flex flex-col gap-1 justify-end">
                  <label className="flex items-center gap-2 cursor-pointer py-1.5">
                    <input
                      type="checkbox"
                      checked={filter5Axis}
                      onChange={e => setFilter5Axis(e.target.checked)}
                      className="accent-[var(--tp-accent-light)]"
                    />
                    <span className="text-sm text-[var(--tp-text-2)]">{t('mcFilter5Axis')}</span>
                  </label>
                </div>
              </div>
            )}

            {/* Compare strip */}
            {compareIds.length >= 2 && (
              <div className="bg-[var(--tp-surface)] border border-[var(--tp-accent-light)] rounded-lg p-3 mb-4 flex items-center justify-between gap-2">
                <div className="text-xs text-[var(--tp-text-2)]">
                  {t('mcCompareReady')}: <span className="font-semibold text-[var(--tp-text)]">{compareIds.length}</span> {t('mcMachinesSelected')}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setShowCompare(v => !v)}
                    className="text-xs px-3 py-1.5 bg-[var(--tp-accent-muted)] border border-[var(--tp-accent-light)] text-[var(--tp-accent-light)] rounded hover:bg-[var(--tp-accent-light)] hover:text-[var(--tp-bg)] transition-colors"
                  >
                    {showCompare ? t('mcCompareHide') : t('mcCompareShow')}
                  </button>
                  <button
                    onClick={() => { setCompareIds([]); setShowCompare(false) }}
                    className="text-xs px-3 py-1.5 border border-[var(--tp-border)] text-[var(--tp-text-2)] rounded hover:border-[var(--tp-text-2)] transition-colors"
                  >
                    {t('mcCompareClear')}
                  </button>
                </div>
              </div>
            )}

            {/* Compare table */}
            {showCompare && compareRecords.length >= 2 && (
              <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4 mb-4">
                <ComparePanel records={compareRecords} onClose={() => setShowCompare(false)} />
              </div>
            )}

            {/* Content */}
            {loading && (
              <div className="flex items-center gap-2 text-sm text-[var(--tp-text-2)] py-8">
                <span>{t('mcLoadingMachines')}</span>
              </div>
            )}

            {error && !loading && (
              <div className="bg-[var(--tp-warn-muted)] border border-[var(--tp-warn)] rounded-lg p-4 text-sm text-[var(--tp-warn)]">
                {error}
              </div>
            )}

            {!loading && !error && machines.length === 0 && (
              <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-6 text-center">
                <div className="text-sm font-medium text-[var(--tp-text)] mb-1">{t('mcNoMatch')}</div>
                <div className="text-xs text-[var(--tp-text-2)]">{t('mcNoMatchHint')}</div>
              </div>
            )}

            {!loading && !error && machines.length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {machines.map(m => (
                  <MachineCard
                    key={m.stable_id}
                    record={m}
                    onClick={() => handleSelectMachine(m.stable_id)}
                    missingVal={t('mcMissingValue')}
                    compareSelected={compareIds.includes(m.stable_id)}
                    onToggleCompare={handleToggleCompare}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
