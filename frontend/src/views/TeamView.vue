<template>
  <PageHeader
    :title="pageTitle"
    :subtitle="pageSubtitle"
  >
    <template #actions>
      <Button outlined severity="secondary" @click="openRolesHelp" :disabled="!hasOrgContext">
        <i class="fa-solid fa-circle-info btn-icon-left" aria-hidden="true"></i>
        {{ t('team.rolesHelp') }}
      </Button>
      <Button @click="openCreate" :disabled="!hasOrgContext">
        <i class="fa-solid fa-user-plus btn-icon-left" aria-hidden="true"></i>
        {{ t('team.addMember') }}
      </Button>
    </template>
  </PageHeader>

  <div class="card-panel card-panel--table">
    <DataTable
      class="app-data-table"
      :value="members"
      :loading="loading"
      striped-rows
      size="small"
      responsive-layout="stack"
      breakpoint="768px"
    >
      <template #empty>
        <div class="team-empty" v-if="!loading">
          <i class="fa-solid fa-users team-empty-icon" aria-hidden="true"></i>
          <p class="team-empty-title">{{ t('team.emptyTitle') }}</p>
          <Button v-if="hasOrgContext" size="small" @click="openCreate">
            <i class="fa-solid fa-user-plus btn-icon-left" aria-hidden="true"></i>
            {{ t('team.addFirstUser') }}
          </Button>
        </div>
      </template>

      <Column :header="t('team.member')">
        <template #body="{ data }">
          <div class="member-identity">
            <span class="member-identity-name">{{ data.username }}</span>
            <span class="member-identity-email">{{ data.email }}</span>
          </div>
        </template>
      </Column>

      <Column :header="t('team.role')">
        <template #body="{ data }">
          <Tag :value="roleLabel(data.org_role)" :severity="roleSeverity(data.org_role)" />
        </template>
      </Column>

      <Column :header="t('team.serverAccess')">
        <template #body="{ data }">
          <span class="access-summary" :class="accessSummaryClass(data)">
            <i :class="accessSummaryIcon(data)" class="access-summary-icon" aria-hidden="true"></i>
            {{ accessSummaryText(data) }}
          </span>
        </template>
      </Column>

      <Column :header="t('common.status')">
        <template #body="{ data }">
          <Tag :value="data.is_active ? t('team.active') : t('team.inactive')" :severity="data.is_active ? 'success' : 'danger'" />
        </template>
      </Column>

      <Column header="" style="width: 72px" body-class="team-actions-cell">
        <template #body="{ data }">
          <Button
            text
            rounded
            size="small"
            :aria-label="t('team.editMember')"
            v-tooltip.left="t('common.edit')"
            @click="openEdit(data)"
          >
            <i class="fa-solid fa-pen" aria-hidden="true"></i>
          </Button>
        </template>
      </Column>
    </DataTable>
  </div>

  <!-- Единая карточка участника: личность → роль → доступ -->
  <Dialog
    v-model:visible="dialogVisible"
    :header="dialogMode === 'create' ? t('team.newMember') : t('team.memberTitle', { name: form.username })"
    modal
    class="member-dialog"
    style="width: 540px"
  >
    <div class="flex-col dialog-body">
      <!-- 1. Учётные данные -->
      <section class="dialog-section">
        <span class="dialog-section-label">{{ t('team.credentials') }}</span>
        <template v-if="dialogMode === 'create'">
          <div class="form-field">
            <label class="form-label" for="m-username">{{ t('team.login') }}</label>
            <InputText id="m-username" v-model="form.username" fluid autocomplete="off" />
          </div>
          <div class="form-field">
            <label class="form-label" for="m-email">Email</label>
            <InputText id="m-email" v-model="form.email" type="email" fluid autocomplete="off" />
          </div>
        </template>
        <div class="form-field">
          <label class="form-label" for="m-password">
            {{ dialogMode === 'create' ? t('team.password') : t('team.newPasswordOptional') }}
          </label>
          <Password id="m-password" v-model="form.password" :feedback="false" toggle-mask fluid />
        </div>
        <div v-if="dialogMode === 'edit'" class="form-field form-inline">
          <ToggleSwitch v-model="form.is_active" input-id="m-active" />
          <label for="m-active">{{ t('team.accountActive') }}</label>
        </div>
      </section>

      <!-- 2. Роль + пояснение прав -->
      <section class="dialog-section">
        <span class="dialog-section-label">{{ t('team.roleSectionLabel') }}</span>
        <div class="form-field">
          <Select
            v-model="form.org_role"
            :options="roleOptions"
            option-label="label"
            option-value="value"
            fluid
          />
        </div>
        <div class="role-caps" v-if="roleCaps.length">
          <span class="role-caps-hint">{{ roleCapsHint }}</span>
          <div class="role-caps-list">
            <Tag
              v-for="cap in roleCaps"
              :key="cap"
              :value="cap"
              severity="secondary"
            />
          </div>
        </div>
      </section>

      <!-- 3. Доступ к серверам/базам -->
      <section class="dialog-section">
        <span class="dialog-section-label">{{ t('team.accessSectionLabel') }}</span>

        <AlertBanner v-if="isAllServersRole(form.org_role)" severity="info">
          <strong>{{ t('team.roleAdmin') }}</strong> {{ t('team.adminSeesAllServers') }}
        </AlertBanner>

        <template v-else>
          <div class="form-field">
            <MultiSelect
              v-model="accessForm.server_ids"
              :options="servers"
              option-label="name"
              option-value="id"
              :placeholder="t('team.selectServers')"
              display="chip"
              filter
              :show-toggle-all="true"
              fluid
            />
          </div>

          <AlertBanner v-if="!accessForm.server_ids.length" severity="warn" class="access-empty-hint">
            {{ t('team.noServersWarning') }}
          </AlertBanner>

          <div v-else class="access-databases-section">
            <span class="access-db-title">{{ t('team.dbRestriction') }}</span>
            <p class="access-db-hint">{{ t('team.dbRestrictionHint') }}</p>
            <div
              v-for="sid in accessForm.server_ids"
              :key="sid"
              class="access-server-db-block"
            >
              <label class="access-server-db-label">{{ serverName(sid) }}</label>
              <MultiSelect
                :model-value="selectedDatabases[sid] ?? []"
                :options="serverDbOptions[sid] ?? []"
                :loading="!!serverDbLoading[sid]"
                :placeholder="t('team.allDatabases')"
                display="chip"
                filter
                fluid
                @update:model-value="(v) => setSelectedDatabases(sid, v)"
              />
            </div>
          </div>
        </template>
      </section>
    </div>

    <template #footer>
      <Button :label="t('common.cancel')" text @click="dialogVisible = false" />
      <Button
        :label="dialogMode === 'create' ? t('team.createMember') : t('common.save')"
        :loading="saving"
        @click="submitMember"
      />
    </template>
  </Dialog>

  <!-- Справочник ролей -->
  <Dialog v-model:visible="rolesHelpVisible" :header="t('team.rolesAndPermissions')" modal style="width: 640px">
    <p class="access-hint" v-html="t('team.rolesHelpIntro')"></p>
    <div v-if="rolesCatalogLoading" class="roles-help-loading">{{ t('common.loading') }}</div>
    <div v-else class="roles-help-list">
      <div v-for="role in rolesCatalog" :key="role.role" class="roles-help-card">
        <div class="roles-help-card-head">
          <Tag :value="role.label" :severity="roleSeverity(role.role)" />
          <Tag
            :value="role.all_servers ? t('team.allServers') : t('team.accessByConfig')"
            :severity="role.all_servers ? 'success' : 'secondary'"
          />
        </div>
        <div class="roles-help-perms">
          <span
            v-for="permId in role.permissions"
            :key="permId"
            class="roles-help-perm"
          >
            <i class="fa-solid fa-check roles-help-perm-icon" aria-hidden="true"></i>
            {{ permissionLabel(permId) }}
          </span>
          <span v-if="!role.permissions.length" class="muted">{{ t('team.noExtraPerms') }}</span>
        </div>
      </div>
    </div>
    <template #footer>
      <Button :label="t('common.close')" @click="rolesHelpVisible = false" />
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Select from 'primevue/select'
import MultiSelect from 'primevue/multiselect'
import ToggleSwitch from 'primevue/toggleswitch'
import { useToast } from 'primevue/usetoast'
import PageHeader from '../components/ui/PageHeader.vue'
import AlertBanner from '../components/ui/AlertBanner.vue'
import api from '../api/client'
import { useAuthStore } from '../stores/auth'
import { useServersStore } from '../stores/servers'

