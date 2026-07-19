<template>
  <div class="app-shell" :class="{ 'mobile-nav-open': isMobile && mobileNavOpen }">
    <div
      v-if="isMobile && mobileNavOpen"
      class="app-sidebar-backdrop"
      aria-hidden="true"
      @click="closeMobileNav"
    ></div>

    <aside
      class="app-sidebar"
      :class="{ collapsed: !isMobile && themeStore.sidebarCollapsed }"
      :aria-hidden="isMobile && !mobileNavOpen ? true : undefined"
    >
      <div class="app-sidebar-header">
        <div v-if="sidebarLabelsVisible" class="sidebar-brand-wrap">
          <img
            src="/logo_mini.png"
            alt=""
            class="sidebar-brand-icon"
            aria-hidden="true"
          />
          <div class="sidebar-brand-text">
            <span class="sidebar-brand-title">PG Control Center</span>
            <span class="sidebar-brand-sub">Manage · Backup · Monitor</span>
          </div>
        </div>
        <img
          v-else
          src="/logo_mini.png"
          alt="PG Control Center"
          class="sidebar-logo-mini"
        />
      </div>

      <div class="app-sidebar-menu">
        <template v-for="(group, gi) in menuGroups" :key="gi">
          <div v-if="sidebarLabelsVisible && group.title" class="app-menu-section">
            {{ group.title }}
          </div>
          <button
            v-for="item in group.items"
            :key="item.key"
            type="button"
            class="app-menu-item"
            :class="{ active: isActive(item.key) }"
            @click="handleNavigate(item.key)"
            :title="!sidebarLabelsVisible ? item.label : ''"
            :aria-current="isActive(item.key) ? 'page' : undefined"
          >
            <i :class="item.icon" aria-hidden="true"></i>
            <span v-if="sidebarLabelsVisible">{{ item.label }}</span>
            <span v-if="sidebarLabelsVisible && item.badge" class="ml-auto">
              <Badge :value="item.badge" severity="warn" />
            </span>
          </button>
        </template>
      </div>

      <div class="app-sidebar-footer" v-if="sidebarLabelsVisible">
        <button
          type="button"
          class="sidebar-tasks-btn"
          :class="{ active: tasksStore.expanded }"
          :aria-expanded="tasksStore.expanded"
          @click="tasksStore.expanded = !tasksStore.expanded"
        >
          <i class="fa-solid fa-list-check"></i>
          <span class="sidebar-tasks-label">{{ t('nav.tasks') }}</span>
          <span v-if="tasksStore.activeCount > 0" class="sidebar-tasks-badge">{{ tasksStore.activeCount }}</span>
          <span v-else-if="tasksStore.failedCount > 0" class="sidebar-tasks-badge failed">{{ tasksStore.failedCount }}</span>
        </button>
        <div class="sidebar-user">
          <div class="sidebar-user-avatar" aria-hidden="true">{{ userInitials }}</div>
          <div>
            <div class="sidebar-user-name">{{ authStore.user?.username }}</div>
            <div class="sidebar-user-role">{{ roleLabel }}</div>
          </div>
        </div>
      </div>
    </aside>

    <div class="app-main">
      <header class="app-topbar">
        <Button
          text
          rounded
          severity="secondary"
          class="app-nav-toggle"
          @click="toggleNav"
          :aria-label="navToggleLabel"
          :aria-expanded="isMobile ? mobileNavOpen : !themeStore.sidebarCollapsed"
        >
          <i :class="navToggleIcon"></i>
        </Button>

        <div class="app-breadcrumbs">
          <i class="fa-solid fa-house app-breadcrumbs-home" aria-hidden="true"></i>
          <template v-for="(c, i) in breadcrumbs" :key="i">
            <i class="fa-solid fa-chevron-right app-breadcrumbs-sep" aria-hidden="true"></i>
            <span :class="{ 'crumb-current': i === breadcrumbs.length - 1 }">{{ c }}</span>
          </template>
        </div>

        <button
          type="button"
          class="worker-indicator"
          :class="workerIndicatorClass"
          :title="workerIndicatorTitle"
          @click="openTaskPanel"
        >
          <i v-if="healthStore.workerLoading" class="fa-solid fa-spinner fa-spin worker-spinner" aria-hidden="true"></i>
          <span v-else class="worker-dot"></span>
          <span class="worker-label">{{ workerIndicatorLabel }}</span>
          <span v-if="!healthStore.workerLoading && healthStore.workerOnline && healthStore.workerTaskCount > 0" class="worker-jobs">
            {{ healthStore.workerTaskCount }}
          </span>
        </button>

        <LangSwitcher />

        <Button text rounded severity="secondary" @click="themeStore.toggleMode()" :aria-label="themeStore.mode === 'dark' ? t('nav.themeLight') : t('nav.themeDark')">
          <i :class="themeStore.mode === 'dark' ? 'fa-solid fa-sun' : 'fa-solid fa-moon'"></i>
        </Button>

        <Button text rounded severity="secondary" @click="userMenu?.toggle($event)">
          <i class="fa-solid fa-user-circle"></i>
        </Button>
        <Menu ref="userMenu" :model="userMenuItems" popup />
      </header>

      <main class="app-content">
        <div class="page-stack">
          <router-view />
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter, useRoute } from 'vue-router'
import Button from 'primevue/button'
import LangSwitcher from './LangSwitcher.vue'
import Menu from 'primevue/menu'
import Badge from 'primevue/badge'
import { useMediaQuery } from '../composables/useMediaQuery'
import { useAuthStore } from '../stores/auth'
import { useThemeStore } from '../stores/theme'
import { useHealthStore } from '../stores/health'
import { useServersStore } from '../stores/servers'
import { useTasksStore } from '../stores/tasks'
import api from '../api/client'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const themeStore = useThemeStore()
const healthStore = useHealthStore()
const serversStore = useServersStore()
const tasksStore = useTasksStore()
const userMenu = ref<InstanceType<typeof Menu> | null>(null)
const isMobile = useMediaQuery('(max-width: 768px)')
const mobileNavOpen = ref(false)
const orgOptions = ref<{ id: number; name: string }[]>([])
const selectedOrgId = ref<number | null>(authStore.activeOrgId)

