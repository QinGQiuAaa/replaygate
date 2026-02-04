import json
import os
import time
import uuid
import statistics
from datetime import datetime
from pathlib import Path

import httpx
import pika
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Gauge, Histogram, generate_latest
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from sqlalchemy import Column, DateTime, Float, String, Text, create_engine, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql+psycopg2://postgres:postgres@localhost:5432/replaygate')
RABBITMQ_URL = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@localhost:5672/')
ARTIFACTS_DIR = Path(os.getenv('ARTIFACTS_DIR', '/artifacts'))
ORDER_SERVICE_URL = os.getenv('ORDER_SERVICE_URL', 'http://localhost:8001')
INVENTORY_SERVICE_URL = os.getenv('INVENTORY_SERVICE_URL', 'http://localhost:8002')

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()

def wait_for_db():
    for _ in range(10):
        try:
            with engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            return
        except Exception:
            time.sleep(2)
    raise RuntimeError('Database not ready')

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

class Settings(Base):
    __tablename__ = 'rg_settings'
    id = Column(String, primary_key=True)
    default_executor = Column(String, nullable=True)
    threshold_templates = Column(JSONB, nullable=True)
    active_template = Column(String, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ThresholdTemplate(BaseModel):
    name: str
    thresholds: dict


class SettingsUpdateRequest(BaseModel):
    default_executor: str | None = None
    threshold_templates: list[ThresholdTemplate] | None = None
    active_template: str | None = None


class SettingsResponse(BaseModel):
    default_executor: str
    threshold_templates: list[ThresholdTemplate]
    active_template: str
    env: dict


class DiffRules(BaseModel):
    global_ignore: list[str] | None = None
    endpoint_rules: dict[str, dict] | None = None
    numeric_tolerance: float | None = None

class GateThresholds(BaseModel):
    replay: dict | None = None
    perf: dict | None = None
    security: dict | None = None
    compat: dict | None = None
    obs: dict | None = None
    model_config = ConfigDict(extra='allow')

class RunCreateRequest(BaseModel):
    name: str
    recording_id: str
    baseline_base_url: str
    candidate_base_url: str
    baseline_version: str | None = 'v1'
    candidate_version: str | None = 'v2'
    baseline_run_id: str | None = None
    runners: list[str] | None = None
    executor: str | None = None
    strict_tolerance: float | None = 0.05
    rules: DiffRules | None = None
    thresholds: GateThresholds | None = None

def init_tracing(app: FastAPI):
    exporter_mode = os.getenv('OTEL_TRACES_EXPORTER', 'console').lower()
    if exporter_mode == 'none':
        return
    resource = Resource.create({'service.name': os.getenv('OTEL_SERVICE_NAME', 'replaygate-platform-api')})
    provider = TracerProvider(resource=resource)
    otlp_endpoint = os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT')
    if otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
    else:
        exporter = ConsoleSpanExporter()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()


app = FastAPI(title='ReplayGate Platform API')
init_tracing(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)

@app.on_event('startup')
def on_startup():
    wait_for_db()
    Base.metadata.create_all(bind=engine)
    ensure_run_schema()
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

@app.get('/health')
def health():
    return {'status': 'ok'}


@app.get('/metrics')
def metrics():
    with SessionLocal() as session:
        runs = session.query(Run).all()

    replay_requests_total = 0
    replay_errors_total = 0
    durations = []
    run_failures = 0
    run_total = 0
    total_req = 0
    total_duration_ms = 0

    for run in runs:
        run_total += 1
        if run.overall_verdict == 'FAIL' or run.status == 'FAILED':
            run_failures += 1
        if run.started_at and run.finished_at:
            duration_ms = (run.finished_at - run.started_at).total_seconds() * 1000.0
            durations.append(duration_ms)
        stats = extract_replay_stats(run)
        if stats:
            replay_requests_total += stats.get('total_requests', 0)
            replay_errors_total += stats.get('baseline_errors', 0) + stats.get('candidate_errors', 0)
            total_req += stats.get('total_requests', 0)
            total_duration_ms += stats.get('duration_ms', 0)

    run_error_rate = (run_failures / run_total) if run_total else 0.0
    run_rps = (total_req / (total_duration_ms / 1000.0)) if total_duration_ms else 0.0
    p95 = percentile(durations, 0.95)
    p99 = percentile(durations, 0.99)

    registry = CollectorRegistry()
    Gauge('replay_requests_total', 'Total replay requests', registry=registry).set(replay_requests_total)
    Gauge('replay_errors_total', 'Total replay errors', registry=registry).set(replay_errors_total)
    Gauge('run_error_rate', 'Run error rate', registry=registry).set(round(run_error_rate, 6))
    Gauge('run_rps', 'Run requests per second', registry=registry).set(round(run_rps, 6))
    Gauge('run_latency_ms_p95', 'Run latency p95 in ms', registry=registry).set(round(p95, 2))
    Gauge('run_latency_ms_p99', 'Run latency p99 in ms', registry=registry).set(round(p99, 2))

    hist = Histogram('run_latency_ms', 'Run latency in ms', buckets=[100, 250, 500, 1000, 2000, 5000, 10000], registry=registry)
    for value in durations:
        hist.observe(value)

    return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

@app.get('/runs')
def list_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    verdict: str | None = None,
    runner: str | None = None,
    status: str | None = None,
    since: str | None = None,
    until: str | None = None,
):
    with SessionLocal() as session:
        query = session.query(Run)
        if verdict:
            query = query.filter(Run.overall_verdict == verdict)
        if status:
            query = query.filter(Run.status == status)
        if runner:
            query = query.filter(Run.runners.contains([runner]))
        if since:
            since_dt = parse_datetime(since)
            if since_dt:
                query = query.filter(Run.created_at >= since_dt)
        if until:
            until_dt = parse_datetime(until)
            if until_dt:
                query = query.filter(Run.created_at <= until_dt)
        total = query.count()
        runs = query.order_by(Run.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return {'items': [serialize_run(r) for r in runs], 'page': page, 'page_size': page_size, 'total': total}

@app.post('/runs', status_code=201)
def create_run(req: RunCreateRequest):
    run_id = str(uuid.uuid4())

    default_rules = {
        'global_ignore': ['run_id', 'trace_id', 'timestamp'],
        'endpoint_rules': {
            '/api/orders': {
                'ignore': ['order_id', 'app_version'],
                'strict': ['status', 'total_price'],
            }
        },
        'numeric_tolerance': 0.05,
    }
    default_thresholds = get_default_thresholds()

    with SessionLocal() as session:
        settings = ensure_settings(session, default_thresholds)
        base_thresholds = select_thresholds(settings, default_thresholds)
        rules = default_rules if req.rules is None else merge_dicts(default_rules, req.rules.model_dump())
        thresholds = base_thresholds if req.thresholds is None else merge_dicts(base_thresholds, req.thresholds.model_dump())
        executor = req.executor or settings.default_executor or 'local'

        run = Run(
            id=run_id,
            name=req.name,
            status='PENDING',
            recording_id=req.recording_id,
            baseline_base_url=req.baseline_base_url,
            candidate_base_url=req.candidate_base_url,
            baseline_version=req.baseline_version or 'v1',
            candidate_version=req.candidate_version or 'v2',
            strict_tolerance=req.strict_tolerance or 0.05,
            runners=req.runners or ['replay'],
            baseline_run_id=req.baseline_run_id,
            executor=executor,
            rules=rules,
            thresholds=thresholds,
            created_at=datetime.utcnow(),
        )
        session.add(run)
        session.commit()

    publish_run(run_id)
    return serialize_run(run)


@app.get('/runs/metrics')
def list_run_metrics(limit: int = Query(20, ge=1, le=200)):
    with SessionLocal() as session:
        runs = session.query(Run).order_by(Run.created_at.desc()).limit(limit).all()
    items = []
    pass_count = 0
    fail_count = 0
    for run in runs:
        summary = extract_perf_summary(run)
        metrics = {
            'id': run.id,
            'created_at': run.created_at.isoformat() + 'Z' if run.created_at else None,
            'overall_verdict': run.overall_verdict,
            'p99_ms': summary.get('p99_ms') if summary else None,
            'error_rate_pct': summary.get('error_rate_pct') if summary else None,
            'rps': summary.get('rps') if summary else None,
        }
        if run.overall_verdict == 'PASS':
            pass_count += 1
        elif run.overall_verdict == 'FAIL':
            fail_count += 1
        items.append(metrics)
    return {'items': items, 'summary': {'pass': pass_count, 'fail': fail_count}}

@app.get('/runs/{run_id}')
def get_run(run_id: str):
    with SessionLocal() as session:
        run = session.query(Run).filter_by(id=run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail='run not found')
        return serialize_run(run)

@app.get('/runs/{run_id}/verdict')
def get_verdict(run_id: str):
    with SessionLocal() as session:
        run = session.query(Run).filter_by(id=run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail='verdict not found')
        if run.overall_verdict or run.runner_results:
            return {
                'overall_verdict': run.overall_verdict,
                'runner_results': run.runner_results or [],
            }
        if not run.verdict:
            raise HTTPException(status_code=404, detail='verdict not found')
        return run.verdict

@app.get('/runs/{run_id}/artifacts')
def list_artifacts(run_id: str):
    run_dir = ARTIFACTS_DIR / run_id
    items = []
    if run_dir.exists():
        for path in run_dir.iterdir():
            if path.is_file():
                items.append({
                    'name': path.name,
                    'size_bytes': path.stat().st_size,
                    'download_url': f'/runs/{run_id}/artifacts/{path.name}',
                })
    return {'items': items}

@app.get('/runs/{run_id}/artifacts/{artifact_name}')
def download_artifact(run_id: str, artifact_name: str):
    path = ARTIFACTS_DIR / run_id / artifact_name
    if not path.exists():
        raise HTTPException(status_code=404, detail='artifact not found')
    return FileResponse(path)

@app.post('/runs/{run_id}/cleanup')
def cleanup_run(run_id: str):
    cleanup_log = []
    try:
        order_resp = httpx.post(f'{ORDER_SERVICE_URL}/internal/cleanup/{run_id}', timeout=10)
        cleanup_log.append({'service': 'order-service', 'status': order_resp.status_code, 'body': order_resp.json()})
    except Exception as exc:
        cleanup_log.append({'service': 'order-service', 'status': 'error', 'error': str(exc)})

    try:
        inv_resp = httpx.post(f'{INVENTORY_SERVICE_URL}/internal/cleanup/{run_id}', timeout=10)
        cleanup_log.append({'service': 'inventory-service', 'status': inv_resp.status_code, 'body': inv_resp.json()})
    except Exception as exc:
        cleanup_log.append({'service': 'inventory-service', 'status': 'error', 'error': str(exc)})

    run_dir = ARTIFACTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    cleanup_path = run_dir / 'cleanup_log.json'
    cleanup_path.write_text(json.dumps({'run_id': run_id, 'items': cleanup_log}, indent=2), encoding='utf-8')

    return {'status': 'ok', 'cleaned_at': datetime.utcnow().isoformat() + 'Z'}


@app.get('/settings', response_model=SettingsResponse)
def get_settings():
    default_thresholds = get_default_thresholds()
    with SessionLocal() as session:
        settings = ensure_settings(session, default_thresholds)
        return build_settings_response(settings)


@app.put('/settings', response_model=SettingsResponse)
def update_settings(req: SettingsUpdateRequest):
    default_thresholds = get_default_thresholds()
    with SessionLocal() as session:
        settings = ensure_settings(session, default_thresholds)
        if req.default_executor is not None:
            settings.default_executor = req.default_executor
        if req.threshold_templates is not None:
            settings.threshold_templates = [t.model_dump() for t in req.threshold_templates]
        if req.active_template is not None:
            settings.active_template = req.active_template
        settings.updated_at = datetime.utcnow()
        session.commit()
        return build_settings_response(settings)


def publish_run(run_id: str):
    params = pika.URLParameters(RABBITMQ_URL)
    for _ in range(5):
        try:
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            channel.queue_declare(queue='replay_runs', durable=True)
            channel.basic_publish(
                exchange='',
                routing_key='replay_runs',
                body=run_id.encode('utf-8'),
            )
            connection.close()
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError('Failed to publish run to RabbitMQ')


def get_default_thresholds() -> dict:
    return {
        'replay': {
            'max_diff_rate': 0.05,
            'max_schema_breaking': 0,
            'max_strict_mismatches': 0,
        },
        'perf': {
            'max_error_rate_pct': 0.5,
            'max_p99_ms': 500,
        },
        'security': {
            'max_high': 0,
            'max_medium': 0,
        },
        'compat': {
            'max_breaking_changes': 0,
            'mode': 'strict',
        },
        'obs': {
            'max_error_rate_pct': 0.5,
            'max_p99_ms': 500,
            'window': 'run',
        },
    }


def ensure_settings(session, default_thresholds: dict) -> Settings:
    settings = session.query(Settings).filter_by(id='default').first()
    if settings:
        return settings
    settings = Settings(
        id='default',
        default_executor='local',
        threshold_templates=[{'name': 'default', 'thresholds': default_thresholds}],
        active_template='default',
        updated_at=datetime.utcnow(),
    )
    session.add(settings)
    session.commit()
    return settings


def select_thresholds(settings: Settings, default_thresholds: dict) -> dict:
    templates = settings.threshold_templates or [{'name': 'default', 'thresholds': default_thresholds}]
    active_name = settings.active_template or templates[0].get('name', 'default')
    selected = next((item for item in templates if item.get('name') == active_name), templates[0])
    return merge_dicts(default_thresholds, selected.get('thresholds', {}))


def build_settings_response(settings: Settings) -> dict:
    thresholds = settings.threshold_templates
    if not thresholds:
        thresholds = [{'name': 'default', 'thresholds': get_default_thresholds()}]
    return {
        'default_executor': settings.default_executor or 'local',
        'threshold_templates': thresholds,
        'active_template': settings.active_template or 'default',
        'env': {
            'k8s_enabled': os.getenv('ENABLE_K8S_EXECUTOR', 'false').lower() == 'true',
            'otel_exporter': os.getenv('OTEL_TRACES_EXPORTER', 'console'),
        },
    }


def extract_replay_stats(run: Run) -> dict | None:
    if not run.runner_results:
        return None
    for item in run.runner_results:
        if item.get('name') == 'replay':
            return (item.get('metrics') or {}).get('replay_stats')
    return None


def extract_perf_summary(run: Run) -> dict | None:
    if not run.runner_results:
        return None
    for item in run.runner_results:
        if item.get('name') == 'perf':
            return (item.get('metrics') or {}).get('summary')
    return None


def parse_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace('Z', ''))
    except Exception:
        return None


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    if len(values) == 1:
        return values[0]
    k = (len(values) - 1) * pct
    f = int(k)
    c = min(f + 1, len(values) - 1)
    if f == c:
        return values[f]
    return values[f] + (values[c] - values[f]) * (k - f)


