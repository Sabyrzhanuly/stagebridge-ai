import type { TagSeverity } from './tags'
import { i18n } from '../i18n'

// Локальный хелпер перевода: t() вызывается в момент обращения,
// поэтому реагирует на инициализацию и смену локали.
const t = (k: string) => i18n.global.t(k)

export interface PgErrorHint {
  code: string
  title: string
  hint: string
}

// Правила хранят ключи локализации, а не готовые строки.
// Перевод выполняется при обращении (в classifyPgError), а не при загрузке модуля.
const RULES: Array<{ pattern: RegExp; code: string; titleKey: string; hintKey: string }> = [
  {
    pattern: /too many clients|53300|remaining connection slots/i,
    code: 'too_many_clients',
    titleKey: 'pgHealth.tooManyConnTitle',
    hintKey: 'pgHealth.tooManyConnHint',
  },
  {
    pattern: /no space left on device|disk full|could not extend file|ENOSPC/i,
    code: 'disk_full',
    titleKey: 'pgHealth.diskFullTitle',
    hintKey: 'pgHealth.diskFullHint',
  },
  {
    pattern: /connection refused|could not connect|actively refused/i,
    code: 'unreachable',
    titleKey: 'pgHealth.unreachableTitle',
    hintKey: 'pgHealth.unreachableHint',
  },
  {
    pattern: /timeout|timed out/i,
    code: 'timeout',
    titleKey: 'pgHealth.timeoutTitle',
    hintKey: 'pgHealth.timeoutHint',
  },
  {
    pattern: /password authentication failed|authentication failed|28P01/i,
    code: 'auth_failed',
    titleKey: 'pgHealth.authFailedTitle',
    hintKey: 'pgHealth.authFailedHint',
  },
]

function defaultHint(): PgErrorHint {
  return {
    code: 'generic',
    title: t('pgHealth.genericTitle'),
    hint: t('pgHealth.genericHint'),
  }
}

export function classifyPgError(error: string | null | undefined): PgErrorHint {
  if (!error?.trim()) return defaultHint()
  for (const rule of RULES) {
    if (rule.pattern.test(error)) {
      return {
        code: rule.code,
        title: t(rule.titleKey),
        hint: t(rule.hintKey),
      }
    }
  }
  return {
    ...defaultHint(),
    hint: error.length > 400 ? `${error.slice(0, 400)}…` : error,
  }
}

export function healthStatusLabel(status: string | null | undefined): string {
  const map: Record<string, string> = {
    online: 'Online',
    degraded: t('pgHealth.statusDegraded'),
    offline: 'Offline',
    unknown: t('pgHealth.statusUnknown'),
  }
  return map[status || 'unknown'] || status || '—'
}

export function healthStatusSeverity(status: string | null | undefined): TagSeverity {
  const map: Record<string, TagSeverity> = {
    online: 'success',
    degraded: 'warn',
    offline: 'danger',
    unknown: 'secondary',
  }
  return map[status || 'unknown'] || 'secondary'
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`
}
