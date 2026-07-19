import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import api from '../api/client'
import { useServersStore } from './servers'
import { useHealthStore } from './health'
import { classifyPgError } from '../utils/pgHealth'
import { i18n } from '../i18n'

// Короткий доступ к глобальному i18n внутри store (это .ts-модуль, не компонент).
// Имя `tr`, а не `t`, потому что `t` в этом файле повсеместно занят под ActiveTask.
const tr = (k: string, p?: Record<string, unknown>) => (p ? i18n.global.t(k, p) : i18n.global.t(k))

export interface PhaseLog {
  ts: string
  message: string
  level: 'info' | 'success' | 'error' | 'log'
  source?: string
}

export interface ActiveTask {
  taskId: string
  type: 'backup' | 'restore' | 'scenario' | 'pg_client' | 'structure_sync'
  serverId: number | null
  serverName: string
  database: string
  pgMajor?: number
  pgAction?: 'install' | 'uninstall' | 'refresh'
  stage: string
  phases: PhaseLog[]
  bytesWritten: number
  totalBytes: number | null
  backupFormat: string
  done: boolean
  failed: boolean
  error: string | null
  startedAt: string
  finishedAt: string | null
  durationSec: number | null
  scenarioName?: string
  runId?: number
  backupHistoryId?: number
  /** false — шаг uploading в UI не показываем (S3 не привязан). */
  hasStorage?: boolean
}

const BACKUP_STAGE_LABELS: Record<string, string> = {
  queued: tr('tasks.status.queued'),
  preparing: tr('tasks.status.preparing'),
  dumping: tr('tasks.status.dumping'),
  uploading: tr('tasks.status.uploading'),
  verifying: tr('tasks.status.verifying'),
  completed: tr('tasks.status.completed'),
  failed: tr('tasks.status.failed'),
}

function backupStagesFor(t: ActiveTask): string[] {
  const base = ['queued', 'preparing', 'dumping']
  if (t.hasStorage !== false) base.push('uploading')
  base.push('verifying', 'completed')
  return base
}
const RESTORE_STAGES = ['download', 'restore', 'completed']
const SCENARIO_STAGES = ['backup_source', 'terminate_connections', 'drop_old_db', 'rename_old_db', 'create_target_db', 'prepare_extensions', 'restore', 'done']
const STRUCTURE_SYNC_STAGES = ['backup_test', 'clone_prod', 'build_plan', 'apply_schemas', 'apply_collations', 'apply_extensions', 'apply_foreign', 'apply_types', 'apply_functions_early', 'apply_sequences', 'apply_aggregates', 'apply_new_tables', 'apply_columns', 'apply_indexes', 'apply_constraints', 'apply_rls', 'apply_matviews', 'apply_functions', 'apply_operators', 'apply_views', 'apply_triggers', 'apply_rules', 'apply_event_triggers', 'apply_publications', 'apply_comments', 'apply_grants', 'verify', 'swap', 'done']
const STRUCTURE_SYNC_STEP_LABELS: Record<string, string> = { init: tr('tasks.ssStep.init'), backup_test: tr('tasks.ssStep.backup_test'), clone_prod: tr('tasks.ssStep.clone_prod'), build_plan: tr('tasks.ssStep.build_plan'), dry_run_diff: tr('tasks.ssStep.dry_run_diff'), apply_schemas: tr('tasks.ssStep.apply_schemas'), apply_collations: tr('tasks.ssStep.apply_collations'), apply_extensions: tr('tasks.ssStep.apply_extensions'), apply_foreign: tr('tasks.ssStep.apply_foreign'), apply_types: tr('tasks.ssStep.apply_types'), apply_functions_early: tr('tasks.ssStep.apply_functions_early'), apply_sequences: tr('tasks.ssStep.apply_sequences'), apply_aggregates: tr('tasks.ssStep.apply_aggregates'), apply_new_tables: tr('tasks.ssStep.apply_new_tables'), apply_columns: tr('tasks.ssStep.apply_columns'), apply_indexes: tr('tasks.ssStep.apply_indexes'), apply_constraints: tr('tasks.ssStep.apply_constraints'), apply_rls: tr('tasks.ssStep.apply_rls'), apply_matviews: tr('tasks.ssStep.apply_matviews'), apply_functions: tr('tasks.ssStep.apply_functions'), apply_operators: tr('tasks.ssStep.apply_operators'), apply_views: tr('tasks.ssStep.apply_views'), apply_triggers: tr('tasks.ssStep.apply_triggers'), apply_rules: tr('tasks.ssStep.apply_rules'), apply_event_triggers: tr('tasks.ssStep.apply_event_triggers'), apply_publications: tr('tasks.ssStep.apply_publications'), apply_comments: tr('tasks.ssStep.apply_comments'), apply_grants: tr('tasks.ssStep.apply_grants'), verify: tr('tasks.ssStep.verify'), awaiting_approval: tr('tasks.ssStep.awaiting_approval'), swap: tr('tasks.ssStep.swap'), done: tr('tasks.ssStep.done') }
const PG_CLIENT_STAGES = ['preparing', 'update', 'install', 'verify', 'completed']
const PG_CLIENT_UNINSTALL_STAGES = ['remove', 'verify', 'completed']
const PG_CLIENT_REFRESH_STAGES = ['preparing', 'update', 'scan', 'completed']

