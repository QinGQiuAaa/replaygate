# ReplayGate K8s Executor

## Prerequisites
- Docker Desktop + Kubernetes tooling
- `kind`, `kubectl` installed
- This repo running locally with `docker compose up -d --build`

## One‑click Kind
```powershell
powershell -ExecutionPolicy Bypass -File scripts\kind-up.ps1
```

This creates a Kind cluster with a hostPath mount for `artifacts` and loads `replaygate-runner-job:latest`.

## Enable K8s Executor
Set these environment variables before starting compose:
```
$env:ENABLE_K8S_EXECUTOR="true"
$env:K8S_NAMESPACE="replaygate"
$env:K8S_GATEWAY_URL="http://host.docker.internal:8000"
$env:K8S_DIFF_ENGINE_URL="http://host.docker.internal:8090"
$env:K8S_GATE_URL="http://host.docker.internal:8091"
$env:K8S_PERF_RUNNER_URL="http://host.docker.internal:8093"
$env:K8S_ARTIFACTS_HOST_PATH="/artifacts"
```
Then:
```
docker compose up -d --build
```

## Run a K8s Job
Use the console or API:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\demo.ps1 -Runners replay,perf
```
Pass `executor: "k8s"` in the Create Run request (Console “执行器”下拉).

## Troubleshooting
- If pods cannot reach host services, ensure `host.docker.internal` resolves in Kind.
- If artifacts are missing, confirm Kind mount `/artifacts` and `K8S_ARTIFACTS_HOST_PATH`.
- Use `kubectl -n replaygate get jobs,pods` to inspect job status.
