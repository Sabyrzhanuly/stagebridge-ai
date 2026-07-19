import { i18n } from './index'

function hasKey(key: string): boolean {
  return i18n.global.te(key)
}

export function translateCode(namespace: string, value: string | null | undefined): string {
  if (!value) return i18n.global.t('common.unknown')
  const normalized = value.trim().toLowerCase().replaceAll(' ', '_').replaceAll('-', '_')
  const key = `${namespace}.${normalized}`
  return hasKey(key) ? i18n.global.t(key) : value.replaceAll('_', ' ')
}

export function translateStatus(value: string): string {
  return translateCode('statuses', value)
}

export function translateCategory(value: string): string {
  return translateCode('conflicts.categories', value)
}

export function translateAction(value: string): string {
  return translateCode('actions.types', value)
}

export function translateDryRunStep(value: string): string {
  return translateCode('dryRun.steps', value)
}

export function translateRole(value: string): string {
  return translateCode('common', value)
}
