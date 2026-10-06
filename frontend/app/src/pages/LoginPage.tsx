/**
 * MachiningPro AI — LoginPage
 * VISUAL-IDENTITY-02A-R5
 *
 * Two-column engineering composition:
 *   LEFT  ~58% — brand identity + CNC milling illustration
 *   RIGHT ~42% — authentication workspace
 *
 * i18n: uses EXISTING canonical useLocale() from ../i18n
 *       (LocaleProvider is in App.tsx — NOT re-created here)
 *
 * MUST NOT: create a second LocaleProvider, locale.ts, or parallel context.
 *
 * R3 corrections (carried forward):
 *   - SVG labels: SPINDLE/PROCESS/ACTIVE/TOOL replaced with language-neutral symbols
 *
 * R5 corrections:
 *   - Backend error text is classified locally and NEVER rendered raw.
 *   - Credential/unauthorized patterns map to t('invalidCredentials').
 *   - Configuration/network/unknown failures map to t('authenticationFailed').
 *   - The Windows apply script verifies every t('...') key used here exists in
 *     BOTH canonical en.ts and tr.ts before any repository mutation.
 *   - SVG runtime labels remain language-neutral engineering notation.
 */

import { useState, type FormEvent } from 'react'
import { useLocale } from '../i18n'
import { LanguageToggle } from '../components/LanguageToggle'

/* ─────────────────────────────────────────────────────────────────────────────
   Localized error mapping
   Raw backend text is inspected ONLY here for classification and is never
   propagated to rendered state.  The R5 apply script verifies that every
   translation key used by this file exists in BOTH canonical locale files.
────────────────────────────────────────────────────────────────────────────── */
type TranslationFn = (key: any) => string

function localizeAuthError(err: any, t: TranslationFn): string {
  const raw = (err?.detail || err?.message || '') as string
  const normalized = raw.toLowerCase()

  const credentialPatterns = [
    'invalid credential',
    'incorrect username',
    'incorrect password',
    'user not found',
    'unauthorized',
    'not authorized',
    'status 401',
    '401 unauthorized',
  ]

  if (credentialPatterns.some(pattern => normalized.includes(pattern))) {
    return t('invalidCredentials')
  }

  // Configuration, network, backend, and unknown failures use one generic
  // localized message. Raw backend strings are intentionally never returned.
  return t('authenticationFailed')
}

