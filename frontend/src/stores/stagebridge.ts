import { defineStore } from 'pinia'
import { api } from '../api'
import { activeLocale, i18n } from '../i18n'
import type { AnalysisRequest, AnalysisRun, ApprovedAction, ConnectionInfo, ConnectionPayload } from '../types'

interface State {
  analyses: AnalysisRun[]
  current: AnalysisRun | null
  connections: ConnectionInfo[]
  loading: boolean
  error: string
  externalHostsEnabled: boolean
  credentialStorage: string
  showcaseStep: string
}

export const useStageBridgeStore = defineStore('stagebridge', {
  state: (): State => ({
    analyses: [],
    current: null,
    connections: [],
    loading: false,
    error: '',
    externalHostsEnabled: false,
    credentialStorage: '',
    showcaseStep: ''
  }),
  actions: {
    async fetchAnalyses() {
      this.error = ''
      const { data } = await api.get('/analysis/')
      this.analyses = data.analyses
    },
    async fetchConnections() {
      this.error = ''
      const { data } = await api.get('/connections/')
      this.connections = data.connections
      this.externalHostsEnabled = data.externalHostsEnabled
      this.credentialStorage = data.credentialStorage
    },
    async createConnection(payload: ConnectionPayload) {
      const { data } = await api.post('/connections/', payload)
      await this.fetchConnections()
      return data as ConnectionInfo
    },
    async updateConnection(id: number, payload: Partial<ConnectionPayload>) {
      const { data } = await api.patch(`/connections/${id}/`, payload)
      await this.fetchConnections()
      return data as ConnectionInfo
    },
    async deleteConnection(id: number) {
      await api.delete(`/connections/${id}/`)
      await this.fetchConnections()
    },
    // Проверка произвольных параметров подключения до сохранения профиля (как «Добавить сервер»).
    async testAdhoc(payload: Partial<ConnectionPayload>) {
      const { data } = await api.post('/connections/test/', { ...payload, locale: activeLocale() })
      return data as { ok: boolean; database?: string; user?: string; readOnly?: boolean; serverVersion?: string; schemas?: string[]; message?: string; error?: string }
    },
    async testConnection(connection: ConnectionInfo) {
      try {
        const { data } = connection.is_demo
          ? await api.post('/connections/test/', { target: connection.target })
          : await api.post(`/connections/${connection.id}/test/`)
        return data
      } finally {
        await this.fetchConnections()
      }
    },
    async runAnalysis(request: AnalysisRequest = { mode: 'demo' }) {
      this.loading = true
      this.error = ''
      try {
        const { data } = await api.post('/analysis/run/', { ...request, locale: activeLocale() })
        this.current = data
        await this.fetchAnalyses()
        return data as AnalysisRun
      } catch (error) {
        this.error = error instanceof Error ? error.message : i18n.global.t('errors.analysisFailed')
        throw error
      } finally {
        this.loading = false
      }
    },
    async fetchAnalysis(id: number | string) {
      this.error = ''
      const { data } = await api.get(`/analysis/${id}/`, { params: { locale: activeLocale() } })
      this.current = data
      return data as AnalysisRun
    },
    async generatePlan(id: number) {
      this.loading = true
      try {
        const { data } = await api.post(`/analysis/${id}/ai-plan/`, { locale: activeLocale() })
        this.current = data
        return data as AnalysisRun
      } finally {
        this.loading = false
      }
    },
    async updateActions(id: number, actions: Partial<ApprovedAction>[]) {
      const { data } = await api.patch(`/analysis/${id}/actions/`, { actions, locale: activeLocale() })
      this.current = data.analysis
      return data.analysis as AnalysisRun
    },
    async runDryRun(id: number) {
      this.loading = true
      try {
        const { data } = await api.post(`/analysis/${id}/dry-run/`, { locale: activeLocale() })
        this.current = data
        return data as AnalysisRun
      } catch (error) {
        await this.fetchAnalysis(id)
        throw error
      } finally {
        this.loading = false
      }
    },
    async runMigration(id: number) {
      this.loading = true
      try {
        const { data } = await api.post(`/analysis/${id}/migrate/`, { locale: activeLocale() })
        this.current = data
        return data as AnalysisRun
      } catch (error) {
        await this.fetchAnalysis(id)
        throw error
      } finally {
        this.loading = false
      }
    },
    // Сценарий миграции: live-анализ → ИИ-план → одобрение действий. Миграция — отдельным подтверждённым шагом.
    async prepareScenario(payload: { production_profile_id: number; development_profile_id: number; schemas: string[] }) {
      this.loading = true
      this.error = ''
      const locale = activeLocale()
      try {
        this.showcaseStep = 'analyzing'
        const created = (await api.post('/analysis/run/', { mode: 'live', ...payload, run_preflight: true, locale })).data
        const id = created.id as number

        this.showcaseStep = 'planning'
        await api.post(`/analysis/${id}/ai-plan/`, { locale })

        this.showcaseStep = 'approving'
        const detail = (await api.get(`/analysis/${id}/`, { params: { locale } })).data
        const actions = (detail.actions || []).map((action: { id: number }) => ({ id: action.id, approved: true }))
        if (actions.length) await api.patch(`/analysis/${id}/actions/`, { actions, locale })

        const final = (await api.get(`/analysis/${id}/`, { params: { locale } })).data
        this.current = final
        await this.fetchAnalyses()
        return final as AnalysisRun
      } finally {
        this.loading = false
        this.showcaseStep = ''
      }
    },
    async runScenarioMigration(id: number, stagingProfileId: number) {
      this.loading = true
      this.error = ''
      const locale = activeLocale()
      try {
        this.showcaseStep = 'migrating'
        const { data } = await api.post(`/analysis/${id}/migrate/`, { staging_profile_id: stagingProfileId, confirm: true, locale })
        this.current = data
        return data as AnalysisRun
      } catch (error) {
        await this.fetchAnalysis(id)
        throw error
      } finally {
        this.loading = false
        this.showcaseStep = ''
      }
    },
    // Единый показательный demo-сценарий для судей: анализ → ИИ-план → одобрение → накат.
    async runDemoShowcase() {
      this.loading = true
      this.error = ''
      const locale = activeLocale()
      try {
        this.showcaseStep = 'analyzing'
        const created = (await api.post('/analysis/run/', { mode: 'demo', schemas: ['public'], run_preflight: true, locale })).data
        const id = created.id as number

        this.showcaseStep = 'planning'
        await api.post(`/analysis/${id}/ai-plan/`, { locale })

        this.showcaseStep = 'approving'
        const detail = (await api.get(`/analysis/${id}/`, { params: { locale } })).data
        const actions = (detail.actions || []).map((action: { id: number }) => ({ id: action.id, approved: true }))
        if (actions.length) await api.patch(`/analysis/${id}/actions/`, { actions, locale })

        this.showcaseStep = 'migrating'
        let final
        try {
          final = (await api.post(`/analysis/${id}/dry-run/`, { locale })).data
        } catch {
          // Провал пробного наката всё равно сохраняет отчёт — показываем как есть.
          final = (await api.get(`/analysis/${id}/`, { params: { locale } })).data
        }
        this.current = final
        await this.fetchAnalyses()
        return final as AnalysisRun
      } finally {
        this.loading = false
        this.showcaseStep = ''
      }
    }
  }
})
