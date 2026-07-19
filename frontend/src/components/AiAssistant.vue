<template>
  <div class="ai-assistant">
    <button v-if="!open" class="ai-fab" @click="open = true" :title="t('ai.assistantTitle')">
      <span class="ai-fab-icon">✦</span>
      <span class="ai-fab-text">{{ t('ai.fabShort') }}</span>
    </button>

    <div v-else class="ai-panel">
      <header class="ai-header">
        <div class="ai-title"><span class="ai-spark">✦</span> {{ t('ai.assistantTitle') }}</div>
        <button class="ai-close" @click="open = false">✕</button>
      </header>

      <div class="ai-body" ref="bodyEl">
        <i18n-t v-if="!available" keypath="ai.disabled" tag="div" class="ai-note">
          <template #key><code>OPENAI_API_KEY</code></template>
          <template #env><code>.env</code></template>
        </i18n-t>
        <div v-for="(m, i) in messages" :key="i" class="ai-msg" :class="m.role">
          <div class="ai-msg-text">{{ m.text }}</div>
        </div>
        <div v-if="loading" class="ai-msg assistant" data-testid="ai-assistant-typing">
          <div class="ai-msg-text ai-typing" role="status" aria-live="polite">
            <span v-if="reducedMotion" class="ai-typing-static">{{ t('ai.thinkingStatic') }}</span>
            <span v-else class="ai-typing-dots" :aria-label="t('ai.thinkingStatic')" data-testid="ai-typing-dots">
              <span aria-hidden="true"></span>
              <span aria-hidden="true"></span>
              <span aria-hidden="true"></span>
            </span>
          </div>
        </div>
      </div>

      <div class="ai-input">
        <textarea
          v-model="draft"
          :disabled="!available || loading"
          :placeholder="t('ai.placeholder')"
          rows="2"
          @keydown.enter.exact.prevent="send"
        ></textarea>
        <button class="ai-send" :disabled="!available || loading || !draft.trim()" @click="send">▸</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '../api/client'
import { useMediaQuery } from '../composables/useMediaQuery'

const { t, locale } = useI18n()
const open = ref(false)
const available = ref(false)
const loading = ref(false)
const draft = ref('')
const messages = ref<Array<{ role: 'user' | 'assistant'; text: string }>>([])
const bodyEl = ref<HTMLElement | null>(null)
const reducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)')

onMounted(async () => {
  try {
    const { data } = await api.get('/ai/status')
    available.value = !!data.available
  } catch {
    available.value = false
  }
})

async function send() {
  const question = draft.value.trim()
  if (!question || loading.value) return
  messages.value.push({ role: 'user', text: question })
  draft.value = ''
  loading.value = true
  await scrollDown()
  try {
    const { data } = await api.post('/ai/assistant', { question, lang: locale.value })
    messages.value.push({ role: 'assistant', text: data.answer || '—' })
  } catch (e: any) {
    const detail = e?.response?.data?.detail || t('ai.requestError')
    messages.value.push({ role: 'assistant', text: detail })
  } finally {
    loading.value = false
    await scrollDown()
  }
}

async function scrollDown() {
  await nextTick()
  if (bodyEl.value) bodyEl.value.scrollTop = bodyEl.value.scrollHeight
}
</script>

<style scoped>
.ai-fab {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 1200;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 18px;
  border: none;
  border-radius: 999px;
  background: linear-gradient(135deg, #2563eb, #0ea5e9);
  color: #fff;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 8px 24px rgba(14, 165, 233, 0.4);
}
.ai-fab-icon { font-size: 1.1rem; }
.ai-panel {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 1200;
  width: 380px;
  max-width: calc(100vw - 32px);
  height: 520px;
  max-height: calc(100vh - 48px);
  display: flex;
  flex-direction: column;
  background: #0f172a;
  border: 1px solid #1e293b;
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
  overflow: hidden;
}
.ai-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  background: linear-gradient(135deg, #1e3a8a, #0c4a6e);
  color: #fff;
}
.ai-title { font-weight: 700; display: flex; align-items: center; gap: 8px; }
.ai-spark { color: #7dd3fc; }
.ai-close { background: transparent; border: none; color: #cbd5e1; cursor: pointer; font-size: 1rem; }
.ai-body { flex: 1; overflow-y: auto; padding: 14px; display: flex; flex-direction: column; gap: 10px; }
.ai-note { color: #94a3b8; font-size: 0.85rem; line-height: 1.5; }
.ai-note code { background: #1e293b; padding: 1px 6px; border-radius: 5px; color: #7dd3fc; }
.ai-msg { max-width: 85%; padding: 9px 12px; border-radius: 12px; font-size: 0.9rem; line-height: 1.45; white-space: pre-wrap; }
.ai-msg.user { align-self: flex-end; background: #2563eb; color: #fff; border-bottom-right-radius: 3px; }
.ai-msg.assistant { align-self: flex-start; background: #1e293b; color: #e2e8f0; border-bottom-left-radius: 3px; }
.ai-typing { display: inline-flex; align-items: center; min-height: 18px; }
.ai-typing-dots { display: inline-flex; align-items: center; gap: 5px; }
.ai-typing-dots span {
  width: 7px; height: 7px; border-radius: 999px;
  background: #7dd3fc;
  opacity: 0.4;
  animation: ai-dot-pulse 1.2s ease-in-out infinite;
}
.ai-typing-dots span:nth-child(2) { animation-delay: 0.16s; }
.ai-typing-dots span:nth-child(3) { animation-delay: 0.32s; }
.ai-typing-static { color: #cbd5e1; }
.ai-input { display: flex; gap: 8px; padding: 12px; border-top: 1px solid #1e293b; }
.ai-input textarea {
  flex: 1; resize: none; padding: 9px 11px; border-radius: 10px;
  border: 1px solid #334155; background: #0b1220; color: #e2e8f0; font: inherit;
}
.ai-send {
  align-self: flex-end; width: 40px; height: 40px; border: none; border-radius: 10px;
  background: #0ea5e9; color: #fff; font-size: 1.1rem; cursor: pointer;
}
.ai-send:disabled { opacity: 0.4; cursor: not-allowed; }

@keyframes ai-dot-pulse {
  0%, 80%, 100% { opacity: 0.35; transform: translateY(0); }
  40% { opacity: 1; transform: translateY(-2px); }
}

@media (prefers-reduced-motion: reduce) {
  .ai-typing-dots span { animation: none; transform: none; opacity: 0.8; }
}
</style>
