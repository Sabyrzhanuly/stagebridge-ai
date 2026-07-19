export type TagSeverity = 'success' | 'info' | 'warn' | 'danger' | 'secondary'

export function envSeverity(env: string): TagSeverity {
  const map: Record<string, TagSeverity> = {
    production: 'danger',
    staging: 'warn',
    test: 'info',
    dev: 'success',
  }
  return map[env] ?? 'secondary'
}

import { i18n } from '../i18n'

export function serverActiveLabel(isActive: boolean): string {
  return isActive ? i18n.global.t('common.active') : i18n.global.t('common.inactive')
}
