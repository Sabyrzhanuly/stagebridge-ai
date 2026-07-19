<template>
  <PageHeader
    :title="t('monitoring.title')"
    :back-to="{ name: 'server', params: { id } }"
    :back-label="t('monitoring.backToServer')"
  >
    <template #actions>
      <span v-if="collectedLabel" class="collected-label">{{ collectedLabel }}</span>
      <Button outlined @click="fetchMonitoring(true)" :loading="loading">
        <i class="fa-solid fa-rotate btn-icon-left" aria-hidden="true"></i>{{ t('common.refresh') }}
      </Button>
    </template>
  </PageHeader>

  <div v-if="snapshot" class="stats-grid">
    <StatCard
      :label="t('monitoring.connectionsLabel')"
      :value="`${snapshot.connections.total}${maxConnLabel}`"
      icon="fa-solid fa-network-wired"
      variant="blue"
      :hint="connUsageHint"
      live
    />
    <StatCard :label="t('monitoring.activeLabel')" :value="snapshot.connections.active" icon="fa-solid fa-bolt" variant="green" />
    <StatCard label="Idle" :value="snapshot.connections.idle" icon="fa-solid fa-pause" variant="slate" />
    <StatCard label="Waiting" :value="snapshot.connections.waiting" icon="fa-solid fa-hourglass-half" variant="amber" />
    <StatCard
      label="Cache hit"
      :value="cacheHitLabel"
      icon="fa-solid fa-gauge-high"
      :variant="cacheHitVariant"
      hint="pg_stat_database, shared buffers"
    />
    <StatCard
      v-if="snapshot.storage"
      :label="t('monitoring.pgDataLabel')"
      :value="storageTotalLabel"
      icon="fa-solid fa-hard-drive"
      variant="blue"
      :hint="t('monitoring.pgDataHint')"
    />
  </div>

  <div class="card-panel card-panel--table" v-if="snapshot">
    <div class="card-panel-title"><span><i class="fa-solid fa-database" aria-hidden="true"></i>{{ t('monitoring.dbSizesTitle') }}</span></div>
    <DataTable
      class="app-data-table"
      :value="snapshot.database_sizes"
      size="small"
      striped-rows
      responsive-layout="stack"
      breakpoint="768px"
      :paginator="snapshot.database_sizes.length > 10"
      :rows="10"
    >
      <Column field="datname" :header="t('common.database')" sortable />
      <Column field="size" :header="t('monitoring.sizeColumn')" sortable />
    </DataTable>
  </div>

  <div class="card-panel card-panel--table" v-if="snapshot">
    <div class="card-panel-title"><span><i class="fa-solid fa-clock" aria-hidden="true"></i>{{ t('monitoring.slowQueriesTitle') }}</span></div>
    <p v-if="slowQueriesHint" class="panel-inline-hint">{{ slowQueriesHint }}</p>
    <DataTable
      class="app-data-table"
      :value="snapshot.slow_queries"
      size="small"
      striped-rows
      responsive-layout="stack"
      breakpoint="768px"
      :paginator="snapshot.slow_queries.length > 10"
      :rows="10"
    >
      <template #empty>
        <EmptyState
          :icon="snapshot.slow_queries_meta.available ? 'fa-solid fa-check' : 'fa-solid fa-chart-line'"
          :title="slowQueriesEmptyTitle"
          :description="slowQueriesEmptyDescription"
          compact
        />
      </template>
      <Column field="query" :header="t('monitoring.queryColumn')">
        <template #body="{ data }">
          <div class="slow-query-cell">
            <code class="text-mono query-snippet">{{ truncate(data.query, 100) }}</code>
            <Button
              size="small"
              outlined
              severity="secondary"
              class="slow-query-ai-btn"
              @click.stop="selectSlowQuery(data)"
            >
              <i class="fa-solid fa-wand-magic-sparkles btn-icon-left" aria-hidden="true"></i>
              {{ t('ai.fabShort') }}: {{ t('queryAdvisor.action') }}
            </Button>
          </div>
        </template>
      </Column>
      <Column field="calls" header="Calls" sortable style="width: 100px" />
      <Column field="mean_time_ms" header="Avg (ms)" sortable style="width: 110px">
        <template #body="{ data }">{{ data.mean_time_ms.toFixed(2) }}</template>
      </Column>
      <Column field="total_time_ms" header="Total (ms)" sortable style="width: 120px">
        <template #body="{ data }">{{ data.total_time_ms.toFixed(2) }}</template>
      </Column>
    </DataTable>
    <AiInsight
      v-if="selectedSlowQuery"
      :key="selectedQuery"
      class="query-advisor-panel"
      :label="t('queryAdvisor.label')"
      endpoint="/ai/query-advisor"
      :payload="queryAdvisorPayload"
      :sections="queryAdvisorSections"
      badge-field="severity"
    />
  </div>

  <div class="card-panel card-panel--table" v-if="snapshot">
    <div class="card-panel-title"><span><i class="fa-solid fa-lock" aria-hidden="true"></i>{{ t('monitoring.locksTitle') }}</span></div>
    <DataTable
      class="app-data-table"
      :value="snapshot.locks"
      size="small"
      striped-rows
      responsive-layout="stack"
      breakpoint="768px"
    >
      <template #empty>
        <EmptyState icon="fa-solid fa-lock-open" :title="t('monitoring.noLocksTitle')" :description="t('monitoring.noLocksDesc')" compact />
      </template>
      <Column field="pid" header="PID" style="width: 90px" />
      <Column field="relation" header="Relation" style="width: 180px" />
      <Column field="mode" header="Mode" style="width: 220px" />
      <Column field="query" :header="t('monitoring.queryColumn')">
        <template #body="{ data }">
          <code class="text-mono query-snippet">{{ truncate(data.query || '', 80) }}</code>
        </template>
      </Column>
    </DataTable>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from 'primevue/usetoast'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import PageHeader from '../components/ui/PageHeader.vue'
