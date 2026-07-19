<template>
  <div
    v-if="store.tasks.length > 0"
    class="task-float"
    :class="{
      open: store.expanded,
      'has-detail': !!store.expandedTaskId,
      fullscreen: fullscreen && store.expanded,
      dark: themeStore.mode === 'dark',
    }"
  >
    <Transition name="task-float-panel">
      <div v-if="store.expanded" class="task-float-panel" role="dialog" :aria-label="t('tasks.title')">
        <div class="task-float-head">
          <span class="task-float-title">{{ t('tasks.title') }}</span>
          <Badge v-if="store.activeCount > 0" :value="String(store.activeCount)" severity="warn" />
          <span v-else-if="store.failedCount > 0" class="dock-failed-hint">{{ t('tasks.failedCount', { count: store.failedCount }) }}</span>
          <span v-else class="muted-text">{{ t('tasks.allDone') }}</span>
          <span class="muted-text dock-meta">{{ t('tasks.inList', { count: store.tasks.length }) }}</span>
          <span class="spacer"></span>
          <Button
            text
            rounded
            size="small"
            severity="secondary"
            :aria-label="t('tasks.manageList')"
            @click="toggleManageMenu"
          >
            <i class="fa-solid fa-ellipsis-vertical"></i>
          </Button>
          <Menu ref="manageMenuRef" :model="manageMenuItems" popup />
          <Button
            text
            rounded
            size="small"
            severity="secondary"
            :aria-label="fullscreen ? t('tasks.normalSize') : t('tasks.fullscreen')"
            v-tooltip.top="fullscreen ? t('tasks.normalSize') : t('tasks.fullscreen')"
            @click="toggleFullscreen"
          >
            <i class="fa-solid" :class="fullscreen ? 'fa-compress' : 'fa-expand'"></i>
          </Button>
          <Button
            text
            rounded
            size="small"
            severity="secondary"
            :aria-label="t('tasks.collapse')"
            @click="collapsePanel"
          >
            <i class="fa-solid fa-chevron-down"></i>
          </Button>
        </div>

        <div class="task-float-body">
        <div class="task-dock-list" role="list">
          <div
            v-for="task in store.tasks"
            :key="task.taskId"
            role="listitem"
            class="task-compact"
            :class="{
              done: task.done,
              failed: task.failed,
              active: !task.done && !task.failed,
              selected: store.expandedTaskId === task.taskId,
            }"
          >
            <button
              type="button"
              class="task-compact-hit"
              :aria-expanded="store.expandedTaskId === task.taskId"
              @click="store.toggleTask(task.taskId)"
            >
              <div class="task-row-top">
                <span
                  class="task-badge"
                  :class="task.failed ? 'is-failed' : task.done ? 'is-done' : 'is-active'"
                >{{ taskTagLabel(task) }}</span>
                <span class="task-compact-title" :title="compactTitle(task)">{{ compactTitle(task) }}</span>
                <span class="task-compact-pct">{{ store.progressPercent(task) }}%</span>
              </div>
              <div class="task-row-meta">
                <span class="task-compact-stage" :title="task.failed ? (task.error || '') : undefined">
                  <template v-if="task.failed">
                    <i class="fa-solid fa-circle-xmark" aria-hidden="true"></i>
                    {{ shortError(task.error) }}
                  </template>
                  <template v-else-if="task.done">
                    <i class="fa-solid fa-circle-check" aria-hidden="true"></i>
                    {{ t('tasks.done') }}
                  </template>
                  <template v-else>
                    <i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i>
                    {{ runningStageLabel(task) }}
                  </template>
                </span>
                <span v-if="task.bytesWritten" class="task-compact-bytes">{{ formatBytes(task.bytesWritten) }}</span>
                <span class="task-compact-elapsed"><i class="fa-regular fa-clock" aria-hidden="true"></i> {{ formatDuration(taskElapsedSec(task)) }}</span>
              </div>
              <div class="task-compact-track" aria-hidden="true">
                <div
                  class="task-compact-fill"
                  :class="{ done: task.done, failed: task.failed }"
                  :style="{ width: store.progressPercent(task) + '%' }"
                ></div>
              </div>
            </button>

            <div class="task-compact-actions" @click.stop>
              <Button
                v-if="task.awaitingApproval"
                severity="success"
                size="small"
                :aria-label="t('tasks.approveSwap')"
                v-tooltip.top="t('tasks.approveSwap')"
                @click="confirmApproveSwap(task)"
              >
                <i class="fa-solid fa-check"></i>
              </Button>
              <Button
                v-if="task.awaitingApproval"
                severity="danger"
                outlined
                size="small"
                :aria-label="t('tasks.rejectSwap')"
                v-tooltip.top="t('tasks.rejectSwap')"
                @click="confirmRejectSwap(task)"
              >
                <i class="fa-solid fa-xmark"></i>
              </Button>
              <Button
                v-if="store.canCancelTask(task)"
                severity="danger"
                outlined
                size="small"
                :aria-label="task.type === 'scenario' ? t('tasks.stopScenario') : t('tasks.cancelTask')"
                v-tooltip.top="task.type === 'scenario' ? t('tasks.stop') : t('tasks.cancel')"
                @click="confirmCancel(task)"
              >
                <i class="fa-solid" :class="task.type === 'scenario' ? 'fa-stop' : 'fa-xmark'"></i>
              </Button>
              <Button
                severity="secondary"
                text
                size="small"
                :aria-label="t('tasks.hideFromList')"
                v-tooltip.top="t('tasks.hide')"
                @click="store.dismissTask(task.taskId)"
              >
                <i class="fa-solid fa-eye-slash"></i>
              </Button>
            </div>
          </div>
        </div>

        <div v-if="store.expandedTaskId && detailTask" class="task-detail-panel">
          <div class="task-detail-header">
            <span class="task-detail-title">{{ compactTitle(detailTask) }}</span>
            <span class="task-detail-elapsed" :title="(detailTask.done || detailTask.failed) ? t('tasks.duration') : t('tasks.running')">
              <i class="fa-regular fa-clock" aria-hidden="true"></i>
              {{ formatDuration(taskElapsedSec(detailTask)) }}<template v-if="!detailTask.done && !detailTask.failed">…</template>
            </span>
            <div class="task-detail-head-actions">
              <Button
                v-if="detailTask.awaitingApproval"
                severity="success"
                size="small"
                @click="confirmApproveSwap(detailTask)"
              >
                <i class="fa-solid fa-check" style="margin-right: 4px"></i>{{ t('tasks.approveSwap') }}
              </Button>
              <Button
                v-if="detailTask.awaitingApproval"
                severity="danger"
                outlined
                size="small"
                @click="confirmRejectSwap(detailTask)"
              >
                <i class="fa-solid fa-xmark" style="margin-right: 4px"></i>{{ t('tasks.rejectSwap') }}
              </Button>
              <Button
                v-if="store.canCancelTask(detailTask)"
                severity="danger"
                outlined
                size="small"
                @click="confirmCancel(detailTask)"
              >
                <i class="fa-solid fa-xmark" style="margin-right: 4px"></i>{{ t('tasks.cancel') }}
              </Button>
              <Button
                severity="secondary"
                text
                size="small"
                @click="store.dismissTask(detailTask.taskId)"
              >
                {{ t('tasks.hide') }}
              </Button>
              <Button text size="small" severity="secondary" :aria-label="t('tasks.closeDetails')" @click="store.expandedTaskId = null">
                <i class="fa-solid fa-xmark"></i>
              </Button>
            </div>
          </div>

          <div class="stage-list">
            <div
              v-for="(s, i) in stagesFor(detailTask)"
              :key="s"
              class="stage-pill"
              :class="stageClass(detailTask, s, i)"
            >
              <i v-if="stageState(detailTask, s, i) === 'done'" class="fa-solid fa-check"></i>
              <i v-else-if="stageState(detailTask, s, i) === 'active'" class="fa-solid fa-spinner fa-spin"></i>
              <i v-else-if="stageState(detailTask, s, i) === 'failed'" class="fa-solid fa-xmark"></i>
              <i v-else class="fa-regular fa-circle"></i>
              <span>{{ stageLabel(detailTask, s) }}</span>
            </div>
          </div>

          <div class="console-wrap">
            <div class="console-toolbar">
              <span class="muted-text">{{ t('tasks.linesCount', { count: detailTask.phases.length }) }}</span>
              <span class="spacer"></span>
              <Button text size="small" severity="secondary" @click="copyLog(detailTask)">
                <i class="fa-regular fa-copy" style="margin-right: 4px"></i>{{ t('tasks.copy') }}
              </Button>
            </div>
            <div class="console" :data-task="detailTask.taskId">
              <div
                v-for="(p, i) in detailTask.phases"
                :key="i"
                class="console-line"
                :class="`level-${p.level}`"
              >
                <span class="console-ts">{{ formatTs(p.ts) }}</span>
                <span v-if="p.source" class="console-src">{{ p.source }}</span>
                <span class="console-msg">{{ p.message }}</span>
              </div>
              <div v-if="detailTask.bytesWritten && !detailTask.done" class="console-line level-bytes">
                <span class="console-ts">{{ formatTs(new Date().toISOString()) }}</span>
                <span class="console-src">live</span>
                <span class="console-msg">→ {{ t('tasks.written') }} {{ formatBytes(detailTask.bytesWritten) }}<template v-if="detailTask.bytesWritten >= 1048576"> ({{ formatKb(detailTask.bytesWritten) }})</template></span>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="fullscreen" class="task-detail-placeholder">
          <i class="fa-solid fa-arrow-left" aria-hidden="true"></i>
          <span>{{ t('tasks.selectHint') }}</span>
        </div>
        </div>
      </div>
    </Transition>

    <!-- Плавающий триггер отключён: задачник теперь закреплён в левой панели (см. AppLayout). -->
    <button
      v-if="false"
      type="button"
      class="task-float-trigger"
      :class="{ 'is-active': store.activeCount > 0, 'is-failed': store.failedCount > 0 && store.activeCount === 0 }"
      :aria-expanded="store.expanded"
      :aria-label="t('tasks.title')"
      @click="store.expanded = !store.expanded"
    >
      <i class="fa-solid fa-list-check task-float-trigger-icon" aria-hidden="true"></i>
      <span class="task-float-trigger-label">{{ t('tasks.title') }}</span>
      <Badge v-if="store.activeCount > 0" :value="String(store.activeCount)" severity="warn" />
      <span v-else-if="store.failedCount > 0" class="task-float-trigger-failed">{{ store.failedCount }}</span>
      <span v-if="primaryTask && !primaryTask.done && !primaryTask.failed" class="task-float-trigger-pct">
        {{ store.progressPercent(primaryTask) }}%
      </span>
      <div
        v-if="primaryTask && !primaryTask.done && !primaryTask.failed"
        class="task-float-trigger-bar"
        aria-hidden="true"
      >
        <div class="task-float-trigger-fill" :style="{ width: store.progressPercent(primaryTask) + '%' }"></div>
      </div>
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import Badge from 'primevue/badge'
import Button from 'primevue/button'
import Menu from 'primevue/menu'
import type { MenuItem } from 'primevue/menuitem'
import { useConfirm } from 'primevue/useconfirm'
import { useToast } from 'primevue/usetoast'
import { useTasksStore, type ActiveTask } from '../stores/tasks'
import { useThemeStore } from '../stores/theme'

