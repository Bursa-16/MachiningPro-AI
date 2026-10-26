import { useEffect, useState, useCallback } from 'react'
import { useLocale } from '../i18n/index'
import {
  fetchMaterials,
  fetchMaterialDetail,
  fetchMaterialIsoGroups,
  type MaterialListItem,
  type IsoGroupInfo,
} from '../services/materials'
import type { MaterialDetail, MaterialConditionRecord, MaterialToolCompatEntry } from '../types/materials'

// ── Shared small components ───────────────────────────────────────────────────

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

// ── ISO group badge colors ────────────────────────────────────────────────────

const ISO_COLORS: Record<string, string> = {
  P: 'bg-blue-900/40 text-blue-300 border-blue-700/40',
  M: 'bg-purple-900/40 text-purple-300 border-purple-700/40',
  K: 'bg-green-900/40 text-green-300 border-green-700/40',
  N: 'bg-orange-900/40 text-orange-300 border-orange-700/40',
  S: 'bg-red-900/40 text-red-300 border-red-700/40',
  H: 'bg-gray-700/40 text-gray-300 border-gray-600/40',
}

function IsoBadge({ group }: { group: string }) {
  const color = ISO_COLORS[group] ?? 'bg-[var(--tp-surface)] text-[var(--tp-text-2)] border-[var(--tp-border)]'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold border ${color}`}>
      {group}
    </span>
  )
}

// ── Confidence badge ──────────────────────────────────────────────────────────

const CONF_COLORS: Record<string, string> = {
  VERIFIED_STANDARD: 'bg-green-900/30 text-green-300 border-green-700/30',
  MANUFACTURER_REFERENCE: 'bg-blue-900/30 text-blue-300 border-blue-700/30',
  REFERENCE_ONLY: 'bg-amber-900/30 text-amber-300 border-amber-700/30',
  GENERAL_INDUSTRY: 'bg-amber-900/30 text-amber-300 border-amber-700/30',
  ESTIMATED: 'bg-orange-900/30 text-orange-300 border-orange-700/30',
  UNKNOWN: 'bg-red-900/30 text-red-300 border-red-700/30',
}

function ConfBadge({ confidence, label }: { confidence: string; label?: string }) {
  const color = CONF_COLORS[confidence] ?? CONF_COLORS['UNKNOWN']
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-semibold uppercase tracking-wider border ${color}`}>
      {label ?? confidence.replace(/_/g, ' ')}
    </span>
  )
}

// ── Tool compat badge ─────────────────────────────────────────────────────────

const COMPAT_COLORS: Record<string, string> = {
  RECOMMENDED: 'text-green-400',
  ACCEPTABLE: 'text-blue-400',
  CONDITIONAL: 'text-amber-400',
  NOT_RECOMMENDED: 'text-red-400',
  INSUFFICIENT_DATA: 'text-[var(--tp-text-3)]',
}

const COMPAT_SYMBOLS: Record<string, string> = {
  RECOMMENDED: '◎',
  ACCEPTABLE: '○',
  CONDITIONAL: '△',
  NOT_RECOMMENDED: '×',
  INSUFFICIENT_DATA: '?',
}

function CompatRow({ entry }: { entry: MaterialToolCompatEntry }) {
  const color = COMPAT_COLORS[entry.rating] ?? 'text-[var(--tp-text-2)]'
  const sym = COMPAT_SYMBOLS[entry.rating] ?? '?'
  return (
    <div className="flex items-start gap-2 py-1 border-b border-[var(--tp-border)] last:border-0">
      <span className={`font-bold text-sm w-5 shrink-0 ${color}`}>{sym}</span>
      <div className="flex-1 min-w-0">
        <span className="text-xs font-medium text-[var(--tp-text)]">{entry.tool_material}</span>
        {entry.condition_notes && (
          <div className="text-[10px] text-[var(--tp-text-2)] mt-0.5">{entry.condition_notes}</div>
        )}
      </div>
      <span className={`text-[10px] font-semibold shrink-0 ${color}`}>{entry.rating.replace(/_/g, ' ')}</span>
    </div>
  )
}

// ── Condition card ────────────────────────────────────────────────────────────

