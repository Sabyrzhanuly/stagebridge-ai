<template>
  <div class="scenario-page">
  <div class="flex-row" style="justify-content: flex-end; gap: 8px; margin-bottom: 16px">
    <Button outlined @click="loadData" :loading="loading">
      <i class="fa-solid fa-rotate btn-icon-left" aria-hidden="true"></i>{{ t('common.refresh') }}
    </Button>
    <Button @click="openCreateModal">
      <i class="fa-solid fa-plus btn-icon-left" aria-hidden="true"></i>{{ t('scenarios.newScenario') }}
    </Button>
  </div>

  <div v-if="loading && scenarios.length === 0" class="card-panel scenario-loading">
    <ProgressSpinner style="width: 40px; height: 40px" stroke-width="4" />
    <span class="muted">{{ t('scenarios.loadingScenarios') }}</span>
  </div>

  <EmptyState
    v-else-if="scenarios.length === 0 && !loading"
    icon="fa-solid fa-rotate"
    :title="t('scenarios.emptyTitle')"
    :description="t('scenarios.emptyDesc')"
  >
    <template #action>
      <Button @click="openCreateModal">
        <i class="fa-solid fa-plus btn-icon-left" aria-hidden="true"></i>{{ t('scenarios.newScenario') }}
      </Button>
    </template>
  </EmptyState>

  <template v-else>
    <div class="stats-grid scenario-stats">
      <StatCard :label="t('scenarios.statTotal')" :value="scenarioStats.total" icon="fa-solid fa-rotate" variant="slate" />
      <StatCard :label="t('scenarios.statActive')" :value="scenarioStats.active" icon="fa-solid fa-circle-check" variant="green" />
      <StatCard
        :label="t('scenarios.statRunning')"
        :value="scenarioStats.running"
        icon="fa-solid fa-spinner"
        variant="blue"
        :live="scenarioStats.running > 0"
        :hint="t('scenarios.statRunningHint')"
      />
    </div>

    <div class="card-panel card-panel--flush scenario-panel">
      <div class="card-panel-title scenario-panel-head">
        <span><i class="fa-solid fa-list-check" aria-hidden="true"></i>{{ t('scenarios.heading') }}</span>
        <span class="scenario-count muted">{{ t('scenarios.countOf', { shown: filteredScenarios.length, total: scenarios.length }) }}</span>
      </div>

      <div class="filters-bar scenario-filters">
        <Select
          v-model="statusFilter"
          :options="statusFilterOptions"
          option-label="label"
          option-value="value"
          style="width: 220px"
        />
        <InputText
          v-model="searchQuery"
          :placeholder="t('scenarios.searchPlaceholder')"
          style="max-width: 280px; flex: 1"
        />
      </div>

      <EmptyState
        v-if="filteredScenarios.length === 0"
        icon="fa-solid fa-filter"
        :title="t('scenarios.notFoundTitle')"
        :description="t('scenarios.notFoundDesc')"
        compact
      />

      <div v-else class="scenarios-grid">
    <article v-for="sc in filteredScenarios" :key="sc.id" class="scenario-card">
      <header class="scenario-card-header">
        <div class="scenario-card-heading">
          <h3 class="scenario-card-title">{{ sc.name }}</h3>
          <Tag
            :value="sc.is_active ? t('scenarios.active') : t('scenarios.inactive')"
            :severity="sc.is_active ? 'success' : 'secondary'"
            class="scenario-status-tag"
          />
        </div>
        <div class="scenario-card-toolbar">
          <ToggleSwitch
            :model-value="sc.is_active"
            @update:model-value="(v) => toggleScenario(sc.id, v)"
            :title="sc.is_active ? t('scenarios.disable') : t('scenarios.enable')"
          />
          <Button size="small" text severity="secondary" @click="openEditModal(sc)" :title="t('common.edit')">
            <i class="fa-solid fa-pen-to-square"></i>
          </Button>
          <Button size="small" text severity="danger" @click="confirmDelete(sc)" :title="t('common.delete')">
            <i class="fa-solid fa-trash"></i>
          </Button>
        </div>
      </header>

      <div class="scenario-route" :aria-label="t('scenarios.routeAria')">
        <div class="route-endpoint">
          <span class="route-label">{{ t('scenarios.source') }}</span>
          <span class="route-server">{{ sc.source_server_name || `#${sc.source_server_id}` }}</span>
          <code class="route-db">{{ sc.source_database }}</code>
        </div>

        <div class="route-connector">
          <i class="fa-solid fa-arrow-right" aria-hidden="true"></i>
          <Tag
            :value="sc.old_db_action === 'rename' ? t('scenarios.renameOld') : t('scenarios.dropOld')"
            :severity="sc.old_db_action === 'rename' ? 'warn' : 'secondary'"
            class="route-action-tag"
          />
        </div>

        <div class="route-endpoint">
          <span class="route-label">{{ t('scenarios.target') }}</span>
          <span class="route-server">{{ sc.target_server_name || `#${sc.target_server_id}` }}</span>
          <code class="route-db">{{ sc.target_database }}</code>
        </div>
      </div>

      <dl class="scenario-facts">
        <div class="scenario-fact">
          <dt>{{ t('scenarios.schedule') }}</dt>
          <dd>
            <code v-if="sc.cron_expression" class="code-chip cron-chip">{{ sc.cron_expression }}</code>
            <span v-else class="muted">{{ t('scenarios.manualOnly') }}</span>
          </dd>
        </div>

        <div class="scenario-fact">
          <dt>{{ t('scenarios.lastRun') }}</dt>
          <dd class="scenario-fact-run">
            <template v-if="sc.last_run">
              <Tag
                :value="runStatusLabel(sc.last_run.status)"
                :severity="runStatusSeverity(sc.last_run.status)"
              />
              <span v-if="sc.last_run.status === 'running'" class="running-step">
                {{ stepLabel(sc.last_run.current_step) }}
              </span>
              <span v-else class="muted scenario-fact-date">{{ formatDate(sc.last_run.started_at) }}</span>
            </template>
            <span v-else class="muted">{{ t('scenarios.neverRun') }}</span>
          </dd>
        </div>

        <div class="scenario-fact">
          <dt>{{ t('scenarios.exclusions') }}</dt>
          <dd>
            <template v-if="sc.excluded_tables?.length">
              <Button
                text
                size="small"
                severity="secondary"
                class="exclude-toggle-btn"
                @click="toggleExcludedList(sc.id)"
              >
                {{ t('scenarios.excludedCount', { count: sc.excluded_tables.length }) }}
                <i
                  :class="expandedExcludeIds.has(sc.id) ? 'fa-solid fa-chevron-up' : 'fa-solid fa-chevron-down'"
                  aria-hidden="true"
                ></i>
              </Button>
            </template>
            <span v-else class="muted">{{ t('scenarios.none') }}</span>
          </dd>
        </div>
      </dl>

      <ul v-if="sc.excluded_tables?.length && expandedExcludeIds.has(sc.id)" class="scenario-exclude-list">
        <li v-for="t in sc.excluded_tables" :key="t">{{ t }}</li>
      </ul>

      <footer class="scenario-actions">
        <Button
          v-if="sc.last_run?.status !== 'running'"
          size="small"
          outlined
          :loading="runningId === sc.id"
          @click="runNow(sc)"
        >
          <i class="fa-solid fa-play btn-icon-left" aria-hidden="true"></i>{{ t('common.run') }}
        </Button>
        <Button
          v-else
          size="small"
          severity="danger"
          outlined
          :loading="stoppingId === sc.id"
          @click="stopRun(sc)"
        >
          <i class="fa-solid fa-stop btn-icon-left" aria-hidden="true"></i>{{ t('scenarios.stop') }}
        </Button>
        <Button size="small" text severity="secondary" @click="showRuns(sc)">
          <i class="fa-solid fa-list-ul btn-icon-left" aria-hidden="true"></i>{{ t('scenarios.history') }}
        </Button>
      </footer>
    </article>
      </div>
    </div>
  </template>

  <!-- Диалог создания/редактирования -->
  <Dialog
    v-model:visible="showModal"
    modal
    :header="editingId ? t('scenarios.editScenario') : t('scenarios.newScenario')"
    :style="{ width: '560px' }"
  >
    <div class="flex-col" style="gap: 16px">
      <div class="flex-col" style="gap: 4px">
        <label class="form-label" for="sc-name">{{ t('scenarios.nameLabel') }}</label>
        <InputText id="sc-name" v-model="form.name" :placeholder="t('scenarios.namePlaceholder')" />
      </div>

      <div class="form-section-title">
        <i class="fa-solid fa-database form-section-icon" aria-hidden="true"></i>
        {{ t('scenarios.sourceSection') }}
      </div>
      <div class="flex-row" style="gap: 12px">
        <div class="flex-col" style="gap: 4px; flex: 1">
          <label class="form-label" for="sc-source-server">{{ t('common.server') }}</label>
          <Select
            input-id="sc-source-server"
            v-model="form.source_server_id"
            :options="servers"
            option-label="name"
            option-value="id"
            :placeholder="t('scenarios.selectServer')"
            @change="onSourceServerChange"
          />
        </div>
        <div class="flex-col" style="gap: 4px; flex: 1">
          <label class="form-label" for="sc-source-db">{{ t('common.database') }}</label>
          <Select
            input-id="sc-source-db"
            v-model="form.source_database"
            :options="sourceDatabases"
            option-label="datname"
            option-value="datname"
            :loading="sourceDbLoading"
            :placeholder="form.source_server_id ? (sourceDbLoading ? t('common.loading') : t('scenarios.selectDb')) : t('scenarios.selectServerFirst')"
            :disabled="!form.source_server_id || sourceDbLoading"
            filter
          />
        </div>
      </div>

      <div class="form-section-title">
        <i class="fa-solid fa-server form-section-icon form-section-icon--accent" aria-hidden="true"></i>
        {{ t('scenarios.targetSection') }}
      </div>
      <div class="flex-row" style="gap: 12px">
        <div class="flex-col" style="gap: 4px; flex: 1">
          <label class="form-label" for="sc-target-server">{{ t('common.server') }}</label>
          <Select
            input-id="sc-target-server"
            v-model="form.target_server_id"
            :options="servers"
            option-label="name"
            option-value="id"
            :placeholder="t('scenarios.selectServer')"
            @change="onTargetServerChange"
          />
        </div>
        <div class="flex-col" style="gap: 4px; flex: 1">
          <label class="form-label" for="sc-target-db">{{ t('common.database') }}</label>
          <Select
            input-id="sc-target-db"
            v-model="form.target_database"
            :options="targetDbOptions"
            option-label="label"
            option-value="value"
            :loading="targetDbLoading"
            :placeholder="form.target_server_id ? (targetDbLoading ? t('common.loading') : t('scenarios.selectOrEnterName')) : t('scenarios.selectServerFirst')"
            :disabled="!form.target_server_id || targetDbLoading"
            editable
          >
            <template #empty>
              <div style="padding: 8px 12px; font-size: 13px; color: var(--p-text-muted-color)">
                <i class="fa-solid fa-circle-plus" style="margin-right: 6px; color: var(--p-primary-color)"></i>
                {{ t('scenarios.newDbHint') }}
              </div>
            </template>
          </Select>
        </div>
      </div>
      <small style="font-size: 11px; color: var(--p-text-muted-color); margin-top: -8px">
        <i class="fa-solid fa-circle-info" style="margin-right: 4px"></i>
        {{ t('scenarios.newDbHint2') }}
      </small>

      <div class="flex-col" style="gap: 4px">
        <label class="form-label">{{ t('scenarios.oldDbActionLabel') }}</label>
        <div class="action-choice">
          <div
            class="action-option"
            :class="{ selected: form.old_db_action === 'drop' }"
            @click="form.old_db_action = 'drop'"
          >
            <i class="fa-solid fa-trash icon-danger" aria-hidden="true"></i>
            <div>
              <div class="action-option-title">{{ t('common.delete') }}</div>
              <div class="action-option-hint">{{ t('scenarios.dropHint') }}</div>
            </div>
          </div>
          <div
            class="action-option"
            :class="{ selected: form.old_db_action === 'rename' }"
            @click="form.old_db_action = 'rename'"
          >
            <i class="fa-solid fa-pen icon-warning" aria-hidden="true"></i>
            <div>
              <div class="action-option-title">{{ t('scenarios.rename') }}</div>
              <div class="action-option-hint">{{ t('scenarios.renameHint') }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Исключение таблиц из бэкапа -->
      <div class="exclude-section-sc" :class="{ open: excludeTablesOpen }">
        <div class="exclude-toggle-sc" @click="excludeTablesOpen = !excludeTablesOpen">
          <div style="display: flex; align-items: center; gap: 8px">
            <i class="fa-solid fa-table" style="font-size: 12px; color: var(--p-text-muted-color)"></i>
            <span style="font-size: 13px; font-weight: 600">{{ t('scenarios.excludeTables') }}</span>
            <Tag v-if="form.excluded_tables.length > 0" severity="info" :value="String(form.excluded_tables.length)" />
          </div>
          <i :class="excludeTablesOpen ? 'fa-solid fa-chevron-up' : 'fa-solid fa-chevron-down'" style="font-size: 11px; color: var(--p-text-muted-color)"></i>
        </div>
        <div v-if="excludeTablesOpen" class="exclude-body-sc">
          <div style="font-size: 12px; color: var(--p-text-muted-color); margin-bottom: 8px">
            {{ t('scenarios.excludeTablesHint') }}
          </div>
          <div v-if="sourceTablesLoading" style="padding: 12px 0; text-align: center; font-size: 13px; color: var(--p-text-muted-color)">
            <i class="fa-solid fa-spinner fa-spin" style="margin-right: 6px"></i>{{ t('scenarios.loadingTables') }}
          </div>
          <template v-else-if="sourceTables.length > 0">
            <div style="font-size: 12px; color: var(--p-text-muted-color); margin-bottom: 6px">{{ t('scenarios.tablesCountOrder', { count: sourceTables.length }) }}</div>
            <div class="tables-list-sc">
              <div
                v-for="t in sourceTables"
                :key="t.schema + '.' + t.tablename"
                class="table-row-sc"
                :class="{ excluded: form.excluded_tables.includes(t.schema + '.' + t.tablename) }"
                @click="toggleExcludeTable(t.schema + '.' + t.tablename)"
              >
                <input
                  type="checkbox"
                  :checked="form.excluded_tables.includes(t.schema + '.' + t.tablename)"
                  @click.stop="toggleExcludeTable(t.schema + '.' + t.tablename)"
                  style="flex-shrink: 0; cursor: pointer; width: 14px; height: 14px"
                />
                <span style="flex: 1; font-size: 12px"><span style="color: var(--p-text-muted-color)">{{ t.schema }}.</span>{{ t.tablename }}</span>
                <span style="font-size: 11px; color: var(--p-text-muted-color)">{{ t.total_size }}</span>
              </div>
            </div>
          </template>
          <div v-else style="font-size: 12px; color: var(--p-text-muted-color); padding: 8px 0">
            {{ form.source_server_id && form.source_database ? t('scenarios.tablesNotFound') : t('scenarios.selectSourceFirst') }}
          </div>
          <div v-if="form.excluded_tables.length > 0" style="margin-top: 8px; display: flex; gap: 6px; flex-wrap: wrap; align-items: center">
            <span v-for="t in form.excluded_tables" :key="t" style="display: flex; align-items: center; gap: 4px; background: var(--p-surface-100); border-radius: 12px; padding: 2px 10px; font-size: 11px; font-family: monospace">
              {{ t }}
              <i class="fa-solid fa-xmark" style="cursor: pointer; opacity: 0.5" @click="form.excluded_tables = form.excluded_tables.filter(x => x !== t)"></i>
            </span>
            <Button text size="small" severity="secondary" @click="form.excluded_tables = []" style="font-size: 11px; padding: 2px 6px">{{ t('scenarios.reset') }}</Button>
          </div>
        </div>
      </div>

      <div class="flex-col" style="gap: 4px">
        <label class="form-label" for="sc-schedule">
          {{ t('scenarios.schedule') }}
          <span class="form-hint">{{ t('scenarios.scheduleHint') }}</span>
        </label>
        <Select
          input-id="sc-schedule"
          v-model="form.schedule_id"
          :options="[{ id: 0, name: t('scenarios.noSchedule'), cron_expression: '' }, ...cronSchedules, { id: -1, name: t('scenarios.customSchedule'), cron_expression: '' }]"
          option-label="name"
          option-value="id"
          @change="onScheduleChange"
        >
          <template #option="{ option }">
            <div style="display: flex; align-items: center; gap: 10px">
              <span style="flex: 1">{{ option.name }}</span>
              <code v-if="option.cron_expression" style="font-size: 11px; color: var(--p-text-muted-color)">{{ option.cron_expression }}</code>
            </div>
          </template>
        </Select>
        <CronInput
          v-if="form.schedule_id === -1"
          v-model="form.cron_expression"
          style="margin-top: 6px"
        />
        <div v-if="activeCronExpr && form.schedule_id !== -1" class="cron-preview">
          <i class="fa-solid fa-circle-info"></i>
          {{ cronPreview(activeCronExpr) }}
        </div>
      </div>

      <div class="flex-row" style="gap: 8px; align-items: center">
        <ToggleSwitch v-model="form.is_active" input-id="sc-active" />
        <label for="sc-active" style="cursor: pointer; font-size: 13px">{{ t('scenarios.activeScheduled') }}</label>
      </div>
    </div>

    <template #footer>
      <Button text @click="showModal = false">{{ t('common.cancel') }}</Button>
      <Button :loading="submitting" @click="submit(saveScenario)" :disabled="!canSave || submitting">
        {{ editingId ? t('common.save') : t('scenarios.create') }}
      </Button>
    </template>
  </Dialog>

  <!-- Диалог истории запусков -->
  <Dialog
    v-model:visible="showRunsModal"
    modal
    :header="t('scenarios.historyOf', { name: selectedScenarioName })"
    :style="{ width: 'min(1040px, 96vw)' }"
    class="scenario-runs-dialog"
  >
    <div class="scenario-runs-layout">
      <DataTable
        class="app-data-table scenario-runs-table"
        :value="scenarioRuns"
        v-model:selection="selectedRun"
        selectionMode="single"
        dataKey="id"
        :metaKeySelection="false"
        striped-rows
        size="small"
        scrollable
        scrollHeight="320px"
        :rowClass="runRowClass"
      >
        <template #empty>
          <EmptyState icon="fa-solid fa-clock-rotate-left" :title="t('scenarios.noRunsTitle')" :description="t('scenarios.noRunsDesc')" compact />
        </template>
        <Column field="status" :header="t('common.status')" style="width: 108px">
          <template #body="{ data }">
            <Tag
              :value="runStatusLabel(data.status)"
              :severity="runStatusSeverity(data.status)"
            />
          </template>
        </Column>
        <Column :header="t('scenarios.step')" style="width: 140px">
          <template #body="{ data }">
            <span :class="{ 'running-pulse': data.status === 'running' }">
              {{ stepLabel(data.current_step) }}
            </span>
          </template>
        </Column>
        <Column :header="t('scenarios.backup')" style="min-width: 160px">
          <template #body="{ data }">
            <span
              v-if="data.backup_path"
              class="run-cell-clip"
              :title="data.backup_path"
            >{{ backupFileName(data.backup_path) }}</span>
            <span v-else class="muted">—</span>
          </template>
        </Column>
        <Column field="started_at" :header="t('scenarios.start')" style="width: 148px">
          <template #body="{ data }">{{ formatDate(data.started_at) }}</template>
        </Column>
        <Column :header="t('scenarios.duration')" style="width: 96px">
          <template #body="{ data }">{{ duration(data.started_at, data.finished_at) }}</template>
        </Column>
        <Column :header="t('scenarios.error')" style="width: 88px">
          <template #body="{ data }">
            <Tag v-if="data.error_message" severity="danger" :value="t('scenarios.hasError')" />
            <span v-else class="muted">—</span>
          </template>
        </Column>
      </DataTable>

      <div v-if="selectedRun" class="run-detail-panel">
        <div class="run-detail-head">
          <span class="run-detail-title">
            {{ t('scenarios.runFrom', { date: formatDate(selectedRun.started_at) }) }}
            · {{ runStatusLabel(selectedRun.status) }}
          </span>
          <Button
            v-if="selectedRun.error_message"
            text
            size="small"
            severity="secondary"
            @click="copyRunError"
          >
            <i class="fa-solid fa-copy btn-icon-left" aria-hidden="true"></i>{{ t('scenarios.copy') }}
          </Button>
        </div>
        <dl class="run-detail-meta">
          <div v-if="selectedRun.backup_path" class="run-detail-item">
            <dt>{{ t('scenarios.backup') }}</dt>
            <dd class="run-detail-path">{{ selectedRun.backup_path }}</dd>
          </div>
          <div v-if="selectedRun.renamed_to" class="run-detail-item">
            <dt>{{ t('scenarios.renamedTo') }}</dt>
            <dd class="run-detail-mono">{{ selectedRun.renamed_to }}</dd>
          </div>
        </dl>
        <div v-if="selectedRun.error_message" class="run-error-block">
          <div class="run-error-label">{{ t('scenarios.errorText') }}</div>
          <pre class="run-error-log">{{ selectedRun.error_message }}</pre>
        </div>
        <p v-else class="run-detail-ok muted">{{ t('scenarios.noErrorSelect') }}</p>
      </div>
      <p v-else-if="scenarioRuns.length" class="run-detail-hint muted">
        {{ t('scenarios.selectRowHint') }}
      </p>
    </div>
  </Dialog>

  <!-- Запуск: переиспользовать ли дамп прошлого прогона (явный тумблер) -->
  <Dialog v-model:visible="showLaunchDialog" modal :header="t('scenarios.launchOf', { name: launchScenario?.name || '' })" :style="{ width: '460px' }">
    <div v-if="launchScenario" class="launch-reuse">
      <p class="muted" style="margin-bottom: 14px">
        {{ t('scenarios.reuseDumpIntro') }}
        <b>{{ launchScenario.source_database }}</b>:
        <b>{{ formatMB(launchScenario.reuse_dump_size) }}</b><template v-if="launchScenario.reuse_dump_at">, {{ formatDate(launchScenario.reuse_dump_at) }}</template>.
      </p>
      <div class="launch-reuse-toggle" style="display: flex; align-items: center; gap: 10px">
        <ToggleSwitch v-model="reuseDumpToggle" input-id="reuseDump" />
        <label for="reuseDump" style="cursor: pointer">
          <b>{{ t('scenarios.reuseDumpLabel') }}</b>{{ t('scenarios.reuseDumpHint') }}
        </label>
      </div>
      <p class="muted" style="margin-top: 10px; font-size: 12px">
        {{ t('scenarios.reuseDumpOff') }}
      </p>
    </div>
    <template #footer>
      <Button text severity="secondary" @click="showLaunchDialog = false">{{ t('common.cancel') }}</Button>
      <Button v-if="launchScenario" @click="doRun(launchScenario, reuseDumpToggle)">
        <i class="fa-solid fa-play btn-icon-left" aria-hidden="true"></i>{{ t('common.run') }}
      </Button>
    </template>
  </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import EmptyState from '../components/ui/EmptyState.vue'
import StatCard from '../components/ui/StatCard.vue'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import ProgressSpinner from 'primevue/progressspinner'
import Select from 'primevue/select'
import ToggleSwitch from 'primevue/toggleswitch'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import api from '../api/client'
import { useTasksStore } from '../stores/tasks'
import CronInput from '../components/CronInput.vue'
import { useSubmitting } from '../composables/useSubmitting'

const { t } = useI18n()
const toast = useToast()
// In-flight guard против двойного клика по кнопке сохранения сценария
const { submitting, submit } = useSubmitting()
const confirm = useConfirm()
const tasksStore = useTasksStore()

interface ScenarioRun {
  id: number
  scenario_id: number
  task_id: string | null
  status: string
  current_step: string | null
  backup_path: string | null
  renamed_to: string | null
  error_message: string | null
  started_at: string
  finished_at: string | null
}

interface Scenario {
  id: number
  name: string
  source_server_id: number
  source_server_name: string | null
  source_database: string
  target_server_id: number
  target_server_name: string | null
  target_database: string
  old_db_action: string
  excluded_tables: string[]
  cron_expression: string | null
  is_active: boolean
  created_at: string
  last_run: ScenarioRun | null
  reuse_dump_available?: boolean
  reuse_dump_size?: number | null
  reuse_dump_at?: string | null
}

const scenarios = ref<Scenario[]>([])
const servers = ref<{ id: number; name: string; environment: string }[]>([])
const cronSchedules = ref<{ id: number; name: string; cron_expression: string }[]>([])
const loading = ref(false)
const runningId = ref<number | null>(null)
const showLaunchDialog = ref(false)
const launchScenario = ref<Scenario | null>(null)
const reuseDumpToggle = ref(true)

function formatMB(bytes?: number | null): string {
  if (!bytes) return '—'
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

// Базы данных для выбора
const sourceDatabases = ref<{ datname: string }[]>([])
const targetDatabases = ref<{ datname: string }[]>([])
const sourceDbLoading = ref(false)
const targetDbLoading = ref(false)

const targetDbOptions = computed(() => [
  ...targetDatabases.value.map(d => ({ label: d.datname, value: d.datname })),
])

const showModal = ref(false)
const editingId = ref<number | null>(null)
const stoppingId = ref<number | null>(null)
const form = reactive({
  name: '',
  source_server_id: null as number | null,
  source_database: '',
  target_server_id: null as number | null,
  target_database: '',
  old_db_action: 'drop',
  excluded_tables: [] as string[],
  schedule_id: 0 as number,
  cron_expression: '',
  is_active: true,
})

// Исключение таблиц
const excludeTablesOpen = ref(false)
const sourceTables = ref<{ schema: string; tablename: string; total_size: string; total_bytes: number }[]>([])
const sourceTablesLoading = ref(false)

const activeCronExpr = computed(() => {
  if (form.schedule_id === -1) return form.cron_expression
  const sc = cronSchedules.value.find(s => s.id === form.schedule_id)
  return sc?.cron_expression ?? ''
})

const showRunsModal = ref(false)
const selectedScenarioName = ref('')
const scenarioRuns = ref<ScenarioRun[]>([])
const selectedRun = ref<ScenarioRun | null>(null)
const expandedExcludeIds = ref(new Set<number>())
const statusFilter = ref<'all' | 'active' | 'inactive'>('all')
const searchQuery = ref('')

const statusFilterOptions = computed(() => [
  { label: t('scenarios.filterAll'), value: 'all' },
  { label: t('scenarios.filterActive'), value: 'active' },
  { label: t('scenarios.filterInactive'), value: 'inactive' },
])

const scenarioStats = computed(() => {
  const list = scenarios.value
  return {
    total: list.length,
    active: list.filter(s => s.is_active).length,
    running: list.filter(s => s.last_run?.status === 'running').length,
  }
})

const filteredScenarios = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return scenarios.value.filter(sc => {
    if (statusFilter.value === 'active' && !sc.is_active) return false
    if (statusFilter.value === 'inactive' && sc.is_active) return false
    if (q && !sc.name.toLowerCase().includes(q)) return false
    return true
  })
})