interface MemberRow {
  id: number
  user_id: number
  username: string
  email: string
  org_role: string
  is_active: boolean
  all_servers: boolean
  server_ids: number[]
}

interface OrgRoleInfo {
  role: string
  label: string
  all_servers: boolean
  permissions: string[]
}

interface OrgPermissionInfo {
  id: string
  label: string
}

interface MemberAccessResponse {
  all_servers: boolean
  server_ids: number[]
  databases: { server_id: number; database_name: string }[]
}

const toast = useToast()
const { t } = useI18n()
const authStore = useAuthStore()
const serversStore = useServersStore()

const members = ref<MemberRow[]>([])
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const rolesHelpVisible = ref(false)
const rolesCatalogLoading = ref(false)
const rolesCatalog = ref<OrgRoleInfo[]>([])
const permissionLabels = ref<Record<string, string>>({})

// Единая форма участника (личность + роль) и форма доступа.
const form = reactive({
  id: 0,
  username: '',
  email: '',
  password: '',
  org_role: 'viewer',
  is_active: true,
})
const accessForm = reactive({ server_ids: [] as number[] })
const serverDbOptions = ref<Record<number, string[]>>({})
const serverDbLoading = ref<Record<number, boolean>>({})
const selectedDatabases = ref<Record<number, string[]>>({})

