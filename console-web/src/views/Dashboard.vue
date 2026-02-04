<template>
  <el-card class="card">
    <template #header>
      <div class="card-header">
        <div>
          <div class="title">Dashboard</div>
          <div class="subtitle">Latest {{ limit }} runs trend</div>
        </div>
        <el-button @click="refresh" :loading="loading">Refresh</el-button>
      </div>
    </template>
    <el-row :gutter="16" data-testid="dash-passfail">
      <el-col :span="8">
        <el-statistic title="PASS" :value="summary.pass ?? 0" />
      </el-col>
      <el-col :span="8">
        <el-statistic title="FAIL" :value="summary.fail ?? 0" />
      </el-col>
      <el-col :span="8">
        <el-statistic title="Runs" :value="metrics.length" />
      </el-col>
    </el-row>
    <div class="chart-grid">
      <div class="chart" ref="chartP99Ref" data-testid="dash-chart-p99"></div>
      <div class="chart" ref="chartRpsRef" data-testid="dash-chart-rps"></div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import * as echarts from 'echarts'
import { listRunMetrics } from '../api'
import type { RunMetric } from '../types/api'

const chartP99Ref = ref<HTMLDivElement | null>(null)
const chartRpsRef = ref<HTMLDivElement | null>(null)
let chartP99: echarts.ECharts | null = null
let chartRps: echarts.ECharts | null = null
const metrics = ref<RunMetric[]>([])
const summary = ref<{ pass?: number; fail?: number }>({})
const loading = ref(false)
const limit = 20

const renderChart = () => {
  if (!chartP99Ref.value || !chartRpsRef.value) return
  if (!chartP99) {
    chartP99 = echarts.init(chartP99Ref.value)
  }
  if (!chartRps) {
    chartRps = echarts.init(chartRpsRef.value)
  }
  const ordered = [...metrics.value].reverse()
  const labels = ordered.map((item) => item.id?.slice(0, 8) || '-')
  const p99 = ordered.map((item) => item.p99_ms ?? 0)
  const errorRate = ordered.map((item) => item.error_rate_pct ?? 0)
  const rps = ordered.map((item) => item.rps ?? 0)

  chartP99.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['P99(ms)', 'Error Rate(%)'] },
    grid: { left: 40, right: 30, top: 40, bottom: 40 },
    xAxis: { type: 'category', data: labels },
    yAxis: { type: 'value' },
    series: [
      { name: 'P99(ms)', type: 'line', data: p99, smooth: true },
      { name: 'Error Rate(%)', type: 'line', data: errorRate, smooth: true },
    ],
  })

  chartRps.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['RPS'] },
    grid: { left: 40, right: 30, top: 40, bottom: 40 },
    xAxis: { type: 'category', data: labels },
    yAxis: { type: 'value' },
    series: [{ name: 'RPS', type: 'bar', data: rps }],
  })
}

const refresh = async () => {
  loading.value = true
  try {
    const data = await listRunMetrics(limit)
    metrics.value = data.items || []
    summary.value = data.summary || {}
    renderChart()
  } finally {
    loading.value = false
  }
}

const resize = () => {
  chartP99?.resize()
  chartRps?.resize()
}

onMounted(() => {
  refresh()
  window.addEventListener('resize', resize)
})

onUnmounted(() => {
  window.removeEventListener('resize', resize)
  chartP99?.dispose()
  chartRps?.dispose()
  chartP99 = null
  chartRps = null
})
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
.chart {
  width: 100%;
  height: 360px;
}
.chart-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 16px;
  margin-top: 24px;
}
</style>