const canSave = computed(() =>
  form.name && form.source_server_id && form.source_database &&
  form.target_server_id && form.target_database
)

async function loadData() {
  loading.value = true
  try {
    const [sc, sv, cron] = await Promise.all([
      api.get('/scenarios'),
      api.get('/servers'),
      api.get('/cron-schedules'),
    ])
    scenarios.value = sc.data
    servers.value = sv.data
    cronSchedules.value = cron.data
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('scenarios.heading'), detail: e?.response?.data?.detail || e?.message || t('scenarios.loadFailed'), life: 5000 })
  } finally {
    loading.value = false
  }
}

async function fetchDatabases(serverId: number, target: 'source' | 'target') {
  if (target === 'source') { sourceDbLoading.value = true; sourceDatabases.value = [] }
  else { targetDbLoading.value = true; targetDatabases.value = [] }
  try {
    const { data } = await api.get(`/servers/${serverId}/databases`)
    if (target === 'source') sourceDatabases.value = data
    else targetDatabases.value = data
  } catch {
  } finally {
    if (target === 'source') sourceDbLoading.value = false
    else targetDbLoading.value = false
  }
}

function openCreateModal() {
  editingId.value = null
  form.name = ''
  form.source_server_id = null
  form.source_database = ''
  form.target_server_id = null
  form.target_database = ''
  form.old_db_action = 'drop'
  form.excluded_tables = []
  form.schedule_id = 0
  form.cron_expression = ''
  form.is_active = true
  sourceDatabases.value = []
  targetDatabases.value = []
  sourceTables.value = []
  excludeTablesOpen.value = false
  showModal.value = true
}

