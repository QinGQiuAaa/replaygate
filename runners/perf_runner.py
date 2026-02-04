import json
from pathlib import Path

import httpx

from runner_registry import RunnerResult, build_reason, get_thresholds, register_runner, write_json


def load_baseline_report(ctx, filename: str):
    if not ctx.baseline_run_id:
        return None
    path = ctx.artifacts_dir / ctx.baseline_run_id / filename
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding='utf-8'))


@register_runner('perf')
def execute(ctx):
    run_id = ctx.run_id
    run_dir = ctx.artifacts_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    thresholds = get_thresholds(ctx.thresholds, 'perf')
    payload = {
        'run_id': run_id,
        'target_url': ctx.gateway_url,
        'vus': thresholds.get('vus', 5),
        'duration': thresholds.get('duration', '5s'),
        'thresholds': thresholds,
    }
    resp = httpx.post(f"{ctx.perf_runner_url}/run", json=payload, timeout=120)
    resp.raise_for_status()
    report = resp.json()

    reasons = list(report.get('reasons', []))
    verdict = report.get('verdict', 'FAIL')

    current_summary = report.get('summary', {})
    baseline_report = load_baseline_report(ctx, 'perf_report.json')
    baseline_summary = (baseline_report or {}).get('summary', {})

    if ctx.baseline_run_id:
        if not baseline_report:
            verdict = 'FAIL'
            reasons.append(build_reason('perf', 'baseline_missing', 'missing', 'exists', '/', ctx.baseline_run_id))
        else:
            baseline_rps = baseline_summary.get('rps', 0)
            baseline_p99 = baseline_summary.get('p99_ms', 0)
            baseline_err = baseline_summary.get('error_rate_pct', 0)

            rps_min = baseline_rps * 0.9
            p99_max = baseline_p99 * 1.2
            err_max = min(0.5, baseline_err + 0.2)

            rps_observed = current_summary.get('rps', 0)
            p99_observed = current_summary.get('p99_ms', 0)
            err_observed = current_summary.get('error_rate_pct', 0)

            reasons.extend([
                build_reason('perf', 'rps_vs_baseline', str(rps_observed), f'>= {rps_min:.3f}', '/', ctx.baseline_run_id),
                build_reason('perf', 'p99_vs_baseline', str(p99_observed), f'<= {p99_max:.2f}', '/', ctx.baseline_run_id),
                build_reason('perf', 'error_rate_vs_baseline', str(err_observed), f'<= {err_max:.3f}', '/', ctx.baseline_run_id),
            ])

            if rps_observed < rps_min:
                verdict = 'FAIL'
            if p99_observed > p99_max:
                verdict = 'FAIL'
            if err_observed > err_max:
                verdict = 'FAIL'

            report['baseline'] = {
                'run_id': ctx.baseline_run_id,
                'summary': baseline_summary,
                'rules': {
                    'rps_min': round(rps_min, 6),
                    'p99_max': round(p99_max, 2),
                    'error_rate_max': round(err_max, 6),
                },
            }

    report['verdict'] = verdict
    report['reasons'] = reasons
    write_json(run_dir / 'perf_report.json', report)

    return RunnerResult(
        name='perf',
        verdict=verdict,
        reasons=reasons,
        artifacts_files=['perf_report.json', 'perf_summary.json'],
        metrics={'summary': current_summary},
    )
