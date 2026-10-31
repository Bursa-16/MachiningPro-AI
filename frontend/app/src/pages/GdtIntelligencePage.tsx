import { useState, useCallback } from 'react'
import { useLocale } from '../i18n/index'
import type { TranslationDictionary } from '../i18n/types'
import {
  fetchGdtSchema,
  validateGdt,
  interpretGdt,
  calcBonusTolerance,
  calcVirtualCondition,
  type FcfIn,
  type FosIn,
  type GdtSchema,
  type ValidationResult,
  type InterpretResult,
  type BonusToleranceResult,
  type VirtualConditionResult,
  type ValidationFinding,
  type ProcessImplication,
  type InspectionImplication,
  type AmbiguityItem,
} from '../services/gdt'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type ActiveTab = 'interpret' | 'validate' | 'bonus' | 'virtualcond' | 'schema'

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--tp-text-3)] mb-2">
      {children}
    </div>
  )
}

function FieldRow({ label, value, mono = true }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex justify-between items-baseline py-1.5 border-b border-[var(--tp-border)] last:border-0">
      <span className="text-xs text-[var(--tp-text-2)]">{label}</span>
      <span className={`text-sm ${mono ? 'font-mono' : ''} text-[var(--tp-text)] ml-4 text-right`}>{value ?? '—'}</span>
    </div>
  )
}

