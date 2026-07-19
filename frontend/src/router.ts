import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from './views/DashboardView.vue'
import ConnectionsView from './views/ConnectionsView.vue'
import NewAnalysisView from './views/NewAnalysisView.vue'
import AnalysisDetailView from './views/AnalysisDetailView.vue'
import ScenarioView from './views/ScenarioView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: DashboardView },
    { path: '/scenario', name: 'scenario', component: ScenarioView },
    { path: '/connections', name: 'connections', component: ConnectionsView },
    { path: '/analysis/new', name: 'analysis-new', component: NewAnalysisView },
    { path: '/analysis/:id', name: 'analysis-detail', component: AnalysisDetailView, props: true }
  ]
})

