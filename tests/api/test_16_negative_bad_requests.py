import pytest


@pytest.mark.parametrize(
    "payload",
    [
        {
            "name": "bad-runner",
            "recording_id": "demo",
            "baseline_base_url": "http://flashsale-gateway:8000",
            "candidate_base_url": "http://flashsale-gateway:8000",
            "runners": "replay",
        },
        {
            "name": "bad-thresholds",
            "recording_id": "demo",
            "baseline_base_url": "http://flashsale-gateway:8000",
            "candidate_base_url": "http://flashsale-gateway:8000",
            "runners": ["replay"],
            "thresholds": "bad",
        },
        {
            "name": "bad-baseline",
            "recording_id": "demo",
            "baseline_base_url": "http://flashsale-gateway:8000",
            "candidate_base_url": "http://flashsale-gateway:8000",
            "runners": ["replay"],
            "baseline_run_id": ["oops"],
        },
        {
            "name": "bad-executor",
            "recording_id": "demo",
            "baseline_base_url": "http://flashsale-gateway:8000",
            "candidate_base_url": "http://flashsale-gateway:8000",
            "runners": ["replay"],
            "executor": 123,
        },
    ],
)
def test_negative_bad_requests(client, payload):
    resp = client.post("/runs", json=payload)
    assert 400 <= resp.status_code < 500
