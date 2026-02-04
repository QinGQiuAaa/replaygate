<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <div>
          <div class="title">Create Run</div>
          <div class="subtitle">Configure runners, thresholds, and executor</div>
        </div>
      </div>
    </template>
    <el-form ref="formRef" :model="form" :rules="rules" label-width="160px">
      <el-form-item label="Name">
        <el-input v-model="form.name" placeholder="demo-run" />
      </el-form-item>
      <el-form-item label="Recording ID">
        <el-input v-model="form.recording_id" placeholder="demo" />
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
      <el-form-item label="Baseline Run ID">
        <el-input v-model="form.baseline_run_id" placeholder="optional" />
      </el-form-item>
      <el-form-item label="Executor" prop="executor">
        <el-select v-model="form.executor" data-testid="create-run-executor">
          <el-option label="local" value="local" />
          <el-option label="k8s" value="k8s" />
        </el-select>
      </el-form-item>
      <el-form-item label="Runners" prop="runners">
        <el-checkbox-group v-model="form.runners">
          <el-checkbox label="replay" data-testid="create-run-runner-replay">replay</el-checkbox>
          <el-checkbox label="perf" data-testid="create-run-runner-perf">perf</el-checkbox>
          <el-checkbox label="security">security</el-checkbox>
          <el-checkbox label="compat">compat</el-checkbox>
          <el-checkbox label="obs">obs</el-checkbox>
          <el-checkbox label="noop">noop</el-checkbox>
        </el-checkbox-group>
      </el-form-item>
      <el-form-item label="Strict Tolerance" prop="strict_tolerance">
        <el-input-number
          v-model="form.strict_tolerance"
          :min="0"
          :step="0.01"
          data-testid="create-run-strict-tolerance"
        />
      </el-form-item>

      <el-collapse>
        <el-collapse-item title="Replay Thresholds" name="replay">
          <el-form-item label="max_diff_rate">
            <el-input-number v-model="form.thresholds.replay.max_diff_rate" :min="0" :step="0.01" />
          </el-form-item>
          <el-form-item label="max_schema_breaking">
            <el-input-number v-model="form.thresholds.replay.max_schema_breaking" :min="0" :step="1" />
          </el-form-item>
          <el-form-item label="max_strict_mismatches">
            <el-input-number v-model="form.thresholds.replay.max_strict_mismatches" :min="0" :step="1" />
          </el-form-item>
        </el-collapse-item>
        <el-collapse-item title="Perf Thresholds" name="perf">
          <el-form-item label="max_error_rate_pct">
            <el-input-number v-model="form.thresholds.perf.max_error_rate_pct" :min="0" :step="0.1" />
          </el-form-item>
          <el-form-item label="max_p99_ms">
            <el-input-number v-model="form.thresholds.perf.max_p99_ms" :min="0" :step="10" />
          </el-form-item>
          <el-form-item label="vus">
            <el-input-number v-model="form.thresholds.perf.vus" :min="1" :step="1" />
          </el-form-item>
          <el-form-item label="duration">
            <el-input v-model="form.thresholds.perf.duration" placeholder="5s" />
          </el-form-item>
        </el-collapse-item>
        <el-collapse-item title="Security Thresholds" name="security">
          <el-form-item label="max_high">
            <el-input-number v-model="form.thresholds.security.max_high" :min="0" :step="1" />
          </el-form-item>
          <el-form-item label="max_medium">
            <el-input-number v-model="form.thresholds.security.max_medium" :min="0" :step="1" />
          </el-form-item>
        </el-collapse-item>
        <el-collapse-item title="Compat Thresholds" name="compat">
          <el-form-item label="max_breaking_changes">
            <el-input-number v-model="form.thresholds.compat.max_breaking_changes" :min="0" :step="1" />
          </el-form-item>
          <el-form-item label="mode">
            <el-select v-model="form.thresholds.compat.mode">
              <el-option label="strict" value="strict" />
              <el-option label="lenient" value="lenient" />
            </el-select>
          </el-form-item>
        </el-collapse-item>
        <el-collapse-item title="Observability Thresholds" name="obs">
          <el-form-item label="max_error_rate_pct">
            <el-input-number v-model="form.thresholds.obs.max_error_rate_pct" :min="0" :step="0.1" />
          </el-form-item>
          <el-form-item label="max_p99_ms">
            <el-input-number v-model="form.thresholds.obs.max_p99_ms" :min="0" :step="10" />
          </el-form-item>
          <el-form-item label="window">
            <el-input v-model="form.thresholds.obs.window" placeholder="run" />
          </el-form-item>
        </el-collapse-item>
      </el-collapse>

      <el-alert
        v-if="form.executor === 'k8s' && !k8sEnabled"
        title="K8s executor is not enabled"
        type="warning"
        show-icon
        :closable="false"
        description="Enable ENABLE_K8S_EXECUTOR=true or switch to local executor."
        class="tip"
      />
      <el-alert
        v-else-if="form.executor === 'k8s'"
        title="K8s executor tips"
        type="info"
        show-icon
        :closable="false"
        description="When using kind + local compose, consider http://host.docker.internal:8000 as Base URL."
        class="tip"
      />

      <el-form-item>
        <el-button
          type="primary"
          @click="submit"
          :loading="loading"
          data-testid="create-run-submit"
        >
          Create & Start
        </el-button>
        <el-button @click="$router.push('/runs')">Back</el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { createRun, getSettings } from '../api'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

