import { ref } from 'vue'

/**
 * Синхронный in-flight guard против двойного клика по «запускающим» кнопкам.
 *
 * Флаг `submitting` поднимается ДО первого await, поэтому закрывает окно между
 * кликом и ответом сервера — когда реактивный `:disabled`, завязанный на данные
 * из ответа/WS, ещё не успел сработать и повторные клики отправляли бы новые
 * запросы (несколько параллельных процессов).
 *
 * Пример:
 *   const { submitting, submit } = useSubmitting()
 *   <Button :loading="submitting" :disabled="submitting" @click="submit(doRun)" />
 */
export function useSubmitting() {
  const submitting = ref(false)

  async function submit<T>(fn: () => Promise<T>): Promise<T | undefined> {
    if (submitting.value) return
    submitting.value = true
    try {
      return await fn()
    } finally {
      submitting.value = false
    }
  }

  return { submitting, submit }
}