import StatCard from '../components/ui/StatCard.vue'
import EmptyState from '../components/ui/EmptyState.vue'
import AiInsight from '../components/AiInsight.vue'
import api from '../api/client'
import type { MonitoringSnapshot } from '../api/types'
import { formatBytes } from '../utils/pgHealth'

const props = defineProps<{ id: string }>()
const { t } = useI18n()
const toast = useToast()
const snapshot = ref<MonitoringSnapshot | null>(null)
type SlowQuery = MonitoringSnapshot['slow_queries'][number]
const selectedSlowQuery = ref<SlowQuery | null>(null)
const loading = ref(false)
const AUTO_REFRESH_MS = 30_000
let refreshTimer: ReturnType<typeof setInterval> | null = null
// Флаг, чтобы автообновление каждые 30с не спамило одинаковыми тостами подряд
let errorShown = false

const maxConnLabel = computed(() => {
  const max = snapshot.value?.connections.max_connections
  if (!max) return ''
  return ` / ${max}`
})

const connUsageHint = computed(() => {
  const c = snapshot.value?.connections
  if (!c?.max_connections) return undefined
  const pct = Math.round((c.total / c.max_connections) * 100)
  return t('monitoring.connUsageHint', { pct })
})

const cacheHitLabel = computed(() => {
  const v = snapshot.value?.cache_hit_ratio
  if (v == null) return '—'
  return `${v.toFixed(1)}%`
})

const cacheHitVariant = computed(() => {
  const v = snapshot.value?.cache_hit_ratio
  if (v == null) return 'slate' as const
  if (v >= 95) return 'green' as const
  if (v >= 90) return 'amber' as const
  return 'red' as const
})

const storageTotalLabel = computed(() => {
  const bytes = snapshot.value?.storage?.total_db_bytes
  if (bytes == null) return '—'
  return formatBytes(bytes)
})

const collectedLabel = computed(() => {
  const at = snapshot.value?.collected_at
  const source = snapshot.value?.source
  if (!at) return ''
  const d = new Date(at)
  const time = Number.isNaN(d.getTime()) ? at : d.toLocaleString('ru-RU')
  const src = source === 'live' ? t('monitoring.sourceLive') : t('monitoring.sourceCache')
  return t('monitoring.collectedLabel', { src, time })
})

const slowQueriesHint = computed(() => {
  const meta = snapshot.value?.slow_queries_meta
  if (!meta || meta.available) return null
  return meta.error ? t('monitoring.errorPrefix', { error: meta.error }) : null
})

const slowQueriesEmptyTitle = computed(() => {
  const meta = snapshot.value?.slow_queries_meta
  if (!meta?.available) return t('monitoring.pgStatUnavailable')
  return t('monitoring.noData')
})

const slowQueriesEmptyDescription = computed(() => {
  const meta = snapshot.value?.slow_queries_meta
  if (!meta) return ''
  if (!meta.available) {
    return meta.hint || t('monitoring.pgStatInstallHint')
  }
  return meta.hint || t('monitoring.pgStatNoStats')
})

const selectedQuery = computed(() => selectedSlowQuery.value?.query || '')

const selectedStats = computed(() => {
  const row = selectedSlowQuery.value
  if (!row) return null
  return {
    calls: row.calls,
    mean_time_ms: row.mean_time_ms,
    total_time_ms: row.total_time_ms,
    collected_at: snapshot.value?.collected_at || null,
    source: snapshot.value?.source || null,
  }
})

const queryAdvisorSections = computed(() => [
  { key: 'problems', title: t('queryAdvisor.secProblems') },
  { key: 'indexes', title: t('queryAdvisor.secIndexes') },
  { key: 'rewrite', title: t('queryAdvisor.secRewrite') },
  { key: 'notes', title: t('queryAdvisor.secNotes') },
])

function queryAdvisorPayload() {
  return {
    payload: JSON.stringify({
      query: selectedQuery.value,
      stats: selectedStats.value,
    }),
  }
}

function selectSlowQuery(row: SlowQuery) {
  selectedSlowQuery.value = row
}

async function fetchMonitoring(forceLive = false) {
  loading.value = true
  try {
    const params = forceLive ? { refresh: true } : {}
    const { data } = await api.get<MonitoringSnapshot>(`/servers/${props.id}/monitoring`, { params })
    snapshot.value = data
    if (selectedSlowQuery.value && !data.slow_queries.some((row) => row.query === selectedSlowQuery.value?.query)) {
      selectedSlowQuery.value = null
    }
    errorShown = false
  } catch (e: any) {
    if (!errorShown) {
      toast.add({ severity: 'error', summary: t('monitoring.toast.title'), detail: e?.response?.data?.detail || e?.message || t('common.loadFailed'), life: 5000 })
      errorShown = true
    }
  } finally {
    loading.value = false
  }
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n) + '…' : s
}

onMounted(() => {
  fetchMonitoring(false)
  refreshTimer = setInterval(() => fetchMonitoring(false), AUTO_REFRESH_MS)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.query-snippet { font-size: 12px; word-break: break-all; }
.slow-query-cell { display: flex; flex-direction: column; align-items: flex-start; gap: 8px; }
.slow-query-ai-btn { white-space: nowrap; }
.query-advisor-panel { margin-top: 12px; }
.btn-icon-left { margin-right: 6px; }
.collected-label {
  font-size: 12px;
  color: var(--text-color-secondary);
  margin-right: 12px;
  white-space: nowrap;
}
</style>
