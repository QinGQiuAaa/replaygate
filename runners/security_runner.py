import httpx

from runner_registry import RunnerResult, build_reason, get_thresholds, register_runner, write_json


@register_runner('security')
def execute(ctx):
    run_id = ctx.run_id
    run_dir = ctx.artifacts_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    thresholds = get_thresholds(ctx.thresholds, 'security')
    payload = {
        'run_id': run_id,
        'target_url': ctx.gateway_url,
        'thresholds': thresholds,
    }
    resp = httpx.post(f"{ctx.security_runner_url}/scan", json=payload, timeout=300)
    resp.raise_for_status()
    report = resp.json()

    reasons = report.get('reasons', [])
    if ctx.baseline_run_id:
        for reason in reasons:
            reason['baseline_run_id'] = ctx.baseline_run_id

    report['reasons'] = reasons
    write_json(run_dir / 'security_report.json', report)

    return RunnerResult(
        name='security',
        verdict=report.get('verdict', 'FAIL'),
        reasons=reasons,
        artifacts_files=['security_report.json', 'bandit_report.json', 'npm_audit.json', 'zap_report.json'],
        metrics={'summary': report.get('summary', {})},
    )
