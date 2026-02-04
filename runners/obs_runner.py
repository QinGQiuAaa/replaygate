import json

from runner_registry import RunnerResult, build_reason, get_thresholds, register_runner, write_json


@register_runner('obs')
def execute(ctx):
    run_id = ctx.run_id
    run_dir = ctx.artifacts_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    thresholds = get_thresholds(ctx.thresholds, 'obs')
    max_error_rate = thresholds.get('max_error_rate_pct', 0.5)
    max_p99 = thresholds.get('max_p99_ms', 500)
    window = thresholds.get('window', 'run')

    perf_path = run_dir / 'perf_report.json'
    reasons = []
    verdict = 'PASS'
    summary = {}

    if not perf_path.exists():
        verdict = 'FAIL'
        reasons.append(build_reason('obs', 'perf_report_missing', 'missing', 'exists', '/'))
    else:
        report = json.loads(perf_path.read_text(encoding='utf-8'))
        summary = report.get('summary', {})
        error_rate = summary.get('error_rate_pct', 0.0)
        p99_ms = summary.get('p99_ms', 0.0)

        reasons.append({
            'domain': 'obs',
            'rule_or_metric': 'error_rate_pct',
            'observed': f'{error_rate:.3f}',
            'threshold': str(max_error_rate),
            'time_window': window,
            'evidence_link': f'/runs/{run_id}/artifacts/perf_report.json',
        })
        if error_rate > max_error_rate:
            verdict = 'FAIL'

        reasons.append({
            'domain': 'obs',
            'rule_or_metric': 'p99_ms',
            'observed': f'{p99_ms:.2f}',
            'threshold': str(max_p99),
            'time_window': window,
            'evidence_link': f'/runs/{run_id}/artifacts/perf_report.json',
        })
        if p99_ms > max_p99:
            verdict = 'FAIL'

    report = {
        'run_id': run_id,
        'summary': summary,
        'thresholds': {'max_error_rate_pct': max_error_rate, 'max_p99_ms': max_p99, 'window': window},
        'verdict': verdict,
        'reasons': reasons,
    }
    write_json(run_dir / 'obs_report.json', report)

    return RunnerResult(
        name='obs',
        verdict=verdict,
        reasons=reasons,
        artifacts_files=['obs_report.json'],
        metrics={'summary': summary},
    )
