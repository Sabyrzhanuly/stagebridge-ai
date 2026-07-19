import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('../views/LoginView.vue'), meta: { public: true } },
    { path: '/', name: 'dashboard', component: () => import('../views/DashboardView.vue') },
    { path: '/servers/:id', name: 'server', component: () => import('../views/ServerView.vue'), props: true },
    { path: '/servers/:id/roles', name: 'roles', component: () => import('../views/RolesView.vue'), props: true },
    { path: '/servers/:id/databases', name: 'databases', component: () => import('../views/DatabasesView.vue'), props: true },
    { path: '/servers/:id/monitoring', name: 'monitoring', component: () => import('../views/MonitoringView.vue'), props: true },
    { path: '/servers/:id/diagnostics', name: 'diagnostics', component: () => import('../views/DiagnosticsView.vue'), props: true },
    { path: '/servers/:id/pg-config', name: 'pg-config', component: () => import('../views/PgConfigView.vue'), props: true },
    { path: '/backups', name: 'backups', component: () => import('../views/BackupsView.vue') },
    { path: '/scenarios', name: 'scenarios', component: () => import('../views/ScenariosHubView.vue') },
    { path: '/structure-sync', name: 'structure-sync', redirect: '/scenarios?tab=structure' },
    { path: '/audit', name: 'audit', component: () => import('../views/AuditView.vue') },
    { path: '/team', name: 'team', component: () => import('../views/TeamView.vue') },
    { path: '/admin', name: 'admin', component: () => import('../views/AdminView.vue') },
    { path: '/settings', name: 'settings', component: () => import('../views/SettingsView.vue') },
    { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('../views/NotFoundView.vue') },
  ],
})

router.beforeEach((to) => {
  if (to.meta.public) return true
  const token = localStorage.getItem('access_token')
  if (!token) return { name: 'login' }
  return true
})

export default router
