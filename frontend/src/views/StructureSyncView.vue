<template>
  <div class="flex-row" style="justify-content: flex-end; gap: 8px; margin-bottom: 16px">
    <Button outlined @click="loadData()" :loading="loading">
      <i class="fa-solid fa-rotate btn-icon-left" aria-hidden="true"></i>{{ t('common.refresh') }}
    </Button>
    <Button @click="openCreate">
      <i class="fa-solid fa-plus btn-icon-left" aria-hidden="true"></i>{{ t('structureSync.newScenario') }}
    </Button>
  </div>

  <div class="card-panel card-panel--table">
    <DataTable
      class="app-data-table"
      :value="scenarios"
      :loading="loading"
      responsive-layout="stack"
      breakpoint="768px"
      striped-rows
    >
      <Column field="name" :header="t('common.name')" sortable style="font-weight: 600" />
      <Column :header="t('structureSync.prodDataSource')">
        <template #body="{ data }">
          <span class="muted">{{ data.prod_server_name }}</span> / {{ data.prod_database }}
        </template>
      </Column>
      <Column :header="t('structureSync.testStructure')">
        <template #body="{ data }">
          <span class="muted">{{ data.test_server_name }}</span> / {{ data.test_database }}
        </template>
      </Column>
      <Column field="target_name" :header="t('structureSync.target')" />
      <Column :header="t('common.status')">
        <template #body="{ data }">
          <Tag v-if="data.last_run" :severity="statusSeverity(data.last_run.status)" :value="statusLabel(data.last_run.status)" />
          <span v-else class="muted">—</span>
          <div v-if="data.last_run?.current_step" class="muted step-hint">
            {{ stepLabel(data.last_run.current_step) }}<template v-if="liveBytes(data)"> · {{ formatBytes(liveBytes(data)) }}<template v-if="clonePercent(data) !== null"> · ~{{ clonePercent(data) }}%</template></template>
          </div>
          <ProgressBar
            v-if="clonePercent(data) !== null"
            :value="clonePercent(data)!"
            :show-value="false"
            class="clone-progress"
          />
        </template>
      </Column>
      <Column :header="t('common.actions')" style="width: 330px">
        <template #body="{ data }">
          <div class="flex-row actions-row">
            <Button size="small" outlined severity="secondary" :disabled="isBusy(data) || actionSending"
              @click="submitAction(() => runScenario(data, true))" v-tooltip.top="t('structureSync.tooltipDryRun')">
              <i class="fa-solid fa-eye" aria-hidden="true"></i>
            </Button>
            <Button size="small" :disabled="isBusy(data) || actionSending" @click="submitAction(() => runScenario(data, false))"
              v-tooltip.top="t('structureSync.tooltipRun')">
              <i class="fa-solid fa-play" aria-hidden="true"></i>
            </Button>
            <Button v-if="data.last_run && ['queued', 'running'].includes(data.last_run.status) && data.last_run.current_step !== 'swap'"
              size="small" severity="danger" outlined :disabled="actionSending" @click="submitAction(() => stopRun(data.last_run!.id))"
              v-tooltip.top="t('structureSync.tooltipStop')">
              <i class="fa-solid fa-stop" aria-hidden="true"></i>
            </Button>
            <template v-if="data.last_run?.status === 'awaiting_approval'">
              <Button size="small" severity="success" :disabled="actionSending" @click="submitAction(() => approveRun(data.last_run!.id))" v-tooltip.top="t('structureSync.tooltipApprove')">
                <i class="fa-solid fa-check" aria-hidden="true"></i>
              </Button>
              <Button size="small" severity="danger" outlined :disabled="actionSending" @click="submitAction(() => rejectRun(data.last_run!.id))" v-tooltip.top="t('structureSync.tooltipReject')">
                <i class="fa-solid fa-xmark" aria-hidden="true"></i>
              </Button>
            </template>
            <Button size="small" text severity="secondary" @click="openHistory(data)" v-tooltip.top="t('structureSync.tooltipHistory')">
              <i class="fa-solid fa-clock-rotate-left" aria-hidden="true"></i>
            </Button>
            <Button size="small" text severity="secondary" @click="openEdit(data)">
              <i class="fa-solid fa-pen" aria-hidden="true"></i>
            </Button>
            <Button size="small" text severity="danger" @click="removeScenario(data)">
              <i class="fa-solid fa-trash" aria-hidden="true"></i>
            </Button>
          </div>
        </template>
      </Column>
    </DataTable>
  </div>

  <!-- Форма создания/редактирования (в стиле сценариев восстановления) -->
  <Dialog v-model:visible="showForm" modal :header="editingId ? t('structureSync.editScenario') : t('structureSync.newScenario')" :style="{ width: '580px' }">
    <div class="flex-col" style="gap: 16px">
      <div class="flex-col" style="gap: 4px">
        <label class="form-label" for="ss-name">{{ t('structureSync.scenarioName') }} <span class="req">*</span></label>
        <InputText id="ss-name" v-model="form.name" :placeholder="t('structureSync.scenarioNamePlaceholder')" fluid />
      </div>

      <div class="flow-hint">
        <i class="fa-solid fa-circle-info" aria-hidden="true"></i>
        <span v-html="t('structureSync.flowHint', { prefix: form.old_db_prefix })"></span>
      </div>

      <div class="form-section-title">
        <i class="fa-solid fa-database form-section-icon" aria-hidden="true"></i>
        {{ t('structureSync.sectionProdSource') }}
      </div>
      <div class="flex-row" style="gap: 12px">
        <div class="flex-col" style="gap: 4px; flex: 1">
          <label class="form-label" for="ss-prod-server">{{ t('common.server') }} <span class="req">*</span></label>
          <Select input-id="ss-prod-server" v-model="form.prod_server_id" :options="servers" option-label="name" option-value="id"
            :placeholder="t('structureSync.selectServer')" fluid @change="onProdServerChange" />
        </div>
        <div class="flex-col" style="gap: 4px; flex: 1">
          <label class="form-label" for="ss-prod-db">{{ t('common.database') }} <span class="req">*</span></label>
          <Select input-id="ss-prod-db" v-model="form.prod_database" :options="prodDatabases" option-label="datname" option-value="datname"
            :loading="prodDbLoading"
            :placeholder="form.prod_server_id ? (prodDbLoading ? t('common.loading') : t('structureSync.selectDb')) : t('structureSync.selectServerFirst')"
            :disabled="!form.prod_server_id || prodDbLoading" filter fluid @change="onProdDbChange" />
        </div>
      </div>

      <!-- Исключение данных таблиц из клона prod -->
      <div class="exclude-section" :class="{ open: excludeTablesOpen }">
        <div class="exclude-toggle" @click="excludeTablesOpen = !excludeTablesOpen">
          <div class="exclude-toggle-left">
            <i class="fa-solid fa-table exclude-toggle-icon" aria-hidden="true"></i>
            <span class="exclude-toggle-title">{{ t('structureSync.excludeTablesTitle') }}</span>
            <Tag v-if="form.excluded_tables.length" severity="info" :value="String(form.excluded_tables.length)" />
          </div>
          <i :class="excludeTablesOpen ? 'fa-solid fa-chevron-up' : 'fa-solid fa-chevron-down'" class="exclude-chevron" aria-hidden="true"></i>
        </div>
        <div v-if="excludeTablesOpen" class="exclude-body">
          <p class="exclude-hint" v-html="t('structureSync.excludeHint')"></p>
          <div v-if="prodTablesLoading" class="exclude-loading">
            <i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i> {{ t('structureSync.loadingTables') }}
          </div>
          <div v-else-if="prodTables.length" class="exclude-list">
            <div
              v-for="t in prodTables"
              :key="t.schema + '.' + t.tablename"
              class="exclude-row"
              :class="{ excluded: form.excluded_tables.includes(t.schema + '.' + t.tablename) }"
              @click="toggleExcludeTable(t.schema + '.' + t.tablename)"
            >
              <input
                type="checkbox"
                :checked="form.excluded_tables.includes(t.schema + '.' + t.tablename)"
                class="exclude-checkbox"
                @click.stop="toggleExcludeTable(t.schema + '.' + t.tablename)"
              />
              <span class="exclude-table-name">{{ t.schema }}.{{ t.tablename }}</span>
              <span class="exclude-table-size muted">{{ t.total_size }}</span>
            </div>
          </div>
          <div v-else class="exclude-empty muted">
            {{ form.prod_server_id && form.prod_database ? t('structureSync.noTables') : t('structureSync.selectProdFirst') }}
          </div>
          <div v-if="form.excluded_tables.length" class="exclude-chips">
            <span v-for="t in form.excluded_tables" :key="t" class="exclude-chip">
              {{ t }}
              <i class="fa-solid fa-xmark exclude-chip-x" aria-hidden="true" @click="form.excluded_tables = form.excluded_tables.filter(x => x !== t)"></i>
            </span>
            <Button text size="small" severity="secondary" @click="form.excluded_tables = []">{{ t('structureSync.reset') }}</Button>
          </div>
        </div>
      </div>

      <div class="form-section-title">
        <i class="fa-solid fa-layer-group form-section-icon form-section-icon--accent" aria-hidden="true"></i>
        {{ t('structureSync.sectionTestSource') }}
      </div>
      <div class="flex-row" style="gap: 12px">
        <div class="flex-col" style="gap: 4px; flex: 1">
          <label class="form-label" for="ss-test-server">{{ t('common.server') }} <span class="req">*</span></label>
          <Select input-id="ss-test-server" v-model="form.test_server_id" :options="servers" option-label="name" option-value="id"
            :placeholder="t('structureSync.selectServer')" fluid @change="onTestServerChange" />
        </div>
        <div class="flex-col" style="gap: 4px; flex: 1">
          <label class="form-label" for="ss-test-db">{{ t('common.database') }} <span class="req">*</span></label>
          <Select input-id="ss-test-db" v-model="form.test_database" :options="testDatabases" option-label="datname" option-value="datname"
            :loading="testDbLoading"
            :placeholder="form.test_server_id ? (testDbLoading ? t('common.loading') : t('structureSync.selectDb')) : t('structureSync.selectServerFirst')"
            :disabled="!form.test_server_id || testDbLoading" filter fluid />
        </div>
      </div>

      <div class="form-section-title">
        <i class="fa-solid fa-flag-checkered form-section-icon form-section-icon--accent" aria-hidden="true"></i>
        {{ t('structureSync.sectionResult') }}
      </div>
      <div class="flex-row" style="gap: 12px">
        <div class="flex-col" style="gap: 4px; flex: 1">
          <label class="form-label" for="ss-target-server">{{ t('structureSync.targetServer') }} <span class="req">*</span></label>
          <Select input-id="ss-target-server" v-model="form.target_server_id" :options="servers" option-label="name" option-value="id"
            :placeholder="t('structureSync.targetServerPlaceholder')" filter fluid @change="onTargetServerChange" />
          <small style="font-size: 11px; color: var(--p-text-muted-color)">
            {{ t('structureSync.targetServerHint') }}
          </small>
        </div>
      </div>
      <div class="flex-row" style="gap: 12px">
        <div class="flex-col" style="gap: 4px; flex: 1">
          <label class="form-label" for="ss-target">{{ t('structureSync.targetName') }} <span class="req">*</span></label>
          <Select input-id="ss-target" v-model="form.target_name" :options="targetDbOptions" option-label="label" option-value="value"
            :placeholder="t('structureSync.targetNamePlaceholder')" :disabled="!form.target_server_id" editable fluid>
            <template #empty>
              <div style="padding: 8px 12px; font-size: 13px; color: var(--p-text-muted-color)">
                {{ t('structureSync.targetNoDb') }}
              </div>
            </template>
          </Select>
          <small style="font-size: 11px; color: var(--p-text-muted-color)">
            {{ t('structureSync.targetNameHint') }}
          </small>
        </div>
        <div class="flex-col" style="gap: 4px; flex: 1">
          <label class="form-label" for="ss-data-mode">{{ t('structureSync.dataMode') }}</label>
          <Select input-id="ss-data-mode" v-model="form.data_copy_mode" :options="dataModes" option-label="label" option-value="value" fluid />
        </div>
      </div>
      <small style="font-size: 11px; color: var(--p-text-muted-color); margin-top: -8px">
        <i class="fa-solid fa-circle-info" style="margin-right: 4px"></i>
        <span v-html="t('structureSync.dataModeHint')"></span>
      </small>

      <div class="form-section-title">
        <i class="fa-solid fa-right-left form-section-icon form-section-icon--accent" aria-hidden="true"></i>
        {{ t('structureSync.sectionSwap') }}
      </div>
      <div class="swap-warning">
        <i class="fa-solid fa-triangle-exclamation" aria-hidden="true"></i>
        <span v-html="t('structureSync.swapWarning', { prefix: form.old_db_prefix })"></span>
      </div>
      <div class="flex-col" style="gap: 8px">
        <label class="form-label">{{ t('structureSync.swapWhen') }}</label>
        <div class="action-choice">
          <div class="action-option" :class="{ selected: form.require_approval }" @click="form.require_approval = true">
            <i class="fa-solid fa-user-shield icon-warning" aria-hidden="true"></i>
            <div>
              <div class="action-option-title">{{ t('structureSync.withApproval') }}</div>
              <div class="action-option-hint">{{ t('structureSync.withApprovalHint') }}</div>
            </div>
          </div>
          <div class="action-option" :class="{ selected: !form.require_approval }" @click="form.require_approval = false">
            <i class="fa-solid fa-bolt icon-danger" aria-hidden="true"></i>
            <div>
              <div class="action-option-title">{{ t('structureSync.automatic') }}</div>
              <div class="action-option-hint">{{ t('structureSync.automaticHint') }}</div>
            </div>
          </div>
        </div>
        <div class="flex-row" style="gap: 12px; align-items: flex-end">
          <div class="flex-col" style="gap: 4px; flex: 1">
            <label class="form-label" for="ss-old-prefix">{{ t('structureSync.oldDbPrefix') }}</label>
            <InputText id="ss-old-prefix" v-model="form.old_db_prefix" fluid />
          </div>
          <div class="flex-col" style="gap: 4px; width: 140px">
            <label class="form-label" for="ss-keep-old">{{ t('structureSync.keepOld') }}</label>
            <InputNumber input-id="ss-keep-old" v-model="form.keep_old_count" :min="0" :use-grouping="false" show-buttons fluid />
          </div>
        </div>
        <small style="font-size: 11px; color: var(--p-text-muted-color)">
          <i class="fa-solid fa-circle-info" style="margin-right: 4px"></i>
          <span v-html="t('structureSync.keepOldHint', { prefix: form.old_db_prefix })"></span>
        </small>
      </div>

      <div class="flex-col" style="gap: 4px">
        <label class="form-label" for="ss-schedule">{{ t('structureSync.schedule') }} <span class="form-hint">{{ t('structureSync.scheduleManualOnly') }}</span></label>
        <Select
          input-id="ss-schedule"
          v-model="form.schedule_id"
          :options="[{ id: 0, name: t('structureSync.noSchedule'), cron_expression: '' }, ...cronSchedules, { id: -1, name: t('structureSync.customSchedule'), cron_expression: '' }]"
          option-label="name" option-value="id" fluid @change="onScheduleChange">
          <template #option="{ option }">
            <div style="display: flex; align-items: center; gap: 10px">
              <span style="flex: 1">{{ option.name }}</span>
              <code v-if="option.cron_expression" style="font-size: 11px; color: var(--p-text-muted-color)">{{ option.cron_expression }}</code>
            </div>
          </template>
        </Select>
        <CronInput v-if="form.schedule_id === -1" v-model="form.cron_expression" style="margin-top: 6px" />
      </div>

      <div class="flex-row" style="gap: 8px; align-items: center">
        <ToggleSwitch v-model="form.is_active" input-id="ss-active" />
        <label for="ss-active" style="cursor: pointer; font-size: 13px">{{ t('structureSync.activeLabel') }}</label>
      </div>

      <details class="adv">
        <summary>{{ t('structureSync.advanced') }}</summary>
        <div class="flex-col" style="gap: 12px; margin-top: 12px">
          <div class="flex-col" style="gap: 4px">
            <label class="form-label" for="ss-temp-tmpl">{{ t('structureSync.tempNameTemplate') }}</label>
            <InputText id="ss-temp-tmpl" v-model="form.temp_name_template" fluid />
            <small class="form-hint" v-html="t('structureSync.tempNameHint', { target: '{target}', ts: '{ts}' })"></small>
          </div>
        </div>
      </details>
    </div>
    <template #footer>
      <div class="req-note"><span class="req">*</span> {{ t('structureSync.requiredNote') }}</div>
      <Button text @click="showForm = false">{{ t('common.cancel') }}</Button>
      <Button :loading="saving" :disabled="!canSave || saving" @click="submitSave(saveScenario)">
        {{ editingId ? t('common.save') : t('structureSync.create') }}
      </Button>
    </template>
  </Dialog>

  <!-- История прогонов + SQL -->
  <Dialog v-model:visible="showHistory" modal :header="t('structureSync.historyTitle', { name: historyScenario?.name || '' })" :style="{ width: '820px' }">
    <DataTable class="app-data-table" :value="runs" :loading="runsLoading" :rows="10" :paginator="runs.length > 10" striped-rows
      selection-mode="single" v-model:selection="selectedRun" data-key="id">
      <Column field="status" :header="t('common.status')" style="width: 150px">
        <template #body="{ data }"><Tag :severity="statusSeverity(data.status)" :value="statusLabel(data.status)" /></template>
      </Column>
      <Column field="current_step" :header="t('structureSync.step')" />
      <Column :header="t('structureSync.startedAt')"><template #body="{ data }">{{ formatTs(data.started_at) }}</template></Column>
      <Column :header="t('structureSync.duration')" style="width: 120px"><template #body="{ data }">{{ formatRunDuration(data) }}</template></Column>
      <Column :header="t('structureSync.objects')">
        <template #body="{ data }">
          <span v-if="data.summary" class="muted">{{ t('structureSync.objectsSummary', { tables: data.summary.new_tables, functions: data.summary.functions, triggers: data.summary.triggers }) }}</span>
        </template>
      </Column>
    </DataTable>

    <div v-if="selectedRun" class="run-detail">
      <div v-if="selectedRun.error_message" class="run-error">{{ selectedRun.error_message }}</div>
      <div v-if="selectedRun.summary" class="muted">
        {{ t('structureSync.applyErrors', { count: (selectedRun.summary.apply_errors || []).length }) }}
        <template v-if="selectedRun.renamed_prod_to">{{ t('structureSync.oldProdRenamed', { name: selectedRun.renamed_prod_to }) }}</template>
      </div>
      <label class="muted" style="margin-top: 8px; display: block">{{ t('structureSync.generatedSql') }}</label>
      <Textarea :model-value="selectedRun.generated_sql || '—'" readonly rows="12" style="width: 100%; font-family: monospace; font-size: 12px" />

      <AiInsight
        :label="t('structureSync.aiLabel')"
        endpoint="/ai/migration-plan"
        :payload="() => ({ diff_summary: 'Structure sync ' + (historyScenario?.name || '') + ' (test→prod)', generated_sql: selectedRun?.generated_sql || '' })"
        :sections="[{ key: 'risks', title: t('structureSync.aiSecRisks') }, { key: 'steps', title: t('structureSync.aiSecSteps') }, { key: 'rollback', title: t('structureSync.aiSecRollback') }]"
        badge-field="overall_risk"
      />
    </div>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSubmitting } from '../composables/useSubmitting'