const PG_CLIENT_STAGE_LABELS: Record<string, string> = {
  preparing: tr('tasks.pgStep.preparing'),
  update: 'apt update',
  scan: 'apt-cache',
  install: tr('tasks.pgStep.install'),
  remove: tr('tasks.pgStep.remove'),
  verify: tr('tasks.pgStep.verify'),
  completed: tr('tasks.pgStep.completed'),
}

const SCENARIO_STEP_LABELS: Record<string, string> = {
  init: tr('tasks.scStep.init'),
  backup_source: tr('tasks.scStep.backup_source'),
  terminate_connections: tr('tasks.scStep.terminate_connections'),
  drop_old_db: tr('tasks.scStep.drop_old_db'),
  rename_old_db: tr('tasks.scStep.rename_old_db'),
  create_target_db: tr('tasks.scStep.create_target_db'),
  prepare_extensions: tr('tasks.scStep.prepare_extensions'),
  restore: tr('tasks.scStep.restore'),
  done: tr('tasks.scStep.done'),
}

const TASKS_SESSION_KEY = 'pgadmin:tasks:v1'
const TASKS_FINISHED_TTL_MS = 30 * 60 * 1000

function apiAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = {}
  const token = localStorage.getItem('access_token')
  if (token) headers.Authorization = `Bearer ${token}`
  const orgId = localStorage.getItem('active_org_id')
  if (orgId) headers['X-Organization-Id'] = orgId
  return headers
}