const roleOptions = computed(() => [
  { label: t('team.roleAdmin'), value: 'org_admin' },
  { label: t('team.roleOperator'), value: 'operator' },
  { label: t('team.roleViewer'), value: 'viewer' },
])

const servers = computed(() => serversStore.servers)

const hasOrgContext = computed(() =>
  !authStore.isSuperAdmin || authStore.activeOrgId != null
)

const pageTitle = computed(() => t('team.pageTitle'))
const pageSubtitle = computed(() => t('team.pageSubtitle'))

function roleLabel(role: string) {
  return rolesCatalog.value.find((r) => r.role === role)?.label
    || roleOptions.value.find((r) => r.value === role)?.label
    || role
}

function roleSeverity(role: string): string {
  if (role === 'org_admin') return 'danger'
  if (role === 'operator') return 'info'
  return 'secondary'
}

function permissionLabel(permId: string) {
  return permissionLabels.value[permId] || permId
}

function isAllServersRole(role: string): boolean {
  const info = rolesCatalog.value.find((r) => r.role === role)
  if (info) return info.all_servers
  return role === 'org_admin'
}

// Пояснение прав выбранной роли — чипами прямо в диалоге.
const roleCaps = computed(() => {
  const info = rolesCatalog.value.find((r) => r.role === form.org_role)
  if (!info) return []
  return info.permissions.map((p) => permissionLabel(p))
})

const roleCapsHint = computed(() =>
  isAllServersRole(form.org_role)
    ? t('team.roleCapsFullAccess')
    : t('team.roleCapsAvailable')
)

// ——— Сводка доступа в таблице ———
function accessSummaryText(row: MemberRow): string {
  if (row.all_servers) return t('team.allServers')
  const n = row.server_ids?.length ?? 0
  if (!n) return t('team.noAccess')
  return t('team.serverCount', n)
}

function accessSummaryClass(row: MemberRow): string {
  if (row.all_servers) return 'access-summary--all'
  if (!(row.server_ids?.length)) return 'access-summary--none'
  return 'access-summary--some'
}

function accessSummaryIcon(row: MemberRow): string {
  if (row.all_servers) return 'fa-solid fa-globe'
  if (!(row.server_ids?.length)) return 'fa-solid fa-ban'
  return 'fa-solid fa-server'
}

function serverName(serverId: number) {
  return servers.value.find((s) => s.id === serverId)?.name || t('team.serverFallback', { id: serverId })
}

function setSelectedDatabases(serverId: number, names: string[]) {
  selectedDatabases.value = { ...selectedDatabases.value, [serverId]: names }
}

async function loadServerDatabases(serverId: number) {
  serverDbLoading.value = { ...serverDbLoading.value, [serverId]: true }
  try {
    const { data } = await api.get<{ datname: string }[]>(`/servers/${serverId}/databases`)
    serverDbOptions.value = {
      ...serverDbOptions.value,
      [serverId]: data.map((d) => d.datname),
    }
  } catch (e: any) {
    serverDbOptions.value = { ...serverDbOptions.value, [serverId]: [] }
    toast.add({
      severity: 'warn',
      summary: serverName(serverId),
      detail: e.response?.data?.detail || t('team.dbLoadFailed'),
      life: 4000,
    })
  } finally {
    serverDbLoading.value = { ...serverDbLoading.value, [serverId]: false }
  }
}

