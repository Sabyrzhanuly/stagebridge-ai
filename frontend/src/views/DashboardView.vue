<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1>{{ t('dashboard.title') }}</h1>
        <p>{{ t('dashboard.subtitle') }}</p>
      </div>
      <div class="button-row">
        <RouterLink class="primary-button" to="/scenario"><GitBranch :size="18" />{{ t('navigation.scenario') }}</RouterLink>
        <RouterLink class="secondary-button" to="/analysis/new"><RadioTower :size="18" />{{ t('dashboard.newLiveAnalysis') }}</RouterLink>
        <button class="secondary-button" @click="startAnalysis" :disabled="store.loading">
          <Play :size="18" />
          {{ store.loading && store.showcaseStep ? t(`dashboard.demoStep.${store.showcaseStep}`) : t('dashboard.runDemo') }}
        </button>
      </div>
    </header>

    <TopologyMap />
    <MetricStrip :metrics="dashboardMetrics" />

    <section class="panel">
      <div class="panel-header">
        <div>
          <h2>{{ t('dashboard.recentRuns') }}</h2>
          <p>{{ t('dashboard.savedAnalyses', { count: store.analyses.length }) }}</p>
        </div>
      </div>
      <div class="run-table">
        <RouterLink v-for="analysis in store.analyses" :key="analysis.id" :to="`/analysis/${analysis.id}`" class="run-row">
          <span>#{{ analysis.id }}</span>
          <span>{{ analysis.mode === 'demo' ? t('analysis.demoTitle') : analysis.title }}</span>
          <span class="mode-tag" :class="analysis.mode">{{ analysis.mode === 'demo' ? t('analysis.demoData') : t('common.live') }}</span>
          <StatusPill :label="analysis.status" />
          <StatusPill :label="analysis.dry_run_status" />
        </RouterLink>
        <div v-if="!store.analyses.length" class="empty-state">{{ t('dashboard.noRuns') }}</div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { GitBranch, Play, RadioTower } from '@lucide/vue'
import MetricStrip from '../components/MetricStrip.vue'
import StatusPill from '../components/StatusPill.vue'
import TopologyMap from '../components/TopologyMap.vue'
import { useStageBridgeStore } from '../stores/stagebridge'

const store = useStageBridgeStore()
const router = useRouter()
const { t } = useI18n()

onMounted(() => store.fetchAnalyses())

const latest = computed(() => store.analyses[0])
const dashboardMetrics = computed(() => {
  const metrics = latest.value?.metrics ?? {}
  return [
    { label: t('metrics.schemaChanges'), value: metrics.schemaChangesDetected ?? 0 },
    { label: t('metrics.blockingConflicts'), value: metrics.blockingConflicts ?? 0 },
    { label: t('metrics.affectedRows'), value: metrics.affectedRows ?? 0 },
    { label: t('metrics.approvedActions'), value: metrics.approvedActions ?? 0 },
    { label: t('metrics.transferredRows'), value: metrics.transferredRows ?? 0 },
    { label: t('metrics.validationFailures'), value: metrics.validationFailures ?? 0 }
  ]
})

async function startAnalysis() {
  const analysis = await store.runDemoShowcase()
  await router.push(`/analysis/${analysis.id}`)
}
</script>
