import axios from 'axios'
import { activeLocale, i18n } from './i18n'

function errorText(value: unknown): string {
  if (typeof value === 'string') return value
  if (Array.isArray(value)) return value.map(errorText).filter(Boolean).join(' ')
  if (value && typeof value === 'object') return Object.values(value).map(errorText).filter(Boolean).join(' ')
  return ''
}

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 20000,
  headers: { 'Content-Type': 'application/json' }
})

api.interceptors.request.use(config => {
  config.headers.set('Accept-Language', activeLocale())
  return config
})

api.interceptors.response.use(
  response => response,
  error => {
    const payload = error.response?.data
    const fieldErrors = errorText(payload?.field_errors)
    const message = payload?.error || payload?.detail || fieldErrors || error.message || i18n.global.t('errors.requestFailed')
    return Promise.reject(new Error(message))
  }
)