function syncDatabaseLoaders(serverIds: number[]) {
  const idSet = new Set(serverIds)
  const nextSelected = { ...selectedDatabases.value }
  const nextOptions = { ...serverDbOptions.value }
  const nextLoading = { ...serverDbLoading.value }
  for (const sid of Object.keys(nextSelected).map(Number)) {
    if (!idSet.has(sid)) {
      delete nextSelected[sid]
      delete nextOptions[sid]
      delete nextLoading[sid]
    }
  }
  selectedDatabases.value = nextSelected
  serverDbOptions.value = nextOptions
  serverDbLoading.value = nextLoading
  for (const sid of serverIds) {
    if (nextOptions[sid] === undefined) {
      if (nextSelected[sid] === undefined) {
        selectedDatabases.value = { ...selectedDatabases.value, [sid]: [] }
      }
      loadServerDatabases(sid)
    }
  }
}

watch(
  () => [...accessForm.server_ids],
  (serverIds) => syncDatabaseLoaders(serverIds),
)

function buildDatabasesPayload() {
  const out: { server_id: number; database_name: string }[] = []
  for (const sid of accessForm.server_ids) {
    for (const name of selectedDatabases.value[sid] ?? []) {
      out.push({ server_id: sid, database_name: name })
    }
  }
  return out
}

function resetAccessForm() {
  accessForm.server_ids = []
  selectedDatabases.value = {}
  serverDbOptions.value = {}
  serverDbLoading.value = {}
}

async function loadRolesCatalog() {
  if (rolesCatalog.value.length) return
  rolesCatalogLoading.value = true
  try {
    const { data } = await api.get<{ permissions: OrgPermissionInfo[]; roles: OrgRoleInfo[] }>(
      '/organizations/org-roles'
    )
    rolesCatalog.value = data.roles
    permissionLabels.value = Object.fromEntries(data.permissions.map((p) => [p.id, p.label]))
    for (const role of data.roles) {
      permissionLabels.value[role.role] = role.label
    }
  } catch (e: any) {
    toast.add({
      severity: 'error',
      summary: t('team.rolesSummary'),
      detail: e.response?.data?.detail || t('team.helpLoadFailed'),
      life: 4000,
    })
  } finally {
    rolesCatalogLoading.value = false
  }
}

async function openRolesHelp() {
  rolesHelpVisible.value = true
  await loadRolesCatalog()
}

async function loadMembers() {
  if (!hasOrgContext.value) {
    members.value = []
    return
  }
  loading.value = true
  try {
    const { data } = await api.get<MemberRow[]>('/organizations/members')
    members.value = data
  } catch (e: any) {
    members.value = []
    toast.add({ severity: 'error', summary: e.response?.data?.detail || t('team.membersLoadFailed'), life: 5000 })
  } finally {
    loading.value = false
  }
}

function openCreate() {
  if (!hasOrgContext.value) return
  dialogMode.value = 'create'
  form.id = 0
  form.username = ''
  form.email = ''
  form.password = ''
  form.org_role = 'viewer'
  form.is_active = true
  resetAccessForm()
  dialogVisible.value = true
}

async function openEdit(row: MemberRow) {
  dialogMode.value = 'edit'
  form.id = row.id
  form.username = row.username
  form.email = row.email
  form.password = ''
  form.org_role = row.org_role
  form.is_active = row.is_active
  resetAccessForm()
  dialogVisible.value = true
  // Подгружаем текущий доступ участника (кроме Администратора — у него все серверы).
  if (!isAllServersRole(row.org_role)) {
    try {
      const { data } = await api.get<MemberAccessResponse>(`/organizations/members/${row.id}/access`)
      if (data.all_servers) return
      const dbByServer: Record<number, string[]> = {}
      for (const item of data.databases) {
        if (!dbByServer[item.server_id]) dbByServer[item.server_id] = []
        dbByServer[item.server_id].push(item.database_name)
      }
      selectedDatabases.value = dbByServer
      accessForm.server_ids = [
        ...new Set([...data.server_ids, ...data.databases.map((d) => d.server_id)]),
      ]
      syncDatabaseLoaders(accessForm.server_ids)
    } catch (e: any) {
      toast.add({
        severity: 'error',
        summary: t('team.memberAccess'),
        detail: e.response?.data?.detail || t('team.accessLoadFailed'),
        life: 4000,
      })
    }
  }
}