function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-[var(--tp-surface)] border border-[var(--tp-border)] rounded-lg p-4 ${className}`}>
      {children}
    </div>
  )
}

function SeverityBadge({ severity }: { severity: string }) {
  const colors: Record<string, string> = {
    ERROR: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300',
    WARNING: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300',
    INFO: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300',
  }
  return (
    <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold ${colors[severity] ?? colors.INFO}`}>
      {severity}
    </span>
  )
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    VALID: 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300',
    INVALID: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300',
    INSUFFICIENT_DATA: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300',
    PENDING_REVIEW: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300',
    CONFIRMED: 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300',
    REJECTED: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300',
  }
  return (
    <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-semibold ${colors[status] ?? colors.PENDING_REVIEW}`}>
      {status}
    </span>
  )
}

function FormField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <label className="text-[10px] font-semibold uppercase tracking-wider text-[var(--tp-text-3)]">{label}</label>
      {children}
    </div>
  )
}

function Input({ value, onChange, type = 'text', placeholder = '' }: {
  value: string
  onChange: (v: string) => void
  type?: string
  placeholder?: string
}) {
  return (
    <input
      type={type}
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-full rounded border border-[var(--tp-border)] bg-[var(--tp-surface-2)] px-2 py-1.5 text-sm text-[var(--tp-text)] focus:outline-none focus:ring-1 focus:ring-[var(--tp-accent)]"
    />
  )
}

function Select({ value, onChange, options }: {
  value: string
  onChange: (v: string) => void
  options: string[]
}) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      className="w-full rounded border border-[var(--tp-border)] bg-[var(--tp-surface-2)] px-2 py-1.5 text-sm text-[var(--tp-text)] focus:outline-none focus:ring-1 focus:ring-[var(--tp-accent)]"
    >
      {options.map(o => <option key={o} value={o}>{o}</option>)}
    </select>
  )
}

// ---------------------------------------------------------------------------
// FCF input sub-form
// ---------------------------------------------------------------------------

const GDT_CHARACTERISTICS = [
  'POSITION', 'PERPENDICULARITY', 'ANGULARITY', 'PARALLELISM',
  'FLATNESS', 'STRAIGHTNESS', 'CIRCULARITY', 'CYLINDRICITY',
  'PROFILE_OF_A_SURFACE', 'PROFILE_OF_A_LINE',
  'CIRCULAR_RUNOUT', 'TOTAL_RUNOUT',
  'CONCENTRICITY', 'SYMMETRY',
]
const GDT_MODIFIERS = ['NONE', 'MMC', 'LMC', 'RFS', 'PROJECTED', 'FREE_STATE', 'TANGENT_PLANE']
const FOS_KINDS = ['INTERNAL_CYLINDRICAL', 'EXTERNAL_CYLINDRICAL', 'WIDTH', 'SPHERICAL', 'NON_FEATURE_OF_SIZE']

interface FcfFormState {
  characteristic: string
  tolerance_value: string
  diameter_zone: boolean
  modifier: string
  datum_primary: string
  datum_secondary: string
  datum_tertiary: string
}

interface FosFormState {
  enabled: boolean
  fos_id: string
  kind: string
  nominal_mm: string
  upper_limit_mm: string
  lower_limit_mm: string
  actual_size_mm: string
}

function defaultFcf(): FcfFormState {
  return {
    characteristic: 'POSITION',
    tolerance_value: '0.05',
    diameter_zone: true,
    modifier: 'MMC',
    datum_primary: 'A',
    datum_secondary: 'B',
    datum_tertiary: '',
  }
}

function defaultFos(): FosFormState {
  return {
    enabled: true,
    fos_id: 'FOS-001',
    kind: 'INTERNAL_CYLINDRICAL',
    nominal_mm: '25',
    upper_limit_mm: '25.021',
    lower_limit_mm: '25.000',
    actual_size_mm: '',
  }
}

function buildFcfIn(fcf: FcfFormState): FcfIn {
  const frame: FcfIn['datum_frame'] = fcf.datum_primary ? {
    primary: { label: fcf.datum_primary, precedence: 1 },
    secondary: fcf.datum_secondary ? { label: fcf.datum_secondary, precedence: 2 } : null,
    tertiary: fcf.datum_tertiary ? { label: fcf.datum_tertiary, precedence: 3 } : null,
  } : null
  return {
    characteristic: fcf.characteristic,
    tolerance_value: parseFloat(fcf.tolerance_value) || 0.05,
    tolerance_unit: 'mm',
    diameter_zone: fcf.diameter_zone,
    modifier: fcf.modifier,
    datum_frame: frame,
  }
}

function buildFosIn(fos: FosFormState): FosIn | null {
  if (!fos.enabled) return null
  return {
    fos_id: fos.fos_id || 'FOS-001',
    kind: fos.kind,
    nominal_mm: fos.nominal_mm ? parseFloat(fos.nominal_mm) : null,
    upper_limit_mm: fos.upper_limit_mm ? parseFloat(fos.upper_limit_mm) : null,
    lower_limit_mm: fos.lower_limit_mm ? parseFloat(fos.lower_limit_mm) : null,
    actual_size_mm: fos.actual_size_mm ? parseFloat(fos.actual_size_mm) : null,
  }
}

function FcfForm({
  fcf,
  setFcf,
  fos,
  setFos,
  t,
}: {
  fcf: FcfFormState
  setFcf: React.Dispatch<React.SetStateAction<FcfFormState>>
  fos: FosFormState
  setFos: React.Dispatch<React.SetStateAction<FosFormState>>
  t: (key: keyof TranslationDictionary) => string
}) {
  const toggle = <K extends keyof FcfFormState>(k: K, v: FcfFormState[K]) =>
    setFcf(prev => ({ ...prev, [k]: v }))
  const tfos = <K extends keyof FosFormState>(k: K, v: FosFormState[K]) =>
    setFos(prev => ({ ...prev, [k]: v }))

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <FormField label={t('gdtCharacteristicLabel')}>
          <Select value={fcf.characteristic} onChange={v => toggle('characteristic', v)} options={GDT_CHARACTERISTICS} />
        </FormField>
        <FormField label={t('gdtModifierLabel')}>
          <Select value={fcf.modifier} onChange={v => toggle('modifier', v)} options={GDT_MODIFIERS} />
        </FormField>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <FormField label="Tolerance (mm)">
          <Input value={fcf.tolerance_value} onChange={v => toggle('tolerance_value', v)} type="number" placeholder="0.05" />
        </FormField>
        <FormField label="Diameter zone (⌀)">
          <label className="flex items-center gap-2 py-1.5">
            <input type="checkbox" checked={fcf.diameter_zone} onChange={e => toggle('diameter_zone', e.target.checked)} className="accent-[var(--tp-accent)]" />
            <span className="text-sm text-[var(--tp-text)]">⌀ zone</span>
          </label>
        </FormField>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <FormField label="Primary datum">
          <Input value={fcf.datum_primary} onChange={v => toggle('datum_primary', v)} placeholder="A" />
        </FormField>
        <FormField label="Secondary">
          <Input value={fcf.datum_secondary} onChange={v => toggle('datum_secondary', v)} placeholder="B" />
        </FormField>
        <FormField label="Tertiary">
          <Input value={fcf.datum_tertiary} onChange={v => toggle('datum_tertiary', v)} placeholder="C" />
        </FormField>
      </div>
      {/* FOS */}
      <div className="border-t border-[var(--tp-border)] pt-3">
        <label className="flex items-center gap-2 mb-3">
          <input type="checkbox" checked={fos.enabled} onChange={e => tfos('enabled', e.target.checked)} className="accent-[var(--tp-accent)]" />
          <span className="text-xs font-semibold uppercase tracking-wider text-[var(--tp-text-2)]">{t('gdtFosTitle')}</span>
        </label>
        {fos.enabled && (
          <div className="space-y-2 pl-2">
            <div className="grid grid-cols-2 gap-2">
              <FormField label="FOS Kind">
                <Select value={fos.kind} onChange={v => tfos('kind', v)} options={FOS_KINDS} />
              </FormField>
              <FormField label="FOS ID">
                <Input value={fos.fos_id} onChange={v => tfos('fos_id', v)} placeholder="FOS-001" />
              </FormField>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <FormField label={t('gdtNominalLabel') + ' (mm)'}>
                <Input value={fos.nominal_mm} onChange={v => tfos('nominal_mm', v)} type="number" />
              </FormField>
              <FormField label={t('gdtUpperLimitLabel') + ' (mm)'}>
                <Input value={fos.upper_limit_mm} onChange={v => tfos('upper_limit_mm', v)} type="number" />
              </FormField>
              <FormField label={t('gdtLowerLimitLabel') + ' (mm)'}>
                <Input value={fos.lower_limit_mm} onChange={v => tfos('lower_limit_mm', v)} type="number" />
              </FormField>
            </div>
            <FormField label={t('gdtFosActualSizeHint')}>
              <Input value={fos.actual_size_mm} onChange={v => tfos('actual_size_mm', v)} type="number" placeholder="leave blank if unknown" />
            </FormField>
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Result panels
// ---------------------------------------------------------------------------

function ValidationPanel({ result, t }: { result: ValidationResult; t: (key: keyof TranslationDictionary) => string }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <SectionLabel>{t('gdtValidationTitle')}</SectionLabel>
        <StatusBadge status={result.overall} />
      </div>
      <div className="space-y-2">
        {result.findings.filter(f => !f.passed || f.severity !== 'INFO' || f.ambiguity_kind).map(f => (
          <FindingRow key={f.rule_id} finding={f} t={t} />
        ))}
        {result.findings.every(f => f.passed) && (
          <p className="text-xs text-[var(--tp-text-2)]">{t('gdtValidationPassed')}</p>
        )}
      </div>
    </div>
  )
}

function FindingRow({ finding, t: _t }: { finding: ValidationFinding; t: (key: keyof TranslationDictionary) => string }) {
  return (
    <div className="rounded border border-[var(--tp-border)] p-2 space-y-1">
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-mono text-[var(--tp-text-3)]">{finding.rule_id}</span>
        <SeverityBadge severity={finding.severity} />
        {finding.passed && <span className="text-[10px] text-green-600 dark:text-green-400">✓</span>}
      </div>
      <p className="text-xs text-[var(--tp-text)]">{finding.message}</p>
      {finding.suggested_resolution && (
        <p className="text-[10px] text-[var(--tp-text-2)] italic">→ {finding.suggested_resolution}</p>
      )}
    </div>
  )
}

function DatumFramePanel({ frame, t }: {
  frame: InterpretResult['datum_frame']
  t: (key: keyof TranslationDictionary) => string
}) {
  if (!frame) return null
  return (
    <Card>
      <SectionLabel>{t('gdtDatumFrameTitle')}</SectionLabel>
      <FieldRow label={t('gdtDatumPrimary')} value={`${frame.primary.label} (${frame.primary.modifier})`} />
      {frame.secondary && (
        <FieldRow label={t('gdtDatumSecondary')} value={`${frame.secondary.label} (${frame.secondary.modifier})`} />
      )}
      {frame.tertiary && (
        <FieldRow label={t('gdtDatumTertiary')} value={`${frame.tertiary.label} (${frame.tertiary.modifier})`} />
      )}
    </Card>
  )
}

function FosPanel({ fos, t }: { fos: InterpretResult['fos_context']; t: (key: keyof TranslationDictionary) => string }) {
  if (!fos) return null
  const fmt = (v: number | null) => v != null ? `${v} mm` : '—'
  return (
    <Card>
      <SectionLabel>{t('gdtFosTitle')}</SectionLabel>
      <FieldRow label={t('gdtCharacteristicLabel')} value={fos.kind} />
      <FieldRow label={t('gdtNominalLabel')} value={fmt(fos.nominal_mm)} />
      <FieldRow label={t('gdtUpperLimitLabel')} value={fmt(fos.upper_limit_mm)} />
      <FieldRow label={t('gdtLowerLimitLabel')} value={fmt(fos.lower_limit_mm)} />
      <FieldRow label={t('gdtMmcSize')} value={fmt(fos.mmc_size_mm)} />
      <FieldRow label={t('gdtLmcSize')} value={fmt(fos.lmc_size_mm)} />
      {fos.actual_size_mm != null && (
        <FieldRow label={t('gdtBonusToleranceActualSize')} value={fmt(fos.actual_size_mm)} />
      )}
    </Card>
  )
}

function ToleranceZonePanel({ tz, t }: { tz: InterpretResult['tolerance_zone']; t: (key: keyof TranslationDictionary) => string }) {
  return (
    <Card>
      <SectionLabel>{t('gdtToleranceZoneLabel')}</SectionLabel>
      <FieldRow label="Geometry" value={tz.geometry.replace(/_/g, ' ')} />
      <FieldRow label="Value" value={`${tz.diameter_zone ? '⌀' : ''}${tz.value_mm} ${tz.unit}`} />
    </Card>
  )
}

function AmbiguityPanel({ ambiguities, t }: { ambiguities: AmbiguityItem[]; t: (key: keyof TranslationDictionary) => string }) {
  return (
    <Card>
      <SectionLabel>{t('gdtAmbiguityDashboard')}</SectionLabel>
      {ambiguities.length === 0 ? (
        <p className="text-xs text-[var(--tp-text-2)]">{t('gdtNoAmbiguities')}</p>
      ) : (
        <div className="space-y-2">
          {ambiguities.map(a => (
            <div key={a.ambiguity_id} className="rounded border border-[var(--tp-border)] p-2 space-y-1">
              <div className="flex items-center gap-2">
                <SeverityBadge severity={a.severity} />
                <span className="text-xs font-medium text-[var(--tp-text)]">{a.kind.replace(/_/g, ' ')}</span>
              </div>
              <p className="text-xs text-[var(--tp-text)]">{a.description}</p>
              {a.suggested_resolution && (
                <p className="text-[10px] text-[var(--tp-text-2)] italic">→ {a.suggested_resolution}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

function ProcessImplicationsPanel({ items, t }: { items: ProcessImplication[]; t: (key: keyof TranslationDictionary) => string }) {
  if (items.length === 0) return null
  return (
    <Card>
      <SectionLabel>{t('gdtProcessImplications')}</SectionLabel>
      <div className="space-y-2">
        {items.map(item => (
          <div key={item.rule_id} className="flex items-start gap-2">
            <SeverityBadge severity={item.severity} />
            <div>
              <span className="text-[10px] font-mono text-[var(--tp-text-3)]">{item.rule_id} </span>
              <span className="text-xs text-[var(--tp-text)]">{item.description}</span>
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}

function InspectionImplicationsPanel({ items, t }: { items: InspectionImplication[]; t: (key: keyof TranslationDictionary) => string }) {
  if (items.length === 0) return null
  return (
    <Card>
      <SectionLabel>{t('gdtInspectionImplications')}</SectionLabel>
      <div className="space-y-2">
        {items.map((item, i) => (
          <div key={i} className="flex items-start gap-2">
            <span className="text-[10px] font-mono bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300 rounded px-1.5 py-0.5 shrink-0">{item.method}</span>
            <span className="text-xs text-[var(--tp-text)]">{item.rationale}</span>
          </div>
        ))}
      </div>
    </Card>
  )
}

function EngineerReviewPanel({
  approvalStatus,
  onConfirm,
  onEdit,
  onReject,
  t,
}: {
  approvalStatus: string
  onConfirm: () => void
  onEdit: () => void
  onReject: () => void
  t: (key: keyof TranslationDictionary) => string
}) {
  return (
    <Card>
      <SectionLabel>{t('gdtEngineerReview')}</SectionLabel>
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs text-[var(--tp-text-2)]">{t('gdtApprovalStatus')}:</span>
        <StatusBadge status={approvalStatus} />
      </div>
      {approvalStatus === 'PENDING_REVIEW' && (
        <div className="flex flex-wrap gap-2">
          <button
            onClick={onConfirm}
            className="rounded bg-green-600 hover:bg-green-700 text-white text-xs font-semibold px-3 py-1.5"
          >
            {t('gdtConfirmBtn')}
          </button>
          <button
            onClick={onEdit}
            className="rounded bg-[var(--tp-accent)] hover:opacity-80 text-white text-xs font-semibold px-3 py-1.5"
          >
            {t('gdtEditBtn')}
          </button>
          <button
            onClick={onReject}
            className="rounded bg-red-600 hover:bg-red-700 text-white text-xs font-semibold px-3 py-1.5"
          >
            {t('gdtRejectBtn')}
          </button>
        </div>
      )}
      {approvalStatus !== 'PENDING_REVIEW' && (
        <p className="text-xs text-[var(--tp-text-2)]">
          {approvalStatus === 'CONFIRMED' ? t('gdtConfirmNote') : t('gdtRejectNote')}
        </p>
      )}
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Bonus Tolerance result panel
// ---------------------------------------------------------------------------

function BonusTolerancePanel({ result, t }: { result: BonusToleranceResult; t: (key: keyof TranslationDictionary) => string }) {
  const fmt = (v: number | null) => v != null ? `${v} mm` : '—'
  return (
    <Card>
      <SectionLabel>{t('gdtBonusToleranceTitle')}</SectionLabel>
      {!result.computed ? (
        <div className="text-xs text-[var(--tp-text-2)]">
          <StatusBadge status="INSUFFICIENT_DATA" />
          <p className="mt-1">{result.reason_not_computed}</p>
        </div>
      ) : (
        <>
          <FieldRow label={t('gdtBonusToleranceStated')} value={fmt(result.stated_tolerance_mm)} />
          <FieldRow label={t('gdtBonusToleranceActualSize')} value={fmt(result.actual_size_mm)} />
          <FieldRow label="MMC/LMC size" value={fmt(result.mmc_or_lmc_size_mm)} />
          <FieldRow label={t('gdtBonusToleranceBonus')} value={fmt(result.bonus_amount_mm)} />
          <FieldRow label={t('gdtBonusToleranceTotal')} value={
            <span className="text-green-600 dark:text-green-400 font-bold">{fmt(result.total_tolerance_mm)}</span>
          } />
        </>
      )}
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Virtual Condition result panel
// ---------------------------------------------------------------------------

function VirtualConditionPanel({ result, t }: { result: VirtualConditionResult; t: (key: keyof TranslationDictionary) => string }) {
  const fmt = (v: number | null) => v != null ? `${v} mm` : '—'
  return (
    <Card>
      <SectionLabel>{t('gdtVirtualConditionTitle')}</SectionLabel>
      {!result.computed ? (
        <div className="text-xs text-[var(--tp-text-2)]">
          <StatusBadge status="INSUFFICIENT_DATA" />
          <p className="mt-1">{result.description}</p>
        </div>
      ) : (
        <>
          <FieldRow label={t('gdtVirtualConditionValue')} value={
            <span className="font-bold">{fmt(result.virtual_condition_mm)}</span>
          } />
          <p className="text-xs text-[var(--tp-text-2)] pt-2">{result.description}</p>
        </>
      )}
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Schema panel
// ---------------------------------------------------------------------------

function SchemaPanel({ schema, t }: { schema: GdtSchema; t: (key: keyof TranslationDictionary) => string }) {
  return (
    <div className="space-y-4">
      <Card>
        <SectionLabel>{t('gdtCharacteristicsLabel')}</SectionLabel>
        <div className="flex flex-wrap gap-1">
          {schema.characteristics.map(c => (
            <span key={c} className="text-[10px] font-mono bg-[var(--tp-surface-2)] text-[var(--tp-text)] rounded px-1.5 py-0.5 border border-[var(--tp-border)]">{c}</span>
          ))}
        </div>
      </Card>
      <Card>
        <SectionLabel>{t('gdtModifiersLabel')}</SectionLabel>
        <div className="flex flex-wrap gap-1">
          {schema.feature_modifiers.map(m => (
            <span key={m} className="text-[10px] font-mono bg-[var(--tp-surface-2)] text-[var(--tp-text)] rounded px-1.5 py-0.5 border border-[var(--tp-border)]">{m}</span>
          ))}
        </div>
      </Card>
      <Card>
        <SectionLabel>{t('gdtZoneGeometriesLabel')}</SectionLabel>
        <div className="flex flex-wrap gap-1">
          {schema.tolerance_zone_geometries.map(g => (
            <span key={g} className="text-[10px] font-mono bg-[var(--tp-surface-2)] text-[var(--tp-text)] rounded px-1.5 py-0.5 border border-[var(--tp-border)]">{g}</span>
          ))}
        </div>
      </Card>
      <Card>
        <SectionLabel>Validation Rules</SectionLabel>
        <div className="flex flex-wrap gap-1">
          {schema.validation_rule_ids.map(r => (
            <span key={r} className="text-[10px] font-mono bg-[var(--tp-surface-2)] text-[var(--tp-text)] rounded px-1.5 py-0.5 border border-[var(--tp-border)]">{r}</span>
          ))}
        </div>
      </Card>
      <Card>
        <SectionLabel>Inspection Methods</SectionLabel>
        <div className="flex flex-wrap gap-1">
          {schema.inspection_methods.map(m => (
            <span key={m} className="text-[10px] font-mono bg-[var(--tp-surface-2)] text-[var(--tp-text)] rounded px-1.5 py-0.5 border border-[var(--tp-border)]">{m}</span>
          ))}
        </div>
      </Card>
      <p className="text-[10px] text-[var(--tp-text-3)]">{schema.disclaimer}</p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function GdtIntelligencePage() {
  const { t } = useLocale()
  const [activeTab, setActiveTab] = useState<ActiveTab>('interpret')

  // Shared FCF/FOS state
  const [fcf, setFcf] = useState<FcfFormState>(defaultFcf)
  const [fos, setFos] = useState<FosFormState>(defaultFos)
  const [reqId, setReqId] = useState('GDT-001')

  // Results
  const [interpretResult, setInterpretResult] = useState<InterpretResult | null>(null)
  const [validateResult, setValidateResult] = useState<ValidationResult | null>(null)
  const [bonusResult, setBonusResult] = useState<BonusToleranceResult | null>(null)
  const [vcResult, setVcResult] = useState<VirtualConditionResult | null>(null)
  const [schema, setSchema] = useState<GdtSchema | null>(null)

  const [approvalStatus, setApprovalStatus] = useState<string>('PENDING_REVIEW')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const clearError = () => setError(null)

  const handleSubmit = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const fcfIn = buildFcfIn(fcf)
      const fosIn = buildFosIn(fos)

      if (activeTab === 'interpret') {
        const r = await interpretGdt({ req_id: reqId, fcf: fcfIn, fos: fosIn })
        setInterpretResult(r)
        setApprovalStatus('PENDING_REVIEW')
      } else if (activeTab === 'validate') {
        const r = await validateGdt({ req_id: reqId, fcf: fcfIn, fos: fosIn })
        setValidateResult(r)
      } else if (activeTab === 'bonus') {
        if (!fosIn) { setError('Feature of Size is required for bonus tolerance'); return }
        const r = await calcBonusTolerance({ req_id: reqId, fcf: fcfIn, fos: fosIn })
        setBonusResult(r)
      } else if (activeTab === 'virtualcond') {
        if (!fosIn) { setError('Feature of Size is required for virtual condition'); return }
        const r = await calcVirtualCondition({ req_id: reqId, fcf: fcfIn, fos: fosIn })
        setVcResult(r)
      } else if (activeTab === 'schema') {
        const r = await fetchGdtSchema()
        setSchema(r)
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Request failed'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [activeTab, fcf, fos, reqId])

  const tabs: { id: ActiveTab; label: string }[] = [
    { id: 'interpret', label: t('gdtInterpretInput') },
    { id: 'validate', label: t('gdtValidateInput') },
    { id: 'bonus', label: t('gdtBonusCalcInput') },
    { id: 'virtualcond', label: t('gdtVcCalcInput') },
    { id: 'schema', label: t('gdtSchemaTitle') },
  ]

  return (
    <div className="min-h-screen bg-[var(--tp-bg)] text-[var(--tp-text)]">
      {/* Header */}
      <div className="border-b border-[var(--tp-border)] bg-[var(--tp-surface)] px-4 py-4">
        <div className="max-w-5xl mx-auto">
          <h1 className="text-lg font-bold text-[var(--tp-text)]">{t('gdtIntelligencePanelTitle')}</h1>
          <p className="text-xs text-[var(--tp-text-2)] mt-0.5">{t('gdtIntelligencePanelSubtitle')}</p>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        {/* Tab bar */}
        <div className="flex flex-wrap gap-1 border-b border-[var(--tp-border)]">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => { setActiveTab(tab.id); clearError() }}
              className={`px-3 py-2 text-xs font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-[var(--tp-accent)] text-[var(--tp-accent)]'
                  : 'border-transparent text-[var(--tp-text-2)] hover:text-[var(--tp-text)]'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left — inputs (all tabs except schema) */}
          {activeTab !== 'schema' && (
            <div className="space-y-4">
              <Card>
                <SectionLabel>{t('gdtReqIdLabel')}</SectionLabel>
                <Input value={reqId} onChange={setReqId} placeholder="GDT-001" />
              </Card>
              <Card>
                <SectionLabel>{t('gdtFcfSection')}</SectionLabel>
                <FcfForm fcf={fcf} setFcf={setFcf} fos={fos} setFos={setFos} t={t} />
              </Card>
              <div className="flex gap-2">
                <button
                  onClick={handleSubmit}
                  disabled={loading}
                  className="flex-1 rounded bg-[var(--tp-accent)] text-white text-sm font-semibold py-2 hover:opacity-80 disabled:opacity-50"
                >
                  {loading ? '…' : t('gdtSubmitBtn')}
                </button>
                <button
                  onClick={() => { setFcf(defaultFcf()); setFos(defaultFos()); clearError() }}
                  className="rounded border border-[var(--tp-border)] text-[var(--tp-text-2)] text-sm px-3 py-2 hover:bg-[var(--tp-surface-2)]"
                >
                  {t('gdtClearBtn')}
                </button>
              </div>
              {error && (
                <div className="rounded border border-red-300 bg-red-50 dark:bg-red-900/20 dark:border-red-800 p-3 text-xs text-red-700 dark:text-red-300">
                  {error}
                </div>
              )}
            </div>
          )}

          {/* Right — results */}
          <div className="space-y-4">
            {activeTab === 'schema' && (
              <>
                <div className="flex gap-2">
                  <button
                    onClick={handleSubmit}
                    disabled={loading}
                    className="rounded bg-[var(--tp-accent)] text-white text-sm font-semibold px-4 py-2 hover:opacity-80 disabled:opacity-50"
                  >
                    {loading ? '…' : t('gdtSubmitBtn')}
                  </button>
                </div>
                {schema && <SchemaPanel schema={schema} t={t} />}
              </>
            )}

            {activeTab === 'interpret' && interpretResult && (
              <>
                {/* Overview */}
                <Card>
                  <SectionLabel>{t('gdtOverviewSection')}</SectionLabel>
                  <FieldRow label={t('gdtCharacteristicLabel')} value={interpretResult.characteristic} />
                  <FieldRow label="Tolerance" value={`${interpretResult.diameter_zone ? '⌀' : ''}${interpretResult.tolerance_value} ${interpretResult.tolerance_unit}`} />
                  <FieldRow label={t('gdtModifierLabel')} value={interpretResult.modifier_description} mono={false} />
                  <FieldRow label="Confidence" value={interpretResult.confidence} />
                  <FieldRow label={t('gdtApprovalStatus')} value={<StatusBadge status={interpretResult.approval_status} />} mono={false} />
                </Card>

                <ToleranceZonePanel tz={interpretResult.tolerance_zone} t={t} />
                <DatumFramePanel frame={interpretResult.datum_frame} t={t} />
                <FosPanel fos={interpretResult.fos_context} t={t} />
                <AmbiguityPanel ambiguities={interpretResult.ambiguities} t={t} />
                <ProcessImplicationsPanel items={interpretResult.process_implications} t={t} />
                <InspectionImplicationsPanel items={interpretResult.inspection_implications} t={t} />

                {/* Route impact */}
                {interpretResult.process_implications.length > 0 && (
                  <Card>
                    <SectionLabel>{t('gdtRouteImpact')}</SectionLabel>
                    <p className="text-xs text-[var(--tp-text-2)]">{t('gdtRouteImpactDesc')}</p>
                    <ul className="mt-2 space-y-1">
                      {interpretResult.process_implications.map(p => (
                        <li key={p.rule_id} className="text-xs text-[var(--tp-text)] flex gap-1">
                          <span className="text-[var(--tp-text-3)] font-mono shrink-0">{p.rule_id}</span>
                          <span>{p.description}</span>
                        </li>
                      ))}
                    </ul>
                  </Card>
                )}

                <EngineerReviewPanel
                  approvalStatus={approvalStatus}
                  onConfirm={() => setApprovalStatus('CONFIRMED')}
                  onEdit={() => setApprovalStatus('PENDING_REVIEW')}
                  onReject={() => setApprovalStatus('REJECTED')}
                  t={t}
                />

                <p className="text-[10px] text-[var(--tp-text-3)]">{interpretResult.disclaimer}</p>
              </>
            )}

            {activeTab === 'validate' && validateResult && (
              <Card>
                <ValidationPanel result={validateResult} t={t} />
                <p className="text-[10px] text-[var(--tp-text-3)] mt-3">{validateResult.disclaimer}</p>
              </Card>
            )}

            {activeTab === 'bonus' && bonusResult && (
              <>
                <BonusTolerancePanel result={bonusResult} t={t} />
                <p className="text-[10px] text-[var(--tp-text-3)]">{bonusResult.disclaimer}</p>
              </>
            )}

            {activeTab === 'virtualcond' && vcResult && (
              <>
                <VirtualConditionPanel result={vcResult} t={t} />
                <p className="text-[10px] text-[var(--tp-text-3)]">{vcResult.disclaimer}</p>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
