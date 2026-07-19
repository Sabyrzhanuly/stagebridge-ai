<template>
  <PageHeader
    :title="t('pgConfig.title')"
    :back-to="{ name: 'server', params: { id } }"
    :back-label="t('common.backToServer')"
  >
    <template #actions>
      <Button outlined @click="loadConfig" :loading="loading">
        <i class="fa-solid fa-rotate btn-icon-left" aria-hidden="true"></i>{{ t('common.refresh') }}
      </Button>
    </template>
  </PageHeader>

  <AlertBanner severity="info">
    {{ t('pgConfig.noticeIntro') }} (<code>pg_settings</code>), {{ t('pgConfig.noticeConfLines') }}
    (<code>pg_file_settings</code>) {{ t('pgConfig.noticeRules') }} <code>pg_hba</code>. {{ t('pgConfig.noticePaths') }}
  </AlertBanner>

  <div v-if="snapshot" class="card-panel" style="margin-bottom: 16px">
    <div class="info-grid">
      <div>
        <div class="info-grid-label">{{ t('common.server') }}</div>
        <div class="info-grid-value">{{ snapshot.server_name }}</div>
      </div>
      <div>
        <div class="info-grid-label">PostgreSQL</div>
        <div class="info-grid-value">{{ snapshot.pg_major_version ? `v${snapshot.pg_major_version}` : '—' }}</div>
      </div>
      <div>
        <div class="info-grid-label">{{ t('pgConfig.currentUser') }}</div>
        <div class="info-grid-value">
          <Tag :severity="snapshot.is_superuser ? 'success' : 'warn'" :value="snapshot.is_superuser ? 'superuser' : t('pgConfig.notSuperuser')" />
        </div>
      </div>
      <div>
        <div class="info-grid-label">config_file</div>
        <div class="info-grid-value mono">{{ snapshot.paths.config_file || '—' }}</div>
      </div>
      <div>
        <div class="info-grid-label">hba_file</div>
        <div class="info-grid-value mono">{{ snapshot.paths.hba_file || '—' }}</div>
      </div>
    </div>
  </div>

  <div v-if="snapshot" class="config-advisor-panel">
    <AiInsight
      :label="t('configAdvisor.label')"
      endpoint="/ai/config-advisor"
      :payload="configAdvisorPayload"
      :sections="configAdvisorSections"
      badge-field="severity"
    />
  </div>

  <div v-if="snapshot" class="card-panel card-panel--table">
    <Tabs v-model:value="activeTab">
      <TabList>
        <Tab value="settings">{{ t('pgConfig.tabSettings') }} ({{ filteredSettings.length }})</Tab>
        <Tab value="file">{{ t('pgConfig.tabFile') }} ({{ snapshot.file_settings?.length ?? 0 }})</Tab>
        <Tab value="hba">pg_hba ({{ snapshot.hba_rules?.length ?? 0 }})</Tab>
      </TabList>
      <TabPanels>
        <TabPanel value="settings">
          <div class="flex-row" style="gap: 12px; margin-bottom: 12px; flex-wrap: wrap">
            <InputText v-model="settingsSearch" :placeholder="t('pgConfig.searchByName')" style="width: 220px" />
            <Select
              v-model="sourceFilter"
              :options="sourceOptions"
              option-label="label"
              option-value="value"
              :placeholder="t('pgConfig.source')"
              style="width: 200px"
              show-clear
            />
          </div>
          <DataTable
            class="app-data-table"
            :value="filteredSettings"
            size="small"
            striped-rows
            scrollable
            scroll-height="520px"
            :paginator="filteredSettings.length > 25"
            :rows="25"
            sort-field="name"
            :sort-order="1"
          >
            <Column field="name" :header="t('pgConfig.paramColumn')" sortable style="min-width: 200px" />
            <Column field="setting" :header="t('pgConfig.value')" sortable style="min-width: 140px">
              <template #body="{ data }">
                <span class="mono">{{ formatSetting(data) }}</span>
              </template>
            </Column>
            <Column field="source" :header="t('pgConfig.source')" sortable style="width: 130px" />
            <Column field="context" header="Context" sortable style="width: 110px" />
            <Column field="category" :header="t('pgConfig.category')" sortable style="width: 140px" />
            <Column :header="t('pgConfig.file')" style="min-width: 180px">
              <template #body="{ data }">
                <span v-if="data.sourcefile" class="mono muted" style="font-size: 12px">
                  {{ data.sourcefile }}:{{ data.sourceline }}
                </span>
                <span v-else class="muted">—</span>
              </template>
            </Column>
            <Column header="Restart" style="width: 80px">
              <template #body="{ data }">
                <Tag v-if="data.pending_restart" severity="warn" :value="t('common.yes')" />
                <span v-else class="muted">—</span>
              </template>
            </Column>
          </DataTable>
        </TabPanel>

        <TabPanel value="file">
          <AlertBanner v-if="snapshot.file_settings_error" severity="warn">
            {{ snapshot.file_settings_error }}
          </AlertBanner>
          <DataTable
            v-else
            class="app-data-table"
            :value="snapshot.file_settings || []"
            size="small"
            striped-rows
            scrollable
            scroll-height="520px"
            :paginator="(snapshot.file_settings?.length ?? 0) > 25"
            :rows="25"
          >
            <Column field="name" :header="t('pgConfig.paramColumn')" sortable style="min-width: 180px" />
            <Column field="setting" :header="t('pgConfig.value')" sortable style="min-width: 120px">
              <template #body="{ data }">
                <span class="mono">{{ data.setting ?? '—' }}</span>
              </template>
            </Column>
            <Column field="sourcefile" :header="t('pgConfig.file')" sortable style="min-width: 200px">
              <template #body="{ data }">
                <span class="mono muted" style="font-size: 12px">{{ data.sourcefile }}:{{ data.sourceline }}</span>
              </template>
            </Column>
            <Column field="applied" header="Applied" style="width: 90px">
              <template #body="{ data }">
                <Tag :severity="data.applied ? 'success' : 'warn'" :value="data.applied ? t('common.yes') : t('common.no')" />
              </template>
            </Column>
            <Column field="error" :header="t('common.error')">
              <template #body="{ data }">
                <span v-if="data.error" style="font-size: 12px; color: var(--p-red-400)">{{ data.error }}</span>
                <span v-else class="muted">—</span>
              </template>
            </Column>
          </DataTable>
        </TabPanel>

        <TabPanel value="hba">
          <AlertBanner v-if="snapshot.hba_error" severity="warn">
            {{ snapshot.hba_error }}
          </AlertBanner>
          <DataTable
            v-else
            class="app-data-table"
            :value="snapshot.hba_rules || []"
            size="small"
            striped-rows
            scrollable
            scroll-height="520px"
            :paginator="(snapshot.hba_rules?.length ?? 0) > 25"
            :rows="25"
          >
            <Column field="line_number" header="#" sortable style="width: 60px" />
            <Column field="type" header="Type" sortable style="width: 90px" />
            <Column field="databases" header="Database" sortable style="min-width: 120px" />
            <Column field="users" header="User" sortable style="min-width: 120px" />
            <Column field="address" header="Address" sortable style="min-width: 120px">
              <template #body="{ data }">
                <span class="mono">{{ formatAddress(data) }}</span>
              </template>
            </Column>
            <Column field="auth_method" header="Method" sortable style="width: 110px" />
            <Column field="options" header="Options">
              <template #body="{ data }">
                <span class="muted" style="font-size: 12px">{{ data.options || '—' }}</span>
              </template>
            </Column>
            <Column field="error" :header="t('common.error')">
              <template #body="{ data }">
                <span v-if="data.error" style="font-size: 12px; color: var(--p-red-400)">{{ data.error }}</span>
                <span v-else class="muted">—</span>
              </template>
            </Column>
          </DataTable>
        </TabPanel>
      </TabPanels>
    </Tabs>
  </div>

  <div v-else-if="!loading" class="card-panel" style="text-align: center; padding: 60px">
    <i class="fa-solid fa-sliders" style="font-size: 48px; opacity: 0.3"></i>
    <div style="margin-top: 16px; color: var(--p-text-muted-color)">{{ t('pgConfig.loadFailed') }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from 'primevue/usetoast'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import PageHeader from '../components/ui/PageHeader.vue'
import AlertBanner from '../components/ui/AlertBanner.vue'
import AiInsight from '../components/AiInsight.vue'
import api from '../api/client'
import type { PgConfigSnapshot, PgHbaRule, PgSetting } from '../api/types'

const props = defineProps<{ id: string }>()
const { t } = useI18n()
const toast = useToast()

const snapshot = ref<PgConfigSnapshot | null>(null)
const loading = ref(false)
const activeTab = ref('settings')
const settingsSearch = ref('')
const sourceFilter = ref<string | null>(null)

const sourceOptions = computed(() => {
  if (!snapshot.value) return []
  const sources = new Set(snapshot.value.settings.map(s => s.source).filter(Boolean))
  return Array.from(sources).sort().map(s => ({ label: s as string, value: s as string }))
})

const configAdvisorSections = computed(() => [
  { key: 'findings', title: t('configAdvisor.secFindings') },
  { key: 'recommendations', title: t('configAdvisor.secRecommendations') },
  { key: 'notes', title: t('configAdvisor.secNotes') },
])

const CONFIG_ADVISOR_SETTINGS = [
  'shared_buffers',
  'work_mem',
  'maintenance_work_mem',
  'effective_cache_size',
  'max_connections',
  'random_page_cost',
  'effective_io_concurrency',
  'wal_level',
  'max_wal_size',
  'min_wal_size',
  'checkpoint_timeout',
  'checkpoint_completion_target',
  'autovacuum',
  'autovacuum_max_workers',
  'autovacuum_naptime',
]

const filteredSettings = computed(() => {
  if (!snapshot.value) return []
  const q = settingsSearch.value.trim().toLowerCase()
  return snapshot.value.settings.filter(s => {
    if (sourceFilter.value && s.source !== sourceFilter.value) return false
    if (!q) return true
    return s.name.toLowerCase().includes(q)
  })
})

function formatSetting(row: PgSetting): string {
  if (row.setting == null) return '—'
  return row.unit ? `${row.setting} ${row.unit}` : row.setting
}

function formatAddress(row: PgHbaRule): string {
  if (row.address && row.netmask) return `${row.address}/${row.netmask}`
  return row.address || '—'
}

function compactSetting(row: PgSetting) {
  return {
    name: row.name,
    setting: row.setting,
    unit: row.unit,
    source: row.source,
    context: row.context,
    pending_restart: row.pending_restart,
  }
}

function configAdvisorPayload() {
  const settings = snapshot.value?.settings || []
  const byName = new Map(settings.map((row) => [row.name, row]))
  return {
    payload: JSON.stringify({
      server_name: snapshot.value?.server_name,
      pg_major_version: snapshot.value?.pg_major_version,
      is_superuser: snapshot.value?.is_superuser,
      settings: CONFIG_ADVISOR_SETTINGS.map((name) => byName.get(name)).filter(Boolean).map((row) => compactSetting(row as PgSetting)),
      pending_restart: settings.filter((row) => row.pending_restart).map((row) => row.name).slice(0, 20),
      file_settings_errors: (snapshot.value?.file_settings || []).filter((row) => row.error).map((row) => ({
        name: row.name,
        error: row.error,
      })).slice(0, 20),
      hba_errors: (snapshot.value?.hba_rules || []).filter((row) => row.error).map((row) => ({
        line_number: row.line_number,
        error: row.error,
      })).slice(0, 20),
    }),
  }
}

async function loadConfig() {
  loading.value = true
  try {
    const { data } = await api.get<PgConfigSnapshot>(`/servers/${props.id}/pg-config`)
    snapshot.value = data
    if (data.hba_error) activeTab.value = 'hba'
    else if (data.file_settings_error) activeTab.value = 'file'
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    toast.add({ severity: 'error', summary: t('common.error'), detail: detail || t('pgConfig.loadFailed'), life: 5000 })
    snapshot.value = null
  } finally {
    loading.value = false
  }
}

onMounted(loadConfig)
</script>

<style scoped>
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  word-break: break-all;
}
.config-advisor-panel {
  margin: 0 0 16px;
}
</style>
