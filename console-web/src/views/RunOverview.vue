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
        <el-descriptions-item label="Baseline">{{ run.baseline_version }}</el-descriptions-item>
        <el-descriptions-item label="Candidate">{{ run.candidate_version }}</el-descriptions-item>
        <el-descriptions-item label="Verdict">
          <el-tag v-if="run.verdict?.verdict === 'PASS'" type="success">PASS</el-tag>
          <el-tag v-else-if="run.verdict?.verdict === 'FAIL'" type="danger">FAIL</el-tag>
          <el-tag v-else type="info">N/A</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="Diff率">{{ run.diff_summary?.diff_rate ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="Schema Breaking">{{ run.diff_summary?.schema_breaking ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="Strict Mismatch">{{ run.diff_summary?.strict_mismatches ?? '-' }}</el-descriptions-item>
      </el-descriptions>

      <div class="section">
        <div class="section-title">Fail原因</div>
        <el-table :data="run.verdict?.reasons || []" size="small">
          <el-table-column prop="domain" label="域" width="140" />
          <el-table-column prop="rule_or_metric" label="规则/指标" width="180" />
          <el-table-column prop="observed" label="Observed" />
          <el-table-column prop="threshold" label="Threshold" />
          <el-table-column prop="evidence_link" label="Evidence" />
        </el-table>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { cleanupRun, getRun } from '../api'
import type { Run } from '../types/api'

const route = useRoute()
const run = ref<Run | null>(null)
const loading = ref(false)
const cleanupLoading = ref(false)

const refresh = async () => {
  loading.value = true
  try {
    run.value = await getRun(String(route.params.id))
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
  margin-bottom: 8px;
}
</style>
