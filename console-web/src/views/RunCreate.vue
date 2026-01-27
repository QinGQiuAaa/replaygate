<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <div>
          <div class="title">创建任务</div>
          <div class="subtitle">指定录制ID与基线/候选版本</div>
        </div>
      </div>
    </template>
    <el-form :model="form" label-width="140px">
      <el-form-item label="任务名称">
        <el-input v-model="form.name" placeholder="例如：demo-run" />
      </el-form-item>
      <el-form-item label="Recording ID">
        <el-input v-model="form.recording_id" placeholder="例如：demo" />
      </el-form-item>
      <el-form-item label="Baseline Base URL">
        <el-input v-model="form.baseline_base_url" placeholder="http://flashsale-gateway:8000" />
      </el-form-item>
      <el-form-item label="Candidate Base URL">
        <el-input v-model="form.candidate_base_url" placeholder="http://flashsale-gateway:8000" />
      </el-form-item>
      <el-form-item label="Baseline Version">
        <el-input v-model="form.baseline_version" placeholder="v1" />
      </el-form-item>
      <el-form-item label="Candidate Version">
        <el-input v-model="form.candidate_version" placeholder="v2" />
      </el-form-item>
      <el-form-item label="最大Diff率">
        <el-input-number v-model="form.max_diff_rate" :min="0" :step="0.01" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="submit" :loading="loading">创建并启动</el-button>
        <el-button @click="$router.push('/')">返回</el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { createRun } from '../api'
import { useRouter } from 'vue-router'

const router = useRouter()
const loading = ref(false)

const form = reactive({
  name: 'demo-run',
  recording_id: 'demo',
  baseline_base_url: 'http://flashsale-gateway:8000',
  candidate_base_url: 'http://flashsale-gateway:8000',
  baseline_version: 'v1',
  candidate_version: 'v2',
  max_diff_rate: 0.05,
})

const submit = async () => {
  loading.value = true
  try {
    const run = await createRun({
      name: form.name,
      recording_id: form.recording_id,
      baseline_base_url: form.baseline_base_url,
      candidate_base_url: form.candidate_base_url,
      baseline_version: form.baseline_version,
      candidate_version: form.candidate_version,
      thresholds: { max_diff_rate: form.max_diff_rate },
    })
    router.push(`/runs/${run.id}/overview`)
  } finally {
    loading.value = false
  }
}
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
</style>