import { useToast } from 'primevue/usetoast'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Textarea from 'primevue/textarea'
import InputNumber from 'primevue/inputnumber'
import ToggleSwitch from 'primevue/toggleswitch'
import ProgressBar from 'primevue/progressbar'
import CronInput from '../components/CronInput.vue'
import AiInsight from '../components/AiInsight.vue'
import api from '../api/client'
import { useTasksStore } from '../stores/tasks'
import type { StructureSyncScenario, StructureSyncRun } from '../api/types'

const { t } = useI18n()
const toast = useToast()
const tasksStore = useTasksStore()

// In-flight guard против двойного клика по кнопкам запуска/свапа/остановки.
const { submitting: actionSending, submit: submitAction } = useSubmitting()
// Отдельный guard + loading для кнопки сохранения формы (Submit Feedback).
const { submitting: saving, submit: submitSave } = useSubmitting()

const scenarios = ref<StructureSyncScenario[]>([])
const loading = ref(false)
const servers = ref<{ id: number; name: string; environment: string }[]>([])
const cronSchedules = ref<{ id: number; name: string; cron_expression: string }[]>([])

const prodDatabases = ref<{ datname: string }[]>([])
const testDatabases = ref<{ datname: string }[]>([])
const targetDatabases = ref<{ datname: string }[]>([])
const prodDbLoading = ref(false)
const testDbLoading = ref(false)
const targetDbLoading = ref(false)
const prodDbOptions = computed(() => prodDatabases.value.map(d => ({ label: d.datname, value: d.datname })))
const targetDbOptions = computed(() => targetDatabases.value.map(d => ({ label: d.datname, value: d.datname })))

