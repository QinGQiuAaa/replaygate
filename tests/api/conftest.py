import os
from typing import Iterator

import httpx
import pytest
from tenacity import retry, stop_after_attempt, wait_fixed

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None


if load_dotenv:
    load_dotenv()


RG_API_BASE = os.getenv("RG_API_BASE", "http://localhost:8080")
RG_GATEWAY_BASE = os.getenv("RG_GATEWAY_BASE", "http://localhost:8000")


@retry(stop=stop_after_attempt(10), wait=wait_fixed(2))
def _get(url: str) -> httpx.Response:
    resp = httpx.get(url, timeout=5)
    resp.raise_for_status()
    return resp


def wait_for_health():
    _get(f"{RG_API_BASE}/health")
    _get(f"{RG_GATEWAY_BASE}/health")
    _get("http://localhost:8090/health")
    _get("http://localhost:8091/health")


@pytest.fixture(scope="session")
def api_base() -> str:
    return RG_API_BASE


@pytest.fixture(scope="session")
def gateway_base() -> str:
    return RG_GATEWAY_BASE


@pytest.fixture(scope="session")
def client(api_base: str) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=api_base, timeout=10.0) as c:
        yield c


@pytest.fixture(scope="session", autouse=True)
def _health_ready() -> None:
    wait_for_health()
