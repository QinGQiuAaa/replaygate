param(
  [string]$RunId
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$artifactsDir = Join-Path $repoRoot 'artifacts'

if (-not (Test-Path $artifactsDir)) {
  Write-Host "未找到 artifacts 目录：$artifactsDir"
  exit 1
}

$runDir = $null
if ($RunId) {
  $candidate = Join-Path $artifactsDir $RunId
  if (Test-Path $candidate) {
    $runDir = $candidate
  } else {
    Write-Host "未找到 RunId 目录：$candidate"
  }
}

if (-not $runDir) {
  $dirs = Get-ChildItem -Path $artifactsDir -Directory | Sort-Object LastWriteTime -Descending
  if (-not $dirs -or $dirs.Count -eq 0) {
    Write-Host "artifacts 下没有可用的 run 目录。"
    exit 1
  }
  $runDir = $dirs[0].FullName
  Write-Host "未指定 RunId，选择最新目录：$($dirs[0].Name)"
}

$gateFile = Join-Path $runDir 'gate_verdict.json'
$diffFile = Join-Path $runDir 'diff_report.json'

if (-not (Test-Path $gateFile)) {
  Write-Host "缺少 gate_verdict.json：$gateFile"
}
if (-not (Test-Path $diffFile)) {
  Write-Host "缺少 diff_report.json：$diffFile"
}

if (-not (Test-Path $gateFile) -or -not (Test-Path $diffFile)) {
  Write-Host "可用的 run 目录："
  Get-ChildItem -Path $artifactsDir -Directory | Sort-Object LastWriteTime -Descending | ForEach-Object { Write-Host "- $($_.Name)" }
  exit 1
}

Write-Host "打开：$gateFile"
Start-Process $gateFile
Write-Host "打开：$diffFile"
Start-Process $diffFile
