import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const locales = ['en', 'ru', 'kk']
const requiredDomains = [
  'common', 'navigation', 'dashboard', 'connections', 'analysis', 'conflicts', 'actions',
  'dryRun', 'reports', 'validation', 'notifications', 'statuses', 'errors', 'ai', 'demo', 'accessibility'
]

const messages = Object.fromEntries(
  locales.map(locale => [locale, JSON.parse(readFileSync(resolve('src/i18n/locales', `${locale}.json`), 'utf8'))])
)

function leafKeys(value, prefix = '') {
  return Object.entries(value).flatMap(([key, item]) => {
    const path = prefix ? `${prefix}.${key}` : key
    return item && typeof item === 'object' && !Array.isArray(item) ? leafKeys(item, path) : [path]
  })
}

const englishKeys = leafKeys(messages.en).sort()
for (const locale of locales) {
  for (const domain of requiredDomains) {
    if (!messages[locale][domain]) throw new Error(`${locale} is missing the ${domain} namespace`)
  }
  const keys = leafKeys(messages[locale]).sort()
  const missing = englishKeys.filter(key => !keys.includes(key))
  const extra = keys.filter(key => !englishKeys.includes(key))
  if (missing.length || extra.length) {
    throw new Error(`${locale} locale mismatch; missing=${missing.join(',')} extra=${extra.join(',')}`)
  }
}

if (messages.kk.language.kk !== 'Қазақша' || messages.ru.language.ru !== 'Русский' || messages.en.language.en !== 'English') {
  throw new Error('Language choices do not match the required display names')
}

console.log(`i18n contract passed: ${locales.length} locales, ${englishKeys.length} keys`)
