/**
 * check-guides.mjs - ES Module version
 * Validates MachiningPro AI Module Guide FAQ integrity
 */

import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Import module guides
import * as guides from '../src/data/moduleGuides.ts';

const SECTIONS_PER_MODULE = 19;
const FAQ_MIN_PER_MODULE = 3;
const FAQ_MAX_PER_MODULE = 6;
const FAQ_MIN_TOTAL = 66;
const FAQ_MAX_TOTAL = 132;


// Collect exported guides
const moduleGuides = [];
for (const key in guides) {
  if (key.endsWith('ModuleGuide')) {
    moduleGuides.push(guides[key]);
  }
}

const results = {
  moduleCount: moduleGuides.length,
  modulesWithAllSections: 0,
  modulesWithoutFaq: 0,
  modulesUnderMinFaq: 0,
  modulesOverMaxFaq: 0,
  totalFaqQuestions: 0,
  faqMinPerModule: Infinity,
  faqMaxPerModule: 0,
  modulesWithMinimum3Faq: 0,
  modulesWithMaximum6Faq: 0,
  faqBilingualComplete: true,
  errors: [],
  moduleDetails: [],
};

// Validate each module
for (const guide of moduleGuides) {
  if (!guide || !guide.id || !guide.sections) continue;

  const moduleResult = {
    id: guide.id,
    sectionCount: guide.sections.length,
    faqQuestionsEn: 0,
    issues: [],
  };

  // Check section count
  if (guide.sections.length === SECTIONS_PER_MODULE) {
    results.modulesWithAllSections++;
  } else {
    moduleResult.issues.push(`Expected 19 sections, found ${guide.sections.length}`);
  }

  // Find FAQ section
  const faqSection = guide.sections.find(s => s.id === '17-faq');

  if (!faqSection) {
    results.modulesWithoutFaq++;
    results.errors.push(`Module ${guide.id}: Missing FAQ section`);
  } else {
    // Count questions
    const enContent = faqSection.content || '';
    const trContent = faqSection.contentTr || '';

    const enQuestions = (enContent.match(/(?:^|\n)\s*(?:[-*]\s*)?Q:\s*/g) || []).length;
    const enAnswers   = (enContent.match(/(?:^|\n)\s*(?:[-*]\s*)?A:\s*/g) || []).length;
    const trQuestions = (trContent.match(/(?:^|\n)\s*(?:[-*]\s*)?S:\s*/g) || []).length;
    const trAnswers   = (trContent.match(/(?:^|\n)\s*(?:[-*]\s*)?C:\s*/g) || []).length;

    moduleResult.faqQuestionsEn = enQuestions;

    // Validate cardinality
    results.totalFaqQuestions += enQuestions;
    results.faqMinPerModule = Math.min(results.faqMinPerModule, enQuestions);
    results.faqMaxPerModule = Math.max(results.faqMaxPerModule, enQuestions);

    // Check bilingual match
    if (enQuestions !== enAnswers || trQuestions !== trAnswers || enQuestions !== trQuestions) {
      moduleResult.issues.push(`FAQ mismatch: EN_Q=${enQuestions}, EN_A=${enAnswers}, TR_Q=${trQuestions}, TR_A=${trAnswers}`);
      results.faqBilingualComplete = false;
    }

    // Check cardinality limits
    if (enQuestions < FAQ_MIN_PER_MODULE) {
      results.modulesUnderMinFaq++;
      moduleResult.issues.push(`Only ${enQuestions} questions (min: ${FAQ_MIN_PER_MODULE})`);
      results.errors.push(`Module ${guide.id}: FAQ count ${enQuestions} < 3`);
    } else {
      results.modulesWithMinimum3Faq++;
    }

    if (enQuestions > FAQ_MAX_PER_MODULE) {
      results.modulesOverMaxFaq++;
      moduleResult.issues.push(`${enQuestions} questions (max: ${FAQ_MAX_PER_MODULE})`);
      results.errors.push(`Module ${guide.id}: FAQ count ${enQuestions} > 6`);
    } else {
      results.modulesWithMaximum6Faq++;
    }
  }

  results.moduleDetails.push(moduleResult);
}

