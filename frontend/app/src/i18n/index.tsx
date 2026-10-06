import React, { createContext, useContext, useState, useEffect } from 'react'
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

export const LocaleProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [locale, setLocaleState] = useState<Locale>('en')
  const [mounted, setMounted] = useState(false)

  // Initialize from localStorage on mount
  useEffect(() => {
    const savedLocale = localStorage.getItem('machiningpro_locale') as Locale | null
    if (savedLocale && (savedLocale === 'tr' || savedLocale === 'en')) {
      setLocaleState(savedLocale)
    }
    setMounted(true)
  }, [])

  const setLocale = (newLocale: Locale) => {
    setLocaleState(newLocale)
    localStorage.setItem('machiningpro_locale', newLocale)
  }

  const t = (key: keyof TranslationDictionary): string => {
    return translations[locale][key] || key
  }

  if (!mounted) {
    return <>{children}</>
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