const { t } = useI18n()
const store = useTasksStore()
const themeStore = useThemeStore()
const toast = useToast()
const confirm = useConfirm()
const manageMenuRef = ref<InstanceType<typeof Menu> | null>(null)
const fullscreen = ref(false)

function toggleFullscreen() {
  fullscreen.value = !fullscreen.value
  if (fullscreen.value && !store.expandedTaskId && store.tasks.length > 0) {
    store.expandedTaskId = store.tasks[0].taskId
  }
}

function collapsePanel() {
  fullscreen.value = false
  store.expanded = false
}

function onFullscreenKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && fullscreen.value && store.expanded) {
    fullscreen.value = false
    e.preventDefault()
  }
}

// Тикающие часы для «прошло …» у активных задач (локально, без сети).
const nowTick = ref(Date.now())
let clockTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  window.addEventListener('keydown', onFullscreenKeydown)
  clockTimer = setInterval(() => { nowTick.value = Date.now() }, 1000)
})
onUnmounted(() => {
  window.removeEventListener('keydown', onFullscreenKeydown)
  if (clockTimer) clearInterval(clockTimer)
})

watch(() => store.expanded, (open) => {
  if (!open) fullscreen.value = false
})

const manageMenuItems = computed<MenuItem[]>(() => [
  {
    label: store.doneCount ? `${t('tasks.clearDone')} (${store.doneCount})` : t('tasks.clearDone'),
    icon: 'fa-solid fa-check',
    disabled: store.doneCount === 0,
    command: () => {
      store.clearDone()
      toast.add({ severity: 'info', summary: t('tasks.listCleared'), detail: t('tasks.doneHidden'), life: 2500 })
    },
  },
  {
    label: store.failedCount ? `${t('tasks.clearFailed')} (${store.failedCount})` : t('tasks.clearFailed'),
    icon: 'fa-solid fa-circle-xmark',
    disabled: store.failedCount === 0,
    command: () => {
      store.clearFailed()
      toast.add({ severity: 'info', summary: t('tasks.listCleared'), detail: t('tasks.failedHidden'), life: 2500 })
    },
  },
  { separator: true },
  {
    label: t('tasks.clearAll'),
    icon: 'fa-solid fa-trash-can',
    disabled: store.tasks.length === 0,
    command: () => confirmClearAll(),
  },
])

