import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface CeleryQueueTask {
  task_id: string
  name: string
  args: unknown[]
  kwargs: Record<string, unknown>
  worker: string
  started?: number | null
}

export interface WorkerStatusPayload {
  online: boolean
  active?: CeleryQueueTask[]
  reserved?: CeleryQueueTask[]
  active_count?: number
  reserved_count?: number
}

// Статус worker приходит ПУШЕМ по WebSocket (сообщение type=worker_status),
// а не клиентским поллингом: сервер делает Celery inspect один раз и рассылает
// всем. Здесь только применяем присланное и следим за «протуханием».
export const useHealthStore = defineStore('health', () => {
  const workerOnline = ref<boolean | null>(null)
  const workerLoading = ref(true)
  const celeryActive = ref<CeleryQueueTask[]>([])
  const celeryReserved = ref<CeleryQueueTask[]>([])
  const activeCount = ref(0)
  const reservedCount = ref(0)

  let lastUpdate = 0
  let watchdog: ReturnType<typeof setInterval> | null = null
  const STALE_MS = 40000   // нет пушей дольше → статус неизвестен (не offline)

  // Счётчик берём из присланных счётчиков: детали задач у не-админа скрыты,
  // а число задач видно всем.
  const workerTaskCount = computed(() => activeCount.value + reservedCount.value)

  function applyStatus(data: WorkerStatusPayload) {
    workerOnline.value = !!data.online
    celeryActive.value = data.active || []
    celeryReserved.value = data.reserved || []
    activeCount.value = data.active_count ?? celeryActive.value.length
    reservedCount.value = data.reserved_count ?? celeryReserved.value.length
    workerLoading.value = false
    lastUpdate = Date.now()
  }

  // Лёгкий локальный таймер (без сети): если пуши пропали — показываем «неизвестно».
  function startWatchdog() {
    if (watchdog) return
    watchdog = setInterval(() => {
      if (lastUpdate && Date.now() - lastUpdate > STALE_MS) {
        workerOnline.value = null
        celeryActive.value = []
        celeryReserved.value = []
        activeCount.value = 0
        reservedCount.value = 0
        workerLoading.value = false
      }
    }, 10000)
  }

  function stopWatchdog() {
    if (watchdog) { clearInterval(watchdog); watchdog = null }
  }

  return {
    workerOnline,
    workerLoading,
    celeryActive,
    celeryReserved,
    workerTaskCount,
    applyStatus,
    startWatchdog,
    stopWatchdog,
  }
})
