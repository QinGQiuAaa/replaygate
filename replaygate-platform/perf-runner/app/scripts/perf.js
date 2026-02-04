import http from 'k6/http'
import { sleep } from 'k6'

const baseUrl = __ENV.TARGET_URL || 'http://flashsale-gateway:8000'
const runId = __ENV.RUN_ID || 'perf'

export default function () {
  const payload = JSON.stringify({ sku: 'SKU-1', qty: 1, user_id: 'perf' })
  const params = {
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': `perf-${runId}-${__VU}-${__ITER}-${Date.now()}`,
    },
  }
  http.post(`${baseUrl}/api/orders`, payload, params)
  sleep(0.5)
}
