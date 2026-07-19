<template>
  <PageHeader
    :title="server?.name || t('common.server')"
    :subtitle="server ? `${server.host}:${server.port}` : undefined"
    :back-to="{ name: 'dashboard' }"
    :back-label="t('serverView.backToList')"
  >
    <template #actions>
      <template v-if="server">
        <Button outlined @click="openEdit">
          <i class="fa-solid fa-pen btn-icon-left" aria-hidden="true"></i>
          {{ t('serverView.edit') }}
        </Button>
        <Button outlined @click="$router.push({ name: 'roles', params: { id } })">
          <i class="fa-solid fa-users btn-icon-left" aria-hidden="true"></i>
          {{ t('serverView.roles') }}
        </Button>
        <Button outlined @click="$router.push({ name: 'databases', params: { id } })">
          <i class="fa-solid fa-database btn-icon-left" aria-hidden="true"></i>
          {{ t('serverView.databases') }}
        </Button>
        <Button outlined @click="$router.push({ name: 'monitoring', params: { id } })">
          <i class="fa-solid fa-chart-line btn-icon-left" aria-hidden="true"></i>
          {{ t('serverView.monitoring') }}
        </Button>
        <Button outlined @click="$router.push({ name: 'diagnostics', params: { id } })">
          <i class="fa-solid fa-stethoscope btn-icon-left" aria-hidden="true"></i>
          {{ t('serverView.diagnostics') }}
        </Button>
        <Button outlined @click="$router.push({ name: 'pg-config', params: { id } })">
          <i class="fa-solid fa-sliders btn-icon-left" aria-hidden="true"></i>
          {{ t('serverView.pgConfig') }}
        </Button>
      </template>
    </template>
  </PageHeader>

  <AlertBanner v-if="server && server.health_status === 'offline'" severity="danger">
    <strong>{{ server.health_error_title || t('serverView.pgUnavailable') }}</strong>
    <span v-if="server.health_error_hint"> — {{ server.health_error_hint }}</span>
    <span v-if="server.health_fail_count"> {{ t('serverView.failCount', { count: server.health_fail_count }) }}</span>
    {{ t('serverView.backupsPaused') }}
  </AlertBanner>

  <AlertBanner v-else-if="server && server.health_status === 'degraded'" severity="warn">
    <strong>{{ t('serverView.unstableConn') }}</strong>
    <span v-if="server.health_error_hint"> — {{ server.health_error_hint }}</span>
  </AlertBanner>

  <AlertBanner v-else-if="server && !server.organization_id" severity="warn">
    <strong>{{ t('serverView.orgNotAssigned') }}</strong> {{ t('serverView.orgNotAssignedDesc') }}
  </AlertBanner>

  <AlertBanner v-else-if="server && !server.storage_id" severity="info">
    {{ t('serverView.s3NotLinked') }}
    <router-link to="/settings">{{ t('serverView.s3SettingsLink') }}</router-link>.
  </AlertBanner>

  <div class="card-panel" v-if="server">
    <div class="card-panel-title">
      <span><i class="fa-solid fa-circle-info" aria-hidden="true"></i>{{ t('serverView.infoTitle') }}</span>
    </div>
    <div class="info-grid">
      <div>
        <div class="info-grid-label">{{ t('serverView.organization') }}</div>
        <div class="info-grid-value">
          <Tag v-if="server.organization_name" severity="secondary" :value="server.organization_name" />
          <Tag v-else severity="warn" :value="t('serverView.notAssigned')" />
        </div>
      </div>
      <div>
        <div class="info-grid-label">{{ t('serverView.host') }}</div>
        <div class="info-grid-value">{{ server.host }}</div>
      </div>
      <div>
        <div class="info-grid-label">{{ t('serverView.port') }}</div>
        <div class="info-grid-value">{{ server.port }}</div>
      </div>
      <div>
        <div class="info-grid-label">Admin User</div>
        <div class="info-grid-value">{{ server.admin_user }}</div>
      </div>
      <div>
        <div class="info-grid-label">{{ t('serverView.environment') }}</div>
        <div class="info-grid-value"><Tag :severity="envSeverity(server.environment)" :value="server.environment" /></div>
      </div>
      <div>
        <div class="info-grid-label">PostgreSQL</div>
        <div class="info-grid-value">{{ server.pg_major_version ? `v${server.pg_major_version}` : '—' }}</div>
      </div>
      <div>
        <div class="info-grid-label">S3</div>
        <div class="info-grid-value">{{ server.storage_name || '—' }}</div>
      </div>
      <div>
        <div class="info-grid-label">PG Health</div>
        <div class="info-grid-value">
          <Tag :severity="healthStatusSeverity(server.health_status)" :value="healthStatusLabel(server.health_status)" />
        </div>
      </div>
      <div v-if="server.health_checked_at">
        <div class="info-grid-label">{{ t('serverView.checkedAt') }}</div>
        <div class="info-grid-value">{{ formatDate(server.health_checked_at) }}</div>
      </div>
      <div>
        <div class="info-grid-label">{{ t('common.status') }}</div>
        <div class="info-grid-value">
          <Tag :severity="server.is_active ? 'success' : 'danger'" :value="serverActiveLabel(server.is_active)" />
        </div>
      </div>
      <div>
        <div class="info-grid-label">{{ t('common.created') }}</div>
        <div class="info-grid-value">{{ formatDate(server.created_at) }}</div>
      </div>
    </div>
  </div>

  <ServerFormDialog
    v-model:visible="formVisible"
    mode="edit"
    :server="server"
    :org-options="orgOptions"
    :show-org-picker="authStore.isSuperAdmin"
    :saving="formSaving"
    @submit="onFormSubmit"
  />
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from 'primevue/usetoast'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import PageHeader from '../components/ui/PageHeader.vue'
import AlertBanner from '../components/ui/AlertBanner.vue'
import ServerFormDialog from '../components/servers/ServerFormDialog.vue'
import { useServersStore } from '../stores/servers'
import { useAuthStore } from '../stores/auth'
import api from '../api/client'
import { formatDate } from '../utils/format'
import { envSeverity, serverActiveLabel } from '../utils/tags'
import { healthStatusLabel, healthStatusSeverity } from '../utils/pgHealth'

