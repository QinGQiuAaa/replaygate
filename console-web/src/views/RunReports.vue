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

    <div v-if="run">
      <el-descriptions border :column="2">
        <el-descriptions-item label="Diff率">{{ run.diff_summary?.diff_rate ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="Diff字段数">{{ run.diff_summary?.diff_fields ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="总字段数">{{ run.diff_summary?.total_fields ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="请求数">{{ run.diff_summary?.total_requests ?? '-' }}</el-descriptions-item>
      </el-descriptions>
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
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getArtifacts, getRun } from '../api'
import type { ArtifactItem, Run } from '../types/api'

const route = useRoute()
const run = ref<Run | null>(null)
const artifacts = ref<ArtifactItem[]>([])
const loading = ref(false)
const apiBase = import.meta.env.VITE_API_BASE || 'http://localhost:8080'

const refresh = async () => {
  loading.value = true
  try {
    run.value = await getRun(String(route.params.id))
    const data = await getArtifacts(String(route.params.id))
    artifacts.value = data.items
  } finally {
    loading.value = false
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
