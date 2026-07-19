<template>
  <div class="cron-input-root">
    <div class="cron-input-wrap" :class="{ focused: focusedIdx !== null, invalid: !isValid && modelValue !== '' }">
      <template v-for="(field, i) in FIELDS" :key="i">
        <div class="cron-field">
          <input
            :ref="el => { if (el) inputRefs[i] = el as HTMLInputElement }"
            class="cron-field-input"
            type="text"
            :placeholder="field.placeholder"
            :value="parts[i]"
            autocomplete="off"
            spellcheck="false"
            @input="onInput(i, $event)"
            @keydown="onKeydown(i, $event)"
            @focus="focusedIdx = i"
            @blur="focusedIdx = null"
          />
        </div>
        <span v-if="i < FIELDS.length - 1" class="cron-sep">·</span>
      </template>
    </div>
    <div class="cron-labels">
      <span v-for="(field, i) in FIELDS" :key="i" class="cron-label" :class="{ active: focusedIdx === i }">
        {{ field.label }}
      </span>
    </div>
    <div v-if="hint" class="cron-hint-row">
      <i class="fa-solid fa-circle-info"></i>
      {{ hint }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps<{ modelValue: string }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: string): void }>()

const FIELDS = computed(() => [
  { label: t('cron.min'),       placeholder: '*', max: 59 },
  { label: t('cron.hour'),      placeholder: '*', max: 23 },
  { label: t('cron.day'),       placeholder: '*', max: 31 },
  { label: t('cron.month'),     placeholder: '*', max: 12 },
  { label: t('cron.dayOfWeek'), placeholder: '*', max: 7  },
])

const inputRefs = ref<HTMLInputElement[]>([])
const focusedIdx = ref<number | null>(null)

const parts = computed(() => {
  const p = props.modelValue.trim().split(/\s+/)
  const result = ['', '', '', '', '']
  for (let i = 0; i < 5; i++) result[i] = p[i] ?? ''
  return result
})

const isValid = computed(() => {
  const p = props.modelValue.trim().split(/\s+/)
  return p.length === 5 && p.every(x => x !== '')
})

const hint = computed(() => {
  if (!isValid.value) return ''
  return cronHint(props.modelValue)
})

function emit5(updated: string[]) {
  emit('update:modelValue', updated.join(' '))
}

function onInput(i: number, e: Event) {
  const raw = (e.target as HTMLInputElement).value
  const updated = [...parts.value]

  // Если введён пробел — перейти в следующее поле
  if (raw.endsWith(' ') || raw.includes(' ')) {
    const val = raw.replace(/\s/g, '')
    updated[i] = val
    emit5(updated)
    focusNext(i)
    return
  }

  updated[i] = raw
  emit5(updated)

  // Автопереход: если поле заполнено максимальным числом цифр
  const maxLen = i === 0 || i === 1 ? 2 : i === 2 ? 2 : i === 3 ? 2 : 1
  if (raw.length >= maxLen && raw !== '*') {
    focusNext(i)
  }
}

function onKeydown(i: number, e: KeyboardEvent) {
  const input = inputRefs.value[i]
  if (e.key === 'Backspace' && input?.value === '' && i > 0) {
    focusPrev(i)
  }
  if (e.key === 'ArrowRight' && input?.selectionStart === input?.value.length) {
    focusNext(i)
    e.preventDefault()
  }
  if (e.key === 'ArrowLeft' && input?.selectionStart === 0) {
    focusPrev(i)
    e.preventDefault()
  }
  if (e.key === 'Tab') return // позволяем браузеру управлять Tab
}

function focusNext(i: number) {
  if (i < 4) {
    const next = inputRefs.value[i + 1]
    next?.focus()
    next?.select()
  }
}

function focusPrev(i: number) {
  if (i > 0) {
    const prev = inputRefs.value[i - 1]
    prev?.focus()
    prev?.select()
  }
}

// При изменении modelValue извне — обновить value в DOM вручную
// (т.к. используем :value + @input, а не v-model)
watch(() => props.modelValue, () => {
  const p = props.modelValue.trim().split(/\s+/)
  inputRefs.value.forEach((el, i) => {
    if (el && document.activeElement !== el) {
      el.value = p[i] ?? ''
    }
  })
})

