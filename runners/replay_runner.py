import json
import time
import uuid
from datetime import datetime

import httpx
from opentelemetry import trace

from runner_registry import RunnerResult, build_reason, get_thresholds, register_runner, write_json


def parse_body(resp: httpx.Response):
    try:
        return resp.json()
    except Exception:
        return resp.text


@register_runner('replay')
def execute(ctx):
    run = ctx.run
    run_id = ctx.run_id
    run_dir = ctx.artifacts_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    log_lines = [f'Replay runner start {datetime.utcnow().isoformat()}Z']
    tracer = trace.get_tracer('replaygate.replay')
    rec_resp = httpx.get(f"{ctx.gateway_url}/api/recordings/{run.recording_id}", timeout=10)
    rec_resp.raise_for_status()
    items = rec_resp.json().get('items', [])

    comparisons = []
    baseline_errors = 0
    candidate_errors = 0

    for idx, item in enumerate(items):
        req = item.get('request', {})
        method = req.get('method', 'GET')
        path = req.get('path', '/')
        body = req.get('body')

        with tracer.start_as_current_span('replay.request') as span:
            trace_id = format(span.get_span_context().trace_id, '032x')

            base_headers = {
                'X-Run-Id': run_id,
                'X-Trace-Id': trace_id,
                'X-Replay-Mode': 'true',
                'Content-Type': 'application/json',
            }

            baseline_headers = base_headers | {
                'Idempotency-Key': f'{run_id}-{idx}-baseline',
                'X-App-Version': run.baseline_version or 'v1',
            }
            candidate_headers = base_headers | {
                'Idempotency-Key': f'{run_id}-{idx}-candidate',
                'X-App-Version': run.candidate_version or 'v2',
            }

            baseline_url = f"{run.baseline_base_url}{path}"
            candidate_url = f"{run.candidate_base_url}{path}"

            baseline_resp = httpx.request(method, baseline_url, json=body, headers=baseline_headers, timeout=10)
            candidate_resp = httpx.request(method, candidate_url, json=body, headers=candidate_headers, timeout=10)

        if baseline_resp.status_code >= 400:
            baseline_errors += 1
        if candidate_resp.status_code >= 400:
            candidate_errors += 1

        comparisons.append({
            'request': {
                'method': method,
                'path': path,
            },
            'baseline': {
                'status_code': baseline_resp.status_code,
                'headers': dict(baseline_resp.headers),
                'body': parse_body(baseline_resp),
            },
            'candidate': {
                'status_code': candidate_resp.status_code,
                'headers': dict(candidate_resp.headers),
                'body': parse_body(candidate_resp),
            },
        })

    diff_payload = {
        'run_id': run_id,
        'rules': run.rules or {},
        'strict_tolerance': ctx.strict_tolerance,
        'comparisons': comparisons,
    }
    diff_resp = httpx.post(f"{ctx.diff_engine_url}/diff", json=diff_payload, timeout=30)
    diff_resp.raise_for_status()
    diff_report = diff_resp.json()
    summary = diff_report.get('summary', {})

    evidence_link = f"/runs/{run_id}/artifacts/diff_report.json"
    replay_thresholds = get_thresholds(ctx.thresholds, 'replay')
    gate_payload = {
        'run_id': run_id,
        'diff_summary': summary,
        'thresholds': replay_thresholds,
        'evidence_link': evidence_link,
    }
    gate_resp = httpx.post(f"{ctx.gate_url}/evaluate", json=gate_payload, timeout=10)
    gate_resp.raise_for_status()
    replay_verdict = gate_resp.json()

    if ctx.baseline_run_id:
        for reason in replay_verdict.get('reasons', []):
            reason['baseline_run_id'] = ctx.baseline_run_id

    write_json(run_dir / 'diff_report.json', diff_report)
    replay_stats = {
        'run_id': run_id,
        'total_requests': len(comparisons),
        'baseline_errors': baseline_errors,
        'candidate_errors': candidate_errors,
        'duration_ms': int((time.time() - start_time) * 1000),
    }
    write_json(run_dir / 'replay_stats.json', replay_stats)
    (run_dir / 'replay_log.txt').write_text('\n'.join(log_lines), encoding='utf-8')

    return RunnerResult(
        name='replay',
        verdict=replay_verdict.get('verdict', 'FAIL'),
        reasons=replay_verdict.get('reasons', []),
        artifacts_files=['diff_report.json', 'replay_stats.json', 'replay_log.txt'],
        metrics={'diff_summary': summary, 'replay_stats': replay_stats},
    )