const router = useRouter()
const loading = ref(false)
const formRef = ref<FormInstance>()
const k8sEnabled = ref(false)

const rules: FormRules = {
  runners: [{ type: 'array', required: true, message: 'Select at least one runner', trigger: 'change' }],
  strict_tolerance: [
    { required: true, message: 'Strict tolerance is required', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        const num = Number(value)
        if (!Number.isFinite(num)) {
          callback(new Error('Strict tolerance must be a number'))
          return
        }
        if (num < 0 || num > 1) {
          callback(new Error('Strict tolerance must be between 0 and 1'))
          return
        }
        callback()
      },
      trigger: 'blur',
    },
  ],
  executor: [{ required: true, message: 'Executor is required', trigger: 'change' }],
}

const form = reactive({
  name: 'demo-run',
  recording_id: 'demo',
  baseline_base_url: 'http://flashsale-gateway:8000',
  candidate_base_url: 'http://flashsale-gateway:8000',
  baseline_version: 'v1',
  candidate_version: 'v2',
  baseline_run_id: '',
  executor: 'local',
  runners: ['replay'],
  strict_tolerance: 0.05,
  thresholds: {
    replay: {
      max_diff_rate: 0.05,
      max_schema_breaking: 0,
      max_strict_mismatches: 0,
    },
    perf: {
      max_error_rate_pct: 0.5,
      max_p99_ms: 500,
      vus: 5,
      duration: '5s',
    },
    security: {
      max_high: 0,
      max_medium: 0,
    },
    compat: {
      max_breaking_changes: 0,
      mode: 'strict',
    },
    obs: {
      max_error_rate_pct: 0.5,
      max_p99_ms: 500,
      window: 'run',
    },
  },
})

const loadSettings = async () => {
  try {
    const settings = await getSettings()
    k8sEnabled.value = Boolean(settings.env?.k8s_enabled)
  } catch (error) {
    k8sEnabled.value = false
  }
}

const submit = async () => {
  const formEl = formRef.value
  if (!formEl) return
  const valid = await formEl.validate().catch(() => false)
  if (!valid) return
  if (form.executor === 'k8s' && !k8sEnabled.value) {
    ElMessage.warning('K8s executor is not enabled')
    return
  }
  loading.value = true
  try {
    const run = await createRun({
      name: form.name,
      recording_id: form.recording_id,
      baseline_base_url: form.baseline_base_url,
      candidate_base_url: form.candidate_base_url,
      baseline_version: form.baseline_version,
      candidate_version: form.candidate_version,
      baseline_run_id: form.baseline_run_id || undefined,
      executor: form.executor,
      runners: form.runners,
      strict_tolerance: form.strict_tolerance,
      thresholds: form.thresholds,
    })
    router.push(`/runs/${run.id}/overview`)
  } finally {
    loading.value = false
  }
}

onMounted(loadSettings)
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
.tip {
  margin-top: 16px;
}
</style>