function toggleManageMenu(event: Event) {
  manageMenuRef.value?.toggle(event)
}

function confirmClearAll() {
  confirm.require({
    message: store.activeCount > 0
      ? t('tasks.confirmClearAllActive')
      : t('tasks.confirmClearAll'),
    header: t('tasks.clearListHeader'),
    icon: 'fa-solid fa-trash-can',
    acceptLabel: t('tasks.clear'),
    rejectLabel: t('common.cancel'),
    acceptClass: 'p-button-danger',
    accept: () => {
      store.clearAll()
      collapsePanel()
      toast.add({ severity: 'info', summary: t('tasks.listEmpty'), life: 2000 })
    },
  })
}

function confirmCancel(task: ActiveTask) {
  const isScenario = task.type === 'scenario'
  confirm.require({
    message: isScenario
      ? t('tasks.confirmStopScenario', { name: task.scenarioName || task.serverName })
      : task.type === 'restore'
        ? t('tasks.confirmCancelRestore', { db: task.database })
        : t('tasks.confirmCancelBackup', { db: task.database }),
    header: isScenario ? t('tasks.stopScenario') : t('tasks.cancelTask'),
    icon: 'fa-solid fa-triangle-exclamation',
    acceptLabel: isScenario ? t('tasks.stop') : t('tasks.cancel'),
    rejectLabel: t('tasks.no'),
    acceptClass: 'p-button-danger',
    accept: () => { void store.cancelTask(task.taskId) },
  })
}

