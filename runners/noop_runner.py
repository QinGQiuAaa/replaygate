from runner_registry import RunnerResult, register_runner, write_json


@register_runner('noop')
def execute(ctx):
    run_dir = ctx.artifacts_dir / ctx.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    report = {
        'run_id': ctx.run_id,
        'verdict': 'PASS',
        'message': 'noop runner executed',
    }
    write_json(run_dir / 'noop_report.json', report)
    return RunnerResult(
        name='noop',
        verdict='PASS',
        reasons=[],
        artifacts_files=['noop_report.json'],
        metrics={},
    )
