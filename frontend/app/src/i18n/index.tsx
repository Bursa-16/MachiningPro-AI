import React, { createContext, useContext, useState } from 'react'
import type { Locale, TranslationDictionary } from './types'
import type { ReactNode } from 'react'
import { enTranslations } from './en'
import { trTranslations } from './tr'

const translations: Record<Locale, TranslationDictionary> = {
  en: enTranslations,
  tr: trTranslations,
}

interface LocaleContextType {
  locale: Locale
  setLocale: (locale: Locale) => void
  t: (key: keyof TranslationDictionary) => string
}

const LocaleContext = createContext<LocaleContextType | undefined>(undefined)

const readSavedLocale = (): Locale => {
  try {
    const saved = localStorage.getItem('machiningpro_locale')
    if (saved === 'tr' || saved === 'en') return saved
  } catch {
    // storage unavailable: fall through to default
  }
  return 'en'
}

export const LocaleProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  // Read synchronously so the context exists on the very first render.
  const [locale, setLocaleState] = useState<Locale>(readSavedLocale)

  const setLocale = (newLocale: Locale) => {
    setLocaleState(newLocale)
    try {
      localStorage.setItem('machiningpro_locale', newLocale)
    } catch {
      // storage unavailable: keep in-memory locale only
    }
  }

  const t = (key: keyof TranslationDictionary): string => {
    return translations[locale][key] || key
  }

  return (
    <LocaleContext.Provider value={{ locale, setLocale, t }}>
      {children}
    </LocaleContext.Provider>
  )
}

export const useLocale = (): LocaleContextType => {
  const context = useContext(LocaleContext)
  if (!context) {
    throw new Error('useLocale must be used within a LocaleProvider')
  }
  return context
}
