import { createI18n } from 'vue-i18n'
import ru from './locales/ru.json'
import kk from './locales/kk.json'
import en from './locales/en.json'

export const SUPPORTED_LANGS = ['ru', 'kk', 'en'] as const
export type Lang = (typeof SUPPORTED_LANGS)[number]

export const LANG_LABELS: Record<Lang, string> = {
  ru: 'Русский',
  kk: 'Қазақша',
  en: 'English',
}

const STORAGE_KEY = 'pgcc.lang'

function savedLang(): Lang {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    if (v && (SUPPORTED_LANGS as readonly string[]).includes(v)) return v as Lang
  } catch {
    /* storage unavailable */
  }
  return 'ru'
}

export const i18n = createI18n({
  legacy: false,
  locale: savedLang(),
  fallbackLocale: 'en',
  messages: { ru, kk, en },
})

export function currentLang(): Lang {
  return i18n.global.locale.value as Lang
}

export function setLang(lang: Lang): void {
  i18n.global.locale.value = lang
  try {
    localStorage.setItem(STORAGE_KEY, lang)
  } catch {
    /* ignore */
  }
  document.documentElement.lang = lang
}

document.documentElement.lang = savedLang()