const roleLabel = computed(() => {
  if (authStore.isSuperAdmin) return t('nav.superAdmin')
  return authStore.organizationName || authStore.user?.org_role || authStore.user?.role || ''
})

const workerIndicatorTitle = computed(() => {
  if (healthStore.workerLoading) return t('nav.workerChecking')
  if (!healthStore.workerOnline) return t('nav.workerOfflineTitle')
  const n = healthStore.workerTaskCount
  if (n > 0) return t('nav.workerBusyTitle', { count: n })
  return t('nav.workerOnlineTitle')
})

const workerIndicatorLabel = computed(() => {
  if (healthStore.workerLoading) return 'Worker…'
  return healthStore.workerOnline ? 'Worker' : 'Worker offline'
})

const workerIndicatorClass = computed(() => {
  if (healthStore.workerLoading) return 'worker-checking'
  return healthStore.workerOnline ? 'worker-online' : 'worker-offline'
})

function openTaskPanel() {
  tasksStore.expanded = true
}

const sidebarLabelsVisible = computed(() =>
  isMobile.value || !themeStore.sidebarCollapsed
)

const navToggleLabel = computed(() => {
  if (isMobile.value) return mobileNavOpen.value ? t('nav.closeMenu') : t('nav.openMenu')
  return themeStore.sidebarCollapsed ? t('nav.expandMenu') : t('nav.collapseMenu')
})

const navToggleIcon = computed(() => {
  if (isMobile.value && mobileNavOpen.value) return 'fa-solid fa-xmark'
  return 'fa-solid fa-bars'
})

watch(isMobile, (mobile) => {
  if (!mobile) mobileNavOpen.value = false
})

watch(() => route.fullPath, () => {
  mobileNavOpen.value = false
})

watch(mobileNavOpen, (open) => {
  document.documentElement.classList.toggle('mobile-nav-open', open)
})

onUnmounted(() => {
  document.documentElement.classList.remove('mobile-nav-open')
})

function closeMobileNav() {
  mobileNavOpen.value = false
}

function toggleNav() {
  if (isMobile.value) {
    mobileNavOpen.value = !mobileNavOpen.value
  } else {
    themeStore.toggleSidebar()
  }
}

const userInitials = computed(() => {
  const name = authStore.user?.username || '?'
  return name.slice(0, 2).toUpperCase()
})

watch(() => authStore.isSuperAdmin, (v) => {
  if (v) loadOrgOptions()
}, { immediate: true })

onMounted(() => {
  if (!serversStore.servers.length) serversStore.fetchServers()
})

async function loadOrgOptions() {
  try {
    const { data } = await api.get<{ id: number; name: string }[]>('/admin/organizations')
    orgOptions.value = data
    // Single-tenant: супер-админ автоматически работает в единственной организации,
    // переключатель компаний в UI скрыт.
    if (authStore.isSuperAdmin && authStore.activeOrgId == null && data.length) {
      selectedOrgId.value = data[0].id
      await onOrgChange()
    } else {
      selectedOrgId.value = authStore.activeOrgId
    }
  } catch { /* ignore */ }
}

async function onOrgChange() {
  authStore.setActiveOrganizationId(selectedOrgId.value)
  await serversStore.fetchServers()
  tasksStore.reconnectWs()
}

interface MenuItem {
  key: string
  label: string
  icon: string
  badge?: number | string
  permission?: string
}
interface MenuGroup {
  title?: string
  items: MenuItem[]
}