def serialize_run(run: Run) -> dict:
    return {
        'id': run.id,
        'name': run.name,
        'status': run.status,
        'recording_id': run.recording_id,
        'baseline_base_url': run.baseline_base_url,
        'candidate_base_url': run.candidate_base_url,
        'baseline_version': run.baseline_version,
        'candidate_version': run.candidate_version,
        'strict_tolerance': run.strict_tolerance,
        'runners': run.runners,
        'runner_results': run.runner_results,
        'overall_verdict': run.overall_verdict,
        'baseline_run_id': run.baseline_run_id,
        'executor': run.executor,
        'rules': run.rules,
        'thresholds': run.thresholds,
        'created_at': run.created_at.isoformat() + 'Z' if run.created_at else None,
        'started_at': run.started_at.isoformat() + 'Z' if run.started_at else None,
        'finished_at': run.finished_at.isoformat() + 'Z' if run.finished_at else None,
        'diff_summary': run.diff_summary,
        'verdict': run.verdict,
        'error_message': run.error_message,
    }


def ensure_run_schema():
    with engine.begin() as conn:
        conn.execute(text('ALTER TABLE rg_runs ADD COLUMN IF NOT EXISTS strict_tolerance DOUBLE PRECISION'))
        conn.execute(text('ALTER TABLE rg_runs ADD COLUMN IF NOT EXISTS runners JSONB'))
        conn.execute(text('ALTER TABLE rg_runs ADD COLUMN IF NOT EXISTS runner_results JSONB'))
        conn.execute(text('ALTER TABLE rg_runs ADD COLUMN IF NOT EXISTS overall_verdict VARCHAR'))
        conn.execute(text('ALTER TABLE rg_runs ADD COLUMN IF NOT EXISTS baseline_run_id VARCHAR'))
        conn.execute(text('ALTER TABLE rg_runs ADD COLUMN IF NOT EXISTS executor VARCHAR'))


def merge_dicts(base: dict, override: dict | None) -> dict:
    if not override:
        return base
    merged = json.loads(json.dumps(base))
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_dicts(merged[key], value)
        elif value is not None:
            merged[key] = value
    return merged

