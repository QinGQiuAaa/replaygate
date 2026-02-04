<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <div>
          <div class="title">任务列表</div>
          <div class="subtitle">分页/筛选运行记录</div>
        </div>
        <div class="actions">
          <el-button type="primary" @click="refresh">刷新</el-button>
          <el-button type="success" @click="$router.push('/runs/new')">创建任务</el-button>
        </div>
      </div>
    </template>

    <el-form class="filters" inline>
      <el-form-item label="Verdict">
        <el-select v-model="filters.verdict" clearable placeholder="ALL" data-testid="runs-filter-verdict">
          <el-option label="PASS" value="PASS" />
          <el-option label="FAIL" value="FAIL" />
        </el-select>
      </el-form-item>
      <el-form-item label="Runner">
        <el-select v-model="filters.runner" clearable placeholder="ALL" data-testid="runs-filter-runner">
          <el-option label="replay" value="replay" />
          <el-option label="perf" value="perf" />
          <el-option label="security" value="security" />
          <el-option label="compat" value="compat" />
          <el-option label="obs" value="obs" />
        </el-select>
      </el-form-item>
      <el-form-item label="时间范围">
        <el-date-picker
          v-model="filters.range"
          type="datetimerange"
          start-placeholder="开始"
          end-placeholder="结束"
          value-format="YYYY-MM-DDTHH:mm:ss"
        />
      </el-form-item>
      <el-form-item>
        <el-button @click="refresh">应用</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="runs" stripe style="width: 100%" v-loading="loading">
      <el-table-column prop="name" label="任务" width="220" />
      <el-table-column prop="status" label="状态" width="130" />
      <el-table-column label="Runners" width="200">
        <template #default="scope">
          <span>{{ (scope.row.runners || []).join(', ') }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" />
      <el-table-column label="结果" width="140">
        <template #default="scope">
          <el-tag v-if="scope.row.overall_verdict === 'PASS'" type="success">PASS</el-tag>
          <el-tag v-else-if="scope.row.overall_verdict === 'FAIL'" type="danger">FAIL</el-tag>
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

    <div class="pagination">
      <el-pagination
        background
        layout="prev, pager, next, sizes, total"
        :total="total"
        :page-size="pageSize"
        :current-page="page"
        @current-change="changePage"
        @size-change="changeSize"
        data-testid="runs-pagination"
      />
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import type { Run } from '../types/api'
import { listRuns } from '../api'
import { useRouter } from 'vue-router'

const runs = ref<Run[]>([])
const loading = ref(false)
const router = useRouter()
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const filters = reactive<{ verdict?: string; runner?: string; range?: string[] | null }>({
  verdict: undefined,
  runner: undefined,
  range: null,
})

const refresh = async () => {
  loading.value = true
  try {
    const params: Record<string, any> = {
      page: page.value,
      page_size: pageSize.value,
    }
    if (filters.verdict) params.verdict = filters.verdict
    if (filters.runner) params.runner = filters.runner
    if (filters.range && filters.range.length === 2) {
      params.since = filters.range[0]
      params.until = filters.range[1]
    }
    const data = await listRuns(params)
    runs.value = data.items
    total.value = data.total || data.items.length
  } finally {
    loading.value = false
  }
}

const changePage = (val: number) => {
  page.value = val
  refresh()
}

const changeSize = (val: number) => {
  pageSize.value = val
  page.value = 1
  refresh()
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
.filters {
  margin-bottom: 16px;
}
.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
