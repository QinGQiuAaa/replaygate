param(
  [string]$ClusterName = "replaygate"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path "."
$configPath = Join-Path $root "k8s\kind-config.generated.yaml"

$config = @"
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    extraMounts:
      - hostPath: $($root.Path)\artifacts
        containerPath: /artifacts
"@

$config | Set-Content -Path $configPath

kind create cluster --name $ClusterName --config $configPath
kubectl apply -f k8s\namespace.yaml

Write-Host "Building runner job image..."
docker build -t replaygate-runner-job:latest -f replaygate-platform/runner-job/Dockerfile .
kind load docker-image replaygate-runner-job:latest --name $ClusterName

Write-Host "Kind cluster ready: $ClusterName"
