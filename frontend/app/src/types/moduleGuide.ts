/**
 * MachiningPro AI - Module Guide Data Model
 * STRICT BILINGUAL 19-SECTION SCHEMA (CUSTOMER-UX-04 Standard)
 *
 * Every module guide MUST use this exact structure.
 * No optional Turkish - full EN+TR required for every applicable section.
 * N/A must be explicitly represented with localized explanation.
 */

// 19-Section Standard Schema
export interface ModuleGuideSection {
  id: '01-purpose' | '02-when-to-use' | '03-required-inputs' | '04-input-definitions' |
      '05-engineering-logic' | '06-workflow' | '07-outputs' | '08-result-interpretation' |
      '09-decision-criteria' | '10-assumptions' | '11-limitations' | '12-validation' |
      '13-traceability' | '14-common-mistakes' | '15-example-workflow' | '16-ai-assistance' |
      '17-faq' | '18-related-modules' | '19-academy'

  // EN content - REQUIRED
  title: string
  content: string

  // TR content - REQUIRED (not optional)
  titleTr: string
  contentTr: string

  // Optional metadata
  logicType?: 'DETERMINISTIC' | 'RULE_BASED' | 'LOOKUP' | 'STATISTICAL' | 'VALIDATION' | 'AI_ASSISTED_EXPLANATION' | 'HYBRID' | 'N/A'
  status?: 'complete' | 'n/a' | 'pending'
}

// Strict Bilingual Module Guide Type
export interface ModuleGuide {
  id: string
  moduleName: string
  moduleTr: string  // NOT optional
  description: string
  descriptionTr: string  // NOT optional
  sections: ModuleGuideSection[]  // MUST include all 19 sections (or explicit N/A)
}

// Localized Module Guide Wrapper - Strict Type
export type LocalizedModuleGuide = {
  en: ModuleGuide
  tr: ModuleGuide
}

// Standard Section IDs - All 19 Required
export const STANDARD_SECTION_IDS = [
  '01-purpose',
  '02-when-to-use',
  '03-required-inputs',
  '04-input-definitions',
  '05-engineering-logic',
  '06-workflow',
  '07-outputs',
  '08-result-interpretation',
  '09-decision-criteria',
  '10-assumptions',
  '11-limitations',
  '12-validation',
  '13-traceability',
  '14-common-mistakes',
  '15-example-workflow',
  '16-ai-assistance',
  '17-faq',
  '18-related-modules',
  '19-academy',
] as const

export const REQUIRED_MODULE_IDS = [
  'dashboard',
  'machining-analysis',
  'cutting-parameters',
  'tool-life',
  'surface-roughness',
  'turning',
  'milling',
  'drilling',
  'threading',
  'hole-finishing',
  'honing',
  'lapping',
  'machines',
  'materials',
  'cutting-tools',
  'libraries',
  'cad-import',
  'technical-drawing-intelligence',
  'process-planning',
  'dfm',
  'machine-capability',
  'validation',
] as const

// Section Titles - Bilingual Standard Labels
export const SECTION_LABELS = {
  '01-purpose': { en: 'Module Purpose', tr: 'Modülün Amacı' },
  '02-when-to-use': { en: 'When to Use', tr: 'Ne Zaman Kullanılır?' },
  '03-required-inputs': { en: 'Required Inputs', tr: 'Gerekli Girdiler' },
  '04-input-definitions': { en: 'Input Definitions', tr: 'Girdi Açıklamaları' },
  '05-engineering-logic': { en: 'Engineering / Decision Logic', tr: 'Hesaplama / Karar Mantığı' },
  '06-workflow': { en: 'Engineering Workflow', tr: 'Mühendislik İş Akışı' },
  '07-outputs': { en: 'Outputs', tr: 'Üretilen Çıktılar' },
  '08-result-interpretation': { en: 'How to Interpret Results', tr: 'Sonuçlar Nasıl Yorumlanır?' },
  '09-decision-criteria': { en: 'Decision Criteria', tr: 'Karar Kriterleri' },
  '10-assumptions': { en: 'Assumptions', tr: 'Varsayımlar' },
  '11-limitations': { en: 'Limitations', tr: 'Sınırlar ve Kısıtlar' },
  '12-validation': { en: 'Validation / Qualification', tr: 'Doğrulama / Yeterlilik' },
  '13-traceability': { en: 'Traceability', tr: 'İzlenebilirlik' },
  '14-common-mistakes': { en: 'Common Mistakes', tr: 'Yaygın Hatalar' },
  '15-example-workflow': { en: 'Example Workflow', tr: 'Örnek Kullanım' },
  '16-ai-assistance': { en: 'AI Assistance', tr: 'AI Desteği' },
  '17-faq': { en: 'Frequently Asked Questions', tr: 'Sık Sorulan Sorular' },
  '18-related-modules': { en: 'Related Modules', tr: 'İlgili Modüller' },
  '19-academy': { en: 'Academy / Learn More', tr: 'Academy / Daha Fazla Bilgi' },
} as const
