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
            ? 'bg-tp-accent text-white'
            : 'bg-tp-surface-2 text-tp-text-2 hover:bg-tp-surface-3 hover:text-tp-text'
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
            ? 'bg-tp-accent text-white'
            : 'bg-tp-surface-2 text-tp-text-2 hover:bg-tp-surface-3 hover:text-tp-text'
        }`}
      >
        EN
      </button>
    </div>
  )
}