function openEditModal(sc: Scenario) {
  editingId.value = sc.id
  form.name = sc.name
  form.source_server_id = sc.source_server_id
  form.source_database = sc.source_database
  form.target_server_id = sc.target_server_id
  form.target_database = sc.target_database
  form.old_db_action = sc.old_db_action
  form.excluded_tables = sc.excluded_tables ? [...sc.excluded_tables] : []
  form.is_active = sc.is_active
  excludeTablesOpen.value = false

  // Найти расписание по cron_expression
  const expr = sc.cron_expression ?? ''
  const found = cronSchedules.value.find(s => s.cron_expression === expr)
  if (!expr) {
    form.schedule_id = 0
    form.cron_expression = ''
  } else if (found) {
    form.schedule_id = found.id
    form.cron_expression = ''
  } else {
    form.schedule_id = -1
    form.cron_expression = expr
  }

  if (sc.source_server_id) fetchDatabases(sc.source_server_id, 'source')
  if (sc.target_server_id) fetchDatabases(sc.target_server_id, 'target')
  showModal.value = true
}

function onSourceServerChange() {
  form.source_database = ''
  sourceTables.value = []
  if (form.source_server_id) fetchDatabases(form.source_server_id, 'source')
}

async function fetchSourceTables() {
  if (!form.source_server_id || !form.source_database) return
  sourceTablesLoading.value = true
  sourceTables.value = []
  try {
    const { data } = await api.get(`/servers/${form.source_server_id}/databases/${form.source_database}/tables-size`)
    sourceTables.value = data
  } catch {
  } finally {
    sourceTablesLoading.value = false
  }
}

