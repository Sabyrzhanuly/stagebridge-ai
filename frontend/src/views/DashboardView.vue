<template>
  <PageHeader title="Dashboard" :subtitle="t('dashboard.subtitle')">
    <template #actions>
      <Button @click="openCreate">
        <i class="fa-solid fa-plus btn-icon-left" aria-hidden="true"></i>
        {{ t('dashboard.addServer') }}
      </Button>
    </template>
  </PageHeader>

  <StatusStrip
    :worker-online="healthStore.workerOnline"
    :worker-loading="healthStore.workerLoading"
    :monitoring-live="tasksStore.wsConnected"
    :monitoring-loading="tasksStore.wsConnected === null"
    :servers-loading="store.loading"
    :server-count="store.servers.length"
    :tasks-loading="tasksStore.tasksLoading"
    :active-tasks="tasksStore.activeCount"
    :worker-task-count="healthStore.workerTaskCount"
    @open-tasks="openTaskPanel"
  />

  <WorkerActivityPanel
    :tasks="[...healthStore.celeryActive, ...healthStore.celeryReserved]"
    @open-tasks="openTaskPanel"
  />

  <div class="stats-grid stats-grid--unified">
    <StatCard :label="t('dashboard.stats.serversLabel')" :value="store.servers.length" icon="fa-solid fa-server" variant="blue" :hint="t('dashboard.stats.serversHint')" />
    <StatCard :label="t('dashboard.stats.activeLabel')" :value="activeCount" icon="fa-solid fa-circle-check" variant="green" :hint="t('dashboard.stats.activeHint')" />
    <StatCard label="Production" :value="envCount('production')" icon="fa-solid fa-shield-halved" variant="red" :hint="t('dashboard.stats.prodHint')" />
    <StatCard
      :label="t('dashboard.stats.activeTasksLabel')"
      :value="Math.max(tasksStore.activeCount, healthStore.workerTaskCount)"
      icon="fa-solid fa-list-check"
      variant="amber"
      hint="UI + Celery"
      live
    />
  </div>

  <div class="card-panel card-panel--table">
    <div class="card-panel-title">
      <span><i class="fa-solid fa-server" aria-hidden="true"></i>{{ t('dashboard.serversTitle') }}</span>
    </div>

    <ServerMobileList
      v-if="isMobile"
      :servers="store.servers"
      :loading="store.loading"
      :testing-id="testingId"
      @open="goToServer"
      @edit="openEdit"
      @navigate="goTo"
      @test="testConn"
      @delete="confirmDelete"
    >
      <template #empty-action>
        <Button size="small" @click="openCreate">
          <i class="fa-solid fa-plus btn-icon-left" aria-hidden="true"></i>
          {{ t('dashboard.addServer') }}
        </Button>
      </template>
    </ServerMobileList>

    <DataTable
      v-else
      class="app-data-table"
      :value="store.servers"
      :loading="store.loading"
      striped-rows
      size="small"
      :paginator="store.servers.length > 10"
      :rows="10"
    >
      <template #empty>
        <EmptyState
          icon="fa-solid fa-server"
          :title="t('dashboard.empty.title')"
          :description="t('dashboard.empty.desc')"
          compact
        >
          <template #action>
            <Button size="small" @click="openCreate">
              <i class="fa-solid fa-plus btn-icon-left" aria-hidden="true"></i>
              {{ t('dashboard.addServer') }}
            </Button>
          </template>
        </EmptyState>
      </template>
      <Column field="name" :header="t('common.name')" sortable>
        <template #body="{ data }">
          <a href="#" class="link-primary" @click.prevent="goToServer(data.id)">{{ data.name }}</a>
        </template>
      </Column>
      <Column v-if="showOrgColumn" :header="t('dashboard.columns.organization')" sortable field="organization_name" style="width: 140px">
        <template #body="{ data }">
          <Tag v-if="data.organization_name" severity="secondary" :value="data.organization_name" />
          <Tag v-else severity="warn" :value="t('dashboard.notAssigned')" />
        </template>
      </Column>
      <Column field="host" :header="t('dashboard.columns.host')" sortable>
        <template #body="{ data }">{{ data.host }}:{{ data.port }}</template>
      </Column>
      <Column field="admin_user" :header="t('dashboard.columns.user')" class="col-hide-narrow" />
      <Column field="environment" :header="t('dashboard.columns.environment')" sortable>
        <template #body="{ data }">
          <Tag :severity="envSeverity(data.environment)" :value="data.environment" />
        </template>
      </Column>
      <Column header="PG" style="width: 70px">
        <template #body="{ data }">
          <span
            v-if="data.pg_major_version"
            class="pg-version-badge"
            :title="`PostgreSQL ${data.pg_major_version}`"
          >v{{ data.pg_major_version }}</span>
          <span v-else class="muted" style="font-size: 11px">—</span>
        </template>
      </Column>
      <Column field="is_active" :header="t('dashboard.columns.enabled')">
        <template #body="{ data }">
          <Tag
            :severity="data.is_active ? 'success' : 'danger'"
            :value="serverActiveLabel(data.is_active)"
          />
        </template>
      </Column>
      <Column field="health_status" header="PG" sortable style="width: 110px">
        <template #body="{ data }">
          <Tag
            :severity="healthStatusSeverity(data.health_status)"
            :value="healthStatusLabel(data.health_status)"
            v-tooltip.top="data.health_error_hint || data.health_error_title || ''"
          />
        </template>
      </Column>
      <Column :header="t('common.actions')" style="width: 120px">
        <template #body="{ data }">
          <ServerRowActions
            :testing="testingId === data.id"
            @open="goToServer(data.id)"
            @edit="openEdit(data.id)"
            @roles="goTo(data.id, 'roles')"
            @databases="goTo(data.id, 'databases')"
            @monitoring="goTo(data.id, 'monitoring')"
            @diagnostics="goTo(data.id, 'diagnostics')"
            @test="testConn(data.id)"
            @delete="confirmDelete(data.id)"
          />
        </template>
      </Column>
    </DataTable>
  </div>

  <ServerFormDialog
    v-model:visible="formVisible"
    :mode="formMode"
    :server="editingServer"
    :org-options="orgOptions"
    :show-org-picker="showOrgPicker"
    :saving="formSaving"
    @submit="onFormSubmit"
  />
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import PageHeader from '../components/ui/PageHeader.vue'
import StatCard from '../components/ui/StatCard.vue'
import StatusStrip from '../components/ui/StatusStrip.vue'
import WorkerActivityPanel from '../components/ui/WorkerActivityPanel.vue'
import EmptyState from '../components/ui/EmptyState.vue'
import ServerMobileList from '../components/servers/ServerMobileList.vue'
import ServerRowActions from '../components/servers/ServerRowActions.vue'
import ServerFormDialog from '../components/servers/ServerFormDialog.vue'
import { useMediaQuery } from '../composables/useMediaQuery'
import { useServersStore } from '../stores/servers'
import { useTasksStore } from '../stores/tasks'
import { useHealthStore } from '../stores/health'
import { useAuthStore } from '../stores/auth'
import api from '../api/client'
import type { Server } from '../api/types'
import { envSeverity, serverActiveLabel } from '../utils/tags'
import { healthStatusLabel, healthStatusSeverity } from '../utils/pgHealth'

