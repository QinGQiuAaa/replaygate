import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path

import httpx
import pika
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
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
    rules = Column(JSONB, nullable=True)
    thresholds = Column(JSONB, nullable=True)
    diff_summary = Column(JSONB, nullable=True)
    verdict = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

class DiffRules(BaseModel):
    global_ignore: list[str] | None = None
    endpoint_rules: dict[str, dict] | None = None
    numeric_tolerance: float | None = None

class GateThresholds(BaseModel):
    max_diff_rate: float | None = 0.05
    max_schema_breaking: int | None = 0
    max_strict_mismatches: int | None = 0

class RunCreateRequest(BaseModel):
    name: str
    recording_id: str
    baseline_base_url: str
    candidate_base_url: str
    baseline_version: str | None = 'v1'
    candidate_version: str | None = 'v2'
    strict_tolerance: float | None = 0.05
    rules: DiffRules | None = None
    thresholds: GateThresholds | None = None

app = FastAPI(title='ReplayGate Platform API')
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

@app.get('/runs')
def list_runs():
    with SessionLocal() as session:
        runs = session.query(Run).order_by(Run.created_at.desc()).all()
        return {'items': [serialize_run(r) for r in runs]}

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
    default_thresholds = {
        'max_diff_rate': 0.05,
        'max_schema_breaking': 0,
        'max_strict_mismatches': 0,
    }

    rules = default_rules if req.rules is None else merge_dicts(default_rules, req.rules.model_dump())
    thresholds = default_thresholds if req.thresholds is None else merge_dicts(default_thresholds, req.thresholds.model_dump())

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
        rules=rules,
        thresholds=thresholds,
        created_at=datetime.utcnow(),
    )
    with SessionLocal() as session:
        session.add(run)
        session.commit()

    publish_run(run_id)
    return serialize_run(run)

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
        if not run or not run.verdict:
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