function confirmApproveSwap(task: ActiveTask) {
  confirm.require({
    message: t('tasks.confirmApproveSwap', { name: task.scenarioName || task.serverName, temp: task.tempDb || '' }),
    header: t('tasks.approveSwap'),
    icon: 'fa-solid fa-triangle-exclamation',
    acceptLabel: t('tasks.approveSwap'),
    rejectLabel: t('tasks.no'),
    acceptClass: 'p-button-success',
    accept: () => { void store.approveSwap(task.taskId) },
  })
}

function confirmRejectSwap(task: ActiveTask) {
  confirm.require({
    message: t('tasks.confirmRejectSwap', { name: task.scenarioName || task.serverName }),
    header: t('tasks.rejectSwap'),
    icon: 'fa-solid fa-triangle-exclamation',
    acceptLabel: t('tasks.rejectSwap'),
    rejectLabel: t('tasks.no'),
    acceptClass: 'p-button-danger',
    accept: () => { void store.rejectSwap(task.taskId) },
  })
}

const detailTask = computed(() =>
  store.expandedTaskId
    ? store.tasks.find(t => t.taskId === store.expandedTaskId)
    : undefined
)

const primaryTask = computed(() =>
  store.tasks.find(t => !t.done && !t.failed) ?? store.tasks[0]
)

const RESTORE_STAGES = ['download', 'restore', 'completed']
const SCENARIO_STAGES_LIST = ['backup_source', 'terminate_connections', 'drop_old_db', 'rename_old_db', 'create_target_db', 'prepare_extensions', 'restore', 'done']
const STRUCTURE_SYNC_STAGES_LIST = ['backup_test', 'clone_prod', 'build_plan', 'apply_schemas', 'apply_collations', 'apply_extensions', 'apply_foreign', 'apply_types', 'apply_functions_early', 'apply_sequences', 'apply_aggregates', 'apply_new_tables', 'apply_columns', 'apply_indexes', 'apply_constraints', 'apply_rls', 'apply_matviews', 'apply_functions', 'apply_operators', 'apply_views', 'apply_triggers', 'apply_rules', 'apply_event_triggers', 'apply_publications', 'apply_comments', 'apply_grants', 'verify', 'swap', 'done']
const STRUCTURE_SYNC_STAGE_LABELS = computed<Record<string, string>>(() => ({
  backup_test: 'Backup test',
  clone_prod: t('tasks.ssStage.clone_prod'),
  build_plan: t('tasks.ssStage.build_plan'),
  apply_schemas: t('tasks.ssStage.apply_schemas'),
  apply_collations: 'Collations',
  apply_extensions: t('tasks.ssStage.apply_extensions'),
  apply_foreign: 'Foreign/FDW',
  apply_types: t('tasks.ssStage.apply_types'),
  apply_functions_early: t('tasks.ssStage.apply_functions_early'),
  apply_sequences: 'Sequences',
  apply_aggregates: 'Aggregates',
  apply_new_tables: t('tasks.ssStage.apply_new_tables'),
  apply_columns: t('tasks.ssStage.apply_columns'),
  apply_indexes: t('tasks.ssStage.apply_indexes'),
  apply_constraints: t('tasks.ssStage.apply_constraints'),
  apply_rls: 'RLS',
  apply_matviews: 'Matviews',
  apply_functions: t('tasks.ssStage.apply_functions'),
  apply_operators: t('tasks.ssStage.apply_operators'),
  apply_views: 'Views',
  apply_triggers: t('tasks.ssStage.apply_triggers'),
  apply_rules: 'Rules',
  apply_event_triggers: t('tasks.ssStage.apply_event_triggers'),
  apply_publications: t('tasks.ssStage.apply_publications'),
  apply_comments: t('tasks.ssStage.apply_comments'),
  apply_grants: t('tasks.ssStage.apply_grants'),
  verify: t('tasks.ssStage.verify'),
  swap: t('tasks.ssStage.swap'),
  done: t('tasks.done'),
}))
const SCENARIO_STAGE_LABELS = computed<Record<string, string>>(() => ({
  backup_source: t('tasks.scStage.backup_source'),
  terminate_connections: t('tasks.scStage.terminate_connections'),
  drop_old_db: t('tasks.scStage.drop_old_db'),
  rename_old_db: t('tasks.scStage.rename_old_db'),
  create_target_db: t('tasks.scStage.create_target_db'),
  prepare_extensions: t('tasks.scStage.prepare_extensions'),
  restore: 'Restore',
  done: t('tasks.done'),
}))

