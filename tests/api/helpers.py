import os
import time
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_fixed

RG_GATEWAY_BASE = os.getenv("RG_GATEWAY_BASE", "http://localhost:8000")
RG_GATEWAY_DOCKER_URL = os.getenv("RG_GATEWAY_DOCKER_URL", "http://flashsale-gateway:8000")


def seed_recording(recording_id: str, gateway_base: str | None = None) -> None:
    gateway = gateway_base or RG_GATEWAY_BASE
    httpx.post(f"{gateway}/api/recordings/{recording_id}/clear", timeout=10)
    payload = {"sku": "SKU-1", "qty": 1, "user_id": "pytest"}
    headers = {"X-Recording-Id": recording_id}
    httpx.post(f"{gateway}/api/orders", json=payload, headers=headers, timeout=10)


def create_run(
    client: httpx.Client,
    runners: list[str],
    strict_tolerance: float | None = None,
    baseline_run_id: str | None = None,
    executor: str | None = None,
    thresholds: dict | None = None,
    recording_id: str = "pytest",
    name: str = "pytest-run",
    baseline_base_url: str | None = None,
    candidate_base_url: str | None = None,
) -> dict:
    payload: dict[str, Any] = {
        "name": name,
        "recording_id": recording_id,
        "baseline_base_url": baseline_base_url or RG_GATEWAY_DOCKER_URL,
        "candidate_base_url": candidate_base_url or RG_GATEWAY_DOCKER_URL,
        "baseline_version": "v1",
        "candidate_version": "v2",
        "runners": runners,
    }
    if strict_tolerance is not None:
        payload["strict_tolerance"] = strict_tolerance
    if baseline_run_id:
        payload["baseline_run_id"] = baseline_run_id
    if executor:
        payload["executor"] = executor
    if thresholds is not None:
        payload["thresholds"] = thresholds

    resp = client.post("/runs", json=payload)
    resp.raise_for_status()
    return resp.json()


@retry(stop=stop_after_attempt(120), wait=wait_fixed(2))
def wait_run_completed(client: httpx.Client, run_id: str) -> dict:
    resp = client.get(f"/runs/{run_id}")
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") in {"COMPLETED", "FAILED"}:
        return data
    raise RuntimeError("run not completed yet")


def get_artifacts(client: httpx.Client, run_id: str) -> dict:
    resp = client.get(f"/runs/{run_id}/artifacts")
    resp.raise_for_status()
    return resp.json()


def download_artifact(client: httpx.Client, run_id: str, filename: str) -> httpx.Response:
    return client.get(f"/runs/{run_id}/artifacts/{filename}")
