<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1>{{ t('scenario.title') }}</h1>
        <p>{{ t('scenario.subtitle') }}</p>
      </div>
    </header>

    <!-- Шаг 1: источник и цель -->
    <section class="panel">
      <div class="panel-header">
        <div>
          <h2><span class="step-badge">1</span>{{ t('scenario.step1') }}</h2>
          <p>{{ t('scenario.step1Hint') }}</p>
        </div>
      </div>
      <p v-if="!hasProfiles" class="hint-line">
        {{ t('scenario.needProfiles') }}
        <RouterLink to="/connections">{{ t('navigation.connections') }}</RouterLink>
      </p>
      <div class="scenario-grid">
        <label>
          <span>{{ t('scenario.source') }}</span>
          <select v-model="sourceId">
            <option :value="0" disabled>{{ t('scenario.selectSource') }}</option>
            <option v-for="p in productionProfiles" :key="p.id" :value="p.id">{{ p.name }} — {{ p.database }}</option>
          </select>
        </label>
        <label>
          <span>{{ t('scenario.development') }}</span>
          <select v-model="devId">
            <option :value="0" disabled>{{ t('scenario.selectDev') }}</option>
            <option v-for="p in developmentProfiles" :key="p.id" :value="p.id">{{ p.name }} — {{ p.database }}</option>
          </select>
        </label>
        <label>
          <span>{{ t('scenario.target') }}</span>
          <select v-model="targetId">
            <option :value="0" disabled>{{ t('scenario.selectTarget') }}</option>
            <option v-for="p in stagingProfiles" :key="p.id" :value="p.id">{{ p.name }} — {{ p.database }}</option>
          </select>
        </label>
        <label>
          <span>{{ t('scenario.schemas') }}</span>
          <input v-model="schemasInput" :placeholder="t('scenario.schemasHint')" />
        </label>
      </div>
      <div class="button-row">
        <button class="primary-button" :disabled="!canAnalyze || store.loading" @click="analyze">
          <Search :size="18" />
          {{ store.loading && store.showcaseStep ? t(`dashboard.demoStep.${store.showcaseStep}`) : t('scenario.analyze') }}
        </button>
      </div>
    </section>

    <!-- Шаг 2: анализ и ИИ-план -->
    <section v-if="analysis" class="panel">
      <div class="panel-header">
        <div>
          <h2><span class="step-badge">2</span>{{ t('scenario.step2') }}</h2>
          <p>{{ analysis.title }}</p>
        </div>
        <StatusPill v-if="analysis.remediation_plan" :label="analysis.remediation_plan.risk_level" />
      </div>
      <MetricStrip :metrics="analysisMetrics" />
      <p v-if="analysis.remediation_plan" class="plan-text">{{ planExplanation }}</p>
      <p class="hint-line">{{ t('scenario.actionsReady', { count: analysis.actions.length }) }}</p>
    </section>

    <!-- Шаг 3: миграция в staging -->
    <section v-if="analysis" class="panel">
      <div class="panel-header">
        <div>
          <h2><span class="step-badge">3</span>{{ t('scenario.step3') }}</h2>
          <p>{{ t('scenario.step3Hint') }}</p>
        </div>
      </div>
      <div class="write-warning">
        <ShieldAlert :size="18" />
        <label class="confirm-check">
          <input type="checkbox" v-model="confirmWrite" />
          <span>{{ t('scenario.confirmWrite', { db: targetDb }) }}</span>
        </label>
      </div>
      <div class="button-row">
        <button class="primary-button" :disabled="!confirmWrite || store.loading" @click="migrate">
          <DatabaseZap :size="18" />
          {{ store.loading && store.showcaseStep === 'migrating' ? t('dashboard.demoStep.migrating') : t('scenario.runMigration') }}
        </button>
      </div>
    </section>

    <!-- Шаг 4: verify-результат -->
    <section v-if="verifyRows.length" class="panel">
      <div class="panel-header">
        <div>
          <h2><span class="step-badge">4</span>{{ t('scenario.step4') }}</h2>
          <p>{{ t('scenario.step4Hint', { db: reportTarget }) }}</p>
        </div>
        <StatusPill :label="analysis?.dry_run_status || ''" />
      </div>
      <MetricStrip :metrics="verifyMetrics" />
      <div class="verify-table">
        <div class="verify-head">
          <span>{{ t('scenario.verifyTable') }}</span>
          <span>{{ t('scenario.verifySource') }}</span>
          <span>{{ t('scenario.verifyMoved') }}</span>
          <span>{{ t('scenario.verifyRejected') }}</span>
          <span>{{ t('scenario.verifyTarget') }}</span>
        </div>
        <div v-for="row in verifyRows" :key="row.table" class="verify-row">
          <span class="mono">{{ row.table }}</span>
          <span>{{ row.source }}</span>
          <span class="ok">{{ row.moved }}</span>
          <span :class="{ warn: row.rejected > 0 }">{{ row.rejected }}</span>
          <span>{{ row.target }}</span>
        </div>
      </div>
    </section>

    <DryRunTimeline v-if="analysis?.dry_run_logs.length" :logs="analysis.dry_run_logs" :status-label="analysis.dry_run_status" />
    <p v-if="operationError" class="error-line" role="alert">{{ operationError }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { DatabaseZap, Search, ShieldAlert } from '@lucide/vue'
import MetricStrip from '../components/MetricStrip.vue'
import StatusPill from '../components/StatusPill.vue'
import DryRunTimeline from '../components/DryRunTimeline.vue'
import { useStageBridgeStore } from '../stores/stagebridge'
import type { ConnectionInfo } from '../types'

const store = useStageBridgeStore()
const { locale, t } = useI18n()

const sourceId = ref(0)
const devId = ref(0)
const targetId = ref(0)
const schemasInput = ref('public')
const confirmWrite = ref(false)
const operationError = ref('')

onMounted(() => store.fetchConnections())

const savedProfiles = computed(() => store.connections.filter(c => !c.is_demo) as ConnectionInfo[])
const productionProfiles = computed(() => savedProfiles.value.filter(p => p.role === 'production'))
const developmentProfiles = computed(() => savedProfiles.value.filter(p => p.role === 'development'))
const stagingProfiles = computed(() => savedProfiles.value.filter(p => p.role === 'staging'))
const hasProfiles = computed(() => productionProfiles.value.length && developmentProfiles.value.length && stagingProfiles.value.length)

const analysis = computed(() => store.current)
const canAnalyze = computed(() => sourceId.value > 0 && devId.value > 0 && schemasInput.value.trim().length > 0)
const targetDb = computed(() => stagingProfiles.value.find(p => Number(p.id) === targetId.value)?.database || '—')
const reportTarget = computed(() => String((analysis.value?.report as Record<string, unknown>)?.migrationTarget || targetDb.value))

const analysisMetrics = computed(() => {
  const m = analysis.value?.metrics ?? {}
  return [
    { label: t('metrics.schemaChanges'), value: m.schemaChangesDetected ?? 0 },
    { label: t('metrics.blockingConflicts'), value: m.blockingConflicts ?? 0 },
    { label: t('metrics.affectedRows'), value: m.affectedRows ?? 0 },
    { label: t('metrics.breakingChanges'), value: m.breakingChanges ?? 0 }
  ]
})
const verifyRows = computed(
  () => ((analysis.value?.report as Record<string, unknown>)?.verify as Array<{ table: string; source: number; moved: number; rejected: number; target: number }>) || []
)
const verifyMetrics = computed(() => {
  const report = (analysis.value?.report ?? {}) as Record<string, unknown>
  return [
    { label: t('metrics.transferredRows'), value: Number(report.transferredRows ?? 0) },
    { label: t('metrics.rejectedRows'), value: Number(report.rejectedRows ?? 0) },
    { label: t('metrics.validationFailures'), value: Number(report.validationFailures ?? 0) },
    { label: t('scenario.mismatches'), value: Number(report.rowMismatches ?? 0) }
  ]
})
const planExplanation = computed(() => {
  if (analysis.value?.remediation_plan?.provider === 'mock') return t('ai.mockExplanation')
  if (analysis.value?.locale !== locale.value) return t('ai.regenerateForLocale')
  return analysis.value?.remediation_plan?.explanation || ''
})

async function analyze() {
  operationError.value = ''
  confirmWrite.value = false
  if (targetId.value === 0 && stagingProfiles.value.length === 1) targetId.value = Number(stagingProfiles.value[0].id)
  try {
    await store.prepareScenario({
      production_profile_id: sourceId.value,
      development_profile_id: devId.value,
      schemas: schemasInput.value.split(',').map(s => s.trim()).filter(Boolean)
    })
  } catch (error) {
    operationError.value = error instanceof Error ? error.message : t('errors.requestFailed')
  }
}

async function migrate() {
  operationError.value = ''
  if (!analysis.value || targetId.value === 0) {
    operationError.value = t('scenario.selectTarget')
    return
  }
  try {
    await store.runScenarioMigration(analysis.value.id, targetId.value)
  } catch (error) {
    operationError.value = error instanceof Error ? error.message : t('errors.requestFailed')
  }
}
</script>
