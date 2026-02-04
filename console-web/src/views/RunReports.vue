<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <div>
          <div class="title">报告与Diff明细</div>
          <div class="subtitle">Run ID: {{ run?.id }}</div>
        </div>
        <div class="actions">
          <el-button @click="refresh" :loading="loading">刷新</el-button>
        </div>
      </div>
    </template>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="Diff" name="diff" data-testid="reports-tab-diff">
        <div v-if="diffReport">
          <el-descriptions border :column="2">
            <el-descriptions-item label="Diff率">{{ diffReport.summary?.diff_rate ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="Strict Mismatches">{{ diffReport.summary?.strict_mismatches ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="Schema Breaking">{{ diffReport.summary?.schema_breaking ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="Strict Tolerance">{{ diffReport.summary?.strict_tolerance_used ?? '-' }}</el-descriptions-item>
          </el-descriptions>
        </div>
        <div v-else class="empty">未生成 diff_report.json</div>
      </el-tab-pane>
      <el-tab-pane label="Perf" name="perf" data-testid="reports-tab-perf">
        <div v-if="perfReport">
          <el-descriptions border :column="2">
            <el-descriptions-item label="Verdict">{{ perfReport.verdict }}</el-descriptions-item>
            <el-descriptions-item label="RPS">{{ perfReport.summary?.rps }}</el-descriptions-item>
            <el-descriptions-item label="P99(ms)">{{ perfReport.summary?.p99_ms }}</el-descriptions-item>
            <el-descriptions-item label="Error Rate(%)">{{ perfReport.summary?.error_rate_pct }}</el-descriptions-item>
          </el-descriptions>
        </div>
        <div v-else class="empty">未生成 perf_report.json</div>
      </el-tab-pane>
      <el-tab-pane label="Security" name="security">
        <div v-if="securityReport">
          <el-descriptions border :column="2">
            <el-descriptions-item label="Verdict">{{ securityReport.verdict }}</el-descriptions-item>
            <el-descriptions-item label="High">{{ securityReport.summary?.high ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="Medium">{{ securityReport.summary?.medium ?? '-' }}</el-descriptions-item>
          </el-descriptions>
        </div>
        <div v-else class="empty">未生成 security_report.json</div>
      </el-tab-pane>
      <el-tab-pane label="Compat" name="compat">
        <div v-if="compatReport">
          <el-descriptions border :column="2">
            <el-descriptions-item label="Verdict">{{ compatReport.verdict }}</el-descriptions-item>
            <el-descriptions-item label="Breaking">{{ compatReport.summary?.breaking_changes ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="Mode">{{ compatReport.summary?.mode ?? '-' }}</el-descriptions-item>
          </el-descriptions>
        </div>
        <div v-else class="empty">未生成 compat_report.json</div>
      </el-tab-pane>
      <el-tab-pane label="Obs" name="obs">
        <div v-if="obsReport">
          <el-descriptions border :column="2">
            <el-descriptions-item label="Verdict">{{ obsReport.verdict }}</el-descriptions-item>
            <el-descriptions-item label="Error Rate(%)">{{ obsReport.summary?.error_rate_pct ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="P99(ms)">{{ obsReport.summary?.p99_ms ?? '-' }}</el-descriptions-item>
          </el-descriptions>
        </div>
        <div v-else class="empty">未生成 obs_report.json</div>
      </el-tab-pane>
    </el-tabs>

    <div v-if="activeReportJson" class="json-view" data-testid="reports-json-view">
      <pre>{{ activeReportJson }}</pre>
    </div>

    <div class="section">
      <div class="section-title">Artifacts</div>
      <el-table :data="artifacts" size="small" v-loading="loading">
        <el-table-column prop="name" label="文件" />
        <el-table-column prop="size_bytes" label="大小(bytes)" width="140" />
        <el-table-column label="下载" width="160">
          <template #default="scope">
            <el-link :href="apiBase + scope.row.download_url" target="_blank">下载</el-link>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getArtifacts, getRun } from '../api'
import type { ArtifactItem, Run } from '../types/api'

const route = useRoute()
const run = ref<Run | null>(null)
const artifacts = ref<ArtifactItem[]>([])
const loading = ref(false)
const apiBase = import.meta.env.VITE_API_BASE || 'http://localhost:8080'
const activeTab = ref('diff')

const diffReport = ref<any>(null)
const perfReport = ref<any>(null)
const securityReport = ref<any>(null)
const compatReport = ref<any>(null)
const obsReport = ref<any>(null)

const loadReport = async (artifactMap: Record<string, string>, name: string) => {
  const url = artifactMap[name]
  if (!url) return null
  const resp = await fetch(apiBase + url)
  if (!resp.ok) return null
  return resp.json()
}

const refresh = async () => {
  loading.value = true
  try {
    run.value = await getRun(String(route.params.id))
    const data = await getArtifacts(String(route.params.id))
    artifacts.value = data.items
    const artifactMap: Record<string, string> = {}
    data.items.forEach((item) => {
      if (item.name && item.download_url) artifactMap[item.name] = item.download_url
    })
    diffReport.value = await loadReport(artifactMap, 'diff_report.json')
    perfReport.value = await loadReport(artifactMap, 'perf_report.json')
    securityReport.value = await loadReport(artifactMap, 'security_report.json')
    compatReport.value = await loadReport(artifactMap, 'compat_report.json')
    obsReport.value = await loadReport(artifactMap, 'obs_report.json')
  } finally {
    loading.value = false
  }
}

const activeReportJson = computed(() => {
  let report: any = null
  switch (activeTab.value) {
    case 'diff':
      report = diffReport.value
      break
    case 'perf':
      report = perfReport.value
      break
    case 'security':
      report = securityReport.value
      break
    case 'compat':
      report = compatReport.value
      break
    case 'obs':
      report = obsReport.value
      break
    default:
      report = null
  }
  if (!report) return ''
  return JSON.stringify(report, null, 2)
})

onMounted(refresh)
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.title {
  font-size: 20px;
  font-weight: 600;
}
.subtitle {
  color: #6b7280;
  margin-top: 4px;
}
.actions {
  display: flex;
  gap: 8px;
}
.section {
  margin-top: 24px;
}
.section-title {
  font-weight: 600;
  margin-bottom: 8px;
}
.empty {
  color: #6b7280;
  padding: 12px 0;
}
.json-view {
  margin-top: 16px;
  padding: 12px;
  background: #111827;
  color: #f9fafb;
  border-radius: 8px;
  max-height: 280px;
  overflow: auto;
  font-size: 12px;
}
</style>
