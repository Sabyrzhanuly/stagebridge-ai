<template>
  <div class="ai-insight">
    <button class="ai-insight-btn" :disabled="loading || !available" @click="run">
      <span class="spark" aria-hidden="true">✦</span>
      <span v-if="loading" class="ai-thinking-loader" :class="{ 'is-static': reducedMotion }" data-testid="ai-thinking-loader" role="status" aria-live="polite">
        <span v-if="!reducedMotion" class="ai-thinking-shimmer" data-testid="ai-thinking-shimmer" aria-hidden="true"></span>
        <span class="ai-thinking-text">{{ activeThinkingPhrase }}</span>
      </span>
      <span v-else>{{ label }}</span>
    </button>
    <span v-if="!available" class="ai-insight-off">{{ t('ai.disabledShort') }}</span>

    <div v-if="error" class="ai-insight-error">{{ error }}</div>

    <div v-if="result" class="ai-insight-card">
      <div class="ai-insight-head">
        <span class="ai-badge" :class="badgeLevel">{{ badgeText }}</span>
        <div class="ai-insight-actions">
          <button type="button" class="ai-export-btn" data-testid="ai-copy" @click="copyMarkdown">
            <i class="fa-solid fa-copy" aria-hidden="true"></i>{{ t('ai.copy') }}
          </button>
          <button v-if="sqlText" type="button" class="ai-export-btn" data-testid="ai-copy-sql" @click="copySql">
            <i class="fa-solid fa-code" aria-hidden="true"></i>{{ t('ai.copySql') }}
          </button>
          <button type="button" class="ai-export-btn" data-testid="ai-download" @click="downloadMarkdown">
            <i class="fa-solid fa-download" aria-hidden="true"></i>{{ t('ai.downloadMd') }}
          </button>
          <button type="button" class="ai-insight-x" @click="clearResult">✕</button>
        </div>
      </div>
      <div v-if="exportMessage" class="ai-export-status">{{ exportMessage }}</div>
      <p v-if="result.summary" class="ai-insight-summary">{{ result.summary }}</p>
      <template v-for="sec in sections" :key="sec.key">
        <div v-if="Array.isArray(result[sec.key]) && result[sec.key].length" class="ai-insight-sec">
          <strong>{{ sec.title }}</strong>
          <ul><li v-for="(item, i) in result[sec.key]" :key="i">{{ item }}</li></ul>
        </div>
      </template>
      <p v-if="result.raw" class="ai-insight-summary">{{ result.summary }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '../api/client'
import { useMediaQuery } from '../composables/useMediaQuery'

const { t, tm, locale } = useI18n()

const props = defineProps<{
  label: string
  endpoint: string
  payload: () => Record<string, unknown>
  sections: Array<{ key: string; title: string }>
  badgeField?: string
  /** запускать анализ сразу при появлении панели (без второго клика) */
  autoRun?: boolean
}>()

const available = ref(false)
const loading = ref(false)
const error = ref('')
const exportMessage = ref('')
const result = ref<Record<string, any> | null>(null)
const reducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)')
const thinkingIndex = ref(0)
let thinkingTimer: ReturnType<typeof setInterval> | null = null

onMounted(async () => {
  try {
    const { data } = await api.get('/ai/status')
    available.value = !!data.available
  } catch {
    available.value = false
  }
  // Клик по строке сразу запускает анализ (родитель пересоздаёт панель через :key).
  if (props.autoRun && available.value && !result.value && !loading.value) run()
})

onBeforeUnmount(() => {
  stopThinkingTimer()
})

const thinkingPhrases = computed(() => {
  const value = tm('ai.thinkingPhrases')
  if (Array.isArray(value)) return value.map((item) => String(item)).filter(Boolean)
  return [t('ai.analyzing')]
})
const activeThinkingPhrase = computed(() => {
  if (reducedMotion.value) return t('ai.thinkingStatic')
  const phrases = thinkingPhrases.value
  return phrases[thinkingIndex.value % phrases.length] || t('ai.analyzing')
})

watch([loading, reducedMotion], ([isLoading, isReduced]) => {
  if (!isLoading || isReduced) {
    thinkingIndex.value = 0
    stopThinkingTimer()
    return
  }
  startThinkingTimer()
})

function startThinkingTimer() {
  if (thinkingTimer || thinkingPhrases.value.length < 2) return
  thinkingTimer = setInterval(() => {
    thinkingIndex.value = (thinkingIndex.value + 1) % thinkingPhrases.value.length
  }, 1500)
}

function stopThinkingTimer() {
  if (!thinkingTimer) return
  clearInterval(thinkingTimer)
  thinkingTimer = null
}

