import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from './views/Dashboard.vue'
import RunList from './views/RunList.vue'
import RunCreate from './views/RunCreate.vue'
import RunOverview from './views/RunOverview.vue'
import RunReports from './views/RunReports.vue'
import Settings from './views/Settings.vue'

const routes = [
  { path: '/', component: Dashboard },
  { path: '/runs', component: RunList },
  { path: '/runs/new', component: RunCreate },
  { path: '/runs/:id/overview', component: RunOverview },
  { path: '/runs/:id/reports', component: RunReports },
  { path: '/settings', component: Settings },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