const store = useServersStore()
const tasksStore = useTasksStore()
const healthStore = useHealthStore()
const authStore = useAuthStore()
const router = useRouter()
const { t } = useI18n()
const toast = useToast()
const confirm = useConfirm()
const isMobile = useMediaQuery('(max-width: 768px)')

const formVisible = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const formSaving = ref(false)
const editingId = ref<number | null>(null)
const testingId = ref<number | null>(null)
const orgOptions = ref<{ id: number; name: string }[]>([])

const showOrgColumn = computed(() => authStore.isSuperAdmin && !authStore.activeOrgId)
const showOrgPicker = computed(() => {
  // Single-tenant: когда организация в контексте выбрана, выбор организации скрыт —
  // сервер привязывается к активной организации на бэкенде.
  if (authStore.isSuperAdmin && !authStore.activeOrgId) return true
  if (formMode.value === 'edit' && authStore.isSuperAdmin && !authStore.activeOrgId) return true
  return false
})

const editingServer = computed(() =>
  editingId.value != null ? store.servers.find(s => s.id === editingId.value) ?? null : null,
)

const activeCount = computed(() => store.servers.filter(s => s.is_active).length)
function envCount(env: string) {
  return store.servers.filter(s => s.environment === env).length
}

onMounted(async () => {
  try {
    await store.fetchServers()
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('dashboard.toast.serversList'), detail: e?.response?.data?.detail || e?.message || t('common.loadFailed'), life: 5000 })
  }
  if (authStore.isSuperAdmin) {
    try {
      const { data } = await api.get<{ id: number; name: string }[]>('/admin/organizations')
      orgOptions.value = data.map(o => ({ id: o.id, name: o.name }))
    } catch { /* ignore */ }
  }
})