/* ─────────────────────────────────────────────────────────────────────────────
   CNC Milling Engineering Illustration
   Palette: graphite #0B0D10, steel #6F8FA3, orange #E97824
   Contents: machine table, aluminium workpiece, end-mill, cutting flutes,
             chip formation, spindle housing, toolpath arc, XYZ axes,
             dimension annotations (280.00 mm width, 18.0 mm depth),
             feed arrow (Vf), process status readout, tool data panel.

   R3: All English word labels removed from SVG.
       Replaced with language-neutral engineering symbols:
         SPINDLE → ⌀ (diameter symbol, universally understood)
         PROCESS → ▶ (run indicator, language-neutral)
         ACTIVE  → ● (status dot only — already a symbol)
         TOOL    → T (ISO tool designation, language-neutral)
────────────────────────────────────────────────────────────────────────────── */
function MachiningSVG() {
  return (
    <svg
      viewBox="0 0 520 340"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      style={{ width: '100%', height: '100%', display: 'block' }}
    >
      {/* ── Technical grid ── */}
      <defs>
        <pattern id="grid" width="26" height="26" patternUnits="userSpaceOnUse">
          <path d="M 26 0 L 0 0 0 26" fill="none" stroke="#1E2530" strokeWidth="0.5" />
        </pattern>
        <linearGradient id="tableGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor="#181E26" />
          <stop offset="100%" stopColor="#0F1318" />
        </linearGradient>
        <linearGradient id="wpGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor="#9EB8C4" />
          <stop offset="40%"  stopColor="#7A9CAD" />
          <stop offset="100%" stopColor="#5A7A8B" />
        </linearGradient>
        <linearGradient id="millGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor="#8AA4B0" />
          <stop offset="100%" stopColor="#4E6A78" />
        </linearGradient>
        <linearGradient id="spindleGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor="#2A3542" />
          <stop offset="100%" stopColor="#1C2530" />
        </linearGradient>
        <filter id="glow">
          <feGaussianBlur stdDeviation="2" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>

      {/* Background */}
      <rect width="520" height="340" fill="#0B0D10" />
      <rect width="520" height="340" fill="url(#grid)" opacity="0.6" />

      {/* ── Machine table ── */}
      <rect x="40" y="210" width="440" height="22" rx="2" fill="url(#tableGrad)"
            stroke="#2A323B" strokeWidth="1" />
      {/* T-slots */}
      {[80, 140, 200, 260, 320, 380, 440].map(x => (
        <rect key={x} x={x} y="210" width="8" height="22" rx="1"
              fill="#0B0D10" opacity="0.7" />
      ))}
      {/* Table surface shine */}
      <rect x="40" y="210" width="440" height="3" rx="1"
            fill="rgba(255,255,255,0.06)" />

      {/* ── Aluminium workpiece ── */}
      <rect x="110" y="165" width="280" height="47" rx="2" fill="url(#wpGrad)"
            stroke="#6F8FA3" strokeWidth="1" />
      {/* Machined top face (cut region) */}
      <rect x="110" y="165" width="280" height="18" rx="2"
            fill="#B4CDD8" opacity="0.55" />
      {/* Side face shading */}
      <rect x="110" y="183" width="280" height="29" rx="0"
            fill="rgba(0,0,0,0.18)" />
      {/* Workpiece top edge highlight */}
      <line x1="110" y1="165" x2="390" y2="165"
            stroke="rgba(255,255,255,0.30)" strokeWidth="1" />

      {/* ── Chip formation ── */}
      {[250, 258, 265, 272].map((x, i) => (
        <path key={i}
          d={`M ${x} 165 Q ${x + 4 + i} ${155 - i * 2} ${x + 8 + i * 2} ${150 - i * 3}`}
          fill="none" stroke="#E97824" strokeWidth="1.2" opacity={0.7 - i * 0.12} />
      ))}

      {/* ── Toolpath arc ── */}
      <path d="M 110 165 Q 250 130 390 165"
            fill="none" stroke="#E97824" strokeWidth="1"
            strokeDasharray="6 4" opacity="0.5" />
      {/* Toolpath direction arrow */}
      <polygon points="383,160 390,165 383,170"
               fill="#E97824" opacity="0.6" />

      {/* ── End-mill body ── */}
      <rect x="237" y="60" width="26" height="108" rx="2"
            fill="url(#millGrad)" stroke="#6F8FA3" strokeWidth="0.8" />
      {/* Mill shaft */}
      <rect x="243" y="30" width="14" height="34" rx="1"
            fill="#5A7A8B" stroke="#4A6878" strokeWidth="0.5" />
      {/* Cutting flutes */}
      {[0, 1, 2, 3].map(i => (
        <line key={i}
          x1={240 + i * 3} y1="168" x2={238 + i * 3} y2="60"
          stroke="#4A6A7A" strokeWidth="1.5" opacity="0.8" />
      ))}
      {/* Flute tips */}
      {[0, 1, 2, 3].map(i => (
        <ellipse key={i} cx={240.5 + i * 3} cy="168" rx="1" ry="1.5"
                 fill="#8AACBA" />
      ))}
      {/* Mill center line */}
      <line x1="250" y1="30" x2="250" y2="168"
            stroke="#E97824" strokeWidth="0.5"
            strokeDasharray="3 3" opacity="0.4" />

      {/* ── Spindle housing ── */}
      <rect x="224" y="10" width="52" height="24" rx="3"
            fill="url(#spindleGrad)" stroke="#2A3A4A" strokeWidth="1" />
      {/* Spindle bolt holes */}
      {[232, 260, 268].map(x => (
        <circle key={x} cx={x} cy="22" r="2" fill="#1C2530" stroke="#3A4A5A"
                strokeWidth="0.5" />
      ))}
      {/* Spindle label — language-neutral: ⌀ (ISO diameter symbol) */}
      <text x="250" y="20" textAnchor="middle"
            fill="#6F8FA3" fontSize="8" fontFamily="monospace" letterSpacing="0.5">
        ⌀16
      </text>

      {/* ── Rotation indicator ── */}
      <path d="M 250 42 m -14 0 a 14 14 0 1 1 28 0"
            fill="none" stroke="#6F8FA3" strokeWidth="1.2"
            strokeDasharray="4 3" opacity="0.7" />
      <polygon points="236,42 232,38 240,38" fill="#6F8FA3" opacity="0.7" />
      <text x="270" y="44" fill="#4E5F6A" fontSize="6" fontFamily="monospace">
        n=4800rpm
      </text>

      {/* ── Dimension annotations ── */}
      {/* Width dimension */}
      <line x1="110" y1="240" x2="390" y2="240"
            stroke="#4E5F6A" strokeWidth="0.7" />
      <line x1="110" y1="236" x2="110" y2="244"
            stroke="#4E5F6A" strokeWidth="0.7" />
      <line x1="390" y1="236" x2="390" y2="244"
            stroke="#4E5F6A" strokeWidth="0.7" />
      <text x="250" y="252" textAnchor="middle"
            fill="#6F8FA3" fontSize="7.5" fontFamily="monospace">
        280.00 mm
      </text>

      {/* Depth dimension */}
      <line x1="400" y1="165" x2="400" y2="212"
            stroke="#4E5F6A" strokeWidth="0.7" />
      <line x1="396" y1="165" x2="404" y2="165"
            stroke="#4E5F6A" strokeWidth="0.7" />
      <line x1="396" y1="212" x2="404" y2="212"
            stroke="#4E5F6A" strokeWidth="0.7" />
      <text x="416" y="191" textAnchor="middle"
            fill="#6F8FA3" fontSize="7.5" fontFamily="monospace">
        18.0 mm
      </text>

      {/* ── Feed vector ── */}
      <line x1="60" y1="165" x2="108" y2="165"
            stroke="#E97824" strokeWidth="1.5" markerEnd="url(#arrow)" />
      <defs>
        <marker id="arrow" markerWidth="7" markerHeight="7"
                refX="5" refY="3.5" orient="auto">
          <polygon points="0 0, 7 3.5, 0 7" fill="#E97824" />
        </marker>
      </defs>
      <text x="84" y="158" textAnchor="middle"
            fill="#E97824" fontSize="7" fontFamily="monospace">
        Vf
      </text>

      {/* ── XYZ Axes ── */}
      <g transform="translate(60, 290)">
        {/* Z up */}
        <line x1="0" y1="0" x2="0" y2="-28" stroke="#6F8FA3" strokeWidth="1.2" />
        <polygon points="-3,-28 0,-34 3,-28" fill="#6F8FA3" />
        <text x="4" y="-28" fill="#6F8FA3" fontSize="7" fontFamily="monospace">Z</text>
        {/* X right */}
        <line x1="0" y1="0" x2="28" y2="0" stroke="#E97824" strokeWidth="1.2" />
        <polygon points="28,-3 34,0 28,3" fill="#E97824" />
        <text x="32" y="4" fill="#E97824" fontSize="7" fontFamily="monospace">X</text>
        {/* Y diagonal */}
        <line x1="0" y1="0" x2="-16" y2="14" stroke="#9ABAAA" strokeWidth="1.2" />
        <polygon points="-14,13 -20,18 -18,11" fill="#9ABAAA" />
        <text x="-24" y="20" fill="#9ABAAA" fontSize="7" fontFamily="monospace">Y</text>
        {/* Origin */}
        <circle cx="0" cy="0" r="2" fill="#4E5F6A" />
      </g>

      {/* ── Process readout panel ── */}
      {/* Header: language-neutral run-state symbol ▶ */}
      <rect x="410" y="60" width="98" height="100" rx="3"
            fill="#0F1318" stroke="#2A323B" strokeWidth="0.8" />
      <text x="459" y="74" textAnchor="middle"
            fill="#4E5F6A" fontSize="8" fontFamily="monospace" letterSpacing="0.5">
        ▶
      </text>
      <line x1="414" y1="78" x2="504" y2="78"
            stroke="#2A323B" strokeWidth="0.5" />
      {[
        ['Vc',  '120 m/min'],
        ['fz',  '0.08 mm'],
        ['ap',  '18.0 mm'],
        ['ae',  '12.0 mm'],
        ['MRR', '2.76 cm³/s'],
      ].map(([label, val], i) => (
        <g key={label} transform={`translate(0, ${i * 15})`}>
          <text x="418" y="91" fill="#4E5F6A" fontSize="6.5" fontFamily="monospace">
            {label}
          </text>
          <text x="504" y="91" textAnchor="end"
                fill="#9ABAAA" fontSize="6.5" fontFamily="monospace">
            {val}
          </text>
        </g>
      ))}
      <line x1="414" y1="153" x2="504" y2="153"
            stroke="#2A323B" strokeWidth="0.5" />
      {/* Status: dot symbol only — language-neutral */}
      <text x="418" y="162" fill="#E97824" fontSize="6" fontFamily="monospace">
        ●
      </text>

      {/* ── Tool data panel ── */}
      {/* Header: T (ISO tool designation) — language-neutral */}
      <rect x="410" y="172" width="98" height="68" rx="3"
            fill="#0F1318" stroke="#2A323B" strokeWidth="0.8" />
      <text x="459" y="184" textAnchor="middle"
            fill="#4E5F6A" fontSize="7" fontFamily="monospace" letterSpacing="1">
        T1
      </text>
      <line x1="414" y1="188" x2="504" y2="188"
            stroke="#2A323B" strokeWidth="0.5" />
      {[
        ['D', '16 mm'],
        ['Z', '4 fl.'],
        ['Mat', 'WC-Co'],
      ].map(([label, val], i) => (
        <g key={label} transform={`translate(0, ${i * 13})`}>
          <text x="418" y="200" fill="#4E5F6A" fontSize="6.5" fontFamily="monospace">
            {label}
          </text>
          <text x="504" y="200" textAnchor="end"
                fill="#9ABAAA" fontSize="6.5" fontFamily="monospace">
            {val}
          </text>
        </g>
      ))}
    </svg>
  )
}

