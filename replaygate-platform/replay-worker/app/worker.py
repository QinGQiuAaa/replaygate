import json
import os
import time
import traceback
import uuid
from datetime import datetime
from pathlib import Path

import httpx
import pika
from sqlalchemy import Column, DateTime, Float, String, Text, create_engine, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, sessionmaker
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql+psycopg2://postgres:postgres@localhost:5432/replaygate')
RABBITMQ_URL = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@localhost:5672/')
GATEWAY_URL = os.getenv('GATEWAY_URL', 'http://localhost:8000')
DIFF_ENGINE_URL = os.getenv('DIFF_ENGINE_URL', 'http://localhost:8090')
GATE_URL = os.getenv('GATE_URL', 'http://localhost:8091')
PERF_RUNNER_URL = os.getenv('PERF_RUNNER_URL', 'http://localhost:8093')
SECURITY_RUNNER_URL = os.getenv('SECURITY_RUNNER_URL', 'http://localhost:8094')
PLATFORM_API_URL = os.getenv('PLATFORM_API_URL', 'http://localhost:8080')
ARTIFACTS_DIR = Path(os.getenv('ARTIFACTS_DIR', '/artifacts'))
CONTRACTS_DIR = Path(os.getenv('CONTRACTS_DIR', '/contracts'))
RUNNERS_DIR = Path(os.getenv('RUNNERS_DIR', '/runners'))
ENABLE_K8S_EXECUTOR = os.getenv('ENABLE_K8S_EXECUTOR', 'false').lower() == 'true'
K8S_NAMESPACE = os.getenv('K8S_NAMESPACE', 'replaygate')

from executors import K8sJobExecutor, LocalExecutor, select_executor
from runner_registry import REGISTRY, RunnerContext, RunnerResult, build_reason, discover_runners, write_json

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()

def init_tracing():
    exporter_mode = os.getenv('OTEL_TRACES_EXPORTER', 'console').lower()
    if exporter_mode == 'none':
        return
    resource = Resource.create({'service.name': os.getenv('OTEL_SERVICE_NAME', 'replaygate-worker')})
    provider = TracerProvider(resource=resource)
    otlp_endpoint = os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT')
    if otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
    else:
        exporter = ConsoleSpanExporter()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    HTTPXClientInstrumentor().instrument()


def wait_for_db():
    for _ in range(10):
        try:
            with engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            return
        except Exception:
            time.sleep(2)
    raise RuntimeError('Database not ready')


def ensure_run_schema():
    with engine.begin() as conn:
        conn.execute(text('ALTER TABLE rg_runs ADD COLUMN IF NOT EXISTS strict_tolerance DOUBLE PRECISION'))
        conn.execute(text('ALTER TABLE rg_runs ADD COLUMN IF NOT EXISTS runners JSONB'))
        conn.execute(text('ALTER TABLE rg_runs ADD COLUMN IF NOT EXISTS runner_results JSONB'))
        conn.execute(text('ALTER TABLE rg_runs ADD COLUMN IF NOT EXISTS overall_verdict VARCHAR'))
        conn.execute(text('ALTER TABLE rg_runs ADD COLUMN IF NOT EXISTS baseline_run_id VARCHAR'))
        conn.execute(text('ALTER TABLE rg_runs ADD COLUMN IF NOT EXISTS executor VARCHAR'))

class Run(Base):
    __tablename__ = 'rg_runs'
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    status = Column(String, nullable=False)
    recording_id = Column(String, nullable=False)
    baseline_base_url = Column(String, nullable=False)
    candidate_base_url = Column(String, nullable=False)
    baseline_version = Column(String, nullable=True)
    candidate_version = Column(String, nullable=True)
    strict_tolerance = Column(Float, nullable=True, default=0.05)
    runners = Column(JSONB, nullable=True)
    runner_results = Column(JSONB, nullable=True)
    overall_verdict = Column(String, nullable=True)
    baseline_run_id = Column(String, nullable=True)
    executor = Column(String, nullable=True)
    rules = Column(JSONB, nullable=True)
    thresholds = Column(JSONB, nullable=True)
    diff_summary = Column(JSONB, nullable=True)
    verdict = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)


def update_artifact_index():
    rows = []
    if not ARTIFACTS_DIR.exists():
        return
    for run_dir in sorted([p for p in ARTIFACTS_DIR.iterdir() if p.is_dir()], key=lambda p: p.name, reverse=True):
        gate_path = run_dir / 'gate_verdict.json'
        verdict = 'UNKNOWN'
        if gate_path.exists():
            try:
                data = json.loads(gate_path.read_text(encoding='utf-8'))
                verdict = data.get('overall_verdict', verdict)
            except Exception:
                verdict = 'UNKNOWN'
        rows.append(
            f"<tr><td>{run_dir.name}</td><td>{verdict}</td>"
            f"<td><a href='./{run_dir.name}/gate_verdict.json'>gate_verdict.json</a></td>"
            f"<td><a href='./{run_dir.name}/'>artifacts</a></td></tr>"
        )

    html = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>ReplayGate Artifacts</title>"
        "<style>body{font-family:Arial, sans-serif;padding:20px;}"
        "table{border-collapse:collapse;width:100%;}"
        "th,td{border:1px solid #ddd;padding:8px;}"
        "th{background:#f3f4f6;text-align:left;}</style></head>"
        "<body><h1>ReplayGate Artifacts Index</h1>"
        "<table><thead><tr><th>Run ID</th><th>Verdict</th><th>Gate Verdict</th><th>Directory</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></body></html>"
    )
    (ARTIFACTS_DIR / 'index.html').write_text(html, encoding='utf-8')