// Исключение данных таблиц из клона prod (--exclude-table-data): структура сохраняется.
const excludeTablesOpen = ref(false)
const prodTables = ref<{ schema: string; tablename: string; total_size: string; total_bytes: number }[]>([])
const prodTablesLoading = ref(false)

const showForm = ref(false)
const editingId = ref<number | null>(null)
const form = reactive(emptyForm())

const showHistory = ref(false)
const historyScenario = ref<StructureSyncScenario | null>(null)
const runs = ref<StructureSyncRun[]>([])
const runsLoading = ref(false)
const selectedRun = ref<StructureSyncRun | null>(null)

const dataModes = computed(() => [
  { label: t('structureSync.dataModeNewTables'), value: 'new_tables_only' },
  { label: t('structureSync.dataModeNone'), value: 'none' },
])

let poll: number | undefined

function emptyForm() {
  return {
    name: '',
    prod_server_id: null as number | null,
    prod_database: '',
    test_server_id: null as number | null,
    test_database: '',
    target_server_id: null as number | null,
    target_name: '',
    temp_name_template: '{target}_build_{ts}',
    old_db_prefix: 'to_delete__',
    keep_old_count: 0,
    data_copy_mode: 'new_tables_only',
    excluded_tables: [] as string[],
    require_approval: true,
    schedule_id: 0 as number,
    cron_expression: '',
    is_active: true,
  }
}

