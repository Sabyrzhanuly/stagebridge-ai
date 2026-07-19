import { describe, expect, it } from 'vitest'
import { envSeverity, serverActiveLabel } from '../tags'
import { classifyPgError, formatBytes as formatHealthBytes, healthStatusSeverity } from '../pgHealth'
import { formatBytes, formatDate } from '../format'

describe('tags utilities', () => {
  it('maps environments to PrimeVue tag severities', () => {
    expect(envSeverity('production')).toBe('danger')
    expect(envSeverity('staging')).toBe('warn')
    expect(envSeverity('dev')).toBe('success')
    expect(envSeverity('sandbox')).toBe('secondary')
  })

  it('returns localized server active labels', () => {
    expect(serverActiveLabel(true)).toBe('Активен')
    expect(serverActiveLabel(false)).toBe('Неактивен')
  })
})

describe('pgHealth utilities', () => {
  it('classifies common PostgreSQL connection errors', () => {
    expect(classifyPgError('FATAL: too many clients already').code).toBe('too_many_clients')
    expect(classifyPgError('password authentication failed for user main').code).toBe('auth_failed')
    expect(classifyPgError('').code).toBe('generic')
  })

  it('maps health statuses to severities', () => {
    expect(healthStatusSeverity('online')).toBe('success')
    expect(healthStatusSeverity('degraded')).toBe('warn')
    expect(healthStatusSeverity('offline')).toBe('danger')
    expect(healthStatusSeverity('unknown')).toBe('secondary')
  })

  it('formats byte values for monitoring cards', () => {
    expect(formatHealthBytes(512)).toBe('512 B')
    expect(formatHealthBytes(2048)).toBe('2.0 KB')
    expect(formatHealthBytes(5 * 1024 ** 2)).toBe('5.0 MB')
  })
})

describe('format utilities', () => {
  it('formats missing dates as an em dash', () => {
    expect(formatDate(null)).toBe('—')
    expect(formatDate(undefined)).toBe('—')
  })

  it('formats byte values consistently', () => {
    expect(formatBytes(1023)).toBe('1023 B')
    expect(formatBytes(1024)).toBe('1.0 KB')
    expect(formatBytes(1024 * 1024)).toBe('1.0 MB')
    expect(formatBytes(3 * 1024 * 1024 * 1024)).toBe('3.00 GB')
  })
})