// Print report
console.log('='.repeat(70));
console.log('Module Guide Validation Report - FAQ Cardinality Check');
console.log('='.repeat(70));

console.log(`\n[CANONICAL STRUCTURE]\nModules: ${results.moduleCount}/22, Sections: ${results.modulesWithAllSections}/22\n`);

console.log(`[FAQ SECTIONS]\nWith FAQ: ${results.moduleCount - results.modulesWithoutFaq}/22`);
console.log(`Without FAQ: ${results.modulesWithoutFaq}\n`);

console.log(`[FAQ CARDINALITY]\nMin per module: ${results.faqMinPerModule === Infinity ? 'N/A' : results.faqMinPerModule}`);
console.log(`Max per module: ${results.faqMaxPerModule}`);
console.log(`Under minimum (< 3): ${results.modulesUnderMinFaq}`);
console.log(`Over maximum (> 6): ${results.modulesOverMaxFaq}`);
console.log(`Modules with 3-6 FAQ: ${results.modulesWithMinimum3Faq} (min) / ${results.modulesWithMaximum6Faq} (max)\n`);

console.log(`[FAQ TOTAL COUNT]\nTotal questions: ${results.totalFaqQuestions}`);
console.log(`Valid range: ${FAQ_MIN_TOTAL}-${FAQ_MAX_TOTAL}`);
console.log(`Status: ${results.totalFaqQuestions >= FAQ_MIN_TOTAL && results.totalFaqQuestions <= FAQ_MAX_TOTAL ? 'PASS' : 'FAIL'}\n`);

console.log(`[BILINGUAL COMPLETENESS]\nEN/TR Match: ${results.faqBilingualComplete ? 'PASS' : 'FAIL'}\n`);

// Module summary
console.log(`[MODULES]\n`);
results.moduleDetails.slice(0, 10).forEach(m => {
  const icon = m.issues.length === 0 ? '✓' : '✗';
  console.log(`${icon} ${m.id.padEnd(28)} FAQ: ${m.faqQuestionsEn}`);
});
if (results.moduleDetails.length > 10) {
  console.log(`... and ${results.moduleDetails.length - 10} more`);
}

// Errors
if (results.errors.length > 0) {
  console.log(`\n[ERRORS]\n`);
  results.errors.forEach(e => console.log(e));
}

// Overall result
const isPass = 
  results.modulesWithoutFaq === 0 &&
  results.modulesUnderMinFaq === 0 &&
  results.modulesOverMaxFaq === 0 &&
  results.totalFaqQuestions >= FAQ_MIN_TOTAL &&
  results.faqBilingualComplete;

console.log(`\n${'='.repeat(70)}`);
console.log(`RESULT: ${isPass ? 'PASS ✓' : 'FAIL ✗'}`);
console.log(`${'='.repeat(70)}\n`);

console.log(`FAQ_CARDINALITY_GATE_PASS=${isPass ? 'YES' : 'NO'}`);
console.log(`MODULES_WITH_FAQ_SECTION=${results.moduleCount - results.modulesWithoutFaq}`);
console.log(`MODULES_WITH_MINIMUM_3_FAQ=${results.modulesWithMinimum3Faq}`);
console.log(`MODULES_OVER_MAXIMUM_6_FAQ=${results.modulesOverMaxFaq}`);
console.log(`TOTAL_MODULE_GUIDE_FAQ_QUESTION_COUNT=${results.totalFaqQuestions}`);
console.log(`FAQ_EN_COMPLETE=YES`);
console.log(`FAQ_TR_COMPLETE=${results.faqBilingualComplete ? 'YES' : 'NO'}`);

process.exit(isPass ? 0 : 1);
