from .helpers import create_run, seed_recording, wait_run_completed


def test_gate_thresholds_strict_tolerance(client, gateway_base):
    recording_id = "pytest-strict"
    seed_recording(recording_id, gateway_base)

    run_fail = create_run(client, runners=["replay"], strict_tolerance=0.05, recording_id=recording_id)
    fail_state = wait_run_completed(client, run_fail["id"])
    assert fail_state["overall_verdict"] == "FAIL"

    run_pass = create_run(client, runners=["replay"], strict_tolerance=0.15, recording_id=recording_id)
    pass_state = wait_run_completed(client, run_pass["id"])
    assert pass_state["overall_verdict"] == "PASS"