export const useTasksStore = defineStore('tasks', () => {
  const tasks = ref<ActiveTask[]>([])
  /** Панель задач открыта (false = только кнопка в углу). */
  const expanded = ref(false)
  const expandedTaskId = ref<string | null>(null)
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  const wsConnected = ref<boolean | null>(null)
  const tasksLoading = ref(true)

  const activeCount = computed(() => tasks.value.filter(t => !t.done && !t.failed).length)
  const failedCount = computed(() => tasks.value.filter(t => t.failed).length)
  const doneCount = computed(() => tasks.value.filter(t => t.done).length)

  function findActive(serverId: number, database: string): ActiveTask | undefined {
    return tasks.value.find(
      t => t.serverId === serverId && t.database === database && !t.done && !t.failed
    )
  }

  function stageIndex(t: ActiveTask): { index: number; total: number } {
    const stages = t.type === 'backup'
      ? backupStagesFor(t)
      : t.type === 'scenario'
        ? SCENARIO_STAGES
        : t.type === 'structure_sync'
          ? STRUCTURE_SYNC_STAGES
        : t.type === 'pg_client'
          ? (t.pgAction === 'uninstall'
            ? PG_CLIENT_UNINSTALL_STAGES
            : t.pgAction === 'refresh'
              ? PG_CLIENT_REFRESH_STAGES
              : PG_CLIENT_STAGES)
          : RESTORE_STAGES
    let idx = stages.indexOf(t.stage)
    if (idx < 0) {
      if (t.done) idx = stages.length
      else idx = 0
    } else {
      idx = idx + 1
    }
    return { index: idx, total: stages.length }
  }

  // Коэффициент сжатия по формату (дамп меньше реального размера БД)
  const COMPRESS_FACTOR: Record<string, number> = {
    custom: 3.5,  // -Fc сжимает примерно в 3-4x
    plain: 0.8,   // SQL больше чем данные
    tar: 1.2,
  }

  function progressPercent(t: ActiveTask): number {
    if (t.done) return 100

    // Во время дампа — byte-based прогресс
    if (!t.failed && t.stage === 'dumping' && t.totalBytes && t.totalBytes > 0 && t.bytesWritten > 0) {
      const factor = COMPRESS_FACTOR[(t as any).backupFormat || 'custom'] ?? 3.5
      const expectedDumpSize = t.totalBytes / factor
      const bytePct = Math.min(t.bytesWritten / expectedDumpSize, 1)
      return Math.round(20 + bytePct * 55)
    }

    const { index, total } = stageIndex(t)
    const pct = Math.round((index / total) * 100)
    if (t.failed) return Math.max(pct, 5)
    return pct
  }

  function upsertTask(task: ActiveTask) {
    const idx = tasks.value.findIndex(t => t.taskId === task.taskId)
    if (idx === -1) {
      tasks.value.unshift(task)
      return
    }
    const cur = tasks.value[idx]
    if (cur.phases.length >= task.phases.length) {
      tasks.value[idx] = { ...cur, ...task, phases: cur.phases }
    } else {
      tasks.value[idx] = task
    }
  }

  function loadTasksFromSession() {
    try {
      const raw = sessionStorage.getItem(TASKS_SESSION_KEY)
      if (!raw) return
      const parsed = JSON.parse(raw) as { savedAt: number; items: ActiveTask[] }
      const now = Date.now()
      for (const t of parsed.items || []) {
        if (!t?.taskId) continue
        if (!t.done && !t.failed) {
          upsertTask(t)
          continue
        }
        const finishedAt = t.finishedAt ? new Date(t.finishedAt).getTime() : 0
        if (finishedAt && now - finishedAt < TASKS_FINISHED_TTL_MS) {
          upsertTask(t)
        } else if (!finishedAt && now - parsed.savedAt < TASKS_FINISHED_TTL_MS) {
          upsertTask(t)
        }
      }
    } catch { /* ignore corrupt session */ }
  }

  function saveTasksToSession() {
    try {
      sessionStorage.setItem(TASKS_SESSION_KEY, JSON.stringify({
        savedAt: Date.now(),
        items: tasks.value.slice(0, 25),
      }))
    } catch { /* quota / private mode */ }
  }

  watch(tasks, saveTasksToSession, { deep: true })

  function findOrCreate(taskId: string, type: ActiveTask['type'], data: any): ActiveTask {
    let task = tasks.value.find(t => t.taskId === taskId)
    if (!task) {
      const major = data.major ?? null
      task = {
        taskId, type,
        serverId: data.server_id ?? null,
        serverName: type === 'pg_client' ? 'PGDG' : (data.server_name || `Server #${data.server_id ?? '?'}`),
        database: type === 'pg_client'
          ? (data.action === 'refresh' ? 'PGDG catalog' : `PG client ${major ?? '?'}`)
          : (data.database || ''),
        pgMajor: major ?? undefined,
        pgAction: data.action,
        stage: type === 'pg_client' ? 'preparing' : 'preparing',
        phases: [],
        bytesWritten: 0,
        totalBytes: null,
        backupFormat: data.backup_format || 'custom',
        done: false, failed: false, error: null,
        startedAt: new Date().toISOString(),
        finishedAt: null,
        durationSec: null,
      }
      tasks.value.unshift(task)
    } else {
      if (data.server_id != null) task.serverId = data.server_id
      if (data.server_name) task.serverName = data.server_name
    }
    return task
  }

  function addPhase(t: ActiveTask, message: string, level: PhaseLog['level'] = 'info', source?: string) {
    t.phases.push({
      ts: new Date().toISOString(),
      message,
      level,
      source,
    })
    if (t.phases.length > 1000) t.phases.splice(0, t.phases.length - 1000)
  }

  // Обновляем bytesWritten только реальным положительным значением: промежуточные
  // события с 0/пустым не сбрасывают прогресс (иначе live-строка мигает, а цифра
  // на гигабайтах выглядит замершей).
  function setBytes(t: ActiveTask, v: unknown) {
    if (typeof v === 'number' && v > 0) t.bytesWritten = v
  }

  function handleMessage(raw: string) {
    try {
      const { type, data } = JSON.parse(raw)
      if (type === 'ping') return

      if (type === 'worker_status') {
        // Статус Celery worker приходит пушем (сервер опрашивает inspect за всех).
        useHealthStore().applyStatus(data)
        return
      }

      if (type === 'backup_started') {
        const t = findOrCreate(data.task_id, 'backup', data)
        t.stage = 'preparing'
        if (data.total_bytes) t.totalBytes = data.total_bytes
        if (data.backup_format) t.backupFormat = data.backup_format
        const sizeHint = data.total_bytes ? tr('tasks.msg.sizeHint', { size: formatBytes(data.total_bytes) }) : ''
        addPhase(t, tr('tasks.msg.backupStarted', { db: t.database, server: t.serverName, hint: sizeHint }), 'info')
      } else if (type === 'backup_progress') {
        const t = findOrCreate(data.task_id, 'backup', data)
        if (data.kind === 'phase') {
          addPhase(t, data.message || data.phase || '...')
        } else if (data.kind === 'stage') {
          t.stage = data.stage
          addPhase(t, `→ ${BACKUP_STAGE_LABELS[data.stage] ?? data.stage}`)
        } else if (data.kind === 'dump_bytes') {
          setBytes(t, data.bytes_written)
        } else if (data.kind === 'log') {
          addPhase(t, data.line || '', data.level || 'log', data.source)
        }
      } else if (type === 'backup_completed') {
        const t = findOrCreate(data.task_id, 'backup', data)
        t.done = true
        t.stage = 'completed'
        t.finishedAt = data.finished_at || new Date().toISOString()
        t.durationSec = data.duration ?? null
        addPhase(t, tr('tasks.msg.backupCompleted', { size: formatBytes(data.size || 0), duration: data.duration || '?' }), 'success')
        scheduleRemove(data.task_id, 60000)
      } else if (type === 'backup_failed') {
        const t = findOrCreate(data.task_id, 'backup', data)
        t.failed = true
        t.error = data.error
        t.stage = 'failed'
        t.finishedAt = data.finished_at || new Date().toISOString()
        addPhase(t, tr('tasks.err.withReason', { error: data.error }), 'error')
        scheduleRemove(data.task_id, 120000)
      } else if (type === 'restore_started') {
        const t = findOrCreate(data.task_id, 'restore', data)
        t.stage = 'download'
        addPhase(t, tr('tasks.msg.restoreStarted', { db: t.database, server: t.serverName }), 'info')
      } else if (type === 'restore_progress') {
        const t = findOrCreate(data.task_id, 'restore', data)
        if (data.kind === 'phase') {
          addPhase(t, data.message || data.phase || '...')
          if (data.phase === 'restore_started') t.stage = 'restore'
        } else if (data.kind === 'log') {
          addPhase(t, data.line || '', data.level || 'log', data.source)
        }
      } else if (type === 'restore_completed') {
        const t = findOrCreate(data.task_id, 'restore', data)
        t.done = true
        t.stage = 'completed'
        addPhase(t, tr('tasks.msg.restoreCompleted'), 'success')
        scheduleRemove(data.task_id, 60000)
      } else if (type === 'restore_failed') {
        const t = findOrCreate(data.task_id, 'restore', data)
        t.failed = true
        t.error = data.error
        addPhase(t, tr('tasks.err.withReason', { error: data.error }), 'error')
        scheduleRemove(data.task_id, 120000)
      } else if (type === 'scenario_started') {
        const t = findOrCreate(data.task_id, 'scenario', {
          ...data,
          server_name: data.scenario_name,
          database: `${data.source_database} → ${data.target_database}`,
        })
        t.scenarioName = data.scenario_name
        t.runId = data.run_id
        t.stage = 'backup_source'
        addPhase(t, tr('tasks.msg.scenarioStarted', { name: data.scenario_name }), 'info')
      } else if (type === 'scenario_step') {
        const t = findOrCreate(data.task_id, 'scenario', data)
        t.stage = data.step
        const label = SCENARIO_STEP_LABELS[data.step] ?? data.step
        addPhase(t, `→ ${label}`, 'info')
      } else if (type === 'scenario_log') {
        const t = findOrCreate(data.task_id, 'scenario', data)
        addPhase(t, data.line || '', data.level || 'log', data.source || undefined)
      } else if (type === 'scenario_bytes') {
        const t = findOrCreate(data.task_id, 'scenario', data)
        setBytes(t, data.bytes_written)
      } else if (type === 'scenario_completed') {
        const t = findOrCreate(data.task_id, 'scenario', data)
        t.done = true
        t.stage = 'done'
        t.finishedAt = new Date().toISOString()
        addPhase(t, tr('tasks.msg.scenarioCompleted'), 'success')
        scheduleRemove(data.task_id, 90000)
      } else if (type === 'scenario_failed') {
        const t = findOrCreate(data.task_id, 'scenario', data)
        t.failed = true
        t.error = data.error
        t.stage = 'failed'
        t.finishedAt = new Date().toISOString()
        addPhase(t, tr('tasks.err.withReason', { error: data.error }), 'error')
        scheduleRemove(data.task_id, 120000)
      } else if (type === 'pg_client_started') {
        const t = findOrCreate(data.task_id, 'pg_client', data)
        t.pgMajor = data.major
        t.pgAction = data.action
        t.stage = 'preparing'
        const verb = data.action === 'uninstall'
          ? tr('tasks.verb.uninstall')
          : data.action === 'refresh'
            ? tr('tasks.verb.refresh')
            : tr('tasks.verb.install')
        const target = data.action === 'refresh'
          ? tr('tasks.verb.packageList')
          : `postgresql-client-${data.major}`
        addPhase(t, tr('tasks.msg.pgClientStarted', { verb, target }), 'info')
      } else if (type === 'pg_client_progress') {
        const t = findOrCreate(data.task_id, 'pg_client', data)
        if (data.kind === 'stage') {
          t.stage = data.stage || t.stage
          if (data.message) addPhase(t, data.message, 'info')
        } else if (data.kind === 'log') {
          addPhase(t, data.line || '', data.level || 'log', data.source)
        }
      } else if (type === 'pg_client_completed') {
        const t = findOrCreate(data.task_id, 'pg_client', data)
        t.done = true
        t.stage = 'completed'
        t.finishedAt = data.finished_at || new Date().toISOString()
        addPhase(t, data.message || tr('tasks.msg.ready'), 'success')
        scheduleRemove(data.task_id, 90000)
      } else if (type === 'pg_client_failed') {
        const t = findOrCreate(data.task_id, 'pg_client', data)
        t.failed = true
        t.error = data.error
        if (t.stage === 'preparing' || t.stage === 'failed') t.stage = 'install'
        t.finishedAt = data.finished_at || new Date().toISOString()
        addPhase(t, tr('tasks.err.withReason', { error: data.error }), 'error')
        scheduleRemove(data.task_id, 120000)
      } else if (type === 'structure_sync_started') {
        const t = findOrCreate(data.task_id, 'structure_sync', { ...data, server_name: data.scenario_name, database: data.scenario_name })
        t.scenarioName = data.scenario_name
        t.runId = data.run_id
        t.stage = 'backup_test'
        addPhase(t, tr('tasks.msg.structureSyncStarted', { name: data.scenario_name }), 'info')
      } else if (type === 'structure_sync_step') {
        const t = findOrCreate(data.task_id, 'structure_sync', data)
        t.stage = data.step
        addPhase(t, `→ ${STRUCTURE_SYNC_STEP_LABELS[data.step] ?? data.step}`, 'info')
      } else if (type === 'structure_sync_log') {
        const t = findOrCreate(data.task_id, 'structure_sync', data)
        addPhase(t, data.line || '', data.level || 'log', data.source || undefined)
      } else if (type === 'structure_sync_bytes') {
        const t = findOrCreate(data.task_id, 'structure_sync', data)
        setBytes(t, data.bytes_written)
      } else if (type === 'structure_sync_total') {
        const t = findOrCreate(data.task_id, 'structure_sync', data)
        if (data.total_bytes) t.totalBytes = data.total_bytes
      } else if (type === 'structure_sync_awaiting_approval') {
        const t = findOrCreate(data.task_id, 'structure_sync', data)
        t.stage = 'swap'
        addPhase(t, tr('tasks.msg.awaitingSwap', { temp: data.temp_db }), 'info')
      } else if (type === 'structure_sync_completed') {
        const t = findOrCreate(data.task_id, 'structure_sync', data)
        t.done = true
        t.stage = 'done'
        t.finishedAt = new Date().toISOString()
        addPhase(t, data.status === 'dry_run' ? tr('tasks.msg.dryRunDone') : tr('tasks.msg.migrationCompleted'), 'success')
        scheduleRemove(data.task_id, 90000)
      } else if (type === 'structure_sync_failed') {
        const t = findOrCreate(data.task_id, 'structure_sync', data)
        t.failed = true
        t.error = data.error
        t.stage = 'failed'
        t.finishedAt = new Date().toISOString()
        addPhase(t, tr('tasks.err.withReason', { error: data.error }), 'error')
        scheduleRemove(data.task_id, 120000)
      } else if (type === 'server_health_update') {
        const serversStore = useServersStore()
        const sid = data.server_id as number
        const idx = serversStore.servers.findIndex(s => s.id === sid)
        if (idx !== -1) {
          const hint = data.health_error ? classifyPgError(data.health_error) : null
          serversStore.servers[idx] = {
            ...serversStore.servers[idx],
            health_status: data.health_status ?? serversStore.servers[idx].health_status,
            health_error: data.health_error ?? null,
            health_error_code: hint?.code ?? null,
            health_error_title: hint?.title ?? null,
            health_error_hint: hint?.hint ?? null,
            health_fail_count: data.health_fail_count ?? serversStore.servers[idx].health_fail_count,
            health_checked_at: data.health_checked_at ?? serversStore.servers[idx].health_checked_at,
          }
        }
      }
    } catch { /* ignore malformed */ }
  }

  const removeTimers = new Map<string, ReturnType<typeof setTimeout>>()
  function scheduleRemove(taskId: string, ms: number) {
    const prev = removeTimers.get(taskId)
    if (prev) clearTimeout(prev)
    removeTimers.set(taskId, setTimeout(() => remove(taskId), ms))
  }

  function remove(taskId: string) {
    tasks.value = tasks.value.filter(t => t.taskId !== taskId)
    if (expandedTaskId.value === taskId) expandedTaskId.value = null
    removeTimers.delete(taskId)
  }

  function dismissTask(taskId: string) {
    remove(taskId)
  }

  function clearDone() {
    tasks.value = tasks.value.filter(t => !t.done)
    if (expandedTaskId.value && !tasks.value.some(t => t.taskId === expandedTaskId.value)) {
      expandedTaskId.value = null
    }
  }

  function clearFailed() {
    tasks.value = tasks.value.filter(t => !t.failed)
    if (expandedTaskId.value && !tasks.value.some(t => t.taskId === expandedTaskId.value)) {
      expandedTaskId.value = null
    }
  }

  function clearAll() {
    for (const id of removeTimers.keys()) {
      const prev = removeTimers.get(id)
      if (prev) clearTimeout(prev)
    }
    removeTimers.clear()
    tasks.value = []
    expandedTaskId.value = null
  }

  function canCancelTask(t: ActiveTask): boolean {
    if (t.done || t.failed) return false
    if (t.type === 'backup' || t.type === 'restore') return true
    if (t.type === 'scenario') return Boolean(t.runId)
    // stage === 'swap' — идёт свап имён БД (или ожидание approve): не отменяем.
    if (t.type === 'structure_sync') return Boolean(t.runId) && t.stage !== 'swap'
    return false
  }

  async function cancelTask(taskId: string) {
    const t = tasks.value.find(x => x.taskId === taskId)
    try {
      if (t?.type === 'backup' || t?.type === 'restore') {
        await api.post(`/backups/task/${taskId}/cancel`)
      } else if (t?.type === 'scenario' && t.runId) {
        await api.post(`/scenarios/runs/${t.runId}/stop`)
      } else if (t?.type === 'structure_sync' && t.runId) {
        await api.post(`/structure-sync/runs/${t.runId}/stop`)
      }
      remove(taskId)  // убираем карточку ТОЛЬКО при успешной отмене
    } catch (e: any) {
      // Отмена не удалась — НЕ убираем карточку (задача, возможно, ещё выполняется),
      // фиксируем причину, чтобы «отменил» не оказалось ложью.
      if (t) {
        addPhase(t, tr('tasks.msg.cancelFailed', { reason: e?.response?.data?.detail || e?.message || tr('tasks.err.error') }), 'error')
      }
      console.error('cancelTask failed', e)
    }
  }

  async function checkStaleTasks() {
    const now = Date.now()
    for (const t of tasks.value) {
      if (t.done || t.failed) continue
      const ageMs = now - new Date(t.startedAt).getTime()
      if (ageMs < 90_000) continue
      if (t.type !== 'backup' && t.type !== 'restore') continue
      if (t.stage !== 'queued') continue
      try {
        const { data } = await api.get<{ status: string; result?: { error?: string } }>(`/backups/task/${t.taskId}`)
        if (data.status === 'PENDING') {
          t.failed = true
          t.stage = 'failed'
          t.error = tr('tasks.err.notProcessed')
          t.finishedAt = new Date().toISOString()
          addPhase(t, t.error, 'error')
        } else if (data.status === 'FAILURE') {
          t.failed = true
          t.stage = 'failed'
          t.error = data.result?.error || tr('tasks.err.executionFailed')
          t.finishedAt = new Date().toISOString()
          addPhase(t, tr('tasks.err.withReason', { error: t.error }), 'error')
        }
      } catch { /* ignore */ }
    }
  }

  function findPgClientTask(major: number): ActiveTask | undefined {
    return tasks.value.find(
      t => t.type === 'pg_client' && t.pgMajor === major && !t.done && !t.failed
    )
  }

  function findPgRepoRefreshTask(): ActiveTask | undefined {
    return tasks.value.find(
      t => t.type === 'pg_client' && t.pgAction === 'refresh' && !t.done && !t.failed
    )
  }

  function seedPgClientTask(taskId: string, major: number, action: 'install' | 'uninstall' | 'refresh') {
    if (tasks.value.find(t => t.taskId === taskId)) return
    const verb = action === 'uninstall'
      ? tr('tasks.verb.uninstall')
      : action === 'refresh'
        ? tr('tasks.verb.refresh')
        : tr('tasks.verb.install')
    const target = action === 'refresh'
      ? tr('tasks.verb.packageList')
      : `postgresql-client-${major}`
    tasks.value.unshift({
      taskId,
      type: 'pg_client',
      serverId: null,
      serverName: 'PGDG',
      database: action === 'refresh' ? 'PGDG catalog' : `PG client ${major}`,
      pgMajor: action === 'refresh' ? undefined : major,
      pgAction: action,
      stage: 'preparing',
      phases: [{
        ts: new Date().toISOString(),
        message: tr('tasks.msg.pgClientQueued', { verb, target }),
        level: 'info',
      }],
      bytesWritten: 0,
      totalBytes: null,
      backupFormat: 'custom',
      done: false,
      failed: false,
      error: null,
      startedAt: new Date().toISOString(),
      finishedAt: null,
      durationSec: null,
    })
  }

  function seedBackupTask(
    taskId: string,
    opts: {
      serverId: number
      serverName: string
      database: string
      backupFormat?: string
      hasStorage?: boolean
    },
  ) {
    if (tasks.value.find(t => t.taskId === taskId)) return
    tasks.value.unshift({
      taskId,
      type: 'backup',
      serverId: opts.serverId,
      serverName: opts.serverName,
      database: opts.database,
      stage: 'queued',
      hasStorage: opts.hasStorage !== false,
      phases: [{
        ts: new Date().toISOString(),
        message: tr('tasks.msg.backupQueued', { db: opts.database }),
        level: 'info',
      }],
      bytesWritten: 0,
      totalBytes: null,
      backupFormat: opts.backupFormat || 'custom',
      done: false,
      failed: false,
      error: null,
      startedAt: new Date().toISOString(),
      finishedAt: null,
      durationSec: null,
    })
  }

  function focusTask(taskId: string) {
    expanded.value = true
    expandedTaskId.value = taskId
  }

  function toggleTask(taskId: string) {
    expandedTaskId.value = expandedTaskId.value === taskId ? null : taskId
  }

  async function syncRunningTasks() {
    const token = localStorage.getItem('access_token')
    if (!token) {
      tasksLoading.value = false
      return
    }

    try {
      const resp = await fetch('/api/backups/running', {
        headers: apiAuthHeaders(),
      })
      if (!resp.ok) return
      const data: any[] = await resp.json()
      for (const r of data) {
        if (!r.task_id) continue
        const existing = tasks.value.find(t => t.taskId === r.task_id)
        if (existing) {
          if (r.stage) existing.stage = r.stage
          if (r.server_name) existing.serverName = r.server_name
          if (r.id) existing.backupHistoryId = r.id
          existing.done = false
          existing.failed = false
        } else {
          upsertTask({
            taskId: r.task_id,
            type: 'backup',
            serverId: r.server_id,
            serverName: r.server_name || `Server #${r.server_id}`,
            database: r.database_name,
            stage: r.stage || 'preparing',
            backupFormat: r.backup_format || 'custom',
            backupHistoryId: r.id,
            phases: [{
              ts: r.started_at || new Date().toISOString(),
              message: tr('tasks.msg.restoredAfterReload'),
              level: 'info',
            }],
            bytesWritten: 0,
            totalBytes: null,
            done: false,
            failed: false,
            error: null,
            startedAt: r.started_at || new Date().toISOString(),
            finishedAt: null,
            durationSec: null,
          })
        }
      }
    } catch { /* ignore network errors */ }
    finally {
      tasksLoading.value = false
    }
  }

  function initTasks() {
    loadTasksFromSession()
    void syncRunningTasks()
    connectWs()
  }

  function wsUrl(): string {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const token = localStorage.getItem('access_token') || ''
    const orgId = localStorage.getItem('active_org_id')
    let url = `${proto}//${location.host}/ws?token=${encodeURIComponent(token)}`
    if (orgId) url += `&org_id=${encodeURIComponent(orgId)}`
    return url
  }

  function connectWs() {
    void syncRunningTasks()
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return
    wsConnected.value = null
    ws = new WebSocket(wsUrl())
    ws.onopen = () => {
      wsConnected.value = true
      void syncRunningTasks()
    }
    ws.onmessage = (e) => handleMessage(e.data)
    ws.onclose = () => {
      wsConnected.value = false
      reconnectTimer = setTimeout(connectWs, 3000)
    }
  }

  function disconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    reconnectTimer = null
    ws?.close()
    ws = null
    wsConnected.value = null
  }

  function reconnectWs() {
    disconnect()
    initTasks()
  }

  let syncPollTimer: ReturnType<typeof setInterval> | null = null

  function startSyncPoll() {
    if (syncPollTimer) return
    syncPollTimer = setInterval(() => {
      // syncRunningTasks/checkStaleTasks реконсилят ТОЛЬКО backup/restore
      // (через /backups/running). Нет смысла дёргать их, когда активна лишь
      // миграция/сценарий — иначе /backups/running крутится вхолостую.
      const hasBackupLike = tasks.value.some(
        t => (t.type === 'backup' || t.type === 'restore') && !t.done && !t.failed
      )
      if (hasBackupLike) {
        void syncRunningTasks()
        void checkStaleTasks()
      }
    }, 4000)
  }

  function stopSyncPoll() {
    if (!syncPollTimer) return
    clearInterval(syncPollTimer)
    syncPollTimer = null
  }

  watch(activeCount, (count) => {
    if (count > 0) startSyncPoll()
    else stopSyncPoll()
  }, { immediate: true })

  function formatBytes(b: number): string {
    if (b < 1024) return `${b} B`
    if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
    if (b < 1024 * 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`
    return `${(b / 1024 / 1024 / 1024).toFixed(2)} GB`
  }

  return {
    tasks, expanded, expandedTaskId, activeCount, failedCount, doneCount,
    wsConnected, tasksLoading,
    connectWs, disconnect, reconnectWs, initTasks, syncRunningTasks, checkStaleTasks,
    cancelTask, dismissTask, clearDone, clearFailed, clearAll, canCancelTask,
    findActive, findPgClientTask, findPgRepoRefreshTask, seedPgClientTask, seedBackupTask, focusTask, toggleTask, remove,
    progressPercent, stageIndex, backupStagesFor,
    SCENARIO_STEP_LABELS, STRUCTURE_SYNC_STEP_LABELS, PG_CLIENT_STAGE_LABELS, BACKUP_STAGE_LABELS,
  }
})
