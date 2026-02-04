param(
  [string]$PlatformApi = "http://localhost:8080",
  [string]$Gateway = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"

function Assert-Healthy($name, $url) {
  Write-Host "Checking $name -> $url"
  $resp = Invoke-RestMethod -Method Get -Uri $url
  if (-not $resp) { throw "$name health check failed" }
}

function Wait-Run($runId) {
  for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 2
    $state = Invoke-RestMethod -Method Get -Uri "$PlatformApi/runs/$runId"
    if ($state.status -eq "COMPLETED" -or $state.status -eq "FAILED") {
      return $state
    }
  }
  throw "Run timeout: $runId"
}

Write-Host "== Health checks =="
Assert-Healthy "platform-api" "$PlatformApi/health"
Assert-Healthy "gateway" "$Gateway/health"
Assert-Healthy "diff-engine" "http://localhost:8090/health"
Assert-Healthy "gate" "http://localhost:8091/health"
Assert-Healthy "console-web" "http://localhost:5173"
Assert-Healthy "prometheus" "http://localhost:9090/-/ready"
Assert-Healthy "grafana" "http://localhost:3000/api/health"

Write-Host "== Run local replay+perf =="
$output = & powershell -ExecutionPolicy Bypass -File scripts\demo.ps1 -Runners replay,perf 2>&1
$output | ForEach-Object { Write-Host $_ }
$match = ($output | Select-String -Pattern 'Run ID: ([a-f0-9-]+)' | Select-Object -First 1)
if (-not $match) { throw "Run ID not found in demo output" }
$runId = $match.Matches[0].Groups[1].Value
$state = Wait-Run $runId
Write-Host "Run Status: $($state.status), Overall Verdict: $($state.overall_verdict)"

Write-Host "== Metrics check =="
$metrics = Invoke-RestMethod -Method Get -Uri "$PlatformApi/metrics"
$required = @('replay_requests_total', 'replay_errors_total', 'run_error_rate', 'run_latency_ms_bucket', 'run_rps')
foreach ($metric in $required) {
  if ($metrics -notmatch $metric) { throw "Missing metric: $metric" }
}
Write-Host "Metrics OK: $($required -join ', ')"

Write-Host "== Artifacts structure =="
Get-ChildItem -Path artifacts -Directory | Select-Object -First 5 | ForEach-Object {
  Write-Host "- $($_.Name)"
}

Write-Host "Grafana: http://localhost:3000 (admin/admin)"

if ($env:ENABLE_K8S_EXECUTOR -eq "true") {
  Write-Host "== K8s executor check =="
  if (Get-Command kubectl -ErrorAction SilentlyContinue) {
    $runBody = @{
      name = "k8s-run"
      recording_id = "demo"
      baseline_base_url = "http://flashsale-gateway:8000"
      candidate_base_url = "http://flashsale-gateway:8000"
      baseline_version = "v1"
      candidate_version = "v2"
      strict_tolerance = 0.05
      runners = @("replay","perf")
      executor = "k8s"
    } | ConvertTo-Json
    $run = Invoke-RestMethod -Method Post -Uri "$PlatformApi/runs" -Body $runBody -ContentType "application/json"
    $k8sState = Wait-Run $run.id
    Write-Host "K8s Run Status: $($k8sState.status), Overall Verdict: $($k8sState.overall_verdict)"
  } else {
    Write-Host "kubectl not found, skip k8s run."
  }
}

Write-Host "Verify OK."