function toggleExcludeTable(fullName: string) {
  const idx = form.excluded_tables.indexOf(fullName)
  if (idx >= 0) form.excluded_tables.splice(idx, 1)
  else form.excluded_tables.push(fullName)
}

async function stopRun(sc: Scenario) {
  if (!sc.last_run?.id) return
  if (stoppingId.value === sc.id) return
  stoppingId.value = sc.id
  try {
    await api.post(`/scenarios/runs/${sc.last_run.id}/stop`)
    toast.add({ severity: 'info', summary: t('scenarios.stopped'), life: 2500 })
    await loadData()
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('scenarios.error'), detail: e.response?.data?.detail || 'Error', life: 4000 })
  } finally {
    stoppingId.value = null
  }
}

function onTargetServerChange() {
  form.target_database = ''
  if (form.target_server_id) fetchDatabases(form.target_server_id, 'target')
}

function onScheduleChange() {
  if (form.schedule_id !== -1) form.cron_expression = ''
}

// Загружать таблицы источника при открытии секции или смене БД
watch(excludeTablesOpen, (open) => {
  if (open && sourceTables.value.length === 0) fetchSourceTables()
})
watch(() => form.source_database, () => {
  sourceTables.value = []
  if (excludeTablesOpen.value) fetchSourceTables()
})