function cronHint(expr: string): string {
  const parts = expr.trim().split(/\s+/)
  if (parts.length !== 5) return ''
  const [min, hour, dom, month, dow] = parts
  if (min === '0' && hour !== '*' && dom === '*' && month === '*' && dow === '*')
    return t('cron.everyDayAt', { time: `${hour.padStart(2, '0')}:00` })
  if (min !== '*' && hour !== '*' && dom === '*' && month === '*' && dow === '*')
    return t('cron.everyDayAt', { time: `${hour.padStart(2, '0')}:${min.padStart(2, '0')}` })
  if (min === '0' && hour === '*') return t('cron.everyHour')
  if (min === '0' && hour.includes(','))
    return t('cron.everyDayAt', { time: hour.split(',').map(h => h.padStart(2, '0') + ':00').join(` ${t('cron.and')} `) })
  if (min === '0' && hour !== '*' && dow !== '*') {
    const days = [t('cron.days.sun'), t('cron.days.mon'), t('cron.days.tue'), t('cron.days.wed'), t('cron.days.thu'), t('cron.days.fri'), t('cron.days.sat')]
    return t('cron.everyWeekdayAt', { day: days[+dow] ?? dow, time: `${hour.padStart(2, '0')}:00` })
  }
  if (hour.startsWith('*/')) return t('cron.everyNHours', { n: hour.slice(2) })
  if (min.startsWith('*/')) return t('cron.everyNMinutes', { n: min.slice(2) })
  return t('cron.raw', { expr })
}
</script>

<style scoped>
.cron-input-root {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cron-input-wrap {
  display: flex;
  align-items: center;
  border: 1px solid var(--p-inputtext-border-color, #d1d5db);
  border-radius: 8px;
  padding: 2px 6px;
  background: var(--p-inputtext-background, #fff);
  transition: border-color 0.15s, box-shadow 0.15s;
  gap: 0;
}
.app-dark .cron-input-wrap {
  background: var(--p-surface-800, #1c2a3f);
  border-color: var(--p-surface-600, #2d3f57);
}
.cron-input-wrap.focused {
  border-color: var(--p-primary-color, #6366f1);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--p-primary-color, #6366f1) 20%, transparent);
}
.cron-input-wrap.invalid {
  border-color: var(--p-red-500, #ef4444);
}

.cron-field {
  flex: 1;
  min-width: 0;
}

.cron-field-input {
  width: 100%;
  border: none;
  outline: none;
  background: transparent;
  text-align: center;
  font-family: ui-monospace, 'SF Mono', Consolas, monospace;
  font-size: 14px;
  color: var(--p-text-color, #111827);
  padding: 6px 2px;
  caret-color: var(--p-primary-color, #6366f1);
}
.app-dark .cron-field-input { color: var(--p-text-color, #e2e8f0); }
.cron-field-input::placeholder { color: var(--p-text-muted-color, #9ca3af); }
.cron-field-input:focus { color: var(--p-primary-color, #6366f1); }

.cron-sep {
  flex-shrink: 0;
  color: var(--p-surface-400, #9ca3af);
  font-size: 16px;
  padding: 0 1px;
  user-select: none;
}

.cron-labels {
  display: flex;
  gap: 0;
}
.cron-label {
  flex: 1;
  text-align: center;
  font-size: 10px;
  font-family: ui-monospace, 'SF Mono', Consolas, monospace;
  color: var(--p-text-muted-color, #9ca3af);
  padding: 1px 0;
  transition: color 0.15s;
}
.cron-label.active { color: var(--p-primary-color, #6366f1); font-weight: 600; }

/* Разделители между labels: учитываем sep */
.cron-labels::after { content: ''; flex: 0 0 16px; }
.cron-labels > :not(:last-child) { margin-right: 6px; }

.cron-hint-row {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 6px 10px;
  border-radius: 7px;
  font-size: 12px;
  background: var(--p-blue-50, #eff6ff);
  color: var(--p-blue-700, #1d4ed8);
  border: 1px solid var(--p-blue-200, #bfdbfe);
}
.app-dark .cron-hint-row {
  background: rgba(56, 189, 248, 0.1);
  color: #7dd3fc;
  border-color: rgba(56, 189, 248, 0.25);
}
</style>
