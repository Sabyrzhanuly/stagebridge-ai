<template>
  <div class="shell">
    <aside class="sidebar">
      <header class="app-header">
        <RouterLink class="brand" to="/">
          <DatabaseZap class="brand-icon" :size="24" />
          <span>StageBridge AI</span>
        </RouterLink>
        <label class="language-control">
          <Languages :size="16" aria-hidden="true" />
          <span class="sr-only">{{ t('language.label') }}</span>
          <select :value="locale" :aria-label="t('accessibility.languageSwitcher')" @change="changeLocale">
            <option v-for="option in languageOptions" :key="option.code" :value="option.code">
              {{ option.label }}
            </option>
          </select>
        </label>
      </header>
      <nav class="nav">
        <RouterLink to="/"><LayoutDashboard :size="18" />{{ t('navigation.dashboard') }}</RouterLink>
        <RouterLink to="/scenario" class="nav-highlight"><GitBranch :size="18" />{{ t('navigation.scenario') }}</RouterLink>
        <RouterLink to="/connections"><Cable :size="18" />{{ t('navigation.connections') }}</RouterLink>
        <RouterLink to="/analysis/new"><PlayCircle :size="18" />{{ t('navigation.newAnalysis') }}</RouterLink>
      </nav>
    </aside>
    <main class="main">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { Cable, DatabaseZap, GitBranch, Languages, LayoutDashboard, PlayCircle } from '@lucide/vue'
import { useI18n } from 'vue-i18n'
import { setLocale, type AppLocale } from './i18n'

const { locale, t } = useI18n()
const languageOptions: Array<{ code: AppLocale; label: string }> = [
  { code: 'kk', label: 'Қазақша' },
  { code: 'ru', label: 'Русский' },
  { code: 'en', label: 'English' }
]

function changeLocale(event: Event) {
  setLocale((event.target as HTMLSelectElement).value as AppLocale)
}
</script>