async function saveScenario() {
  let cron: string | null = null
  if (form.schedule_id === -1) {
    cron = form.cron_expression || null
  } else if (form.schedule_id) {
    cron = cronSchedules.value.find(s => s.id === form.schedule_id)?.cron_expression ?? null
  }

  const payload = {
    name: form.name,
    source_server_id: form.source_server_id,
    source_database: form.source_database,
    target_server_id: form.target_server_id,
    target_database: form.target_database,
    old_db_action: form.old_db_action,
    excluded_tables: form.excluded_tables,
    cron_expression: cron,
    is_active: form.is_active,
  }
  try {
    if (editingId.value) {
      await api.put(`/scenarios/${editingId.value}`, payload)
      toast.add({ severity: 'success', summary: t('scenarios.updated'), life: 2500 })
    } else {
      await api.post('/scenarios', payload)
      toast.add({ severity: 'success', summary: t('scenarios.created'), life: 2500 })
    }
    showModal.value = false
    loadData()
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('scenarios.error'), detail: e.response?.data?.detail || 'Error', life: 4000 })
  }
}

async function toggleScenario(id: number, isActive: boolean) {
  try {
    await api.put(`/scenarios/${id}`, { is_active: isActive })
    const idx = scenarios.value.findIndex(s => s.id === id)
    if (idx !== -1) scenarios.value[idx].is_active = isActive
  } catch (e: any) {
    toast.add({ severity: 'error', summary: t('scenarios.error'), detail: e.response?.data?.detail || 'Error', life: 3000 })
  }
}

