import httpx


def test_smoke_health_and_metrics(client, api_base):
    assert client.get("/health").status_code == 200
    assert httpx.get("http://localhost:8000/health", timeout=5).status_code == 200
    assert httpx.get("http://localhost:8090/health", timeout=5).status_code == 200
    assert httpx.get("http://localhost:8091/health", timeout=5).status_code == 200

    prom = httpx.get("http://localhost:9090/-/ready", timeout=5)
    assert prom.status_code == 200
    grafana = httpx.get("http://localhost:3000/api/health", timeout=5)
    assert grafana.status_code == 200

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    body = metrics.text
    assert "replay_requests_total" in body
    assert "replay_errors_total" in body
    assert "run_error_rate" in body
