import React from 'react'
import { useLocale } from '../i18n'

export const LanguageToggle: React.FC<{ className?: string }> = ({ className = '' }) => {
  const { locale, setLocale } = useLocale()

  return (
    <div className={`flex gap-1 items-center ${className}`}>
      <button
        onClick={() => setLocale('tr')}
        aria-pressed={locale === 'tr'}
        aria-label="Switch to Turkish"
        title="Türkçeye geç"
        className={`px-2.5 py-1 rounded text-xs font-semibold transition-colors ${
          locale === 'tr'
            ? 'bg-mp-orange text-white'
            : 'bg-mp-surface-hover text-mp-text-2 hover:bg-mp-surface-1'
        }`}
      >
        TR
      </button>
      <button
        onClick={() => setLocale('en')}
        aria-pressed={locale === 'en'}
        aria-label="Switch to English"
        title="Switch to English"
        className={`px-2.5 py-1 rounded text-xs font-semibold transition-colors ${
          locale === 'en'
            ? 'bg-mp-orange text-white'
            : 'bg-mp-surface-hover text-mp-text-2 hover:bg-mp-surface-1'
        }`}
      >
        EN
      </button>
    </div>
  )
}