function confirmDelete(sc: Scenario) {
  confirm.require({
    message: t('scenarios.deleteConfirm', { name: sc.name }),
    header: t('common.confirm'),
    icon: 'fa-solid fa-triangle-exclamation',
    acceptLabel: t('common.delete'),
    rejectLabel: t('common.cancel'),
    accept: async () => {
      try {
        await api.delete(`/scenarios/${sc.id}`)
        scenarios.value = scenarios.value.filter(s => s.id !== sc.id)
        toast.add({ severity: 'info', summary: t('scenarios.deleted'), life: 2000 })
      } catch (e: any) {
        toast.add({ severity: 'error', summary: t('scenarios.error'), detail: e.response?.data?.detail || 'Error', life: 4000 })
      }
    },
  })
}

// Есть дамп от прошлого прогона → спросим, переиспользовать ли (тумблер).
function runNow(sc: Scenario) {
  if (runningId.value === sc.id) return
  if (sc.reuse_dump_available) {
    launchScenario.value = sc
    reuseDumpToggle.value = true
    showLaunchDialog.value = true
  } else {
    doRun(sc, false)
  }
}

async function doRun(sc: Scenario, reuseDump: boolean) {
  showLaunchDialog.value = false
  runningId.value = sc.id
  try {
    await api.post(`/scenarios/${sc.id}/run`, null, { params: { reuse_dump: reuseDump } })
    toast.add({
      severity: 'info',
      summary: t('scenarios.launched'),
      detail: reuseDump
        ? t('scenarios.launchedReuse', { name: sc.name })
        : t('scenarios.launchedQueued', { name: sc.name }),
      life: 3000,
    })
    // Обновляем список через 2 сек чтобы подтянуть статус running
    setTimeout(() => loadData(), 2000)
  } catch (e: any) {
    const detail = e.response?.data?.detail || t('scenarios.launchError')
    toast.add({ severity: 'error', summary: t('scenarios.error'), detail, life: 4000 })
  } finally {
    runningId.value = null
  }
}

