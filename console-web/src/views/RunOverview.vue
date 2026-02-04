<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <div>
          <div class="title">结果总览</div>
          <div class="subtitle">Run ID: {{ run?.id }}</div>
        </div>
        <div class="actions">
          <el-button @click="refresh" :loading="loading">刷新</el-button>
          <el-button type="warning" @click="doCleanup" :loading="cleanupLoading">清理副作用</el-button>
        </div>
      </div>
    </template>

    <div v-if="run">
      <el-descriptions border :column="2">
        <el-descriptions-item label="任务名称">{{ run.name }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ run.status }}</el-descriptions-item>
        <el-descriptions-item label="执行器">{{ run.executor || 'local' }}</el-descriptions-item>
        <el-descriptions-item label="Runners">{{ (run.runners || []).join(', ') }}</el-descriptions-item>
        <el-descriptions-item label="Baseline">{{ run.baseline_version }}</el-descriptions-item>
        <el-descriptions-item label="Candidate">{{ run.candidate_version }}</el-descriptions-item>
        <el-descriptions-item label="Overall Verdict">
          <span data-testid="overview-overall-verdict">
            <el-tag v-if="run.overall_verdict === 'PASS'" type="success">PASS</el-tag>
            <el-tag v-else-if="run.overall_verdict === 'FAIL'" type="danger">FAIL</el-tag>
            <el-tag v-else type="info">N/A</el-tag>
          </span>
        </el-descriptions-item>
        <el-descriptions-item label="Diff率">{{ run.diff_summary?.diff_rate ?? '-' }}</el-descriptions-item>
      </el-descriptions>

      <div class="section">
        <div class="section-title">Runner Results</div>
        <div class="runner-grid">
          <el-card
            v-for="runner in run.runner_results || []"
            :key="runner.name"
            class="runner-card"
            :data-testid="`overview-runner-card-${runner.name}`"
          >
            <div class="runner-header">
              <div class="runner-name">{{ runner.name }}</div>
              <el-tag v-if="runner.verdict === 'PASS'" type="success">PASS</el-tag>
              <el-tag v-else-if="runner.verdict === 'FAIL'" type="danger">FAIL</el-tag>
              <el-tag v-else type="info">N/A</el-tag>
            </div>
            <el-table :data="runner.reasons || []" size="small">
              <el-table-column prop="domain" label="域" width="140" />
              <el-table-column prop="rule_or_metric" label="规则/指标" width="180" />
              <el-table-column prop="observed" label="Observed" />
              <el-table-column prop="threshold" label="Threshold" />
            </el-table>
            <div v-if="runner.artifacts_files?.length" class="artifact-links">
              <el-link
                v-for="file in runner.artifacts_files"
                :key="file"
                :href="apiBase + (artifactMap[file] || '')"
                target="_blank"
                :data-testid="file === 'diff_report.json' ? 'overview-download-diff' : null"
              >
                {{ file }}
              </el-link>
            </div>
          </el-card>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { cleanupRun, getArtifacts, getRun } from '../api'
import type { ArtifactItem, Run } from '../types/api'

const route = useRoute()
const run = ref<Run | null>(null)
const loading = ref(false)
const cleanupLoading = ref(false)
const artifacts = ref<ArtifactItem[]>([])
const artifactMap = ref<Record<string, string>>({})
const apiBase = import.meta.env.VITE_API_BASE || 'http://localhost:8080'

const refresh = async () => {
  loading.value = true
  try {
    run.value = await getRun(String(route.params.id))
    const data = await getArtifacts(String(route.params.id))
    artifacts.value = data.items
    const map: Record<string, string> = {}
    data.items.forEach((item) => {
      if (item.name && item.download_url) map[item.name] = item.download_url
    })
    artifactMap.value = map
  } finally {
    loading.value = false
  }
}

const doCleanup = async () => {
  cleanupLoading.value = true
  try {
    await cleanupRun(String(route.params.id))
  } finally {
    cleanupLoading.value = false
  }
}

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
  margin-bottom: 12px;
}
.runner-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}
.runner-card {
  margin-bottom: 12px;
}
.runner-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.runner-name {
  font-weight: 600;
}
.artifact-links {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}
</style>
