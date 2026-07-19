import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export type ThemeMode = 'dark' | 'light'

export const useThemeStore = defineStore('theme', () => {
  const stored = (localStorage.getItem('theme') as ThemeMode | null) || 'dark'
  const mode = ref<ThemeMode>(stored)
  const sidebarCollapsed = ref<boolean>(localStorage.getItem('sidebar_collapsed') === 'true')

  function applyMode(m: ThemeMode) {
    const html = document.documentElement
    if (m === 'dark') html.classList.add('app-dark')
    else html.classList.remove('app-dark')
  }

  function setMode(m: ThemeMode) {
    mode.value = m
    localStorage.setItem('theme', m)
    applyMode(m)
  }

  function toggleMode() {
    setMode(mode.value === 'dark' ? 'light' : 'dark')
  }

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
    localStorage.setItem('sidebar_collapsed', String(sidebarCollapsed.value))
  }

  applyMode(mode.value)

  watch(mode, applyMode)

  return { mode, sidebarCollapsed, setMode, toggleMode, toggleSidebar }
})
