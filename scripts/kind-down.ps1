param(
  [string]$ClusterName = "replaygate"
)

kind delete cluster --name $ClusterName