/* ─────────────────────────────────────────────────────────────────────────────
   LoginPage
────────────────────────────────────────────────────────────────────────────── */
export default function LoginPage({
  onLogin,
}: {
  onLogin: (u: string, p: string) => Promise<any>
}) {
  const { locale, t } = useLocale()  // ← CANONICAL — no second locale system

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await onLogin(username, password)
    } catch (err: any) {
      // R5: localizeAuthError() owns all raw backend inspection.
      // The rendered error state receives only a translated message.
      setError(localizeAuthError(err, t))
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      {/* ── Scoped styles ──────────────────────────────────────────────── */}
      <style>{`
        /* ── Outer shell ─────────────────────────────────────────────── */
        .mp-login-outer {
          display: flex;
          min-height: 100vh;
          background: var(--color-mp-bg-0, #0B0D10);
          overflow: hidden;
        }

        /* ── LEFT panel — brand + engineering illustration ────────────── */
        .mp-login-left {
          flex: 0 0 58%;
          display: flex;
          flex-direction: column;
          padding: 40px 48px;
          background: var(--color-mp-bg-1, #10141A);
          border-right: 1px solid var(--color-mp-border, #2A323B);
          position: relative;
          overflow: hidden;
        }

        /* Subtle industrial grain texture overlay */
        .mp-login-left::before {
          content: '';
          position: absolute;
          inset: 0;
          background: repeating-linear-gradient(
            90deg,
            transparent,
            transparent 39px,
            rgba(42,50,59,0.18) 39px,
            rgba(42,50,59,0.18) 40px
          );
          pointer-events: none;
        }

        /* ── Logo plate — machined satin-steel inset ─────────────────── */
        .mp-login-logo-plate {
          display: inline-flex;
          align-items: center;
          background: linear-gradient(160deg, #CAD3D8 0%, #B0BCBF 40%, #9CAAB0 100%);
          border-radius: 3px;
          padding: 8px 14px;
          box-shadow:
            inset 0 1px 2px rgba(255,255,255,0.22),
            inset 0 -1px 2px rgba(0,0,0,0.20),
            0 1px 4px rgba(0,0,0,0.40);
          width: fit-content;
          margin-bottom: 6px;
        }
        .mp-login-logo-plate img {
          height: 32px;
          width: auto;
          max-width: 280px;
          object-fit: contain;
          display: block;
        }

        /* ── Header row — logo + lang toggle ────────────────────────── */
        .mp-login-header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          margin-bottom: 28px;
          position: relative;
          z-index: 1;
        }

        .mp-login-badge {
          display: inline-block;
          font-size: 9px;
          font-family: monospace;
          letter-spacing: 0.12em;
          color: var(--color-mp-orange, #E97824);
          border: 1px solid var(--color-mp-orange, #E97824);
          border-radius: 2px;
          padding: 1px 5px;
          opacity: 0.75;
          margin-top: 6px;
        }

        /* ── Engineering title block ─────────────────────────────────── */
        .mp-login-title-block {
          position: relative;
          z-index: 1;
          margin-bottom: 24px;
        }
        .mp-login-title-block h1 {
          font-size: 18px;
          font-weight: 700;
          color: var(--color-mp-text-1, #E7EBEF);
          margin: 0 0 4px 0;
          line-height: 1.25;
          letter-spacing: -0.01em;
        }
        .mp-login-title-block p {
          font-size: 12px;
          color: var(--color-mp-steel, #6F8FA3);
          margin: 0;
          font-family: monospace;
          letter-spacing: 0.04em;
        }

        /* ── SVG illustration wrapper ────────────────────────────────── */
        .mp-login-svg-wrapper {
          flex: 1;
          position: relative;
          z-index: 1;
          min-height: 0;
          display: flex;
          align-items: center;
        }

        /* ── RIGHT panel — authentication workspace ───────────────────── */
        .mp-login-right {
          flex: 0 0 42%;
          display: flex;
          flex-direction: column;
          justify-content: center;
          padding: 48px 52px;
          background: var(--color-mp-bg-0, #0B0D10);
        }

        /* ── Auth workspace heading ──────────────────────────────────── */
        .mp-login-workspace-label {
          font-size: 9px;
          font-family: monospace;
          letter-spacing: 0.14em;
          color: var(--color-mp-text-3, #4E5F6A);
          text-transform: uppercase;
          margin-bottom: 20px;
        }

        /* ── Form field ──────────────────────────────────────────────── */
        .mp-login-field {
          margin-bottom: 16px;
        }
        .mp-login-label {
          display: block;
          font-size: 11px;
          color: var(--color-mp-text-2, #9AA6B2);
          margin-bottom: 5px;
          font-family: monospace;
          letter-spacing: 0.03em;
        }
        .mp-login-input {
          width: 100%;
          background: var(--color-mp-surface-1, #141920);
          border: 1px solid var(--color-mp-border, #2A323B);
          border-radius: 3px;
          color: var(--color-mp-text-1, #E7EBEF);
          font-size: 14px;
          padding: 8px 12px;
          outline: none;
          box-sizing: border-box;
          transition: border-color 120ms;
          font-family: inherit;
        }
        .mp-login-input:focus {
          border-color: var(--color-mp-steel, #6F8FA3);
        }
        .mp-login-input::placeholder {
          color: var(--color-mp-text-3, #4E5F6A);
        }

        /* ── Submit button ───────────────────────────────────────────── */
        .mp-login-btn {
          width: 100%;
          background: var(--color-mp-orange, #E97824);
          color: #fff;
          border: none;
          border-radius: 3px;
          font-size: 14px;
          font-weight: 600;
          padding: 10px 0;
          cursor: pointer;
          transition: background 120ms, box-shadow 120ms;
          margin-top: 8px;
          letter-spacing: 0.02em;
          font-family: inherit;
        }
        .mp-login-btn:hover:not(:disabled) {
          background: #D4671A;
        }
        .mp-login-btn:active:not(:disabled) {
          background: #BF5B14;
        }
        .mp-login-btn:focus-visible {
          outline: 2px solid var(--color-mp-orange, #E97824);
          outline-offset: 2px;
        }
        .mp-login-btn:disabled {
          background: var(--color-mp-steel, #6F8FA3);
          opacity: 0.5;
          cursor: not-allowed;
        }

        /* ── Error panel ─────────────────────────────────────────────── */
        .mp-login-error {
          display: flex;
          align-items: center;
          gap: 8px;
          background: rgba(198,90,90,0.10);
          border: 1px solid rgba(198,90,90,0.30);
          border-radius: 3px;
          padding: 8px 12px;
          margin-top: 12px;
        }
        .mp-login-error-dot {
          width: 5px;
          height: 5px;
          border-radius: 50%;
          background: var(--color-mp-error, #C65A5A);
          flex-shrink: 0;
        }
        .mp-login-error-text {
          font-size: 11px;
          color: var(--color-mp-error, #C65A5A);
          font-family: monospace;
        }

        /* ── Footer ──────────────────────────────────────────────────── */
        .mp-login-footer {
          font-size: 9px;
          font-family: monospace;
          color: var(--color-mp-text-3, #4E5F6A);
          margin-top: 28px;
          letter-spacing: 0.06em;
        }

        /* ── Responsive: 1024px — 52/48 ─────────────────────────────── */
        @media (max-width: 1023px) {
          .mp-login-left  { flex: 0 0 52%; padding: 32px 36px; }
          .mp-login-right { flex: 0 0 48%; padding: 36px 40px; }
        }

        /* ── Responsive: <768px — single column ─────────────────────── */
        @media (max-width: 767px) {
          .mp-login-outer {
            flex-direction: column;
          }
          .mp-login-left {
            flex: none;
            padding: 28px 24px 20px;
            border-right: none;
            border-bottom: 1px solid var(--color-mp-border, #2A323B);
          }
          .mp-login-svg-wrapper {
            max-height: 180px;
          }
          .mp-login-right {
            flex: none;
            padding: 28px 24px;
          }
          .mp-login-logo-plate img {
            height: 26px;
            max-width: 200px;
          }
        }
      `}</style>

      {/* ── Layout ─────────────────────────────────────────────────────── */}
      <div className="mp-login-outer">

        {/* ── LEFT — engineering brand panel ──────────────────────────── */}
        <div className="mp-login-left">
          <div className="mp-login-header">
            {/* Authoritative horizontal master logo on machined-steel inset */}
            <div>
              <div className="mp-login-logo-plate">
                <img
                  src="/branding/machiningpro-ai-logo.png"
                  alt="MachiningPro AI"
                />
              </div>
              <span className="mp-login-badge">
                {t('alphaEngineeringPreview')}
              </span>
            </div>

            {/* Language toggle — uses EXISTING canonical LanguageToggle */}
            <LanguageToggle />
          </div>

          <div className="mp-login-title-block">
            <h1>{t('workstationTitle')}</h1>
            <p>{t('workstationSubtitle')}</p>
          </div>

          {/* CNC milling engineering illustration */}
          <div className="mp-login-svg-wrapper">
            <MachiningSVG />
          </div>
        </div>

        {/* ── RIGHT — authentication workspace ────────────────────────── */}
        <div className="mp-login-right">
          <div className="mp-login-workspace-label">
            {locale === 'tr' ? 'GİRİŞ ÇALIŞMA ALANI' : 'AUTHENTICATION WORKSPACE'}
          </div>

          <form onSubmit={submit} noValidate>
            {/* Username */}
            <div className="mp-login-field">
              <label className="mp-login-label" htmlFor="mp-username">
                {t('username')}
              </label>
              <input
                id="mp-username"
                className="mp-login-input"
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                autoComplete="username"
                autoFocus
                required
                aria-label={t('username')}
              />
            </div>

            {/* Password */}
            <div className="mp-login-field">
              <label className="mp-login-label" htmlFor="mp-password">
                {t('password')}
              </label>
              <input
                id="mp-password"
                className="mp-login-input"
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                autoComplete="current-password"
                required
                aria-label={t('password')}
              />
            </div>

            {/* Submit */}
            <button
              className="mp-login-btn"
              type="submit"
              disabled={loading}
            >
              {loading
                ? (locale === 'tr' ? 'Giriş yapılıyor…' : 'Signing in…')
                : t('signIn')}
            </button>

            {/* Error — always localized via localizeAuthError() */}
            {error && (
              <div className="mp-login-error" role="alert" aria-live="polite">
                <div className="mp-login-error-dot" />
                <span className="mp-login-error-text">{error}</span>
              </div>
            )}
          </form>

          <div className="mp-login-footer">
            MachiningPro AI — {locale === 'tr'
              ? 'mühendislik araştırma önizlemesi'
              : 'engineering research preview'}
          </div>
        </div>
      </div>
    </>
  )
}