async function showRuns(sc: Scenario) {
  selectedScenarioName.value = sc.name
  selectedRun.value = null
  try {
    const { data } = await api.get(`/scenarios/${sc.id}/runs`)
    scenarioRuns.value = data
    selectedRun.value = data.find((r: ScenarioRun) => r.error_message) ?? data[0] ?? null
    showRunsModal.value = true
  } catch {
    toast.add({ severity: 'error', summary: t('scenarios.historyLoadError'), life: 3000 })
  }
}

function backupFileName(path: string): string {
  const parts = path.split(/[/\\]/)
  return parts[parts.length - 1] || path
}

function runRowClass(data: ScenarioRun): string {
  const classes = ['scenario-run-row']
  if (data.status === 'failed') classes.push('scenario-run-row--failed')
  return classes.join(' ')
}

async function copyRunError() {
  const text = selectedRun.value?.error_message
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    toast.add({ severity: 'success', summary: t('scenarios.copied'), life: 2000 })
  } catch {
    toast.add({ severity: 'error', summary: t('scenarios.copyFailed'), life: 2500 })
  }
}

watch(showRunsModal, (open) => {
  if (!open) selectedRun.value = null
})

// ── Утилиты ────────────────────────────────────────────
function runStatusLabel(status: string): string {
  const m: Record<string, string> = { running: t('scenarios.statusRunning'), success: t('scenarios.statusSuccess'), failed: t('scenarios.statusFailed') }
  return m[status] || status
}

