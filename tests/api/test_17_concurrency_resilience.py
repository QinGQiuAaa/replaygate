from concurrent.futures import ThreadPoolExecutor

from .helpers import create_run, seed_recording, wait_run_completed


def test_concurrency_resilience(client, gateway_base):
    recording_id = "pytest-concurrent"
    seed_recording(recording_id, gateway_base)

    def _create_and_wait(index: int) -> dict:
        run = create_run(
            client,
            runners=["replay"],
            strict_tolerance=0.05,
            recording_id=recording_id,
            name=f"pytest-concurrent-{index}",
        )
        return wait_run_completed(client, run["id"])

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(_create_and_wait, range(4)))

    assert len(results) == 4
    for result in results:
        assert result["status"] in {"COMPLETED", "FAILED"}
