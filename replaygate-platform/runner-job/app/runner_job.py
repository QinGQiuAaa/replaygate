import json
import os
from pathlib import Path
from types import SimpleNamespace

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from runner_registry import REGISTRY, RunnerContext, discover_runners, write_json


def init_tracing():
    exporter_mode = os.getenv('OTEL_TRACES_EXPORTER', 'console').lower()
    if exporter_mode == 'none':
        return
    resource = Resource.create({'service.name': os.getenv('OTEL_SERVICE_NAME', 'replaygate-runner-job')})
    provider = TracerProvider(resource=resource)
    otlp_endpoint = os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT')
    if otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
    else:
        exporter = ConsoleSpanExporter()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    HTTPXClientInstrumentor().instrument()


def to_namespace(data: dict) -> SimpleNamespace:
    return SimpleNamespace(**data)


def main():
    init_tracing()
    runner_name = os.getenv('RUNNER_NAME')
    ctx_json = os.getenv('RUN_CONTEXT_JSON', '{}')
    if not runner_name:
        raise RuntimeError('RUNNER_NAME not set')

    ctx_payload = json.loads(ctx_json)
    run_dict = ctx_payload.get('run', {})
    run = to_namespace(run_dict)

    artifacts_dir = Path(ctx_payload.get('artifacts_dir', '/artifacts'))
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    runners_dir = Path(os.getenv('RUNNERS_DIR', '/app/runners'))
    discover_runners(runners_dir)

    ctx = RunnerContext(
        run_id=ctx_payload.get('run_id'),
        run=run,
        thresholds=ctx_payload.get('thresholds', {}),
        strict_tolerance=ctx_payload.get('strict_tolerance', 0.05),
        artifacts_dir=artifacts_dir,
        gateway_url=ctx_payload.get('gateway_url'),
        diff_engine_url=ctx_payload.get('diff_engine_url'),
        gate_url=ctx_payload.get('gate_url'),
        perf_runner_url=ctx_payload.get('perf_runner_url'),
        security_runner_url=ctx_payload.get('security_runner_url'),
        contracts_dir=Path(ctx_payload.get('contracts_dir', '/contracts')),
        baseline_run_id=ctx_payload.get('baseline_run_id'),
    )

    runner = REGISTRY.get(runner_name)
    if not runner:
        payload = {
            'name': runner_name,
            'verdict': 'FAIL',
            'reasons': [{'domain': 'runner', 'rule_or_metric': 'not_found', 'observed': runner_name, 'threshold': 'registered', 'time_window': 'run', 'evidence_link': '/'}],
            'artifacts_files': [],
            'metrics': {},
        }
        write_json(artifacts_dir / ctx.run_id / f'runner_result_{runner_name}.json', payload)
        return

    result = runner(ctx)
    result_payload = {
        'name': result.name,
        'verdict': result.verdict,
        'reasons': result.reasons,
        'artifacts_files': result.artifacts_files,
        'metrics': result.metrics,
    }
    result_path = artifacts_dir / ctx.run_id / f'runner_result_{runner_name}.json'
    write_json(result_path, result_payload)


if __name__ == '__main__':
    main()
