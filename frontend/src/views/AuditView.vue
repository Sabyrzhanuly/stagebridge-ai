<template>
  <PageHeader :title="t('audit.title')" :subtitle="t('audit.subtitle')">
    <template #actions>
      <Button outlined @click="resetAndLoad" :loading="loading">
        <i class="fa-solid fa-rotate btn-icon-left" aria-hidden="true"></i>{{ t('common.refresh') }}
      </Button>
    </template>
  </PageHeader>

  <div class="card-panel card-panel--table">
    <div class="filters-bar">
      <InputText
        v-if="authStore.hasPermission('view_all')"
        v-model="filters.username"
        :placeholder="t('audit.user')"
        style="width: 200px"
        @keyup.enter="resetAndLoad"
      />
      <Select
        v-model="filters.action"
        :options="actionOptions"
        option-label="label"
        option-value="value"
        :placeholder="t('audit.action')"
        show-clear
        style="width: 180px"
        @change="resetAndLoad"
      />
      <Select
        v-model="filters.entity_type"
        :options="entityOptions"
        option-label="label"
        option-value="value"
        :placeholder="t('audit.entityType')"
        show-clear
        style="width: 180px"
        @change="resetAndLoad"
      />
    </div>

    <DataTable
      class="app-data-table"
      :value="rows"
      :loading="loading"
      :paginator="true"
      :rows="pageSize"
      :total-records="totalRecords"
      :first="first"
      lazy
      responsive-layout="stack"
      breakpoint="768px"
      @page="onPage"
      striped-rows
    >
      <Column field="id" header="ID" style="width: 80px" />
      <Column field="username" :header="t('audit.user')" style="width: 160px" />
      <Column field="action" :header="t('audit.action')" style="width: 130px">
        <template #body="{ data }">
          <Tag :value="data.action" severity="info" />
        </template>
      </Column>
      <Column :header="t('audit.entity')" style="width: 200px">
        <template #body="{ data }">
          {{ data.entity_id ? `${data.entity_type} #${data.entity_id}` : data.entity_type }}
        </template>
      </Column>
      <Column field="result" :header="t('audit.result')" style="width: 120px">
        <template #body="{ data }">
          <Tag :severity="resultSeverity(data.result)" :value="data.result" />
        </template>
      </Column>
      <Column field="ip_address" header="IP" style="width: 140px" />
      <Column field="created_at" :header="t('audit.date')" style="width: 180px">
        <template #body="{ data }">{{ formatDate(data.created_at) }}</template>
      </Column>
    </DataTable>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import PageHeader from '../components/ui/PageHeader.vue'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import api from '../api/client'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const { t } = useI18n()

interface AuditEntry {
  id: number
  user_id: number | null
  username: string
  action: string
  entity_type: string
  entity_id: string | null
  payload: Record<string, unknown> | null
  result: string
  ip_address: string | null
  created_at: string
}

const pageSize = 50
const rows = ref<AuditEntry[]>([])
const loading = ref(false)
const first = ref(0)
const totalRecords = ref(0)

const filters = reactive({
  username: null as string | null,
  action: null as string | null,
  entity_type: null as string | null,
})

const actionOptions = [
  { label: 'login', value: 'login' },
  { label: 'create', value: 'create' },
  { label: 'update', value: 'update' },
  { label: 'delete', value: 'delete' },
  { label: 'execute', value: 'execute' },
  { label: 'refresh', value: 'refresh' },
  { label: 'install', value: 'install' },
]

const entityOptions = [
  { label: 'user', value: 'user' },
  { label: 'organization', value: 'organization' },
  { label: 'organization_member', value: 'organization_member' },
  { label: 'member_access', value: 'member_access' },
  { label: 'server', value: 'server' },
  { label: 'database', value: 'database' },
  { label: 'role', value: 'role' },
  { label: 'backup', value: 'backup' },
  { label: 'backup_schedule', value: 'backup_schedule' },
  { label: 'scenario', value: 'scenario' },
  { label: 'structure_sync', value: 'structure_sync' },
  { label: 'notification_channel', value: 'notification_channel' },
  { label: 'alert_rule', value: 'alert_rule' },
  { label: 'cron_schedule', value: 'cron_schedule' },
  { label: 's3_storage', value: 's3_storage' },
  { label: 'pg_client', value: 'pg_client' },
  { label: 'pg_client_repo', value: 'pg_client_repo' },
  { label: 'pg_client_catalog', value: 'pg_client_catalog' },
]

function resultSeverity(result: string): 'success' | 'danger' | 'warn' | 'secondary' {
  if (result === 'success') return 'success'
  if (result === 'pending') return 'warn'
  if (result === 'failed' || result === 'rejected') return 'danger'
  return 'secondary'
}

async function loadData() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { limit: pageSize + 1, offset: first.value }
    if (filters.username?.trim()) params.username = filters.username.trim()
    if (filters.action) params.action = filters.action
    if (filters.entity_type) params.entity_type = filters.entity_type
    const { data } = await api.get<AuditEntry[]>('/audit', { params })
    const hasMore = data.length > pageSize
    rows.value = hasMore ? data.slice(0, pageSize) : data
    totalRecords.value = first.value + data.length + (hasMore ? pageSize : 0)
  } finally { loading.value = false }
}

function resetAndLoad() { first.value = 0; loadData() }
function onPage(e: { first: number }) { first.value = e.first; loadData() }
function formatDate(iso: string) {
  try {
    const utc = iso && !iso.endsWith('Z') && !/[+-]\d{2}:\d{2}$/.test(iso) ? iso + 'Z' : iso
    return new Date(utc).toLocaleString('ru-RU')
  } catch { return iso }
}

onMounted(loadData)
</script>