function openTaskPanel() {
  tasksStore.expanded = true
}

function openCreate() {
  formMode.value = 'create'
  editingId.value = null
  formVisible.value = true
}

function openEdit(id: number) {
  formMode.value = 'edit'
  editingId.value = id
  formVisible.value = true
}

async function onFormSubmit(payload: Record<string, unknown>) {
  formSaving.value = true
  try {
    if (formMode.value === 'create') {
      const createPayload = {
        name: payload.name as string,
        host: payload.host as string,
        port: payload.port as number,
        admin_user: payload.admin_user as string,
        admin_password: payload.admin_password as string,
        environment: payload.environment as string,
        organization_id: payload.organization_id as number | undefined,
      }
      await store.createServer(createPayload)
      toast.add({ severity: 'success', summary: t('dashboard.toast.serverCreated'), life: 3000 })
    } else if (editingId.value != null) {
      const server = store.servers.find(s => s.id === editingId.value)
      const orgId = payload.organization_id as number | undefined
      const updatePayload = { ...payload }
      delete updatePayload.organization_id
      if (Object.keys(updatePayload).length) {
        await store.updateServer(editingId.value, updatePayload)
      }
      if (authStore.isSuperAdmin && orgId && server?.organization_id !== orgId) {
        await store.assignOrganization(editingId.value, orgId)
      }
      toast.add({ severity: 'success', summary: t('dashboard.toast.serverSaved'), life: 3000 })
    }
    formVisible.value = false
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('common.error'), detail: e.response?.data?.detail || 'Error', life: 4000 })
  } finally {
    formSaving.value = false
  }
}

function goToServer(id: number) { router.push({ name: 'server', params: { id } }) }
function goTo(id: number, name: string) { router.push({ name, params: { id } }) }

async function testConn(id: number) {
  testingId.value = id
  try {
    const res = await store.testServer(id)
    if (res.success) {
      toast.add({ severity: 'success', summary: t('dashboard.toast.connected'), detail: res.version, life: 3000 })
      void store.fetchServers()
    } else {
      const detail = res.error_hint || res.error_title || res.error || t('dashboard.toast.connError')
      toast.add({ severity: 'error', summary: res.error_title || t('common.error'), detail, life: 8000 })
      void store.fetchServers()
    }
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('dashboard.toast.testConnTitle'), detail: e?.response?.data?.detail || e?.message || t('common.loadFailed'), life: 5000 })
  } finally {
    testingId.value = null
  }
}

function confirmDelete(id: number) {
  confirm.require({
    message: t('dashboard.confirm.deleteMsg'),
    header: t('dashboard.confirm.header'),
    icon: 'fa-solid fa-exclamation-triangle',
    acceptLabel: t('common.delete'),
    rejectLabel: t('common.cancel'),
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        await store.deleteServer(id)
        toast.add({ severity: 'success', summary: t('dashboard.toast.deleted'), life: 2000 })
      } catch (e: any) {
        toast.add({
          severity: 'error',
          summary: t('dashboard.toast.deleteFailed'),
          detail: e?.response?.data?.detail || e?.message || t('common.error'),
          life: 5000,
        })
      }
    },
  })
}
</script>

<style scoped>
.btn-icon-left { margin-right: 8px; }
</style>