const PG_CLIENT_STAGES_LIST = ['preparing', 'update', 'install', 'verify', 'completed']
const PG_CLIENT_UNINSTALL_STAGES_LIST = ['remove', 'verify', 'completed']
const PG_CLIENT_REFRESH_STAGES_LIST = ['preparing', 'update', 'scan', 'completed']

function taskTagLabel(task: ActiveTask): string {
  if (task.type === 'backup') return t('tasks.tagBackup')
  if (task.type === 'scenario') return t('tasks.tagScenario')
  if (task.type === 'structure_sync') return t('tasks.tagMigration')
  if (task.type === 'pg_client') {
    if (task.pgAction === 'uninstall') return 'PG −'
    if (task.pgAction === 'refresh') return 'PGDG'
    return 'PG +'
  }
  return 'Restore'
}

function compactTitle(t: ActiveTask): string {
  if (t.type === 'structure_sync') return t.scenarioName || t.serverName
  if (t.type === 'scenario') {
    const name = t.scenarioName || t.serverName
    return `${name} · ${t.database}`
  }
  if (t.type === 'pg_client') return t.database
  return `${t.serverName} / ${t.database}`
}

function shortError(msg: string | null | undefined, max = 48): string {
  const text = (msg || t('tasks.error')).trim()
  if (text.length <= max) return text
  return `${text.slice(0, max - 1)}…`
}

function runningStageLabel(t: ActiveTask): string {
  if (t.type === 'scenario') return store.SCENARIO_STEP_LABELS[t.stage] ?? t.stage
  if (t.type === 'structure_sync') return store.STRUCTURE_SYNC_STEP_LABELS[t.stage] ?? t.stage
  if (t.type === 'pg_client') return store.PG_CLIENT_STAGE_LABELS[t.stage] ?? t.stage
  if (t.type === 'backup') return store.BACKUP_STAGE_LABELS[t.stage] ?? t.stage
  return t.stage
}

function stagesFor(t: ActiveTask): string[] {
  if (t.type === 'backup') return store.backupStagesFor(t)
  if (t.type === 'scenario') return SCENARIO_STAGES_LIST
  if (t.type === 'structure_sync') return STRUCTURE_SYNC_STAGES_LIST
  if (t.type === 'pg_client') {
    if (t.pgAction === 'uninstall') return PG_CLIENT_UNINSTALL_STAGES_LIST
    if (t.pgAction === 'refresh') return PG_CLIENT_REFRESH_STAGES_LIST
    return PG_CLIENT_STAGES_LIST
  }
  return RESTORE_STAGES
}

function stageLabel(task: ActiveTask, s: string): string {
  if (task.type === 'scenario') return SCENARIO_STAGE_LABELS.value[s] ?? s
  if (task.type === 'structure_sync') return STRUCTURE_SYNC_STAGE_LABELS.value[s] ?? s
  if (task.type === 'pg_client') return store.PG_CLIENT_STAGE_LABELS[s] ?? s
  if (task.type === 'backup') return store.BACKUP_STAGE_LABELS[s] ?? s
  return s
}

function stageState(t: ActiveTask, s: string, i: number): 'done' | 'active' | 'pending' | 'failed' {
  const stages = stagesFor(t)
  const cur = stages.indexOf(t.stage)
  if (t.done) return 'done'
  if (t.failed) {
    if (cur < 0) return i === 0 ? 'failed' : 'pending'
    if (i < cur) return 'done'
    if (i === cur) return 'failed'
    return 'pending'
  }
  if (cur < 0) return 'pending'
  if (i < cur) return 'done'
  if (i === cur) return 'active'
  return 'pending'
}

function stageClass(t: ActiveTask, s: string, i: number) {
  return `stage-${stageState(t, s, i)}`
}

