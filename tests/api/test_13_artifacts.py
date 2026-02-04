from .helpers import create_run, download_artifact, get_artifacts, seed_recording, wait_run_completed


def test_artifacts_listing_and_download(client, gateway_base):
    recording_id = "pytest-artifacts"
    seed_recording(recording_id, gateway_base)

    run = create_run(client, runners=["replay"], strict_tolerance=0.05, recording_id=recording_id)
    wait_run_completed(client, run["id"])

    artifacts = get_artifacts(client, run["id"])
    names = [item["name"] for item in artifacts["items"]]
    assert "diff_report.json" in names

    resp = download_artifact(client, run["id"], "diff_report.json")
    assert resp.status_code == 200
    assert "summary" in resp.text

    not_found = download_artifact(client, run["id"], "nope.json")
    assert not_found.status_code == 404

    traversal = download_artifact(client, run["id"], "../README.md")
    assert traversal.status_code == 404
