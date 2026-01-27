import { createRouter, createWebHistory } from 'vue-router'
import RunList from './views/RunList.vue'
import RunCreate from './views/RunCreate.vue'
import RunOverview from './views/RunOverview.vue'
import RunReports from './views/RunReports.vue'

const routes = [
  { path: '/', component: RunList },
  { path: '/runs/new', component: RunCreate },
  { path: '/runs/:id/overview', component: RunOverview },
  { path: '/runs/:id/reports', component: RunReports },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
