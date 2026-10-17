import { useState, useEffect } from 'react'
import { useLocale } from '../i18n'
import {
  fetchToolHolderSchema,
  fetchToolHolders,
  fetchToolHolderDetail,
  type ToolHolderCatalogRecord,
  type ToolHolderSchema,
} from '../services/toolHolders'

// ── Interface badge colours ────────────────────────────────────────────────────
const INTERFACE_COLORS: Record<string, string> = {
  'CAT-40': 'bg-blue-500/15 text-blue-300 border border-blue-500/30',
  'HSK-A63': 'bg-purple-500/15 text-purple-300 border border-purple-500/30',
  'SK40': 'bg-amber-500/15 text-amber-300 border border-amber-500/30',
  'BMT65': 'bg-rose-500/15 text-rose-300 border border-rose-500/30',
}

function InterfaceBadge({ label }: { label: string }) {
  const cls = INTERFACE_COLORS[label] ?? 'bg-tp-surface-2 text-tp-text-2 border border-tp-border'
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide ${cls}`}>
      {label}
    </span>
  )
}

// ── Category badge ─────────────────────────────────────────────────────────────
function CategoryBadge({ label }: { label: string }) {
  const display = label.replace(/_/g, ' ')
  return (
    <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-tp-surface-2 text-tp-text-2 border border-tp-border">
      {display}
    </span>
  )
}

// ── Field row ──────────────────────────────────────────────────────────────────
function FieldRow({ label, value, unit }: { label: string; value: React.ReactNode; unit?: string }) {
  return (
    <div className="flex items-start gap-2 text-sm">
      <span className="text-tp-text-3 shrink-0 w-40">{label}</span>
      <span className="text-tp-text font-medium">
        {value}{unit ? <span className="text-tp-text-3 font-normal ml-1">{unit}</span> : null}
      </span>
    </div>
  )
}

// ── Detail view ────────────────────────────────────────────────────────────────
function HolderDetail({
  holder,
  onBack,
}: {
  holder: ToolHolderCatalogRecord
  onBack: () => void
}) {
  const { t } = useLocale()
  const mv = t('thMissingValue')

  const fmt = (v: number | null, unit: string) =>
    v != null ? <>{v} <span className="text-tp-text-3 font-normal">{unit}</span></> : <>{mv}</>

  const fmtStr = (v: string | null) => v ?? mv
  const fmtBool = (v: boolean | null) => v == null ? mv : (v ? t('thYes') : t('thNo'))

  const isRotating = !['EXTERNAL_TURNING_HOLDER', 'BORING_BAR_HOLDER'].includes(holder.holder_category)
  const hasCollet = holder.collet_system != null
  const hasClamping = holder.clamping_range_min_mm != null || holder.clamping_range_max_mm != null

  const clampRange = () => {
    if (holder.clamping_range_min_mm == null && holder.clamping_range_max_mm == null) return mv
    if (holder.clamping_range_min_mm === holder.clamping_range_max_mm) {
      return <>{holder.clamping_range_min_mm} <span className="text-tp-text-3 font-normal">{t('thUnitMm')}</span></>
    }
    return (
      <>{holder.clamping_range_min_mm ?? '?'} – {holder.clamping_range_max_mm ?? '?'}{' '}
        <span className="text-tp-text-3 font-normal">{t('thUnitMm')}</span>
      </>
    )
  }

  const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
    <div className="bg-tp-surface border border-tp-border rounded-lg p-4 space-y-2">
      <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light mb-3">{title}</div>
      {children}
    </div>
  )

  return (
    <div className="space-y-4">
      <button
        onClick={onBack}
        className="text-sm text-tp-accent-light hover:text-tp-accent transition-colors"
      >
        ← {t('thBack')}
      </button>

      {/* Header */}
      <div className="bg-tp-surface border border-tp-border rounded-lg p-4">
        <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-text-3 mb-1">
          {holder.manufacturer}
        </div>
        <h2 className="text-lg font-semibold text-tp-text mb-1">{holder.product_name}</h2>
        <div className="flex flex-wrap gap-2">
          <CategoryBadge label={holder.holder_category} />
          <InterfaceBadge label={holder.machine_interface} />
          {holder.holder_subcategory && (
            <span className="text-sm text-tp-text-2">{holder.holder_subcategory}</span>
          )}
        </div>
      </div>

      <div className="text-xs text-tp-text-3 bg-tp-surface border border-tp-border rounded px-3 py-2">
        {t('thProductionNotValidated')}
      </div>

      {/* Identity */}
      <Section title={t('thIdentitySection')}>
        <FieldRow label={t('thManufacturer')} value={holder.manufacturer} />
        {holder.product_family && <FieldRow label={t('thProductFamily')} value={holder.product_family} />}
        {holder.catalog_code && <FieldRow label={t('thCatalogCode')} value={holder.catalog_code} />}
        <FieldRow label={t('thHolderCategory')} value={<CategoryBadge label={holder.holder_category} />} />
        {holder.holder_subcategory && (
          <FieldRow label={t('thHolderSubcategory')} value={holder.holder_subcategory} />
        )}
      </Section>

      {/* Machine Interface */}
      <Section title={t('thMachineInterfaceSection')}>
        <FieldRow label={t('thMachineInterface')} value={<InterfaceBadge label={holder.machine_interface} />} />
        {holder.taper && <FieldRow label={t('thTaper')} value={holder.taper} />}
      </Section>

      {/* Tool Interface */}
      <Section title={t('thToolInterfaceSection')}>
        <FieldRow label={t('thToolInterface')} value={holder.tool_interface} />
        {hasCollet && <FieldRow label={t('thColletSystem')} value={fmtStr(holder.collet_system)} />}
        {hasClamping && <FieldRow label={t('thClampingRange')} value={clampRange()} />}
        {holder.compatible_shank_types.length > 0 && (
          <FieldRow
            label={t('thCompatibleShanks')}
            value={<span className="text-tp-text-2">{holder.compatible_shank_types.join(', ')}</span>}
          />
        )}
      </Section>

      {/* Geometry */}
      <Section title={t('thGeometrySection')}>
        {holder.gauge_length_mm != null && (
          <FieldRow label={t('thGaugeLengthMm')} value={fmt(holder.gauge_length_mm, t('thUnitMm'))} />
        )}
        {holder.body_diameter_mm != null && (
          <FieldRow label={t('thBodyDiameterMm')} value={fmt(holder.body_diameter_mm, t('thUnitMm'))} />
        )}
        {holder.nose_diameter_mm != null && (
          <FieldRow label={t('thNoseDiameterMm')} value={fmt(holder.nose_diameter_mm, t('thUnitMm'))} />
        )}
        {holder.overall_length_mm != null && (
          <FieldRow label={t('thOverallLengthMm')} value={fmt(holder.overall_length_mm, t('thUnitMm'))} />
        )}
        {holder.weight_kg != null && (
          <FieldRow label={t('thWeightKg')} value={fmt(holder.weight_kg, t('thUnitKg'))} />
        )}
        {holder.gauge_length_mm == null && holder.body_diameter_mm == null &&
         holder.nose_diameter_mm == null && holder.overall_length_mm == null && (
          <div className="text-sm text-tp-text-3">{mv}</div>
        )}
      </Section>

      {/* Performance — only for rotating holders */}
      {isRotating && (
        <Section title={t('thPerformanceSection')}>
          {holder.max_rpm != null && (
            <FieldRow label={t('thMaxRpm')} value={fmt(holder.max_rpm, t('thUnitRpm'))} />
          )}
          {holder.balance_grade && (
            <FieldRow label={t('thBalanceGrade')} value={holder.balance_grade} />
          )}
          {holder.runout_um != null && (
            <FieldRow label={t('thRunoutUm')} value={fmt(holder.runout_um, t('thUnitUm'))} />
          )}
          {holder.max_rpm == null && !holder.balance_grade && holder.runout_um == null && (
            <div className="text-sm text-tp-text-3">{mv}</div>
          )}
        </Section>
      )}

      {/* Coolant */}
      <Section title={t('thCoolantSection')}>
        <FieldRow label={t('thThroughCoolant')} value={fmtBool(holder.through_coolant)} />
        {holder.coolant_pressure_bar != null && (
          <FieldRow label={t('thCoolantPressureBar')} value={fmt(holder.coolant_pressure_bar, t('thUnitBar'))} />
        )}
      </Section>

      {/* Application */}
      <Section title={t('thApplicationSection')}>
        {holder.supported_processes.length > 0 && (
          <FieldRow
            label={t('thSupportedProcesses')}
            value={<span className="capitalize">{holder.supported_processes.join(', ')}</span>}
          />
        )}
        {holder.holder_notes && (
          <div className="text-sm text-tp-text-2 leading-relaxed pt-1 border-t border-tp-border mt-2">
            {holder.holder_notes}
          </div>
        )}
      </Section>

      {/* Compatibility Foundation */}
      <Section title={t('thCompatSection')}>
        {holder.compatible_collet_family && (
          <FieldRow label={t('thCompatColletFamily')} value={holder.compatible_collet_family} />
        )}
        {holder.compatible_tool_shank_family && (
          <FieldRow label={t('thCompatToolShankFamily')} value={holder.compatible_tool_shank_family} />
        )}
        <div className="text-xs text-tp-text-3 border-t border-tp-border pt-2 mt-2">
          {t('thCompatInterfaceNote')}
        </div>
      </Section>

      {/* Provenance */}
      <Section title={t('thSourceSection')}>
        <div className="space-y-1">
          <div className="flex gap-2 text-sm">
            <span className="text-tp-text-3">{t('thEvidenceLabel')}:</span>
            <span className="text-tp-text font-medium">{holder.evidence_status}</span>
          </div>
          <div className="flex gap-2 text-sm">
            <span className="text-tp-text-3">{t('thSourceTitle')}:</span>
            <span className="text-tp-text-2">{holder.source_title}</span>
          </div>
        </div>
        {holder.source_note && (
          <div className="text-xs text-tp-text-3 leading-relaxed mt-2">{holder.source_note}</div>
        )}
        {holder.missing_fields.length > 0 && (
          <div className="mt-3 border-t border-tp-border pt-3">
            <div className="text-xs font-medium text-tp-text-2 mb-2">{t('thMissingFields')}</div>
            <div className="flex flex-wrap gap-1.5">
              {holder.missing_fields.map(f => (
                <span key={f} className="text-[10px] bg-tp-surface-2 text-tp-text-3 border border-tp-border rounded px-1.5 py-0.5 font-mono">
                  {f}
                </span>
              ))}
            </div>
          </div>
        )}
      </Section>
    </div>
  )
}

// ── Card for list view ─────────────────────────────────────────────────────────
function HolderCard({
  holder,
  onClick,
}: {
  holder: ToolHolderCatalogRecord
  onClick: () => void
}) {
  const clampInfo = () => {
    if (holder.clamping_range_min_mm != null && holder.clamping_range_max_mm != null) {
      if (holder.clamping_range_min_mm === holder.clamping_range_max_mm) {
        return `Ø${holder.clamping_range_min_mm} mm`
      }
      return `Ø${holder.clamping_range_min_mm}–${holder.clamping_range_max_mm} mm`
    }
    return null
  }

  return (
    <button
      onClick={onClick}
      className="w-full text-left bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4
                 hover:border-[var(--tp-accent-light)] transition-colors flex flex-col gap-2"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-[11px] text-tp-text-3 uppercase tracking-wide mb-0.5">{holder.manufacturer}</div>
          <div className="text-sm font-medium text-tp-text leading-snug truncate">{holder.product_name}</div>
          <div className="text-xs text-tp-text-2 mt-0.5">{holder.holder_category.replace(/_/g, ' ')}</div>
        </div>
        <div className="shrink-0 text-right space-y-1">
          <div>{clampInfo() && <span className="text-xs text-tp-text-2">{clampInfo()}</span>}</div>
        </div>
      </div>
      <div className="flex flex-wrap gap-1.5">
        <InterfaceBadge label={holder.machine_interface} />
        {holder.collet_system && (
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-tp-surface-2 text-tp-text-2 border border-tp-border">
            {holder.collet_system}
          </span>
        )}
      </div>
    </button>
  )
}

// ── Summary card ───────────────────────────────────────────────────────────────
function StatCard({ value, label }: { value: string | number; label: string }) {
  return (
    <div className="bg-tp-surface border border-tp-border rounded-lg px-4 py-3 flex flex-col gap-0.5">
      <div className="text-xl font-bold text-tp-text">{value}</div>
      <div className="text-xs text-tp-text-3 uppercase tracking-wide">{label}</div>
    </div>
  )
}

// ── Filter select ──────────────────────────────────────────────────────────────
function FilterSelect({
  label,
  value,
  options,
  allLabel,
  onChange,
}: {
  label: string
  value: string
  options: string[]
  allLabel: string
  onChange: (v: string) => void
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[10px] font-semibold uppercase tracking-widest text-tp-text-3">{label}</label>
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        className="bg-tp-surface border border-tp-border rounded px-2 py-1.5 text-sm text-tp-text
                   focus:outline-none focus:border-tp-accent-light w-full"
      >
        <option value="">{allLabel} — {label}</option>
        {options.map(o => (
          <option key={o} value={o}>{o.replace(/_/g, ' ')}</option>
        ))}
      </select>
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────────
export default function ToolHolderCatalogPage() {
  const { t } = useLocale()

  const [schema, setSchema] = useState<ToolHolderSchema | null>(null)
  const [holders, setHolders] = useState<ToolHolderCatalogRecord[]>([])
  const [selected, setSelected] = useState<ToolHolderCatalogRecord | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  const [filterMfr, setFilterMfr] = useState('')
  const [filterCat, setFilterCat] = useState('')
  const [filterMI, setFilterMI] = useState('')
  const [filterTI, setFilterTI] = useState('')

  useEffect(() => {
    fetchToolHolderSchema()
      .then(s => setSchema(s))
      .catch(() => setError(true))
  }, [])

  useEffect(() => {
    if (!schema) return
    setLoading(true)
    fetchToolHolders({
      manufacturer: filterMfr || undefined,
      category: filterCat || undefined,
      machine_interface: filterMI || undefined,
      tool_interface: filterTI || undefined,
    })
      .then(data => { setHolders(data); setLoading(false) })
      .catch(() => { setError(true); setLoading(false) })
  }, [schema, filterMfr, filterCat, filterMI, filterTI])

  const handleSelect = (h: ToolHolderCatalogRecord) => {
    fetchToolHolderDetail(h.stable_id)
      .then(detail => setSelected(detail))
      .catch(() => {})
  }

  const handleBack = () => setSelected(null)

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-5xl space-y-6">

        {/* Page header */}
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-widest text-tp-accent-light mb-2">
            MachiningPro AI
          </div>
          <h1 className="text-xl font-semibold text-tp-text mb-1">{t('thPageTitle')}</h1>
          <p className="text-sm text-tp-text-2">{t('thPageSubtitle')}</p>
        </div>

        {/* Summary cards */}
        {schema && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatCard value={schema.holder_count} label={t('thHolderCount')} />
            <StatCard value={schema.manufacturers.length} label={t('thManufacturerCount')} />
            <StatCard value={schema.categories.length} label={t('thCategoryCount')} />
            <StatCard value={t('thEvidenceStatus')} label="Evidence" />
          </div>
        )}

        {/* Disclaimer */}
        <div className="bg-tp-surface border border-tp-border rounded-lg px-4 py-3">
          <div className="text-xs font-semibold text-tp-text mb-0.5">{t('thCatalogBrowseOnly')}</div>
          <div className="text-xs text-tp-text-2">{t('thProductionNotValidated')}</div>
        </div>

        {/* Detail or list */}
        {selected ? (
          <HolderDetail holder={selected} onBack={handleBack} />
        ) : (
          <>
            {/* Filters */}
            {schema && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <FilterSelect
                  label={t('thFilterManufacturer')}
                  value={filterMfr}
                  options={schema.manufacturers}
                  allLabel={t('thFilterAll')}
                  onChange={setFilterMfr}
                />
                <FilterSelect
                  label={t('thFilterCategory')}
                  value={filterCat}
                  options={schema.categories}
                  allLabel={t('thFilterAll')}
                  onChange={setFilterCat}
                />
                <FilterSelect
                  label={t('thFilterMachineInterface')}
                  value={filterMI}
                  options={schema.machine_interfaces}
                  allLabel={t('thFilterAll')}
                  onChange={setFilterMI}
                />
                <FilterSelect
                  label={t('thFilterToolInterface')}
                  value={filterTI}
                  options={schema.tool_interfaces}
                  allLabel={t('thFilterAll')}
                  onChange={setFilterTI}
                />
              </div>
            )}

            {/* Results */}
            {error && (
              <div className="text-sm text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-4 py-3">
                {t('thBackendError')}
              </div>
            )}
            {loading && !error && (
              <div className="text-sm text-tp-text-2">{t('thLoadingHolders')}</div>
            )}
            {!loading && !error && holders.length === 0 && (
              <div className="text-center py-12 space-y-2">
                <div className="text-sm font-medium text-tp-text">{t('thNoMatch')}</div>
                <div className="text-xs text-tp-text-3">{t('thNoMatchHint')}</div>
              </div>
            )}
            {!loading && !error && holders.length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {holders.map(h => (
                  <HolderCard key={h.stable_id} holder={h} onClick={() => handleSelect(h)} />
                ))}
              </div>
            )}
          </>
        )}

      </div>
    </div>
  )
}
