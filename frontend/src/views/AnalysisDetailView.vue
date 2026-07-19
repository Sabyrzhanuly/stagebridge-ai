<template>
  <div class="page" v-if="analysis">
    <header class="page-header">
      <div>
        <h1>{{ t('analysis.numberedTitle', { id: analysis.id }) }}</h1>
        <p>{{ analysis.mode === 'demo' ? t('analysis.demoTitle') : analysis.title }}</p>
      </div>
      <div class="button-row">
        <button class="secondary-button" @click="downloadReport('markdown')"><Download :size="18" />{{ t('reports.markdown') }}</button>
        <button class="secondary-button" @click="downloadReport('json')"><Download :size="18" />{{ t('reports.json') }}</button>
        <button class="secondary-button" @click="copySql"><Copy :size="18" />{{ t(copied ? 'common.copied' : 'analysis.copySql') }}</button>
        <button class="secondary-button" @click="generatePlan" :disabled="store.loading || !analysis.conflicts.length">
          <Sparkles :size="18" />{{ t('analysis.aiPlan') }}
        </button>
        <button v-if="analysis.mode === 'demo'" class="primary-button" @click="runDryRun" :disabled="store.loading || !analysis.actions.length">
          <ShieldCheck :size="18" />{{ t('analysis.dryRun') }}
        </button>
        <button v-else class="primary-button" @click="runMigration" :disabled="store.loading || !analysis.actions.length">
          <ShieldCheck :size="18" />{{ t('analysis.migrate') }}
        </button>
      </div>
    </header>

    <div class="mode-banner" :class="analysis.mode === 'demo' ? 'demo-mode-note' : 'live-banner'">
      <FlaskConical v-if="analysis.mode === 'demo'" :size="18" />
      <RadioTower v-else :size="18" />
      <strong>{{ t(analysis.mode === 'demo' ? 'analysis.demoData' : 'analysis.liveBanner') }}</strong>
      <span>{{ modeSafetyText }}</span>
    </div>

    <MetricStrip :metrics="metrics" />

    <section class="change-summary">
      <div><span>{{ t('analysis.tablesAdded') }}</span><strong>{{ analysis.metrics.tablesAdded ?? 0 }}</strong></div>
      <div><span>{{ t('analysis.tablesRemoved') }}</span><strong>{{ analysis.metrics.tablesRemoved ?? 0 }}</strong></div>
      <div><span>{{ t('analysis.columnsChanged') }}</span><strong>{{ analysis.metrics.columnsChanged ?? 0 }}</strong></div>
      <div><span>{{ t('analysis.constraintsChanged') }}</span><strong>{{ analysis.metrics.constraintsChanged ?? 0 }}</strong></div>
      <div><span>{{ t('analysis.breakingChanges') }}</span><strong>{{ analysis.metrics.breakingChanges ?? 0 }}</strong></div>
    </section>

    <div class="analysis-grid">
      <ConflictList v-model="filter" :conflicts="analysis.conflicts" :selected-id="selectedId" @select="selectedId = $event" />
      <ConflictDetail :conflict="selectedConflict" />
    </div>

    <section v-if="analysis.remediation_plan" class="panel">
      <div class="panel-header">
        <div>
          <h2>{{ t('ai.recommendation') }}</h2>
          <p>{{ providerLabel }}</p>
        </div>
        <StatusPill :label="analysis.remediation_plan.risk_level" />
      </div>
      <p class="plan-text">{{ planExplanation }}</p>
      <div class="check-list">
        <span v-for="check in validationChecks" :key="check">{{ check }}</span>
      </div>
    </section>

    <ActionApproval
      v-if="analysis.actions.length"
      :actions="analysis.actions"
      @toggle="toggleAction"
      @approve-all="approveAll"
    />

    <DryRunTimeline v-if="analysis.dry_run_logs.length" :logs="analysis.dry_run_logs" :status-label="analysis.dry_run_status" />

    <section v-if="Object.keys(analysis.report || {}).length" class="panel report-panel">
      <div class="panel-header">
        <div>
          <h2>{{ t('reports.final') }}</h2>
          <p>{{ reportLimitation }}</p>
        </div>
        <StatusPill :label="analysis.dry_run_status !== 'not_started' ? analysis.dry_run_status : analysis.status" />
      </div>
      <MetricStrip v-if="analysis.dry_run_status !== 'not_started'" :metrics="reportMetrics" />
    </section>
    <p v-if="operationError" class="error-line" role="alert">{{ operationError }}</p>
  </div>
  <div v-else class="page">
    <div class="empty-state">{{ t('analysis.loading') }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Copy, Download, FlaskConical, RadioTower, ShieldCheck, Sparkles } from '@lucide/vue'
import ActionApproval from '../components/ActionApproval.vue'
import ConflictDetail from '../components/ConflictDetail.vue'
import ConflictList from '../components/ConflictList.vue'
import DryRunTimeline from '../components/DryRunTimeline.vue'
import MetricStrip from '../components/MetricStrip.vue'
import StatusPill from '../components/StatusPill.vue'
import { api } from '../api'
import { useStageBridgeStore } from '../stores/stagebridge'
import { translateAction, translateCategory } from '../i18n/formatters'

const route = useRoute()
const store = useStageBridgeStore()
const { locale, t, tm } = useI18n()
const filter = ref('All')
const selectedId = ref('')
const copied = ref(false)
const operationError = ref('')
watch(locale, () => {
  operationError.value = ''
})

