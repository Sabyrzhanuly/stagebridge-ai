import { createI18n } from 'vue-i18n'
import en from './locales/en.json'
import kk from './locales/kk.json'
import ru from './locales/ru.json'

export const SUPPORTED_LOCALES = ['kk', 'ru', 'en'] as const
export type AppLocale = (typeof SUPPORTED_LOCALES)[number]
export const LOCALE_STORAGE_KEY = 'stagebridge.locale'

function isLocale(value: unknown): value is AppLocale {
  return typeof value === 'string' && SUPPORTED_LOCALES.includes(value as AppLocale)
}

function savedLocale(): AppLocale {
  try {
    const value = window.localStorage.getItem(LOCALE_STORAGE_KEY)
    if (isLocale(value)) return value
  } catch {
    // Storage can be unavailable in hardened browser contexts.
  }
  return 'ru'
}

export const i18n = createI18n({
  legacy: false,
  locale: savedLocale(),
  fallbackLocale: 'en',
  messages: { en, kk, ru }
})

export function activeLocale(): AppLocale {
  return i18n.global.locale.value as AppLocale
}

export function setLocale(locale: AppLocale): void {
  i18n.global.locale.value = locale
  document.documentElement.lang = locale
  try {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale)
  } catch {
    // The active in-memory locale still works when persistence is unavailable.
  }
}

document.documentElement.lang = activeLocale()
