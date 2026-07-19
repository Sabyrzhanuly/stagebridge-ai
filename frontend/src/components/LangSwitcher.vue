<template>
  <div class="lang-switch" role="group" :aria-label="t('lang.label')">
    <button
      v-for="l in langs"
      :key="l"
      type="button"
      class="lang-btn"
      :class="{ active: current === l }"
      :aria-pressed="current === l"
      @click="pick(l)"
    >{{ code(l) }}</button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { SUPPORTED_LANGS, setLang, type Lang } from '../i18n'

const { locale, t } = useI18n()
const langs = SUPPORTED_LANGS
const current = computed(() => locale.value)

function pick(l: Lang) {
  setLang(l)
}
function code(l: Lang): string {
  return { ru: 'РУС', kk: 'ҚАЗ', en: 'ENG' }[l]
}
</script>

<style scoped>
.lang-switch {
  display: inline-flex;
  gap: 2px;
  padding: 2px;
  border-radius: 8px;
  background: var(--p-content-background, rgba(148, 163, 184, 0.12));
  border: 1px solid var(--p-content-border-color, rgba(148, 163, 184, 0.3));
}
.lang-btn {
  border: none;
  background: transparent;
  color: var(--p-text-muted-color, #8b9bb4);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.03em;
  padding: 4px 9px;
  border-radius: 6px;
  cursor: pointer;
  font-family: inherit;
}
.lang-btn:hover { color: var(--p-text-color, inherit); }
.lang-btn.active {
  background: var(--p-primary-color, #2563eb);
  color: #fff;
}
</style>
