<template>
  <div class="ai-insight">
    <button class="ai-insight-btn" :disabled="loading || !available" @click="run">
      <span class="spark">✦</span>
      {{ loading ? t('ai.analyzing') : label }}
    </button>
    <span v-if="!available" class="ai-insight-off">{{ t('ai.disabledShort') }}</span>

    <div v-if="error" class="ai-insight-error">{{ error }}</div>

    <div v-if="result" class="ai-insight-card">
      <div class="ai-insight-head">
        <span class="ai-badge" :class="badgeLevel">{{ badgeText }}</span>
        <button class="ai-insight-x" @click="result = null">✕</button>
      </div>
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
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '../api/client'

const { t, locale } = useI18n()

const props = defineProps<{
  label: string
  endpoint: string
  payload: () => Record<string, unknown>
  sections: Array<{ key: string; title: string }>
  badgeField?: string
}>()

const available = ref(false)
const loading = ref(false)
const error = ref('')
const result = ref<Record<string, any> | null>(null)

onMounted(async () => {
  try {
    const { data } = await api.get('/ai/status')
    available.value = !!data.available
  } catch {
    available.value = false
  }
})

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

async function run() {
  loading.value = true
  error.value = ''
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
.ai-insight-off { color: #94a3b8; font-size: 0.82rem; }
.ai-insight-error { color: #fb7185; font-size: 0.88rem; }
.ai-insight-card {
  border: 1px solid #1e293b; border-radius: 12px; padding: 14px;
  background: rgba(15, 23, 42, 0.6);
}
.ai-insight-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.ai-insight-x { background: transparent; border: none; color: #64748b; cursor: pointer; }
.ai-badge { padding: 3px 12px; border-radius: 999px; font-size: 0.78rem; font-weight: 700; }
.ai-badge.ok { background: rgba(16, 185, 129, 0.2); color: #34d399; }
.ai-badge.warn { background: rgba(245, 158, 11, 0.2); color: #fbbf24; }
.ai-badge.bad { background: rgba(239, 68, 68, 0.2); color: #fb7185; }
.ai-insight-summary { color: #cbd5e1; font-size: 0.92rem; line-height: 1.5; margin: 6px 0; }
.ai-insight-sec { margin-top: 10px; }
.ai-insight-sec strong { color: #7dd3fc; font-size: 0.85rem; }
.ai-insight-sec ul { margin: 6px 0 0; padding-left: 18px; }
.ai-insight-sec li { color: #cbd5e1; font-size: 0.88rem; line-height: 1.5; margin-bottom: 4px; }
</style>