onMounted(async () => {
  const data = await store.fetchAnalysis(route.params.id as string)
  selectedId.value = data.conflicts[0]?.conflict_id || ''
})

const analysis = computed(() => store.current)
watch(
  () => analysis.value?.conflicts,
  conflicts => {
    if (!selectedId.value && conflicts?.length) selectedId.value = conflicts[0].conflict_id
  }
)

const selectedConflict = computed(() => analysis.value?.conflicts.find(conflict => conflict.conflict_id === selectedId.value) ?? null)
const providerLabel = computed(() => {
  if (!analysis.value?.remediation_plan) return ''
  const provider = t(analysis.value.remediation_plan.provider === 'mock' ? 'ai.mockProvider' : 'ai.openaiProvider')
  return t('ai.providerModel', { provider, model: analysis.value.remediation_plan.model || t('ai.modelNotSet') })
})
const modeSafetyText = computed(() =>
  analysis.value?.mode === 'demo'
    ? t('analysis.demoSafety')
    : t('analysis.liveDetailSafety')
)
const planExplanation = computed(() => {
  if (analysis.value?.remediation_plan?.provider === 'mock') return t('ai.mockExplanation')
  if (analysis.value?.locale !== locale.value) return t('ai.regenerateForLocale')
  return analysis.value?.remediation_plan?.explanation || ''
})
const validationChecks = computed(() => {
  if (analysis.value?.remediation_plan?.provider !== 'mock' && analysis.value?.locale === locale.value) return analysis.value?.remediation_plan?.content.validation_checks || []
  const checks = tm('ai.validationChecks')
  return Array.isArray(checks) ? checks.map(String) : []
})
const reportLimitation = computed(() =>
  t(analysis.value?.mode === 'demo' ? 'reports.demoLimitation' : 'reports.liveLimitation')
)
const metrics = computed(() => {
  const m = analysis.value?.metrics ?? {}
  return [
    { label: t('metrics.schemaChanges'), value: m.schemaChangesDetected ?? 0 },
    { label: t('metrics.blockingConflicts'), value: m.blockingConflicts ?? 0 },
    { label: t('metrics.affectedRows'), value: m.affectedRows ?? 0 },
    { label: t('metrics.breakingChanges'), value: m.breakingChanges ?? 0 },
    { label: t('metrics.preflight'), value: t(analysis.value?.run_preflight ? 'common.enabled' : 'common.disabled') }
  ]
})
const reportMetrics = computed(() => {
  const report = analysis.value?.report ?? {}
  return [
    { label: t('metrics.transferredRows'), value: Number(report.transferredRows ?? 0) },
    { label: t('metrics.rejectedRows'), value: Number(report.rejectedRows ?? 0) },
    { label: t('metrics.validationFailures'), value: Number(report.validationFailures ?? 0) }
  ]
})

async function generatePlan() {
  operationError.value = ''
  if (!analysis.value) return
  try {
    await store.generatePlan(analysis.value.id)
  } catch (error) {
    operationError.value = error instanceof Error ? error.message : t('errors.requestFailed')
  }
}

async function toggleAction(id: number, approved: boolean) {
  if (!analysis.value) return
  await store.updateActions(analysis.value.id, [{ id, approved }])
}

async function approveAll() {
  if (!analysis.value) return
  await store.updateActions(
    analysis.value.id,
    analysis.value.actions.map(action => ({ id: action.id, approved: true }))
  )
}

async function runDryRun() {
  if (!analysis.value) return
  try {
    await store.runDryRun(analysis.value.id)
  } catch (error) {
    // Failed demo dry runs persist their report and return 409.
    operationError.value = error instanceof Error ? error.message : t('errors.requestFailed')
  }
}

async function runMigration() {
  if (!analysis.value) return
  operationError.value = ''
  try {
    await store.runMigration(analysis.value.id)
  } catch (error) {
    // Провал наката сохраняет отчёт и возвращает 409 — цель откачена.
    operationError.value = error instanceof Error ? error.message : t('errors.requestFailed')
  }
}

async function downloadReport(format: 'markdown' | 'json') {
  if (!analysis.value) return
  operationError.value = ''
  try {
    const response = await api.get(`/analysis/${analysis.value.id}/report/`, { params: { format }, responseType: 'blob' })
    const extension = format === 'markdown' ? 'md' : 'json'
    const url = URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = url
    link.download = `stagebridge-analysis-${analysis.value.id}.${extension}`
    link.click()
    URL.revokeObjectURL(url)
  } catch {
    operationError.value = t('errors.reportFailed')
  }
}

async function copySql() {
  if (!analysis.value) return
  operationError.value = ''
  try {
    const previews = analysis.value.conflicts.map(conflict => `-- ${translateCategory(conflict.category)}: ${conflict.conflict_id}\n${conflict.sql_preview}`)
    const actionPreviews = analysis.value.actions.map(action => `-- ${translateAction(action.action_type)}\n${action.sql_preview}`)
    await navigator.clipboard.writeText([...previews, ...actionPreviews].join('\n\n'))
    copied.value = true
    window.setTimeout(() => (copied.value = false), 1600)
  } catch {
    operationError.value = t('errors.clipboardFailed')
  }
}
</script>
