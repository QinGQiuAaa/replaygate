param(
  [double]$StrictTolerance = 0.05
)

$ErrorActionPreference = "Stop"

$platformApi = $env:PLATFORM_API
if (-not $platformApi) { $platformApi = "http://localhost:8080" }
$gateway = $env:GATEWAY_URL
if (-not $gateway) { $gateway = "http://localhost:8000" }

function Wait-For($url) {
  for ($i = 0; $i -lt 30; $i++) {
    try {
      Invoke-RestMethod -Method Get -Uri $url | Out-Null
      return
    } catch {
      Start-Sleep -Seconds 2
    }
  }
  throw "Service not ready: $url"
}

Write-Host "等待平台与网关就绪..."
Wait-For "$platformApi/health"
Wait-For "$gateway/health"

Write-Host "[1/4] 清理录制并生成录制流量..."
Invoke-RestMethod -Method Post -Uri "$gateway/api/recordings/demo/clear" | Out-Null

$orderBody = @{ sku = "SKU-1"; qty = 1; user_id = "u1" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$gateway/api/orders" -Headers @{ "X-Recording-Id" = "demo" } -Body $orderBody -ContentType "application/json" | Out-Null

Write-Host "[2/4] 创建回放任务..."
$runBody = @{
  name = "demo-run"
  recording_id = "demo"
  baseline_base_url = "http://flashsale-gateway:8000"
  candidate_base_url = "http://flashsale-gateway:8000"
  baseline_version = "v1"
  candidate_version = "v2"
  strict_tolerance = $StrictTolerance
} | ConvertTo-Json

$run = Invoke-RestMethod -Method Post -Uri "$platformApi/runs" -Body $runBody -ContentType "application/json"
$runId = $run.id
Write-Host "Run ID: $runId"

Write-Host "[3/4] 等待回放完成..."
for ($i = 0; $i -lt 30; $i++) {
  Start-Sleep -Seconds 2
  $state = Invoke-RestMethod -Method Get -Uri "$platformApi/runs/$runId"
  if ($state.status -eq "COMPLETED" -or $state.status -eq "FAILED") {
    Write-Host "Status: $($state.status)"
    break
  }
}

Write-Host "[4/4] 获取Verdict与Artifacts..."
$verdict = Invoke-RestMethod -Method Get -Uri "$platformApi/runs/$runId/verdict"
$artifacts = Invoke-RestMethod -Method Get -Uri "$platformApi/runs/$runId/artifacts"

Write-Host "Verdict: $($verdict.verdict)"
if ($verdict.reasons) {
  Write-Host "Reasons:"
  $verdict.reasons | ForEach-Object {
    Write-Host ("- {0} | {1} | observed={2} | threshold={3}" -f $_.domain, $_.rule_or_metric, $_.observed, $_.threshold)
  }
}
Write-Host "Artifacts:"
$artifacts.items | ForEach-Object { Write-Host "- $($_.name)" }

Write-Host "触发清理..."
Invoke-RestMethod -Method Post -Uri "$platformApi/runs/$runId/cleanup" | Out-Null
Write-Host "完成。"