const menuGroups = computed<MenuGroup[]>(() => {
  const groups: MenuGroup[] = [
    {
      items: [
        { key: 'dashboard', label: t('nav.dashboard'), icon: 'fa-solid fa-gauge-high' },
      ],
    },
    {
      title: t('nav.groupManagement'),
      items: [
        { key: 'backups', label: t('nav.backups'), icon: 'fa-solid fa-box-archive', permission: 'run_backup' },
        { key: 'scenarios', label: t('nav.scenarios'), icon: 'fa-solid fa-rotate', permission: 'manage_scenarios' },
        { key: 'audit', label: t('nav.audit'), icon: 'fa-solid fa-clipboard-list', permission: 'view_audit' },
      ],
    },
    {
      title: t('nav.groupSystem'),
      items: [
        { key: 'team', label: t('nav.users'), icon: 'fa-solid fa-users', permission: 'manage_members' },
        { key: 'settings', label: t('nav.settings'), icon: 'fa-solid fa-gear' },
      ],
    },
  ]
  return groups.map(group => ({
    ...group,
    items: group.items.filter(item => !item.permission || authStore.hasPermission(item.permission)),
  })).filter(group => group.items.length > 0)
})

const userMenuItems = computed(() => [
  { label: authStore.user?.username || t('nav.guest'), icon: 'fa-solid fa-user', disabled: true },
  { separator: true },
  { label: t('nav.logout'), icon: 'fa-solid fa-right-from-bracket', command: () => handleLogout() },
])

const breadcrumbs = computed<string[]>(() => {
  const map: Record<string, string> = {
    dashboard: t('nav.dashboard'),
    server: t('nav.overview'),
    roles: t('nav.roles'),
    databases: t('nav.databases'),
    monitoring: t('nav.monitoring'),
    diagnostics: t('nav.diagnostics'),
    backups: t('nav.backups'),
    scenarios: t('nav.scenarios'),
    'structure-sync': t('nav.structureSync'),
    audit: t('nav.audit'),
    team: t('nav.users'),
    admin: t('nav.platform'),
    settings: t('nav.settings'),
  }
  const name = (route.name as string) || ''
  if (!name) return []

  const serverRoutes = ['server', 'roles', 'databases', 'monitoring', 'diagnostics']
  if (serverRoutes.includes(name)) {
    const crumbs = [t('nav.dashboard')]
    const server = serversStore.servers.find(s => s.id === Number(route.params.id))
    if (server) crumbs.push(server.name)
    if (name !== 'server') crumbs.push(map[name] ?? name)
    return crumbs
  }
  return [map[name] || name]
})

function isActive(key: string) {
  if (key === 'dashboard') {
    return ['dashboard', 'server', 'roles', 'databases', 'monitoring', 'diagnostics'].includes(route.name as string)
  }
  return route.name === key
}

function navigate(key: string) {
  router.push({ name: key })
}

function handleNavigate(key: string) {
  navigate(key)
  if (isMobile.value) closeMobileNav()
}

function handleLogout() {
  authStore.logout()
  router.push({ name: 'login' })
}
</script>

<style scoped>
.ml-auto { margin-left: auto; }

.sidebar-logo-mini {
  width: 32px;
  height: 32px;
  object-fit: contain;
}

.worker-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  border: none;
  font: inherit;
}
.worker-jobs {
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: rgba(245, 158, 11, 0.25);
  color: #b45309;
  font-size: 11px;
  line-height: 18px;
  text-align: center;
}
.worker-online {
  background: rgba(34, 197, 94, 0.12);
  color: #16a34a;
}
.worker-offline {
  background: rgba(239, 68, 68, 0.15);
  color: #dc2626;
  animation: pulse-red 1.5s infinite;
}
.worker-checking {
  background: rgba(100, 116, 139, 0.12);
  color: #64748b;
}
.worker-spinner {
  font-size: 11px;
  width: 12px;
  text-align: center;
}
.worker-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}
.worker-online .worker-dot { background: #22c55e; }
.worker-offline .worker-dot { background: #ef4444; }

@keyframes pulse-red {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.super-admin-org-select { min-width: 200px; max-width: 260px; }

@media (max-width: 768px) {
  .worker-label { display: none; }
  .worker-indicator { padding: 4px 8px; }
}

.sidebar-tasks-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  margin-bottom: 10px;
  border: 1px solid var(--p-content-border-color, rgba(148, 163, 184, 0.3));
  border-radius: 10px;
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}
.sidebar-tasks-btn:hover,
.sidebar-tasks-btn.active {
  background: rgba(37, 99, 235, 0.12);
  border-color: rgba(37, 99, 235, 0.5);
}
.sidebar-tasks-btn i { color: #2563eb; }
.sidebar-tasks-label { font-weight: 600; }
.sidebar-tasks-badge {
  margin-left: auto;
  min-width: 20px;
  padding: 1px 7px;
  border-radius: 999px;
  background: #f59e0b;
  color: #fff;
  font-size: 0.75rem;
  font-weight: 700;
  text-align: center;
}
.sidebar-tasks-badge.failed { background: #ef4444; }
</style>
