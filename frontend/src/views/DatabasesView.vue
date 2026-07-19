<template>
  <PageHeader :title="t('databases.title')" :back-to="{ name: 'server', params: { id } }" :back-label="t('common.backToServer')">
    <template #actions>
      <Button @click="showCreate = true">
        <i class="fa-solid fa-plus btn-icon-left" aria-hidden="true"></i>{{ t('databases.createDb') }}
      </Button>
    </template>
  </PageHeader>

  <div class="card-panel card-panel--table">
    <DataTable
      class="app-data-table"
      :value="databases"
      :loading="loading"
      :paginator="databases.length > 20"
      :rows="20"
      responsive-layout="stack"
      breakpoint="768px"
      striped-rows
    >
      <Column field="datname" :header="t('common.database')" sortable style="font-weight: 600" />
      <Column field="owner" :header="t('databases.owner')" sortable />
      <Column field="size" :header="t('databases.size')" sortable />
      <Column field="encoding" header="Encoding" />
      <Column field="datacl" header="ACL">
        <template #body="{ data }">
          <span class="muted" style="font-size: 12px">{{ data.datacl || '—' }}</span>
        </template>
      </Column>
    </DataTable>
  </div>

  <Dialog v-model:visible="showCreate" modal :header="t('databases.createDb')" :style="{ width: '450px' }">
    <div class="flex-col" style="gap: 14px">
      <div class="flex-col" style="gap: 4px">
        <label>{{ t('common.name') }}</label>
        <InputText v-model="form.name" />
      </div>
      <div class="flex-col" style="gap: 4px">
        <label>{{ t('databases.mode') }}</label>
        <Select v-model="form.mode" :options="modeOptions" option-label="label" option-value="value" />
      </div>
      <div v-if="form.mode === 'restricted'" class="flex-row" style="gap: 8px; align-items: center">
        <ToggleSwitch v-model="form.with_service" />
        <label>{{ t('databases.serviceAccountLabel') }}</label>
      </div>
    </div>
    <template #footer>
      <Button text @click="showCreate = false">{{ t('common.cancel') }}</Button>
      <Button :loading="submitting" :disabled="submitting" @click="submit(createDb)">{{ t('common.create') }}</Button>
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
import PageHeader from '../components/ui/PageHeader.vue'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import ToggleSwitch from 'primevue/toggleswitch'
import api from '../api/client'
import type { Database } from '../api/types'
import { useSubmitting } from '../composables/useSubmitting'

const props = defineProps<{ id: string }>()
const { t } = useI18n()
const toast = useToast()
const { submitting, submit } = useSubmitting()
const databases = ref<Database[]>([])
const loading = ref(false)
const showCreate = ref(false)
const form = reactive({ name: '', mode: 'shared', with_service: false })

const modeOptions = [
  { label: 'Shared', value: 'shared' },
  { label: 'Restricted', value: 'restricted' },
]

async function fetchDatabases() {
  loading.value = true
  try {
    const { data } = await api.get<Database[]>(`/servers/${props.id}/databases`)
    databases.value = data
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('databases.title'), detail: e?.response?.data?.detail || e?.message || t('common.loadFailed'), life: 5000 })
  } finally { loading.value = false }
}

async function createDb() {
  try {
    await api.post(`/servers/${props.id}/databases`, form)
    toast.add({ severity: 'success', summary: t('databases.created'), detail: form.name, life: 3000 })
    showCreate.value = false
    fetchDatabases()
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('common.error'), detail: e.response?.data?.detail || 'Error', life: 4000 })
  }
}

onMounted(fetchDatabases)
</script>
