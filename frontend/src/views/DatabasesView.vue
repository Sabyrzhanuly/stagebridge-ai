<template>
  <PageHeader :title="t('databases.title')" :back-to="{ name: 'server', params: { id } }" :back-label="t('common.backToServer')">
    <template #actions>
      <Button @click="showCreate = true">
        <i class="fa-solid fa-plus btn-icon-left" aria-hidden="true"></i>{{ t('databases.createDb') }}
      </Button>
    </template>
  </PageHeader>

  <div class="card-panel nl-sql-panel">
    <div class="card-panel-title">
      <span><i class="fa-solid fa-terminal" aria-hidden="true"></i>{{ t('nlToSql.title') }}</span>
    </div>
    <div class="nl-sql-controls">
      <Select
        v-model="selectedNlDb"
        :options="databaseOptions"
        option-label="label"
        option-value="value"
        :placeholder="t('nlToSql.selectDatabase')"
        class="nl-sql-db"
      />
      <Textarea
        v-model="nlQuestion"
        :placeholder="t('nlToSql.placeholder')"
        rows="3"
        auto-resize
        class="nl-sql-question"
      />
      <Button :loading="nlLoading" :disabled="nlRunDisabled" @click="runNlToSql">
        <i class="fa-solid fa-play btn-icon-left" aria-hidden="true"></i>{{ t('common.run') }}
      </Button>
    </div>
    <span v-if="!aiAvailable" class="nl-sql-muted">{{ t('nlToSql.aiDisabledHint') }}</span>
    <div v-if="nlError" class="nl-sql-error">{{ nlError }}</div>

    <div v-if="nlResult" class="nl-sql-result">
      <div>
        <strong>{{ t('nlToSql.generatedSql') }}</strong>
        <pre class="nl-sql-code"><code>{{ nlResult.sql || '—' }}</code></pre>
      </div>
      <p v-if="nlResult.explanation" class="nl-sql-text">
        <strong>{{ t('nlToSql.explanation') }}:</strong> {{ nlResult.explanation }}
      </p>
      <p v-if="!nlResult.executed" class="nl-sql-not-executed">
        <strong>{{ t('nlToSql.notExecuted') }}:</strong> {{ nlResult.reason || t('nlToSql.reason') }}
      </p>
      <div v-if="Array.isArray(nlResult.notes) && nlResult.notes.length" class="nl-sql-notes">
        <strong>{{ t('nlToSql.notes') }}</strong>
        <ul>
          <li v-for="(note, i) in nlResult.notes" :key="i">{{ note }}</li>
        </ul>
      </div>

      <div v-if="nlResult.executed" class="nl-sql-table-wrap">
        <strong>{{ t('nlToSql.rowsReturned', { count: nlResult.row_count ?? nlRows.length }) }}</strong>
        <DataTable
          v-if="nlRows.length"
          class="app-data-table nl-sql-table"
          :value="nlRows"
          :paginator="nlRows.length > 20"
          :rows="20"
          responsive-layout="scroll"
          striped-rows
        >
          <Column v-for="col in nlColumns" :key="col" :header="col">
            <template #body="{ data }">{{ formatCell(data[col]) }}</template>
          </Column>
        </DataTable>
        <p v-else class="nl-sql-muted">{{ t('nlToSql.noRows') }}</p>
      </div>
    </div>
  </div>

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
      <Column :header="t('schemaReview.action')" style="width: 180px">
        <template #body="{ data }">
          <Button size="small" outlined severity="secondary" @click.stop="selectSchemaDb(data.datname)">
            <i class="fa-solid fa-wand-magic-sparkles btn-icon-left" aria-hidden="true"></i>
            {{ t('schemaReview.action') }}
          </Button>
        </template>
      </Column>
    </DataTable>

    <AiInsight
      v-if="selectedSchemaDb"
      :key="selectedSchemaDb"
      class="schema-review-panel"
      :label="t('schemaReview.label')"
      endpoint="/ai/schema-review"
      :payload="schemaReviewPayload"
      :sections="schemaReviewSections"
      badge-field="severity"
      auto-run
    />
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
import { computed, ref, reactive, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from 'primevue/usetoast'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import PageHeader from '../components/ui/PageHeader.vue'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Select from 'primevue/select'
import ToggleSwitch from 'primevue/toggleswitch'
import AiInsight from '../components/AiInsight.vue'
import api from '../api/client'
import type { Database } from '../api/types'
import { useSubmitting } from '../composables/useSubmitting'

const props = defineProps<{ id: string }>()
const { t, locale } = useI18n()
const toast = useToast()
const { submitting, submit } = useSubmitting()
const databases = ref<Database[]>([])
const loading = ref(false)
const showCreate = ref(false)
const selectedSchemaDb = ref('')
const selectedNlDb = ref('')
const nlQuestion = ref('')
const nlLoading = ref(false)
const nlError = ref('')
const aiAvailable = ref(false)
const form = reactive({ name: '', mode: 'shared', with_service: false })

interface NlToSqlResult {
  sql: string
  explanation?: string
  notes?: string[]
  executed: boolean
  reason?: string
  columns?: string[]
  rows?: Record<string, unknown>[]
  row_count?: number
}

const nlResult = ref<NlToSqlResult | null>(null)

const modeOptions = [
  { label: 'Shared', value: 'shared' },
  { label: 'Restricted', value: 'restricted' },
]

const schemaReviewSections = computed(() => [
  { key: 'issues', title: t('schemaReview.secIssues') },
  { key: 'recommendations', title: t('schemaReview.secRecommendations') },
  { key: 'notes', title: t('schemaReview.secNotes') },
])
const databaseOptions = computed(() => databases.value.map((db) => ({ label: db.datname, value: db.datname })))
const nlRows = computed(() => nlResult.value?.rows || [])
const nlColumns = computed(() => nlResult.value?.columns || (nlRows.value[0] ? Object.keys(nlRows.value[0]) : []))
const nlRunDisabled = computed(() => nlLoading.value || !aiAvailable.value || !selectedNlDb.value || !nlQuestion.value.trim())

function selectSchemaDb(name: string) {
  selectedSchemaDb.value = name
}

function schemaReviewPayload() {
  return {
    server_id: Number(props.id),
    database: selectedSchemaDb.value,
  }
}

async function fetchAiStatus() {
  try {
    const { data } = await api.get('/ai/status')
    aiAvailable.value = !!data.available
  } catch {
    aiAvailable.value = false
  }
}

async function runNlToSql() {
  if (nlRunDisabled.value) return
  nlLoading.value = true
  nlError.value = ''
  nlResult.value = null
  try {
    const { data } = await api.post<NlToSqlResult>('/ai/nl-to-sql', {
      server_id: Number(props.id),
      database: selectedNlDb.value,
      question: nlQuestion.value.trim(),
      lang: locale.value,
    })
    nlResult.value = data
  } catch (e: any) {
    nlError.value = e?.response?.data?.detail || e?.message || t('ai.requestError')
  } finally {
    nlLoading.value = false
  }
}

function formatCell(value: unknown) {
  if (value === null || value === undefined) return t('nlToSql.nullValue')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

async function fetchDatabases() {
  loading.value = true
  try {
    const { data } = await api.get<Database[]>(`/servers/${props.id}/databases`)
    databases.value = data
    if (!selectedNlDb.value && data.length) selectedNlDb.value = data[0].datname
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

onMounted(() => {
  fetchDatabases()
  fetchAiStatus()
})
</script>

<style scoped>
.nl-sql-panel {
  margin-bottom: 16px;
}
.nl-sql-controls {
  display: grid;
  grid-template-columns: minmax(180px, 240px) minmax(0, 1fr) auto;
  gap: 12px;
  align-items: start;
}
.nl-sql-db,
.nl-sql-question {
  width: 100%;
}
.nl-sql-muted {
  display: inline-block;
  margin-top: 10px;
  color: var(--p-text-muted-color);
  font-size: 0.86rem;
}
.nl-sql-error {
  margin-top: 10px;
  color: #fb7185;
  font-size: 0.9rem;
}
.nl-sql-result {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 14px;
}
.nl-sql-code {
  margin: 8px 0 0;
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
  background: rgba(15, 23, 42, 0.7);
  color: #cbd5e1;
  font-size: 0.84rem;
  line-height: 1.45;
}
.nl-sql-text,
.nl-sql-not-executed {
  margin: 0;
  color: var(--p-text-color);
  line-height: 1.5;
}
.nl-sql-not-executed {
  color: #fbbf24;
}
.nl-sql-notes ul {
  margin: 6px 0 0;
  padding-left: 18px;
}
.nl-sql-notes li {
  margin-bottom: 4px;
  color: var(--p-text-muted-color);
}
.nl-sql-table-wrap {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.nl-sql-table {
  margin-top: 2px;
}
.schema-review-panel {
  margin-top: 12px;
}
.btn-icon-left {
  margin-right: 6px;
}
@media (max-width: 860px) {
  .nl-sql-controls {
    grid-template-columns: 1fr;
  }
}
</style>
