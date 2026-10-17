import { useCallback, useEffect, useState } from 'react'
import { useLocale } from '../i18n/index'
import {
  fetchCuttingToolDetail,
  fetchCuttingTools,
  fetchCuttingToolSchema,
  type CuttingToolCatalogRecord,
  type CuttingToolSchema,
} from '../services/cuttingTools'

// ── Shared primitives ─────────────────────────────────────────────────────────

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
      <div className="text-[11px] text-[var(--tp-text-2)] uppercase tracking-wide truncate">{label}</div>
    </div>
  )
}

function OpBadge({ name }: { name: string }) {
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-[var(--tp-surface-3)] text-[var(--tp-text-2)] mr-1 mb-1">
      {name}
    </span>
  )
}

function IsoBadge({ group }: { group: string }) {
  const colorMap: Record<string, string> = {
    P: 'bg-blue-900/40 text-blue-300',
    M: 'bg-yellow-900/40 text-yellow-300',
    K: 'bg-red-900/40 text-red-300',
    N: 'bg-green-900/40 text-green-300',
    S: 'bg-orange-900/40 text-orange-300',
    H: 'bg-purple-900/40 text-purple-300',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold mr-1 mb-1 ${colorMap[group] ?? 'bg-[var(--tp-surface-3)] text-[var(--tp-text-2)]'}`}>
      ISO {group}
    </span>
  )
}

function MissingVal({ label }: { label: string }) {
  return <span className="text-[var(--tp-text-3)]">{label}</span>
}

// ── Detail panel ──────────────────────────────────────────────────────────────

function ToolDetail({
  record,
  onBack,
}: {
  record: CuttingToolCatalogRecord
  onBack: () => void
}) {
  const { t } = useLocale()
  const mv = t('ctMissingValue')

  function num(val: number | null, unit: string) {
    if (val === null) return <MissingVal label={mv} />
    return <>{val.toLocaleString()} {unit}</>
  }

  function str(val: string | null) {
    if (!val) return <MissingVal label={mv} />
    return <>{val}</>
  }

  function bool(val: boolean | null) {
    if (val === null) return <MissingVal label={mv} />
    return <>{val ? t('ctYes') : t('ctNo')}</>
  }

  const isInsert = record.tool_category_code === 'TURNING_INSERT'
  const isSolid = ['END_MILL', 'DRILL'].includes(record.tool_category_code)

  return (
    <div className="flex flex-col gap-4">
      <button
        onClick={onBack}
        className="self-start text-xs text-[var(--tp-accent-light)] hover:underline mb-1"
      >
        ← {t('ctBack')}
      </button>

      {/* Header */}
      <div>
        <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--tp-accent-light)] mb-1">
          {record.manufacturer}
        </div>
        <h2 className="text-xl font-semibold text-[var(--tp-text)]">{record.product_name}</h2>
        <div className="text-sm text-[var(--tp-text-2)] mt-0.5">{record.tool_category}</div>
        {record.tool_subcategory && (
          <div className="text-xs text-[var(--tp-text-3)]">{record.tool_subcategory}</div>
        )}
      </div>

      {/* Disclaimer */}
      <div className="bg-[var(--tp-warn-muted)] border border-[var(--tp-warn)] rounded-lg p-3 text-xs text-[var(--tp-warn)]">
        {t('ctCatalogBrowseOnly')}
      </div>

      {/* Identity */}
      <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4 flex flex-col gap-1">
        <SectionLabel>{t('ctIdentitySection')}</SectionLabel>
        <FieldRow label={t('ctManufacturer')} value={record.manufacturer} />
        {record.product_family && (
          <FieldRow label={t('ctProductFamily')} value={record.product_family} />
        )}
        {record.catalog_code && (
          <FieldRow label={t('ctCatalogCode')} value={<span className="font-mono text-xs">{record.catalog_code}</span>} />
        )}
        <FieldRow label={t('ctToolCategory')} value={record.tool_category} />
        {record.tool_subcategory && (
          <FieldRow label={t('ctToolSubcategory')} value={record.tool_subcategory} />
        )}
      </div>

      {/* Application */}
      <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4 flex flex-col gap-2">
        <SectionLabel>{t('ctApplicationSection')}</SectionLabel>
        <div>
          <div className="text-xs text-[var(--tp-text-2)] mb-1">{t('ctSupportedOperations')}</div>
          <div className="flex flex-wrap">
            {record.supported_operations.map(op => <OpBadge key={op} name={op} />)}
          </div>
        </div>
        <div>
          <div className="text-xs text-[var(--tp-text-2)] mb-1">{t('ctIsoMaterialGroups')}</div>
          <div className="flex flex-wrap">
            {record.iso_material_groups.map(g => <IsoBadge key={g} group={g} />)}
          </div>
        </div>
      </div>

      {/* Tool Material */}
      <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4 flex flex-col gap-1">
        <SectionLabel>{t('ctMaterialSection')}</SectionLabel>
        <FieldRow label={t('ctToolMaterial')} value={str(record.tool_material)} />
        <FieldRow label={t('ctCoating')} value={str(record.coating)} />
        <FieldRow label={t('ctCoatingType')} value={str(record.coating_type)} />
      </div>

      {/* Insert Geometry */}
      {isInsert && (
        <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4 flex flex-col gap-1">
          <SectionLabel>{t('ctInsertSection')}</SectionLabel>
          <FieldRow label={t('ctInsertShape')} value={str(record.insert_shape)} />
          <FieldRow label={t('ctInsertIcMm')} value={num(record.insert_ic_mm, t('ctUnitMm'))} />
          <FieldRow label={t('ctInsertThicknessMm')} value={num(record.insert_thickness_mm, t('ctUnitMm'))} />
          <FieldRow label={t('ctNoseRadiusMm')} value={num(record.nose_radius_mm, t('ctUnitMm'))} />
          <FieldRow label={t('ctClearanceAngleDeg')} value={num(record.clearance_angle_deg, t('ctUnitDeg'))} />
        </div>
      )}

      {/* Solid Tool Geometry */}
      {isSolid && (
        <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4 flex flex-col gap-1">
          <SectionLabel>{t('ctGeometrySection')}</SectionLabel>
          {record.cutting_diameter_mm !== null && (
            <FieldRow label={t('ctCuttingDiameterMm')} value={num(record.cutting_diameter_mm, t('ctUnitMm'))} />
          )}
          {record.shank_diameter_mm !== null && (
            <FieldRow label={t('ctShankDiameterMm')} value={num(record.shank_diameter_mm, t('ctUnitMm'))} />
          )}
          {record.overall_length_mm !== null && (
            <FieldRow label={t('ctOverallLengthMm')} value={num(record.overall_length_mm, t('ctUnitMm'))} />
          )}
          {record.cutting_length_mm !== null && (
            <FieldRow label={t('ctCuttingLengthMm')} value={num(record.cutting_length_mm, t('ctUnitMm'))} />
          )}
          {record.flute_length_mm !== null && (
            <FieldRow label={t('ctFluteLengthMm')} value={num(record.flute_length_mm, t('ctUnitMm'))} />
          )}
          {record.number_of_flutes !== null && (
            <FieldRow label={t('ctNumberOfFlutes')} value={`${record.number_of_flutes}`} />
          )}
          {record.helix_angle_deg !== null && (
            <FieldRow label={t('ctHelixAngleDeg')} value={num(record.helix_angle_deg, t('ctUnitDeg'))} />
          )}
          {record.corner_radius_mm !== null && (
            <FieldRow label={t('ctCornerRadiusMm')} value={num(record.corner_radius_mm, t('ctUnitMm'))} />
          )}
          {record.point_angle_deg !== null && (
            <FieldRow label={t('ctPointAngleDeg')} value={num(record.point_angle_deg, t('ctUnitDeg'))} />
          )}
        </div>
      )}

      {/* Machine Interface */}
      <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4 flex flex-col gap-1">
        <SectionLabel>{t('ctInterfaceSection')}</SectionLabel>
        <FieldRow label={t('ctShankInterface')} value={str(record.shank_interface)} />
        <FieldRow label={t('ctThroughCoolant')} value={bool(record.through_coolant)} />
        <FieldRow label={t('ctMaxRpm')} value={num(record.max_rpm, t('ctUnitRpm'))} />
        {record.compatible_holder_interface && (
          <FieldRow label={t('ctCompatibleHolder')} value={record.compatible_holder_interface} />
        )}
      </div>

      {/* Cutting Guidance */}
      <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4 flex flex-col gap-2">
        <SectionLabel>{t('ctGuidanceSection')}</SectionLabel>
        <p className="text-xs text-[var(--tp-text-2)]">{t('ctGuidanceNotProvided')}</p>
      </div>

      {/* Source */}
      <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4 flex flex-col gap-2">
        <SectionLabel>{t('ctSourceSection')}</SectionLabel>
        <div className="text-xs text-[var(--tp-text-2)]">
          <span className="font-medium text-[var(--tp-text)]">{t('ctEvidenceLabel')}: </span>
          {record.evidence_status}
        </div>
        <div className="text-xs text-[var(--tp-text-2)]">
          <span className="font-medium text-[var(--tp-text)]">{t('ctSourceTitle')}: </span>
          {record.source_title}
        </div>
        {record.source_note && (
          <div className="text-[11px] text-[var(--tp-text-3)] mt-1">{record.source_note}</div>
        )}
        {record.missing_fields.length > 0 && (
          <div className="mt-2">
            <div className="text-xs text-[var(--tp-text-2)] mb-1">{t('ctMissingFields')}</div>
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

// ── Tool list card ─────────────────────────────────────────────────────────────

function ToolCard({
  record,
  onClick,
}: {
  record: CuttingToolCatalogRecord
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4 hover:border-[var(--tp-accent-light)] transition-colors flex flex-col gap-2"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--tp-accent-light)]">
            {record.manufacturer}
          </div>
          <div className="text-base font-semibold text-[var(--tp-text)] truncate">{record.product_name}</div>
          <div className="text-xs text-[var(--tp-text-2)]">{record.tool_category}</div>
        </div>
        <div className="flex-shrink-0 text-right">
          {record.tool_material && (
            <div className="text-xs font-mono text-[var(--tp-text)]">{record.tool_material}</div>
          )}
          {record.cutting_diameter_mm && (
            <div className="text-xs text-[var(--tp-text-3)]">Ø{record.cutting_diameter_mm} mm</div>
          )}
          {record.insert_ic_mm && !record.cutting_diameter_mm && (
            <div className="text-xs text-[var(--tp-text-3)]">IC {record.insert_ic_mm} mm</div>
          )}
        </div>
      </div>
      <div className="flex flex-wrap gap-1">
        {record.iso_material_groups.slice(0, 5).map(g => (
          <IsoBadge key={g} group={g} />
        ))}
      </div>
    </button>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function CuttingToolCatalogPage() {
  const { t } = useLocale()

  const [schema, setSchema] = useState<CuttingToolSchema | null>(null)
  const [tools, setTools] = useState<CuttingToolCatalogRecord[]>([])
  const [selectedTool, setSelectedTool] = useState<CuttingToolCatalogRecord | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [filterManufacturer, setFilterManufacturer] = useState('')
  const [filterCategory, setFilterCategory] = useState('')
  const [filterOperation, setFilterOperation] = useState('')
  const [filterToolMaterial, setFilterToolMaterial] = useState('')
  const [filterIsoGroup, setFilterIsoGroup] = useState('')

  useEffect(() => {
    fetchCuttingToolSchema()
      .then(setSchema)
      .catch(() => setError(t('ctBackendError')))
  }, [])

  const loadTools = useCallback(async () => {
    setLoading(true)
    setError(null)
    setSelectedTool(null)
    try {
      const params: Record<string, string> = {}
      if (filterManufacturer) params.manufacturer = filterManufacturer
      if (filterCategory) params.category = filterCategory
      if (filterOperation) params.operation = filterOperation
      if (filterToolMaterial) params.tool_material = filterToolMaterial
      if (filterIsoGroup) params.iso_group = filterIsoGroup
      const list = await fetchCuttingTools(params)
      setTools(list)
    } catch {
      setError(t('ctBackendError'))
    } finally {
      setLoading(false)
    }
  }, [filterManufacturer, filterCategory, filterOperation, filterToolMaterial, filterIsoGroup])

  useEffect(() => { loadTools() }, [loadTools])

  const handleSelectTool = useCallback(async (id: string) => {
    try {
      const detail = await fetchCuttingToolDetail(id)
      setSelectedTool(detail)
    } catch {
      const found = tools.find(t => t.stable_id === id) ?? null
      setSelectedTool(found)
    }
  }, [tools])

  const selectLabel = (label: string) => `${t('ctFilterAll')} — ${label}`

  return (
    <div className="h-full overflow-y-auto p-4 sm:p-6">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="mb-5">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--tp-accent-light)] mb-2">
            MachiningPro AI
          </div>
          <h1 className="text-xl font-semibold text-[var(--tp-text)] mb-1">{t('ctPageTitle')}</h1>
          <p className="text-sm text-[var(--tp-text-2)]">{t('ctPageSubtitle')}</p>
        </div>

        {/* Summary cards */}
        {schema && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
            <StatCard label={t('ctToolCount')} value={schema.tool_count} />
            <StatCard label={t('ctManufacturerCount')} value={schema.manufacturers.length} />
            <StatCard label={t('ctCategoryCount')} value={schema.categories.length} />
            <StatCard label={t('ctEvidenceLabel')} value={t('ctEvidenceStatus')} />
          </div>
        )}

        {/* Disclaimer */}
        <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-3 text-xs text-[var(--tp-text-2)] mb-5">
          <span className="font-semibold text-[var(--tp-text)]">{t('ctProductionNotValidated')}. </span>
          {t('ctCatalogBrowseOnly')}
        </div>

        {selectedTool ? (
          <ToolDetail record={selectedTool} onBack={() => setSelectedTool(null)} />
        ) : (
          <>
            {/* Filters */}
            {schema && (
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-4">
                {[
                  { label: t('ctFilterManufacturer'), value: filterManufacturer, set: setFilterManufacturer, options: schema.manufacturers },
                  { label: t('ctFilterCategory'), value: filterCategory, set: setFilterCategory, options: schema.categories },
                  { label: t('ctFilterOperation'), value: filterOperation, set: setFilterOperation, options: schema.operations },
                  { label: t('ctFilterToolMaterial'), value: filterToolMaterial, set: setFilterToolMaterial, options: schema.tool_materials },
                  { label: t('ctFilterIsoGroup'), value: filterIsoGroup, set: setFilterIsoGroup, options: schema.iso_material_groups },
                ].map(({ label, value, set, options }) => (
                  <div key={label} className="flex flex-col gap-1">
                    <label className="text-[10px] font-semibold uppercase tracking-wider text-[var(--tp-text-2)]">
                      {label}
                    </label>
                    <select
                      value={value}
                      onChange={e => set(e.target.value)}
                      className="text-sm bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded px-2 py-1.5 text-[var(--tp-text)] focus:outline-none focus:border-[var(--tp-accent-light)]"
                    >
                      <option value="">{selectLabel(label)}</option>
                      {options.map(o => <option key={o} value={o}>{o}</option>)}
                    </select>
                  </div>
                ))}
              </div>
            )}

            {loading && (
              <div className="flex items-center gap-2 text-sm text-[var(--tp-text-2)] py-8">
                <span>{t('ctLoadingTools')}</span>
              </div>
            )}

            {error && !loading && (
              <div className="bg-[var(--tp-warn-muted)] border border-[var(--tp-warn)] rounded-lg p-4 text-sm text-[var(--tp-warn)]">
                {error}
              </div>
            )}

            {!loading && !error && tools.length === 0 && (
              <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-6 text-center">
                <div className="text-sm font-medium text-[var(--tp-text)] mb-1">{t('ctNoMatch')}</div>
                <div className="text-xs text-[var(--tp-text-2)]">{t('ctNoMatchHint')}</div>
              </div>
            )}

            {!loading && !error && tools.length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {tools.map(tool => (
                  <ToolCard
                    key={tool.stable_id}
                    record={tool}
                    onClick={() => handleSelectTool(tool.stable_id)}
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