function runStatusSeverity(status: string): string {
  const m: Record<string, string> = { running: 'info', success: 'success', failed: 'danger' }
  return m[status] || 'secondary'
}

function toggleExcludedList(id: number) {
  const next = new Set(expandedExcludeIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expandedExcludeIds.value = next
}

function stepLabel(step: string | null): string {
  if (!step) return '—'
  const labels: Record<string, string> = {
    init: t('scenarios.stepInit'),
    backup_source: t('scenarios.stepBackup'),
    terminate_connections: t('scenarios.stepTerminate'),
    rename_old_db: t('scenarios.stepRenameOld'),
    drop_old_db: t('scenarios.stepDropOld'),
    create_target_db: t('scenarios.stepCreateTarget'),
    prepare_extensions: t('scenarios.stepPrepareExt'),
    restore: t('scenarios.stepRestore'),
    done: t('scenarios.stepDone'),
  }
  return labels[step] || step
}

function cronPreview(expr: string): string {
  const parts = expr.trim().split(/\s+/)
  if (parts.length !== 5) return t('scenarios.invalidCron')
  const [min, hour, dom, month, dow] = parts
  if (dom === '*' && month === '*' && dow === '*') {
    if (min !== '*' && hour !== '*') return t('scenarios.cronDaily', { time: `${hour.padStart(2, '0')}:${min.padStart(2, '0')}` })
    if (min === '0' && hour === '*') return t('scenarios.cronHourly')
  }
  return `cron: ${expr}`
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  try {
    const utc = !iso.endsWith('Z') && !/[+-]\d{2}:\d{2}$/.test(iso) ? iso + 'Z' : iso
    return new Date(utc).toLocaleString('ru-RU')
  } catch { return iso }
}

function duration(start: string, end: string | null): string {
  if (!end) return '...'
  try {
    const s = new Date(start.endsWith('Z') ? start : start + 'Z')
    const e = new Date(end.endsWith('Z') ? end : end + 'Z')
    const sec = Math.round((e.getTime() - s.getTime()) / 1000)
    if (sec < 60) return t('scenarios.durSec', { n: sec })
    return t('scenarios.durMin', { m: Math.floor(sec / 60), s: sec % 60 })
  } catch { return '—' }
}

// Автообновление карточек когда сценарий завершается через WebSocket
watch(
  () => tasksStore.tasks
    .filter(t => t.type === 'scenario')
    .map(t => ({ id: t.taskId, done: t.done, failed: t.failed })),
  (curr, prev) => {
    if (!prev) return
    const prevMap = new Map(prev.map(t => [t.id, t]))
    const justFinished = curr.some(t => {
      const was = prevMap.get(t.id)
      return (t.done || t.failed) && was && !was.done && !was.failed
    })
    if (justFinished) loadData()
  },
)

onMounted(loadData)
</script>
