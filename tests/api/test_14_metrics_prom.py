def test_metrics_prom(client):
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    text = metrics.text
    assert "replay_requests_total" in text
    assert "replay_errors_total" in text
    assert "run_error_rate" in text
    assert "run_rps" in text
    has_hist = "run_latency_ms_bucket" in text
    has_p95 = "run_latency_ms_p95" in text
    has_p99 = "run_latency_ms_p99" in text
    assert has_hist or (has_p95 and has_p99)
