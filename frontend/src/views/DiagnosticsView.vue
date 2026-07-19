<template>
  <PageHeader :title="t('diagnostics.title')" :back-to="{ name: 'server', params: { id } }" :back-label="t('common.backToServer')">
    <template #actions>
      <Button @click="runDiagnostics" :loading="loading">
        <i class="fa-solid fa-stethoscope btn-icon-left" aria-hidden="true"></i>{{ t('common.run') }}
      </Button>
    </template>
  </PageHeader>

  <div v-if="report" class="card-panel card-panel--table">
    <div class="card-panel-title">
      <span><i class="fa-solid fa-clipboard-check" style="margin-right: 8px"></i>{{ report.server_name }}</span>
      <div class="flex-row" style="gap: 8px">
        <Tag severity="success" :value="`OK: ${report.ok}`" />
        <Tag :severity="report.warnings > 0 ? 'warn' : 'success'" :value="`Warnings: ${report.warnings}`" />
      </div>
    </div>

    <DataTable
      class="app-data-table"
      :value="report.checks"
      responsive-layout="stack"
      breakpoint="768px"
      striped-rows
    >
      <Column field="name" :header="t('diagnostics.check')" style="width: 320px" />
      <Column field="status" :header="t('common.status')" style="width: 110px">
        <template #body="{ data }">
          <Tag :severity="statusSeverity(data.status)" :value="data.status.toUpperCase()" />
        </template>
      </Column>
      <Column field="details" :header="t('diagnostics.details')">
        <template #body="{ data }">
          <span style="font-size: 13px">{{ data.details || '—' }}</span>
        </template>
      </Column>
    </DataTable>

    <AiInsight
      :label="t('diagnostics.aiLabel')"
      endpoint="/ai/diagnostics"
      :payload="() => ({ payload: JSON.stringify(report) })"
      :sections="[{ key: 'findings', title: t('diagnostics.aiSecFindings') }, { key: 'recommendations', title: t('diagnostics.aiSecRecommendations') }, { key: 'quick_wins', title: t('diagnostics.aiSecQuickWins') }]"
      badge-field="severity"
    />
  </div>

  <div v-else class="card-panel" style="text-align: center; padding: 60px">
    <i class="fa-solid fa-stethoscope" style="font-size: 48px; opacity: 0.3"></i>
    <div style="margin-top: 16px; color: var(--p-text-muted-color)">{{ t('diagnostics.runPrompt') }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from 'primevue/usetoast'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import PageHeader from '../components/ui/PageHeader.vue'
import AiInsight from '../components/AiInsight.vue'
import api from '../api/client'
import type { DiagnosticReport } from '../api/types'

const props = defineProps<{ id: string }>()
const { t } = useI18n()
const toast = useToast()
const report = ref<DiagnosticReport | null>(null)
const loading = ref(false)

function statusSeverity(s: string): 'success' | 'warn' | 'info' | 'secondary' {
  if (s === 'ok') return 'success'
  if (s === 'warning') return 'warn'
  if (s === 'info') return 'info'
  return 'secondary'
}

async function runDiagnostics() {
  loading.value = true
  try {
    const { data } = await api.get<DiagnosticReport>(`/servers/${props.id}/diagnostics`)
    report.value = data
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('diagnostics.title'), detail: e?.response?.data?.detail || e?.message || t('common.loadFailed'), life: 5000 })
  } finally { loading.value = false }
}
</script>
