from .helpers import create_run, get_artifacts, seed_recording, wait_run_completed


def test_run_lifecycle(client, gateway_base):
    recording_id = "pytest-lifecycle"
    seed_recording(recording_id, gateway_base)

    run = create_run(client, runners=["replay"], strict_tolerance=0.05, recording_id=recording_id)
    run_id = run["id"]
    completed = wait_run_completed(client, run_id)

    assert completed["status"] in {"COMPLETED", "FAILED"}
    assert completed.get("runner_results") is not None
    assert completed.get("overall_verdict") in {"PASS", "FAIL"}

    artifacts = get_artifacts(client, run_id)
    names = {item["name"] for item in artifacts["items"]}
    assert "gate_verdict.json" in names
    assert "diff_report.json" in names
