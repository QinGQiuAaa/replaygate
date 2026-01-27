<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <div>
          <div class="title">任务列表</div>
          <div class="subtitle">回放任务 / 差异检测 / 门禁结果</div>
        </div>
        <div class="actions">
          <el-button type="primary" @click="refresh">刷新</el-button>
          <el-button type="success" @click="$router.push('/runs/new')">创建任务</el-button>
        </div>
      </div>
    </template>
    <el-table :data="runs" stripe style="width: 100%" v-loading="loading">
      <el-table-column prop="name" label="任务" width="220" />
      <el-table-column prop="status" label="状态" width="130" />
      <el-table-column prop="created_at" label="创建时间" />
      <el-table-column label="结果" width="140">
        <template #default="scope">
          <el-tag v-if="scope.row.verdict?.verdict === 'PASS'" type="success">PASS</el-tag>
          <el-tag v-else-if="scope.row.verdict?.verdict === 'FAIL'" type="danger">FAIL</el-tag>
          <el-tag v-else type="info">N/A</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="240">
        <template #default="scope">
          <el-button size="small" @click="goOverview(scope.row.id)">结果总览</el-button>
          <el-button size="small" @click="goReports(scope.row.id)">报告</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { Run } from '../types/api'
import { listRuns } from '../api'
import { useRouter } from 'vue-router'

const runs = ref<Run[]>([])
const loading = ref(false)
const router = useRouter()

const refresh = async () => {
  loading.value = true
  try {
    const data = await listRuns()
    runs.value = data.items
  } finally {
    loading.value = false
  }
}

const goOverview = (id?: string) => {
  if (id) router.push(`/runs/${id}/overview`)
}
const goReports = (id?: string) => {
  if (id) router.push(`/runs/${id}/reports`)
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
</style>