function formatBytes(b: number): string {
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
  if (b < 1024 * 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`
  return `${(b / 1024 / 1024 / 1024).toFixed(2)} GB`
}

// Точное значение в КБ с разделителями — чтобы на гигабайтах было видно движение
// (MB/GB округляются грубо и выглядят «замершими»).
function formatKb(b: number): string {
  return `${Math.round(b / 1024).toLocaleString('ru-RU')} ${t('tasks.unitKb')}`
}

function formatDuration(sec: number): string {
  const s = Math.floor(Math.max(0, sec))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const ss = s % 60
  if (h > 0) return `${h}${t('tasks.unitHour')} ${String(m).padStart(2, '0')}${t('tasks.unitMin')}`
  if (m > 0) return `${m}${t('tasks.unitMin')} ${String(ss).padStart(2, '0')}${t('tasks.unitSec')}`
  return `${ss}${t('tasks.unitSec')}`
}

// Прошло с начала задачи: для активной — тикает от nowTick, для завершённой —
// фиксируется по finishedAt (или durationSec).
function taskElapsedSec(t: ActiveTask): number {
  const start = new Date(t.startedAt).getTime()
  if (Number.isNaN(start)) return 0
  const end = (t.done || t.failed)
    ? (t.finishedAt ? new Date(t.finishedAt).getTime() : start + (t.durationSec ?? 0) * 1000)
    : nowTick.value
  return (end - start) / 1000
}

function formatTs(iso: string): string {
  try {
    const d = new Date(iso)
    const hh = String(d.getHours()).padStart(2, '0')
    const mm = String(d.getMinutes()).padStart(2, '0')
    const ss = String(d.getSeconds()).padStart(2, '0')
    const ms = String(d.getMilliseconds()).padStart(3, '0')
    return `${hh}:${mm}:${ss}.${ms}`
  } catch { return '' }
}

async function copyLog(task: ActiveTask) {
  const lines = task.phases.map(p => {
    const src = p.source ? ` ${p.source}` : ''
    return `[${formatTs(p.ts)}]${src} ${p.message}`
  }).join('\n')
  try {
    await navigator.clipboard.writeText(lines)
    toast.add({ severity: 'success', summary: t('tasks.copied'), life: 2000 })
  } catch {
    toast.add({ severity: 'error', summary: t('tasks.copyFailed'), life: 2500 })
  }
}

// Пин консоли к низу: реагируем и на новые строки, и на обновление live-байтов,
// чтобы строка «→ записано …» не уезжала вниз. Прокручиваем только если
// пользователь уже внизу — иначе не мешаем ручному просмотру истории.
watch(
  () => store.tasks.map(t => `${t.phases.length}:${t.bytesWritten}`).join(','),
  () => {
    if (!store.expandedTaskId) return
    nextTick(() => {
      const el = document.querySelector<HTMLElement>(`.console[data-task="${store.expandedTaskId}"]`)
      if (!el) return
      if (el.scrollHeight - el.scrollTop - el.clientHeight < 48) el.scrollTop = el.scrollHeight
    })
  }
)
</script>

<style scoped>
.task-float {
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: 1100;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
  pointer-events: none;
}

.task-float > * {
  pointer-events: auto;
}

.task-float-panel {
  width: min(420px, calc(100vw - 32px));
  max-height: min(72vh, 560px);
  display: flex;
  flex-direction: column;
  background: #ffffff;
  color: #1e293b;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  box-shadow: 0 12px 40px rgba(15, 23, 42, 0.18);
  overflow: hidden;
}

.task-float-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.task-float.fullscreen {
  position: fixed;
  left: 0;
  top: 0;
  right: 0;
  bottom: 0;
  width: 100vw;
  height: 100vh;
  z-index: 9999;
  padding: 0;
  margin: 0;
  gap: 0;
  align-items: stretch;
  justify-content: stretch;
  background: transparent;
}

.task-float.fullscreen .task-float-panel {
  flex: 1;
  width: 100% !important;
  max-width: none !important;
  height: 100% !important;
  max-height: none !important;
  border-radius: 0;
  border: none;
  box-shadow: none;
}

.task-float.fullscreen .task-float-body {
  flex: 1;
  flex-direction: row;
}

.task-float.fullscreen .task-dock-list {
  width: min(400px, 34vw);
  min-width: 300px;
  max-height: none !important;
  flex: 0 0 auto;
  border-bottom: none;
  border-right: 1px solid #e2e8f0;
}

.task-float.fullscreen .task-detail-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.task-float.fullscreen .console-wrap {
  flex: 1;
  min-height: 0;
}

.task-float.fullscreen .console {
  flex: 1;
  max-height: none !important;
  min-height: 0;
  font-size: 12px;
}

.task-float.fullscreen .task-float-trigger {
  display: none;
}

.task-float.fullscreen .task-float-panel-enter-from,
.task-float.fullscreen .task-float-panel-leave-to {
  transform: none;
}

.task-detail-placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 24px;
  color: #64748b;
  font-size: 14px;
}

.task-float.dark.fullscreen {
  background: transparent;
}

.task-float.dark.fullscreen .task-dock-list {
  border-right-color: #2d3f57;
}

.task-float.dark .task-detail-placeholder {
  color: #94a3b8;
}

.task-float.has-detail .task-float-panel {
  width: min(480px, calc(100vw - 32px));
  max-height: min(80vh, 640px);
}

.task-float.fullscreen.has-detail .task-float-panel {
  width: 100% !important;
  max-width: none !important;
  max-height: none !important;
}

.task-float.fullscreen.has-detail .task-dock-list {
  max-height: none !important;
}

.task-float-panel-enter-active,
.task-float-panel-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
  transform-origin: bottom right;
}

.task-float-panel-enter-from,
.task-float-panel-leave-to {
  opacity: 0;
  transform: translateY(8px) scale(0.98);
}

.task-float-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px 10px 14px;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
}

.task-float-title {
  font-weight: 600;
  font-size: 13px;
  flex-shrink: 0;
}

.task-float-trigger {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  background: #ffffff;
  color: #1e293b;
  box-shadow: 0 4px 18px rgba(15, 23, 42, 0.12);
  cursor: pointer;
  overflow: hidden;
  transition: box-shadow 0.18s ease, border-color 0.18s ease, transform 0.18s ease;
}

.task-float-trigger:hover {
  border-color: #94a3b8;
  box-shadow: 0 6px 22px rgba(15, 23, 42, 0.16);
}

.task-float-trigger.is-active {
  border-color: #fbbf24;
}

.task-float-trigger.is-failed {
  border-color: #f87171;
}

.task-float-trigger-icon {
  font-size: 14px;
  color: #0369a1;
}

.task-float-trigger-label {
  font-size: 13px;
  font-weight: 600;
}

.task-float-trigger-pct {
  font-size: 12px;
  font-weight: 600;
  color: #0369a1;
  font-variant-numeric: tabular-nums;
}

.task-float-trigger-failed {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 999px;
  background: #fee2e2;
  color: #b91c1c;
  font-size: 11px;
  font-weight: 700;
}

.task-float-trigger-bar {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 3px;
  background: #e2e8f0;
}

.task-float-trigger-fill {
  height: 100%;
  background: linear-gradient(90deg, #0369a1, #38bdf8);
  transition: width 0.35s ease;
}

.dock-meta {
  flex-shrink: 0;
}

.muted-text {
  font-size: 12px;
  color: #64748b;
}

.dock-failed-hint {
  font-size: 12px;
  color: #b91c1c;
  font-weight: 500;
}

.spacer {
  flex: 1;
  min-width: 8px;
}

.task-dock-list {
  flex: 1;
  min-height: 0;
  max-height: min(220px, 28vh);
  overflow-y: auto;
  border-bottom: 1px solid #e2e8f0;
}

.task-float.has-detail .task-dock-list {
  max-height: min(160px, 22vh);
}

.task-compact {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0;
  align-items: stretch;
  border-bottom: 1px solid #f1f5f9;
  background: #ffffff;
}

.task-compact:last-child {
  border-bottom: none;
}

.task-compact.selected {
  background: #f0f9ff;
  box-shadow: inset 3px 0 0 #0369a1;
}

.task-compact-hit {
  display: block;
  width: 100%;
  padding: 10px 12px;
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
  color: inherit;
}

.task-row-top {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.task-badge {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.02em;
  padding: 2px 6px;
  border-radius: 4px;
  text-transform: uppercase;
}

.task-badge.is-active {
  background: #fef9c3;
  color: #a16207;
}

.task-badge.is-done {
  background: #dcfce7;
  color: #15803d;
}

.task-badge.is-failed {
  background: #fee2e2;
  color: #b91c1c;
}

.task-compact-title {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.task-compact-pct {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
  font-variant-numeric: tabular-nums;
}

.task-row-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  min-width: 0;
}

.task-compact-stage {
  flex: 1;
  min-width: 0;
  font-size: 11px;
  color: #64748b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.task-compact-stage i {
  margin-right: 4px;
}

.task-compact.failed .task-compact-stage {
  color: #b91c1c;
}

.task-compact.done .task-compact-stage {
  color: #15803d;
}

.task-compact-bytes {
  flex-shrink: 0;
  font-size: 10px;
  color: #94a3b8;
  font-variant-numeric: tabular-nums;
}

.task-compact-elapsed {
  flex-shrink: 0;
  font-size: 10px;
  color: #94a3b8;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.task-detail-elapsed {
  flex-shrink: 0;
  font-size: 11px;
  color: #64748b;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.task-compact-track {
  margin-top: 6px;
  height: 3px;
  background: #e2e8f0;
  border-radius: 2px;
  overflow: hidden;
}

.task-compact-fill {
  height: 100%;
  background: #0369a1;
  border-radius: 2px;
  transition: width 0.35s ease;
}

.task-compact-fill.done {
  background: #22c55e;
}

.task-compact-fill.failed {
  background: #ef4444;
}

.task-compact-actions {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding-right: 6px;
  flex-shrink: 0;
}

.task-detail-head-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.task-detail-panel {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.task-detail-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid #f1f5f9;
  flex-shrink: 0;
}

.task-detail-title {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.stage-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 8px 12px;
  flex-shrink: 0;
}

.stage-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  padding: 3px 8px;
  border-radius: 999px;
  background: #f1f5f9;
  color: #64748b;
}

.stage-pill.stage-done {
  background: #dcfce7;
  color: #15803d;
}

.stage-pill.stage-active {
  background: #fef9c3;
  color: #a16207;
  font-weight: 600;
}

.stage-pill.stage-failed {
  background: #fee2e2;
  color: #b91c1c;
  font-weight: 600;
}

.console-wrap {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border-top: 1px solid #f1f5f9;
}

.console-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-bottom: 1px solid #f1f5f9;
  flex-shrink: 0;
}

.console {
  flex: 1;
  min-height: 80px;
  max-height: min(200px, 24vh);
  overflow-y: auto;
  padding: 8px 12px;
  font-family: ui-monospace, 'SF Mono', Consolas, monospace;
  font-size: 11px;
  line-height: 1.45;
  background: #0f172a;
  color: #e2e8f0;
}

.console-line {
  display: flex;
  gap: 8px;
  margin-bottom: 2px;
  align-items: flex-start;
}

.console-ts {
  flex-shrink: 0;
  color: #64748b;
}

.console-src {
  flex-shrink: 0;
  color: #38bdf8;
  min-width: 28px;
}

.console-msg {
  flex: 1;
  min-width: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.console-line.level-error .console-msg {
  color: #fca5a5;
}

.console-line.level-bytes .console-msg {
  color: #86efac;
}

.task-float.dark .task-float-panel {
  background: #1c2a3f;
  border-color: #2d3f57;
  color: #e2e8f0;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.45);
}

.task-float.dark .task-float-head {
  border-bottom-color: #2d3f57;
}

.task-float.dark .task-float-trigger {
  background: #1c2a3f;
  border-color: #2d3f57;
  color: #e2e8f0;
  box-shadow: 0 4px 18px rgba(0, 0, 0, 0.35);
}

.task-float.dark .task-float-trigger-icon {
  color: #38bdf8;
}

.task-float.dark .task-float-trigger-pct {
  color: #38bdf8;
}

.task-float.dark .task-dock-list {
  border-bottom-color: #2d3f57;
}

.task-float.dark .task-compact {
  background: #1c2a3f;
  border-bottom-color: #243044;
}

.task-float.dark .task-compact.selected {
  background: rgba(56, 189, 248, 0.08);
  box-shadow: inset 3px 0 0 #38bdf8;
}

.task-float.dark .task-badge.is-active {
  background: rgba(234, 179, 8, 0.12);
  color: #facc15;
}

.task-float.dark .task-badge.is-done {
  background: rgba(34, 197, 94, 0.12);
  color: #4ade80;
}

.task-float.dark .task-badge.is-failed {
  background: rgba(239, 68, 68, 0.12);
  color: #f87171;
}

.task-float.dark .task-compact-title {
  color: #e2e8f0;
}

.task-float.dark .task-compact-stage {
  color: #94a3b8;
}

.task-float.dark .task-compact.done .task-compact-stage {
  color: #4ade80;
}

.task-float.dark .task-compact.failed .task-compact-stage {
  color: #f87171;
}

.task-float.dark .task-compact-pct {
  color: #94a3b8;
}

.task-float.dark .task-compact-track,
.task-float.dark .task-float-trigger-bar {
  background: #243044;
}

.task-float.dark .task-detail-panel {
  border-top-color: #2d3f57;
}

.task-float.dark .stage-pill {
  background: #243044;
  color: #94a3b8;
}

.task-float.dark .stage-pill.stage-done {
  background: rgba(34, 197, 94, 0.12);
  color: #4ade80;
}

.task-float.dark .stage-pill.stage-active {
  background: rgba(234, 179, 8, 0.12);
  color: #facc15;
}

.task-float.dark .stage-pill.stage-failed {
  background: rgba(239, 68, 68, 0.12);
  color: #f87171;
}

.task-float.dark .console-wrap {
  border-top-color: #2d3f57;
}

.task-float.dark .console-toolbar {
  background: #1c2a3f;
  border-bottom-color: #2d3f57;
}

.task-float.dark .muted-text {
  color: #94a3b8;
}

.task-float.dark .dock-failed-hint {
  color: #f87171;
}

@media (prefers-reduced-motion: reduce) {
  .task-compact-fill,
  .task-float-trigger-fill,
  .task-float-panel-enter-active,
  .task-float-panel-leave-active {
    transition: none;
  }
}

@media (max-width: 768px) {
  .task-float {
    right: 12px;
    bottom: 12px;
  }

  .task-compact-bytes {
    display: none;
  }
}
</style>
