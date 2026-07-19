<template>
  <PageHeader :title="t('admin.title')" :subtitle="t('admin.subtitle')" />

  <div class="card-panel card-panel--tabs">
    <Tabs value="orgs">
      <TabList>
        <Tab value="orgs"><i class="fa-solid fa-building" style="margin-right: 8px"></i>{{ t('admin.organizations') }}</Tab>
        <Tab value="users"><i class="fa-solid fa-users" style="margin-right: 8px"></i>{{ t('admin.users') }}</Tab>
      </TabList>
      <TabPanels>
        <TabPanel value="orgs">
          <DataTable class="app-data-table" :value="organizations" :loading="loading" striped-rows>
            <Column field="id" header="ID" style="width: 70px" />
            <Column field="name" :header="t('common.name')" />
            <Column field="slug" header="Slug" />
            <Column field="members_count" :header="t('admin.membersCount')" style="width: 120px" />
            <Column :header="t('common.actions')" style="width: 160px">
              <template #body="{ data }">
                <Button size="small" outlined @click="selectOrg(data)">
                  {{ t('admin.manageCompany') }}
                </Button>
              </template>
            </Column>
          </DataTable>
        </TabPanel>
        <TabPanel value="users">
          <DataTable class="app-data-table" :value="users" :loading="loadingUsers" striped-rows>
            <Column field="id" header="ID" style="width: 70px" />
            <Column field="username" :header="t('admin.login')" />
            <Column field="email" header="Email" />
            <Column field="role" header="Platform role" style="width: 120px">
              <template #body="{ data }">
                <Tag :value="data.role" :severity="data.role === 'admin' ? 'warn' : 'secondary'" />
              </template>
            </Column>
            <Column :header="t('admin.organizations')">
              <template #body="{ data }">
                <span v-if="!data.organizations.length" class="text-muted">—</span>
                <span v-else>{{ data.organizations.map((o: any) => `${o.organization_name} (${o.org_role})`).join(', ') }}</span>
              </template>
            </Column>
          </DataTable>
        </TabPanel>
      </TabPanels>
    </Tabs>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import { useToast } from 'primevue/usetoast'
import PageHeader from '../components/ui/PageHeader.vue'
import api from '../api/client'
import { useAuthStore } from '../stores/auth'
import { useServersStore } from '../stores/servers'

interface OrgRow {
  id: number
  name: string
  slug: string
  members_count: number
}

const toast = useToast()
const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const serversStore = useServersStore()

const organizations = ref<OrgRow[]>([])
const users = ref<any[]>([])
const loading = ref(false)
const loadingUsers = ref(false)

async function loadOrgs() {
  loading.value = true
  try {
    const { data } = await api.get<OrgRow[]>('/admin/organizations')
    organizations.value = data
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('admin.orgsList'), detail: e?.response?.data?.detail || e?.message || t('common.loadFailed'), life: 5000 })
  } finally {
    loading.value = false
  }
}

async function loadUsers() {
  loadingUsers.value = true
  try {
    const { data } = await api.get('/admin/users')
    users.value = data
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('admin.usersList'), detail: e?.response?.data?.detail || e?.message || t('common.loadFailed'), life: 5000 })
  } finally {
    loadingUsers.value = false
  }
}

async function selectOrg(org: OrgRow) {
  authStore.setActiveOrganizationId(org.id)
  try {
    await serversStore.fetchServers()
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('common.serversList'), detail: e?.response?.data?.detail || e?.message || t('common.loadFailed'), life: 5000 })
  }
  toast.add({ severity: 'info', summary: t('admin.contextSet', { name: org.name }), life: 3000 })
  router.push('/')
}

onMounted(() => {
  loadOrgs()
  loadUsers()
})
</script>

<style scoped>
.text-muted { color: var(--text-color-secondary); }
</style>