const canSave = computed(() =>
  !!form.name && !!form.prod_server_id && !!form.prod_database &&
  !!form.test_server_id && !!form.test_database &&
  !!form.target_server_id && !!form.target_name
)

function statusSeverity(s: string): string {
  return { success: 'success', failed: 'danger', queued: 'info', running: 'info', awaiting_approval: 'warn', dry_run: 'secondary' }[s] || 'secondary'
}
function statusLabel(s: string): string {
  return {
    success: t('structureSync.statusSuccess'),
    failed: t('structureSync.statusFailed'),
    queued: t('structureSync.statusQueued'),
    running: t('structureSync.statusRunning'),
    awaiting_approval: t('structureSync.statusAwaitingApproval'),
    dry_run: t('structureSync.statusDryRun'),
  }[s] || s
}
function isBusy(sc: StructureSyncScenario): boolean {
  return ['queued', 'running', 'awaiting_approval'].includes(sc.last_run?.status || '')
}
function formatTs(ts: string): string { return ts ? new Date(ts.endsWith('Z') ? ts : ts + 'Z').toLocaleString('ru-RU') : '' }

function stepLabel(step: string): string {
  return tasksStore.STRUCTURE_SYNC_STEP_LABELS[step] ?? step
}

// -Fc сжимает дамп примерно в 3.5x — тот же коэффициент, что и в бэкапах.
const DUMP_COMPRESS_FACTOR = 3.5

