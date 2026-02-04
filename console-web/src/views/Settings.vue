<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <div>
          <div class="title">Settings</div>
          <div class="subtitle">Default templates and executor</div>
        </div>
        <el-button type="primary" :loading="saving" @click="save" data-testid="settings-save">Save</el-button>
      </div>
    </template>
    <el-form label-width="160px" v-loading="loading">
      <el-form-item label="Default Executor">
        <el-select v-model="form.default_executor" placeholder="local" data-testid="settings-default-executor">
          <el-option label="local" value="local" />
          <el-option label="k8s" value="k8s" />
        </el-select>
      </el-form-item>
      <el-form-item label="Active Template">
        <el-input v-model="form.active_template" placeholder="default" />
      </el-form-item>
      <el-form-item label="Threshold Templates (JSON)">
        <el-input v-model="templatesJson" type="textarea" :rows="10" data-testid="settings-template-json" />
      </el-form-item>
    </el-form>

    <div class="section">
      <div class="section-title">Environment</div>
      <el-descriptions border :column="2">
        <el-descriptions-item label="K8s Enabled">{{ env.k8s_enabled }}</el-descriptions-item>
        <el-descriptions-item label="OTEL Exporter">{{ env.otel_exporter }}</el-descriptions-item>
      </el-descriptions>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { getSettings, updateSettings } from '../api'
import type { SettingsResponse, ThresholdTemplate } from '../types/api'

const loading = ref(false)
const saving = ref(false)
const templatesJson = ref('')
const env = reactive<Record<string, any>>({})
const form = reactive({
  default_executor: 'local',
  active_template: 'default',
})

const load = async () => {
  loading.value = true
  try {
    const data: SettingsResponse = await getSettings()
    form.default_executor = data.default_executor
    form.active_template = data.active_template
    templatesJson.value = JSON.stringify(data.threshold_templates, null, 2)
    Object.assign(env, data.env || {})
  } finally {
    loading.value = false
  }
}

const save = async () => {
  saving.value = true
  try {
    const templates = JSON.parse(templatesJson.value || '[]') as ThresholdTemplate[]
    await updateSettings({
      default_executor: form.default_executor,
      active_template: form.active_template,
      threshold_templates: templates,
    })
    await load()
  } finally {
    saving.value = false
  }
}

onMounted(load)
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
.section {
  margin-top: 24px;
}
.section-title {
  font-weight: 600;
  margin-bottom: 8px;
}
</style>