def process_run(run_id: str):
    log_lines = []
    runner_results: list[dict] = []
    diff_summary = None
    try:
        with SessionLocal() as session:
            run = session.query(Run).filter_by(id=run_id).first()
            if not run:
                return
            run.status = 'RUNNING'
            run.started_at = datetime.utcnow()
            session.commit()

        log_lines.append(f'Run {run_id} started at {datetime.utcnow().isoformat()}Z')
        run_dir = ARTIFACTS_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        discover_runners(RUNNERS_DIR)
        run_runners = run.runners or ['replay']

        ctx = RunnerContext(
            run_id=run_id,
            run=run,
            thresholds=run.thresholds or {},
            strict_tolerance=run.strict_tolerance or 0.05,
            artifacts_dir=ARTIFACTS_DIR,
            gateway_url=GATEWAY_URL,
            diff_engine_url=DIFF_ENGINE_URL,
            gate_url=GATE_URL,
            perf_runner_url=PERF_RUNNER_URL,
            security_runner_url=SECURITY_RUNNER_URL,
            contracts_dir=CONTRACTS_DIR,
            baseline_run_id=run.baseline_run_id,
        )

        local_executor = LocalExecutor()
        k8s_executor = None
        if ENABLE_K8S_EXECUTOR:
            try:
                k8s_executor = K8sJobExecutor(K8S_NAMESPACE)
            except Exception as exc:
                log_lines.append(f'K8S executor disabled: {exc}')

        for runner_name in run_runners:
            executor = select_executor(run.executor, runner_name, k8s_executor, local_executor)
            handle = executor.submit(ctx, runner_name)
            status = executor.wait(handle)
            if status != 'SUCCEEDED':
                reason = build_reason('executor', 'execution_failed', status, 'SUCCEEDED', '/', run.baseline_run_id)
                runner_results.append({
                    'name': runner_name,
                    'verdict': 'FAIL',
                    'reasons': [reason],
                    'artifacts_files': [],
                    'metrics': {},
                })
                continue
            try:
                result: RunnerResult = executor.fetch_result(handle)
                result_dict = {
                    'name': result.name,
                    'verdict': result.verdict,
                    'reasons': result.reasons,
                    'artifacts_files': result.artifacts_files,
                    'metrics': result.metrics,
                }
                runner_results.append(result_dict)
                if result.name == 'replay' and result.metrics.get('diff_summary'):
                    diff_summary = result.metrics.get('diff_summary')
            except Exception as exc:
                reason = build_reason('runner', 'execute_error', str(exc), 'none', '/', run.baseline_run_id)
                runner_results.append({
                    'name': runner_name,
                    'verdict': 'FAIL',
                    'reasons': [reason],
                    'artifacts_files': [],
                    'metrics': {},
                })

        overall_verdict = 'PASS'
        if any(r.get('verdict') == 'FAIL' for r in runner_results):
            overall_verdict = 'FAIL'

        gate_verdict = {
            'overall_verdict': overall_verdict,
            'runner_results': runner_results,
            'config': {
                'runners': run_runners,
                'strict_tolerance': run.strict_tolerance or 0.05,
                'thresholds': run.thresholds or {},
                'baseline_run_id': run.baseline_run_id,
                'executor': run.executor or 'local',
            },
        }
        write_json(run_dir / 'gate_verdict.json', gate_verdict)
        update_artifact_index()

        with SessionLocal() as session:
            run = session.query(Run).filter_by(id=run_id).first()
            if run:
                run.status = 'COMPLETED'
                run.finished_at = datetime.utcnow()
                run.diff_summary = diff_summary
                run.runner_results = runner_results
                run.overall_verdict = overall_verdict
                if runner_results:
                    replay_result = next((r for r in runner_results if r.get('name') == 'replay'), None)
                    if replay_result:
                        run.verdict = {'verdict': replay_result.get('verdict'), 'reasons': replay_result.get('reasons', [])}
                session.commit()

    except Exception as exc:
        error_text = f'{exc}\n{traceback.format_exc()}'
        log_lines.append(error_text)
        run_dir = ARTIFACTS_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / 'replay_error.txt').write_text(error_text, encoding='utf-8')
        update_artifact_index()
        with SessionLocal() as session:
            run = session.query(Run).filter_by(id=run_id).first()
            if run:
                run.status = 'FAILED'
                run.error_message = error_text
                run.finished_at = datetime.utcnow()
                run.overall_verdict = 'FAIL'
                run.runner_results = runner_results
                session.commit()
    finally:
        try:
            httpx.post(f'{PLATFORM_API_URL}/runs/{run_id}/cleanup', timeout=10)
        except Exception:
            pass


def on_message(channel, method_frame, header_frame, body):
    run_id = body.decode('utf-8')
    process_run(run_id)
    channel.basic_ack(delivery_tag=method_frame.delivery_tag)


def main():
    params = pika.URLParameters(RABBITMQ_URL)
    while True:
        try:
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            channel.queue_declare(queue='replay_runs', durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume('replay_runs', on_message)
            channel.start_consuming()
        except Exception:
            time.sleep(2)


if __name__ == '__main__':
    init_tracing()
    wait_for_db()
    Base.metadata.create_all(bind=engine)
    ensure_run_schema()
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    main()

