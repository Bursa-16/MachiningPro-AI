/**
 * PipelineBreadcrumb — Drawing-to-Process pipeline navigation indicator.
 *
 * Shows the four pipeline steps and highlights the current step.
 * Completed steps are clickable. Future steps are disabled.
 *
 * EPIC_05_CUSTOMER_DEMO_AND_PRODUCTIZATION
 */
import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { usePipeline } from '../context/PipelineContext';
import { useLocale } from '../i18n';

const STEPS = [
  { key: 'drawing',  labelKey: 'breadcrumbDrawing' as const,  path: '/app/planning-quality/drawing-parser' },
  { key: 'features', labelKey: 'breadcrumbFeatures' as const, path: '/app/cad-drawing/cad-features' },
  { key: 'routes',   labelKey: 'breadcrumbRoutes' as const,   path: '/app/planning-quality/process-routes' },
  { key: 'plan',     labelKey: 'breadcrumbPlan' as const,     path: '/app/planning-quality/manufacturing-plan' },
];

const STEP_SLUGS = STEPS.map(s => s.path.split('/').pop() || '');

export function PipelineBreadcrumb() {
  const navigate = useNavigate();
  const location = useLocation();
  const pipeline = usePipeline();
  const { t } = useLocale();

  const currentIdx = STEP_SLUGS.findIndex(slug => location.pathname.includes(slug));
  if (currentIdx === -1) return null;

  return (
    <div className="flex items-center gap-1 text-xs text-gray-400 mb-4 px-1">
      {STEPS.map((step, idx) => {
        const isActive = idx === currentIdx;
        const isDone = idx < currentIdx;
        return (
          <React.Fragment key={step.key}>
            <button
              onClick={() => { if (isDone || isActive) navigate(step.path); }}
              disabled={!isDone && !isActive}
              style={{
                padding: '2px 8px',
                borderRadius: '4px',
                fontSize: '11px',
                fontFamily: 'monospace',
                fontWeight: isActive ? 600 : 400,
                cursor: isDone ? 'pointer' : isActive ? 'default' : 'not-allowed',
                background: isActive ? '#E97824' : 'transparent',
                color: isActive ? '#fff' : isDone ? '#6F8FA3' : '#2A323B',
                border: 'none',
                transition: 'background 120ms, color 120ms',
              }}
            >
              {t(step.labelKey)}
            </button>
            {idx < STEPS.length - 1 && (
              <span style={{ color: '#2A323B', fontSize: '10px' }}>→</span>
            )}
          </React.Fragment>
        );
      })}
      {pipeline.manufacturingPlanId && (
        <span style={{
          marginLeft: '8px',
          fontSize: '10px',
          color: '#4CAF50',
          fontFamily: 'monospace',
        }}>
          Plan: {pipeline.manufacturingPlanId.slice(0, 8)}…
        </span>
      )}
    </div>
  );
}