function ConditionCard({ cond }: { cond: MaterialConditionRecord }) {
  return (
    <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-3 mb-2">
      <div className="text-xs font-semibold text-[var(--tp-text)] mb-2">{cond.condition_label}</div>
      {cond.hardness.map((h, i) => (
        <div key={i} className="text-xs text-[var(--tp-text-2)]">
          {h.scale}: {h.value_min}–{h.value_max} {h.scale}
        </div>
      ))}
      {cond.tensile_strength_mpa !== null && (
        <div className="text-xs text-[var(--tp-text-2)]">Rm: {cond.tensile_strength_mpa} MPa</div>
      )}
      {cond.yield_strength_mpa !== null && (
        <div className="text-xs text-[var(--tp-text-2)]">Rp0.2: {cond.yield_strength_mpa} MPa</div>
      )}
      {cond.elongation_pct !== null && (
        <div className="text-xs text-[var(--tp-text-2)]">A: {cond.elongation_pct}%</div>
      )}
      <div className="mt-1">
        <ConfBadge confidence={cond.confidence} />
      </div>
    </div>
  )
}

// ── Detail panel ──────────────────────────────────────────────────────────────

function MaterialDetailPanel({
  detail,
  onBack,
}: {
  detail: MaterialDetail
  onBack: () => void
}) {
  const { t } = useLocale()
  const rec = detail.record

  return (
    <div className="flex flex-col gap-4">
      <button
        onClick={onBack}
        className="self-start text-xs text-[var(--tp-accent-light)] hover:underline mb-1"
      >
        ← {t('mcBack')}
      </button>

      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <IsoBadge group={rec.iso_group} />
          <span className="text-[10px] text-[var(--tp-text-2)]">{detail.iso_group_label}</span>
        </div>
        <h2 className="text-xl font-semibold text-[var(--tp-text)]">{rec.designation}</h2>
        <div className="text-sm text-[var(--tp-text-2)]">{detail.family_label}</div>
        {rec.werkstoff_nr && (
          <div className="text-xs text-[var(--tp-text-3)] font-mono">{rec.werkstoff_nr}</div>
        )}
        <div className="mt-1 flex flex-wrap gap-1">
          <ConfBadge confidence={rec.data_confidence} />
          <ConfBadge confidence="REFERENCE_ONLY" label={t('matBadgeRefOnly')} />
        </div>
      </div>

      {/* Identity */}
      <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4">
        <SectionLabel>{t('matSectionIdentity')}</SectionLabel>
        {rec.werkstoff_nr && <FieldRow label={t('matColWorkstoff')} value={<span className="font-mono">{rec.werkstoff_nr}</span>} />}
        {rec.standard_en && <FieldRow label="EN" value={rec.standard_en} />}
        {rec.standard_din && <FieldRow label="DIN" value={rec.standard_din} />}
        {rec.standard_aisi && <FieldRow label={t('matColAISI')} value={rec.standard_aisi} />}
        {rec.standard_uns && <FieldRow label="UNS" value={rec.standard_uns} />}
        {rec.aliases.length > 0 && (
          <FieldRow label={t('matAliasesLabel')} value={rec.aliases.join(', ')} />
        )}
        {rec.density_kg_m3 !== null && (
          <FieldRow label={t('matDensityLabel')} value={`${rec.density_kg_m3} kg/m³`} />
        )}
        {rec.notes && (
          <div className="mt-2 text-xs text-[var(--tp-text-2)] bg-[var(--tp-bg)] rounded p-2 border border-[var(--tp-border)]">{rec.notes}</div>
        )}
        {rec.source_document && (
          <div className="mt-2 text-[10px] text-[var(--tp-text-3)]">Source: {rec.source_document}</div>
        )}
      </div>

      {/* Conditions */}
      {rec.conditions.length > 0 && (
        <div>
          <SectionLabel>{t('matSectionConditions')}</SectionLabel>
          {rec.conditions.map((c, i) => <ConditionCard key={i} cond={c} />)}
        </div>
      )}

      {/* Machinability */}
      {rec.machinability && (
        <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4">
          <SectionLabel>{t('matSectionMachinability')}</SectionLabel>
          {rec.machinability.chip_formation && (
            <FieldRow label={t('matChipFormation')} value={rec.machinability.chip_formation} />
          )}
          {rec.machinability.work_hardening && (
            <FieldRow label={t('matWorkHardening')} value={rec.machinability.work_hardening} />
          )}
          {rec.machinability.bue_tendency && (
            <FieldRow label={t('matBUETendency')} value={rec.machinability.bue_tendency} />
          )}
          {rec.machinability.abrasiveness && (
            <FieldRow label={t('matAbrasiveness')} value={rec.machinability.abrasiveness} />
          )}
          {rec.machinability.thermal_load && (
            <FieldRow label={t('matThermalBehavior')} value={rec.machinability.thermal_load} />
          )}
          {rec.machinability.cutting_force && (
            <FieldRow label={t('matCuttingForce')} value={rec.machinability.cutting_force} />
          )}
          {rec.machinability.coolant_guidance && (
            <div className="mt-2 text-xs text-[var(--tp-text-2)] bg-[var(--tp-bg)] rounded p-2 border border-[var(--tp-border)]">
              <span className="font-semibold text-[var(--tp-text)]">{t('matCoolantGuidance')}: </span>
              {rec.machinability.coolant_guidance}
            </div>
          )}
          {rec.machinability.notes && (
            <div className="mt-1 text-xs text-[var(--tp-text-2)] italic">{rec.machinability.notes}</div>
          )}
          <div className="mt-2">
            <ConfBadge confidence="REFERENCE_ONLY" label={t('matBadgeRefOnly')} />
          </div>
        </div>
      )}

      {/* Tool Compatibility */}
      {rec.tool_compatibility.length > 0 && (
        <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4">
          <SectionLabel>{t('matSectionToolCompat')}</SectionLabel>
          {rec.tool_compatibility.map((tc, i) => <CompatRow key={i} entry={tc} />)}
          <div className="mt-2">
            <ConfBadge confidence="REFERENCE_ONLY" label={t('matBadgeRefOnly')} />
          </div>
        </div>
      )}

      {/* Cutting Context */}
      {rec.cutting_references.length > 0 && (
        <div className="bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4">
          <SectionLabel>{t('matSectionCuttingContext')}</SectionLabel>
          <div className="bg-[var(--tp-warn-muted)] border border-[var(--tp-warn)] rounded p-2 text-xs text-[var(--tp-warn)] mb-3">
            {t('matCuttingContextNote')}
          </div>
          {rec.cutting_references.map((cr, i) => (
            <div key={i} className="mb-3 last:mb-0 border-b border-[var(--tp-border)] last:border-0 pb-2 last:pb-0">
              <div className="text-xs font-semibold text-[var(--tp-text)] mb-1 capitalize">
                {cr.operation} / {cr.tool_material}
              </div>
              {cr.vc_min_m_min !== null && cr.vc_max_m_min !== null && (
                <FieldRow label="vc" value={`${cr.vc_min_m_min}–${cr.vc_max_m_min} m/min`} />
              )}
              {cr.fn_min_mm_rev !== null && cr.fn_max_mm_rev !== null && (
                <FieldRow label="fn" value={`${cr.fn_min_mm_rev}–${cr.fn_max_mm_rev} mm/rev`} />
              )}
              {cr.fz_min_mm_tooth !== null && cr.fz_max_mm_tooth !== null && (
                <FieldRow label="fz" value={`${cr.fz_min_mm_tooth}–${cr.fz_max_mm_tooth} mm/tooth`} />
              )}
              {cr.ap_min_mm !== null && cr.ap_max_mm !== null && (
                <FieldRow label="ap" value={`${cr.ap_min_mm}–${cr.ap_max_mm} mm`} />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── List row ──────────────────────────────────────────────────────────────────

function MaterialRow({
  item,
  onSelect,
}: {
  item: MaterialListItem
  onSelect: (item: MaterialListItem) => void
}) {
  return (
    <button
      onClick={() => onSelect(item)}
      className="w-full text-left flex items-center gap-3 px-4 py-3 border-b border-[var(--tp-border)] hover:bg-[var(--tp-surface-2)] transition-colors last:border-0"
    >
      <IsoBadge group={item.iso_group} />
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-[var(--tp-text)] truncate">{item.designation}</div>
        <div className="text-xs text-[var(--tp-text-2)] truncate">
          {[item.werkstoff_nr, item.standard_aisi, item.aliases[0]].filter(Boolean).join(' · ')}
        </div>
      </div>
      <div className="shrink-0">
        <ConfBadge confidence={item.data_confidence} />
      </div>
      <div className="text-xs text-[var(--tp-text-3)] shrink-0 hidden sm:block">
        {item.iso_subgroup.replace(/_/g, ' ')}
      </div>
    </button>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function MaterialLibraryPage() {
  const { t } = useLocale()

  const [items, setItems] = useState<MaterialListItem[]>([])
  const [isoGroups, setIsoGroups] = useState<IsoGroupInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchText, setSearchText] = useState('')
  const [filterIsoGroup, setFilterIsoGroup] = useState('')
  const [selectedDetail, setSelectedDetail] = useState<MaterialDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const load = useCallback(async (iso: string, search: string) => {
    setLoading(true)
    setError(null)
    try {
      const [data, groups] = await Promise.all([
        fetchMaterials({ iso_group: iso || undefined, search: search || undefined }),
        isoGroups.length > 0 ? Promise.resolve(isoGroups) : fetchMaterialIsoGroups(),
      ])
      setItems(data)
      if (isoGroups.length === 0) setIsoGroups(groups)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load materials')
    } finally {
      setLoading(false)
    }
  }, [isoGroups])

  useEffect(() => {
    load(filterIsoGroup, searchText)
  }, [filterIsoGroup, searchText]) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleSelect(item: MaterialListItem) {
    setDetailLoading(true)
    setSelectedDetail(null)
    try {
      const detail = await fetchMaterialDetail(item.material_id)
      setSelectedDetail(detail)
    } catch {
      // ignore detail errors — user can retry
    } finally {
      setDetailLoading(false)
    }
  }

  function handleBack() {
    setSelectedDetail(null)
  }

  const isGroupCounts: Record<string, number> = {}
  for (const item of items) {
    isGroupCounts[item.iso_group] = (isGroupCounts[item.iso_group] ?? 0) + 1
  }

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-5xl">

        {/* Page header */}
        <div className="mb-5">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--tp-accent-light)] mb-1">
            {t('matBadgeRefOnly')}
          </div>
          <h1 className="text-xl font-semibold text-[var(--tp-text)]">{t('matPageTitle')}</h1>
        </div>

        {/* Stat cards */}
        <div className="flex flex-wrap gap-3 mb-5">
          <StatCard label={t('matRecords')} value={items.length} />
          {Object.entries(isGroupCounts).map(([g, n]) => (
            <StatCard key={g} label={`ISO ${g}`} value={n} />
          ))}
        </div>

        {selectedDetail || detailLoading ? (
          <div className="bg-[var(--tp-bg)] border border-[var(--tp-border)] rounded-lg p-5">
            {detailLoading ? (
              <div className="text-sm text-[var(--tp-text-2)]">Loading...</div>
            ) : selectedDetail ? (
              <MaterialDetailPanel detail={selectedDetail} onBack={handleBack} />
            ) : null}
          </div>
        ) : (
          <>
            {/* Search + filter bar */}
            <div className="flex flex-wrap gap-2 mb-4">
              <input
                type="text"
                value={searchText}
                onChange={e => setSearchText(e.target.value)}
                placeholder={t('matSearchPlaceholder')}
                className="flex-1 min-w-[200px] px-3 py-2 text-sm bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg text-[var(--tp-text)] placeholder-[var(--tp-text-3)] focus:outline-none focus:border-[var(--tp-accent)]"
              />
              <select
                value={filterIsoGroup}
                onChange={e => setFilterIsoGroup(e.target.value)}
                className="px-3 py-2 text-sm bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg text-[var(--tp-text)] focus:outline-none focus:border-[var(--tp-accent)]"
              >
                <option value="">{t('matIsoGroupFilter')}: All</option>
                {isoGroups.map(g => (
                  <option key={g.code} value={g.code}>ISO {g.code} — {g.label}</option>
                ))}
              </select>
            </div>

            {/* Error */}
            {error && (
              <div className="mb-4 p-3 bg-red-900/20 border border-red-700/30 rounded-lg text-sm text-red-400">
                {error}
              </div>
            )}

            {/* Table */}
            <div className="bg-[var(--tp-bg)] border border-[var(--tp-border)] rounded-lg overflow-hidden">
              {/* Header */}
              <div className="hidden sm:grid grid-cols-[56px_1fr_1fr_120px_100px] gap-2 px-4 py-2 bg-[var(--tp-surface)] border-b border-[var(--tp-border)] text-[10px] font-semibold uppercase tracking-widest text-[var(--tp-text-3)]">
                <div>{t('matColIsoGroup')}</div>
                <div>{t('matColDesignation')}</div>
                <div>{t('matColWorkstoff')} / AISI</div>
                <div>{t('matColFamily')}</div>
                <div>Confidence</div>
              </div>

              {loading ? (
                <div className="px-4 py-6 text-sm text-[var(--tp-text-2)]">Loading...</div>
              ) : items.length === 0 ? (
                <div className="px-4 py-6 text-sm text-[var(--tp-text-2)]">{t('matNoResults')}</div>
              ) : (
                <div>
                  {items.map(item => (
                    <MaterialRow key={item.material_id} item={item} onSelect={handleSelect} />
                  ))}
                </div>
              )}
            </div>

            {/* Evidence note */}
            <div className="mt-3 text-[10px] text-[var(--tp-text-3)]">
              {t('matCuttingContextNote')}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