async function submitMember() {
  // Синхронный guard от двойного клика: saving выставляем до первого await.
  if (saving.value) return
  saving.value = true
  try {
    let memberId = form.id
    if (dialogMode.value === 'create') {
      const { data } = await api.post<{ id: number }>('/organizations/members', {
        username: form.username,
        email: form.email,
        password: form.password,
        org_role: form.org_role,
      })
      memberId = data.id
    } else {
      const payload: Record<string, unknown> = {
        org_role: form.org_role,
        is_active: form.is_active,
      }
      if (form.password) payload.password = form.password
      await api.patch(`/organizations/members/${memberId}`, payload)
    }

    // Доступ сохраняем только для scoped-ролей; Администратору не требуется.
    if (!isAllServersRole(form.org_role)) {
      await api.put(`/organizations/members/${memberId}/access`, {
        server_ids: accessForm.server_ids,
        databases: buildDatabasesPayload(),
      })
    }

    dialogVisible.value = false
    await loadMembers()
    toast.add({
      severity: 'success',
      summary: dialogMode.value === 'create' ? t('team.memberCreated') : t('team.saved'),
      life: 3000,
    })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: e.response?.data?.detail || t('common.error'), life: 5000 })
  } finally {
    saving.value = false
  }
}

// Супер-админ получает org-контекст асинхронно (авто-выбор единственной
// организации в AppLayout) — перезагружаем список, когда контекст появился.
watch(() => authStore.activeOrgId, () => {
  loadMembers()
})

onMounted(async () => {
  try {
    if (!serversStore.servers.length) await serversStore.fetchServers()
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('common.serversList'), detail: e?.response?.data?.detail || e?.message || t('common.loadFailed'), life: 5000 })
  }
  await loadRolesCatalog()
  await loadMembers()
})
</script>

<style scoped>
.dialog-body { gap: 22px; }

/* Секции диалога */
.dialog-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.dialog-section-label {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-color-secondary);
  padding-bottom: 8px;
  border-bottom: 1px solid var(--surface-border);
}
.form-inline {
  flex-direction: row;
  align-items: center;
  gap: 10px;
}

/* Идентичность участника в таблице */
.member-identity {
  display: flex;
  flex-direction: column;
  line-height: 1.35;
}
.member-identity-name {
  font-weight: 600;
  color: var(--text-color);
}
.member-identity-email {
  font-size: 12px;
  color: var(--text-color-secondary);
}

/* Пояснение прав роли */
.role-caps {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 14px;
  border: 1px solid var(--surface-border);
  border-radius: 10px;
  background: var(--surface-ground);
}
.role-caps-hint {
  font-size: 12px;
  color: var(--text-color-secondary);
}
.role-caps-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

/* Сводка доступа в таблице */
.access-summary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
}
.access-summary-icon { font-size: 12px; }
.access-summary--all { color: var(--p-green-400, #4ade80); }
.access-summary--some { color: var(--text-color); }
.access-summary--none { color: var(--p-orange-400, #fb923c); }

/* Доступ к базам */
.access-databases-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.access-db-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-color);
}
.access-db-hint {
  margin: 0;
  font-size: 12px;
  color: var(--text-color-secondary);
}
.access-empty-hint { margin: 0; }
.access-server-db-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.access-server-db-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-color);
}

/* Пустое состояние таблицы */
.team-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 40px 16px;
  text-align: center;
}
.team-empty-icon {
  font-size: 32px;
  color: var(--text-color-secondary);
  opacity: 0.6;
}
.team-empty-title {
  margin: 0;
  color: var(--text-color-secondary);
}

/* Справочник ролей */
.access-hint {
  margin: 0 0 16px;
  font-size: 13px;
  color: var(--text-color-secondary);
  line-height: 1.5;
}
.roles-help-loading {
  padding: 24px;
  text-align: center;
  color: var(--text-color-secondary);
}
.roles-help-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.roles-help-card {
  border: 1px solid var(--surface-border);
  border-radius: 10px;
  padding: 14px;
  background: var(--surface-ground);
}
.roles-help-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.roles-help-perms {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 18px;
}
.roles-help-perm {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-color);
}
.roles-help-perm-icon {
  font-size: 11px;
  color: var(--p-green-400, #4ade80);
}
.muted { color: var(--text-color-secondary); }

:deep(.team-actions-cell) { text-align: right; }
</style>