const props = defineProps<{ id: string }>()
const store = useServersStore()
const authStore = useAuthStore()
const { t } = useI18n()
const toast = useToast()

const formVisible = ref(false)
const formSaving = ref(false)
const orgOptions = ref<{ id: number; name: string }[]>([])

onMounted(async () => {
  try {
    if (!store.servers.length) await store.fetchServers()
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('serverView.toast.serversList'), detail: e?.response?.data?.detail || e?.message || t('common.loadFailed'), life: 5000 })
  }
  if (authStore.isSuperAdmin) {
    try {
      const { data } = await api.get<{ id: number; name: string }[]>('/admin/organizations')
      orgOptions.value = data.map(o => ({ id: o.id, name: o.name }))
    } catch { /* ignore */ }
  }
})

const server = computed(() => store.servers.find(s => s.id === Number(props.id)))

function openEdit() {
  formVisible.value = true
}

async function onFormSubmit(payload: Record<string, unknown>) {
  if (!server.value) return
  formSaving.value = true
  try {
    const orgId = payload.organization_id as number | undefined
    const updatePayload = { ...payload }
    delete updatePayload.organization_id
    if (Object.keys(updatePayload).length) {
      await store.updateServer(server.value.id, updatePayload)
    }
    if (authStore.isSuperAdmin && orgId && server.value.organization_id !== orgId) {
      await store.assignOrganization(server.value.id, orgId)
    }
    toast.add({ severity: 'success', summary: t('serverView.toast.serverSaved'), life: 3000 })
    formVisible.value = false
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('common.error'), detail: e.response?.data?.detail || 'Error', life: 4000 })
  } finally {
    formSaving.value = false
  }
}
</script>

<style scoped>
.btn-icon-left { margin-right: 8px; }
</style>