const badgeText = computed(() => {
  const field = props.badgeField || ''
  const v = String(field ? result.value?.[field] || '' : '').toLowerCase()
  const map: Record<string, string> = {
    low: t('ai.riskLow'), medium: t('ai.riskMedium'), high: t('ai.riskHigh'),
    ok: t('ai.statusOk'), warning: t('ai.statusWarning'), critical: t('ai.statusCritical'),
  }
  return map[v] || (field && result.value?.[field] ? String(result.value[field]) : t('ai.badgeDefault'))
})
const badgeLevel = computed(() => {
  const field = props.badgeField || ''
  const v = String(field ? result.value?.[field] || '' : '').toLowerCase()
  if (['high', 'critical'].includes(v)) return 'bad'
  if (['medium', 'warning'].includes(v)) return 'warn'
  return 'ok'
})
const resultMarkdown = computed(() => {
  if (!result.value) return ''
  const lines = [`# ${props.label}`, '']
  lines.push(`**${t('ai.exportBadge')}:** ${badgeText.value}`, '')
  if (result.value.summary) {
    lines.push(String(result.value.summary), '')
  }
  for (const sec of props.sections) {
    const values = result.value[sec.key]
    if (!Array.isArray(values) || !values.length) continue
    lines.push(`## ${sec.title}`)
    for (const item of values) lines.push(`- ${String(item)}`)
    lines.push('')
  }
  if (result.value.raw && result.value.summary) {
    lines.push('```text', String(result.value.summary), '```', '')
  }
  return lines.join('\n').trim() + '\n'
})
const sqlText = computed(() => {
  if (!result.value) return ''
  const items: string[] = []
  for (const sec of props.sections) {
    const values = result.value[sec.key]
    if (!Array.isArray(values) || !values.length) continue
    const sectionLooksSql = /\b(sql|index|indexes|ddl)\b/i.test(`${sec.key} ${sec.title}`)
    for (const item of values) {
      const text = String(item)
      if (sectionLooksSql || /\b(select|with|create\s+(unique\s+)?index|alter|drop|explain)\b/i.test(text)) {
        items.push(text)
      }
    }
  }
  return items.join('\n\n')
})

async function run() {
  loading.value = true
  error.value = ''
  exportMessage.value = ''
  result.value = null
  try {
    const { data } = await api.post(props.endpoint, { ...props.payload(), lang: locale.value })
    result.value = data
  } catch (e: any) {
    error.value = e?.response?.data?.detail || t('ai.requestError')
  } finally {
    loading.value = false
  }
}

function clearResult() {
  result.value = null
  exportMessage.value = ''
}

async function writeClipboard(text: string) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', 'true')
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  document.body.appendChild(textarea)
  textarea.select()
  document.execCommand('copy')
  textarea.remove()
}

async function copyMarkdown() {
  try {
    await writeClipboard(resultMarkdown.value)
    exportMessage.value = t('ai.copied')
  } catch {
    exportMessage.value = t('ai.copyFailed')
  }
}

async function copySql() {
  try {
    await writeClipboard(sqlText.value)
    exportMessage.value = t('ai.copied')
  } catch {
    exportMessage.value = t('ai.copyFailed')
  }
}

function downloadMarkdown() {
  const blob = new Blob([resultMarkdown.value], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'ai-insight.md'
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
  exportMessage.value = t('ai.downloaded')
}
</script>

<style scoped>
.ai-insight { display: flex; flex-direction: column; gap: 10px; margin: 8px 0; }
.ai-insight-btn {
  align-self: flex-start;
  display: inline-flex; align-items: center; gap: 8px;
  padding: 9px 16px; border: none; border-radius: 10px;
  background: linear-gradient(135deg, #2563eb, #0ea5e9); color: #fff;
  font-weight: 600; cursor: pointer;
}
.ai-insight-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.spark { color: #bae6fd; }
.ai-thinking-loader { display: inline-flex; align-items: center; gap: 8px; min-width: 220px; }
.ai-thinking-loader.is-static { min-width: 0; }
.ai-thinking-shimmer {
  width: 34px; height: 7px; border-radius: 999px;
  background: linear-gradient(90deg, rgba(186, 230, 253, 0.25), #fff, rgba(186, 230, 253, 0.25));
  background-size: 200% 100%;
  box-shadow: 0 0 12px rgba(125, 211, 252, 0.55);
  animation: ai-shimmer 1.2s linear infinite;
}
.ai-thinking-text { white-space: nowrap; }
.ai-insight-off { color: #94a3b8; font-size: 0.82rem; }
.ai-insight-error { color: #fb7185; font-size: 0.88rem; }
.ai-insight-card {
  border: 1px solid #1e293b; border-radius: 12px; padding: 14px;
  background: rgba(15, 23, 42, 0.6);
}
.ai-insight-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 8px; }
.ai-insight-actions { display: flex; align-items: center; justify-content: flex-end; flex-wrap: wrap; gap: 6px; }
.ai-insight-x { background: transparent; border: none; color: #64748b; cursor: pointer; }
.ai-export-btn {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 5px 8px; border: 1px solid rgba(125, 211, 252, 0.3); border-radius: 7px;
  background: rgba(15, 23, 42, 0.45); color: #bae6fd;
  font-size: 0.76rem; cursor: pointer;
}
.ai-export-btn:hover { background: rgba(14, 165, 233, 0.14); }
.ai-export-status { color: #7dd3fc; font-size: 0.78rem; margin-bottom: 6px; }
.ai-badge { padding: 3px 12px; border-radius: 999px; font-size: 0.78rem; font-weight: 700; }
.ai-badge.ok { background: rgba(16, 185, 129, 0.2); color: #34d399; }
.ai-badge.warn { background: rgba(245, 158, 11, 0.2); color: #fbbf24; }
.ai-badge.bad { background: rgba(239, 68, 68, 0.2); color: #fb7185; }
.ai-insight-summary { color: #cbd5e1; font-size: 0.92rem; line-height: 1.5; margin: 6px 0; }
.ai-insight-sec { margin-top: 10px; }
.ai-insight-sec strong { color: #7dd3fc; font-size: 0.85rem; }
.ai-insight-sec ul { margin: 6px 0 0; padding-left: 18px; }
.ai-insight-sec li { color: #cbd5e1; font-size: 0.88rem; line-height: 1.5; margin-bottom: 4px; }

@keyframes ai-shimmer {
  from { background-position: 200% 0; }
  to { background-position: -200% 0; }
}

@media (prefers-reduced-motion: reduce) {
  .ai-thinking-shimmer { animation: none; }
}
</style>
