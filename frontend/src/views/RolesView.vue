<template>
  <PageHeader :title="t('roles.title')" :back-to="{ name: 'server', params: { id } }" :back-label="t('common.backToServer')">
    <template #actions>
      <Button @click="showCreateUser = true">
        <i class="fa-solid fa-user-plus btn-icon-left" aria-hidden="true"></i>{{ t('roles.user') }}
      </Button>
      <Button outlined @click="showCreateSA = true">
        <i class="fa-solid fa-robot btn-icon-left" aria-hidden="true"></i>Service Account
      </Button>
    </template>
  </PageHeader>

  <div class="card-panel card-panel--table">
    <DataTable
      class="app-data-table"
      :value="roles"
      :loading="loading"
      :paginator="roles.length > 20"
      :rows="20"
      responsive-layout="stack"
      breakpoint="768px"
      striped-rows
    >
      <Column field="rolname" :header="t('roles.roleColumn')" sortable style="font-weight: 600" />
      <Column field="rolcanlogin" header="Login" style="width: 100px">
        <template #body="{ data }">
          <Tag :severity="data.rolcanlogin ? 'success' : 'secondary'" :value="data.rolcanlogin ? t('common.yes') : t('common.no')" />
        </template>
      </Column>
      <Column field="rolsuper" header="Super" style="width: 100px">
        <template #body="{ data }">
          <Tag v-if="data.rolsuper" severity="danger" value="SUPER" />
          <span v-else class="muted">—</span>
        </template>
      </Column>
      <Column header="Member of">
        <template #body="{ data }">
          <div class="flex-row" style="gap: 4px; flex-wrap: wrap">
            <Tag v-for="g in data.member_of" :key="g" :value="g" severity="info" />
          </div>
        </template>
      </Column>
    </DataTable>
  </div>

  <Dialog v-model:visible="showCreateUser" modal :header="t('roles.createUser')" :style="{ width: '450px' }">
    <div class="flex-col" style="gap: 14px">
      <div class="flex-col" style="gap: 4px">
        <label>Username</label>
        <InputText v-model="userForm.username" />
      </div>
      <div class="flex-col" style="gap: 4px">
        <label>{{ t('roles.password') }} <span class="muted" style="font-size: 12px">{{ t('roles.passwordHint') }}</span></label>
        <Password v-model="userForm.password" :feedback="false" toggleMask fluid />
      </div>
      <div class="flex-col" style="gap: 4px">
        <label>{{ t('roles.group') }}</label>
        <Select v-model="userForm.group" :options="groupOptions" option-label="label" option-value="value" />
      </div>
    </div>
    <template #footer>
      <Button text @click="showCreateUser = false">{{ t('common.cancel') }}</Button>
      <Button :loading="submittingUser" :disabled="submittingUser" @click="submitUser(createUser)">{{ t('common.create') }}</Button>
    </template>
  </Dialog>

  <Dialog v-model:visible="showCreateSA" modal header="Service Account" :style="{ width: '450px' }">
    <div class="flex-col" style="gap: 14px">
      <div class="flex-col" style="gap: 4px">
        <label>Username</label>
        <InputText v-model="saForm.username" />
      </div>
      <div class="flex-col" style="gap: 4px">
        <label>{{ t('common.database') }}</label>
        <InputText v-model="saForm.database" />
      </div>
      <div class="flex-col" style="gap: 4px">
        <label>{{ t('roles.password') }} <span class="muted" style="font-size: 12px">{{ t('roles.passwordHint') }}</span></label>
        <Password v-model="saForm.password" :feedback="false" toggleMask fluid />
      </div>
    </div>
    <template #footer>
      <Button text @click="showCreateSA = false">{{ t('common.cancel') }}</Button>
      <Button :loading="submittingSA" :disabled="submittingSA" @click="submitSA(createServiceAccount)">{{ t('common.create') }}</Button>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from 'primevue/usetoast'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import PageHeader from '../components/ui/PageHeader.vue'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Select from 'primevue/select'
import api from '../api/client'
import type { Role } from '../api/types'
import { useSubmitting } from '../composables/useSubmitting'

const props = defineProps<{ id: string }>()
const { t } = useI18n()
const toast = useToast()
const { submitting: submittingUser, submit: submitUser } = useSubmitting()
const { submitting: submittingSA, submit: submitSA } = useSubmitting()
const roles = ref<Role[]>([])
const loading = ref(false)
const showCreateUser = ref(false)
const showCreateSA = ref(false)
const userForm = reactive({ username: '', password: '', group: 'app_users' })
const saForm = reactive({ username: '', database: '', password: '' })

const groupOptions = [
  { label: 'app_users', value: 'app_users' },
  { label: 'main', value: 'main' },
]

async function fetchRoles() {
  loading.value = true
  try {
    const { data } = await api.get<Role[]>(`/servers/${props.id}/roles`)
    roles.value = data
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('roles.title'), detail: e?.response?.data?.detail || e?.message || t('common.loadFailed'), life: 5000 })
  } finally { loading.value = false }
}

async function createUser() {
  try {
    const { data } = await api.post(`/servers/${props.id}/roles/user`, userForm)
    toast.add({ severity: 'success', summary: t('roles.created'), detail: `${data.username} / ${data.password}`, life: 8000 })
    showCreateUser.value = false
    fetchRoles()
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('common.error'), detail: e.response?.data?.detail || 'Error', life: 4000 })
  }
}

async function createServiceAccount() {
  try {
    const { data } = await api.post(`/servers/${props.id}/roles/service-account`, saForm)
    toast.add({ severity: 'success', summary: t('roles.created'), detail: `${data.username} / ${data.password}`, life: 8000 })
    showCreateSA.value = false
    fetchRoles()
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('common.error'), detail: e.response?.data?.detail || 'Error', life: 4000 })
  }
}

onMounted(fetchRoles)
</script>