// Активная задача дампа (клон prod / safety-бэкап) текущего прогона — из WS-стора.
function liveTask(row: StructureSyncScenario) {
  const lr: any = row.last_run
  if (!lr || !['queued', 'running'].includes(lr.status)) return null
  if (!['clone_prod', 'backup_test'].includes(lr.current_step)) return null
  return tasksStore.tasks.find(x => x.type === 'structure_sync' && x.runId === lr.id) ?? null
}

function liveBytes(row: StructureSyncScenario): number {
  return liveTask(row)?.bytesWritten ?? 0
}

// Прогресс «по весу»: доля записанного дампа от ожидаемого (размер БД / сжатие).
// Приблизительно (коэффициент сжатия — оценка), поэтому в UI помечаем «~» и не даём 100%.
function clonePercent(row: StructureSyncScenario): number | null {
  const t = liveTask(row)
  if (!t || !t.totalBytes || !t.bytesWritten) return null
  const expected = t.totalBytes / DUMP_COMPRESS_FACTOR
  if (expected <= 0) return null
  return Math.min(Math.round((t.bytesWritten / expected) * 100), 99)
}

function formatBytes(b: number): string {
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
  if (b < 1024 * 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`
  return `${(b / 1024 / 1024 / 1024).toFixed(2)} GB`
}

function formatDuration(sec: number): string {
  const s = Math.floor(Math.max(0, sec))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const ss = s % 60
  if (h > 0) return `${h}${t('structureSync.durH')} ${String(m).padStart(2, '0')}${t('structureSync.durM')}`
  if (m > 0) return `${m}${t('structureSync.durM')} ${String(ss).padStart(2, '0')}${t('structureSync.durS')}`
  return `${ss}${t('structureSync.durS')}`
}

// «За сколько сделалось» для завершённого прогона.
function formatRunDuration(run: StructureSyncRun): string {
  if (!run.finished_at) return '—'
  const start = new Date(run.started_at).getTime()
  const end = new Date(run.finished_at).getTime()
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) return '—'
  return formatDuration((end - start) / 1000)
}
function anyActive(): boolean {
  return scenarios.value.some(s => s.last_run && ['queued', 'running', 'awaiting_approval'].includes(s.last_run.status))
}

async function loadData(silent = false) {
  if (!silent) loading.value = true
  try {
    const [sc, sv, cron] = await Promise.all([
      api.get<StructureSyncScenario[]>('/structure-sync'),
      api.get('/servers'),
      api.get('/cron-schedules'),
    ])
    scenarios.value = sc.data
    servers.value = sv.data
    cronSchedules.value = cron.data
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('common.error'), detail: e.response?.data?.detail || t('structureSync.loadFailed'), life: 4000 })
  } finally { if (!silent) loading.value = false }
}

async function fetchDatabases(serverId: number, which: 'prod' | 'test' | 'target') {
  const loading = { prod: prodDbLoading, test: testDbLoading, target: targetDbLoading }[which]
  const store = { prod: prodDatabases, test: testDatabases, target: targetDatabases }[which]
  loading.value = true
  store.value = []
  try {
    const { data } = await api.get(`/servers/${serverId}/databases`)
    store.value = data
  } catch { /* ignore */ } finally {
    loading.value = false
  }
}

function onProdServerChange() {
  form.prod_database = ''
  if (form.prod_server_id) fetchDatabases(form.prod_server_id, 'prod')
}

function onTargetServerChange() {
  // Список БД приёмника — чтобы выбрать существующую (её заменим) или ввести новое имя.
  if (form.target_server_id) fetchDatabases(form.target_server_id, 'target')
}
function onProdDbChange() {
  if (!form.target_name) form.target_name = form.prod_database
}

async function fetchProdTables() {
  if (!form.prod_server_id || !form.prod_database) return
  prodTablesLoading.value = true
  prodTables.value = []
  try {
    const { data } = await api.get(`/servers/${form.prod_server_id}/databases/${form.prod_database}/tables-size`)
    prodTables.value = data
  } catch {
    prodTables.value = []
  } finally {
    prodTablesLoading.value = false
  }
}

function toggleExcludeTable(fullName: string) {
  const idx = form.excluded_tables.indexOf(fullName)
  if (idx >= 0) form.excluded_tables.splice(idx, 1)
  else form.excluded_tables.push(fullName)
}

watch(excludeTablesOpen, (open) => {
  if (open && prodTables.value.length === 0) fetchProdTables()
})
watch(() => form.prod_database, () => {
  prodTables.value = []
  if (excludeTablesOpen.value) fetchProdTables()
})
function onTestServerChange() {
  form.test_database = ''
  if (form.test_server_id) fetchDatabases(form.test_server_id, 'test')
}
function onScheduleChange() {
  if (form.schedule_id !== -1) form.cron_expression = ''
}

function openCreate() {
  editingId.value = null
  Object.assign(form, emptyForm())
  prodDatabases.value = []
  testDatabases.value = []
  targetDatabases.value = []
  prodTables.value = []
  excludeTablesOpen.value = false
  showForm.value = true
}

function openEdit(sc: StructureSyncScenario) {
  editingId.value = sc.id
  Object.assign(form, {
    name: sc.name,
    prod_server_id: sc.prod_server_id,
    prod_database: sc.prod_database,
    test_server_id: sc.test_server_id,
    test_database: sc.test_database,
    target_server_id: sc.target_server_id ?? sc.prod_server_id,
    target_name: sc.target_name,
    temp_name_template: sc.temp_name_template,
    old_db_prefix: sc.old_db_prefix,
    keep_old_count: sc.keep_old_count,
    data_copy_mode: sc.data_copy_mode,
    excluded_tables: sc.excluded_tables ? [...sc.excluded_tables] : [],
    require_approval: sc.require_approval,
    is_active: sc.is_active,
    schedule_id: 0,
    cron_expression: '',
  })
  prodTables.value = []
  excludeTablesOpen.value = false
  const expr = sc.cron_expression ?? ''
  const found = cronSchedules.value.find(s => s.cron_expression === expr)
  if (!expr) { form.schedule_id = 0; form.cron_expression = '' }
  else if (found) { form.schedule_id = found.id; form.cron_expression = '' }
  else { form.schedule_id = -1; form.cron_expression = expr }

  if (sc.prod_server_id) fetchDatabases(sc.prod_server_id, 'prod')
  if (sc.test_server_id) fetchDatabases(sc.test_server_id, 'test')
  const tgt = sc.target_server_id ?? sc.prod_server_id
  if (tgt) fetchDatabases(tgt, 'target')
  showForm.value = true
}

function resolveCron(): string | null {
  if (form.schedule_id === -1) return form.cron_expression || null
  if (form.schedule_id) return cronSchedules.value.find(s => s.id === form.schedule_id)?.cron_expression ?? null
  return null
}

async function saveScenario() {
  const payload = {
    name: form.name.trim(),
    prod_server_id: form.prod_server_id,
    prod_database: form.prod_database,
    test_server_id: form.test_server_id,
    test_database: form.test_database,
    target_server_id: form.target_server_id,
    target_name: form.target_name.trim(),
    temp_name_template: form.temp_name_template.trim(),
    old_db_prefix: form.old_db_prefix.trim(),
    keep_old_count: form.keep_old_count,
    data_copy_mode: form.data_copy_mode,
    excluded_tables: form.excluded_tables,
    require_approval: form.require_approval,
    cron_expression: resolveCron(),
    is_active: form.is_active,
  }
  try {
    if (editingId.value) {
      await api.put(`/structure-sync/${editingId.value}`, payload)
      toast.add({ severity: 'success', summary: t('structureSync.toastUpdated'), life: 2500 })
    } else {
      await api.post('/structure-sync', payload)
      toast.add({ severity: 'success', summary: t('structureSync.toastCreated'), life: 2500 })
    }
    showForm.value = false
    loadData()
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('common.error'), detail: e.response?.data?.detail || t('common.error'), life: 4000 })
  }
}

async function removeScenario(sc: StructureSyncScenario) {
  if (!confirm(t('structureSync.confirmDelete', { name: sc.name }))) return
  try {
    await api.delete(`/structure-sync/${sc.id}`)
    loadData()
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('common.error'), detail: e.response?.data?.detail || t('common.error'), life: 4000 })
  }
}

async function runScenario(sc: StructureSyncScenario, dryRun: boolean) {
  try {
    await api.post(`/structure-sync/${sc.id}/run`, null, { params: { dry_run: dryRun } })
    toast.add({ severity: 'info', summary: dryRun ? t('structureSync.toastDryRunStarted') : t('structureSync.toastMigrationStarted'), life: 2500 })
    setTimeout(() => refreshActive(),1500)
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('common.error'), detail: e.response?.data?.detail || t('common.error'), life: 4000 })
  }
}

async function stopRun(runId: number) {
  if (!confirm(t('structureSync.confirmStop'))) return
  try {
    await api.post(`/structure-sync/runs/${runId}/stop`)
    toast.add({ severity: 'warn', summary: t('structureSync.toastStopped'), life: 2500 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('common.error'), detail: e.response?.data?.detail || t('common.error'), life: 4000 })
  } finally {
    refreshActive()   // всегда обновляем список — снимаем устаревший статус/кнопку
  }
}

async function approveRun(runId: number) {
  if (!confirm(t('structureSync.confirmApprove'))) return
  try {
    await api.post(`/structure-sync/runs/${runId}/approve`)
    toast.add({ severity: 'success', summary: t('structureSync.toastSwapStarted'), life: 2500 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('common.error'), detail: e.response?.data?.detail || t('common.error'), life: 4000 })
  } finally {
    refreshActive()
  }
}

async function rejectRun(runId: number) {
  try {
    await api.post(`/structure-sync/runs/${runId}/reject`)
    toast.add({ severity: 'warn', summary: t('structureSync.toastSwapRejected'), life: 2500 })
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('common.error'), detail: e.response?.data?.detail || t('common.error'), life: 4000 })
  } finally {
    refreshActive()
  }
}

async function openHistory(sc: StructureSyncScenario) {
  historyScenario.value = sc
  selectedRun.value = null
  showHistory.value = true
  runsLoading.value = true
  try {
    const { data } = await api.get<StructureSyncRun[]>(`/structure-sync/${sc.id}/runs`)
    runs.value = data
    selectedRun.value = data[0] || null
  } finally { runsLoading.value = false }
}

// Лёгкое обновление во время активной миграции: тянем ТОЛЬКО статусы сценариев
// (и открытую историю), без статики servers/cron — она грузится один раз в
// loadData(). Живой прогресс и так идёт по WebSocket (tasksStore).
async function refreshActive() {
  try {
    const sc = await api.get<StructureSyncScenario[]>('/structure-sync')
    scenarios.value = sc.data
    if (showHistory.value && historyScenario.value) {
      const { data } = await api.get<StructureSyncRun[]>(`/structure-sync/${historyScenario.value.id}/runs`)
      runs.value = data
      if (!selectedRun.value && data[0]) selectedRun.value = data[0]
    }
  } catch { /* тихо: это фоновое обновление */ }
}

// Реактивность без F5: WS обновляет tasksStore. При ЛЮБОЙ смене состояния
// structure_sync-задачи (этап/завершение/ошибка) сразу обновляем список сценариев
// — чтобы статус в таблице и кнопки (стоп/approve) соответствовали реальности.
watch(
  () => tasksStore.tasks
    .filter(t => t.type === 'structure_sync')
    .map(t => `${t.runId}:${t.stage}:${t.done}:${t.failed}`).join('|'),
  () => refreshActive()
)

onMounted(() => {
  loadData()
  // Медленный fallback (только пока миграция активна) — страховка на случай
  // пропущенного WS-события. Прогресс сам по себе идёт пушем.
  poll = window.setInterval(() => { if (anyActive()) refreshActive() }, 8000)
})
onUnmounted(() => { if (poll) window.clearInterval(poll) })
</script>

<style scoped>
.actions-row { gap: 4px; flex-wrap: nowrap; }
.flow-hint {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  font-size: 12px;
  line-height: 1.5;
  color: var(--p-text-muted-color);
  background: var(--p-surface-100);
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  padding: 10px 12px;
}
.flow-hint i { margin-top: 2px; color: var(--p-primary-color); }
.flow-hint code { font-family: var(--font-mono, monospace); }
.swap-warning {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  font-size: 12px;
  line-height: 1.5;
  color: var(--p-text-color);
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.4);
  border-radius: 8px;
  padding: 10px 12px;
}
.swap-warning i { margin-top: 2px; color: var(--p-amber-500, #f59e0b); }
.swap-warning code { font-family: var(--font-mono, monospace); }
.req { color: var(--color-danger, #dc2626); font-weight: 600; }
.req-note { margin-right: auto; font-size: 11px; color: var(--p-text-muted-color); }
.req-note .req { margin-right: 2px; }
.step-hint { font-size: 11px; margin-top: 2px; }
.clone-progress { height: 6px; margin-top: 4px; max-width: 220px; }

/* Секция исключения таблиц */
.exclude-section {
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  overflow: hidden;
}
.exclude-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  cursor: pointer;
  user-select: none;
}
.exclude-toggle:hover { background: var(--p-surface-100); }
.exclude-toggle-left { display: flex; align-items: center; gap: 8px; }
.exclude-toggle-icon { font-size: 12px; color: var(--p-text-muted-color); }
.exclude-toggle-title { font-size: 13px; font-weight: 600; }
.exclude-chevron { font-size: 11px; color: var(--p-text-muted-color); }
.exclude-body { padding: 0 12px 12px; }
.exclude-hint {
  margin: 0 0 8px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--p-text-muted-color);
}
.exclude-hint code { font-family: var(--font-mono, monospace); }
.exclude-loading, .exclude-empty { font-size: 13px; color: var(--p-text-muted-color); padding: 8px 0; }
.exclude-list {
  max-height: 220px;
  overflow-y: auto;
  border: 1px solid var(--p-content-border-color);
  border-radius: 6px;
}
.exclude-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  cursor: pointer;
  font-size: 13px;
  border-bottom: 1px solid var(--p-content-border-color);
}
.exclude-row:last-child { border-bottom: none; }
.exclude-row:hover { background: var(--p-surface-100); }
.exclude-row.excluded { background: var(--p-surface-200); }
.exclude-checkbox { flex-shrink: 0; width: 14px; height: 14px; cursor: pointer; }
.exclude-table-name { flex: 1; font-family: var(--font-mono, monospace); }
.exclude-table-size { font-size: 12px; white-space: nowrap; }
.exclude-chips {
  margin-top: 8px;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}
.exclude-chip {
  display: flex;
  align-items: center;
  gap: 4px;
  background: var(--p-surface-100);
  border-radius: 12px;
  padding: 2px 10px;
  font-size: 11px;
  font-family: var(--font-mono, monospace);
}
.exclude-chip-x { cursor: pointer; opacity: 0.5; }
.exclude-chip-x:hover { opacity: 1; }
.adv summary { cursor: pointer; color: var(--p-text-muted-color, #64748b); font-size: 13px; }
.run-detail { margin-top: 16px; }
.run-error {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
  white-space: pre-wrap;
}
</style>
