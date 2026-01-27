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

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql+psycopg2://postgres:postgres@localhost:5432/replaygate')
RABBITMQ_URL = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@localhost:5672/')
GATEWAY_URL = os.getenv('GATEWAY_URL', 'http://localhost:8000')
DIFF_ENGINE_URL = os.getenv('DIFF_ENGINE_URL', 'http://localhost:8090')
GATE_URL = os.getenv('GATE_URL', 'http://localhost:8091')
ARTIFACTS_DIR = Path(os.getenv('ARTIFACTS_DIR', '/artifacts'))

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


def ensure_run_schema():
    with engine.begin() as conn:
        conn.execute(text('ALTER TABLE rg_runs ADD COLUMN IF NOT EXISTS strict_tolerance DOUBLE PRECISION'))

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


def parse_body(resp: httpx.Response):
    try:
        return resp.json()
    except Exception:
        return resp.text


def process_run(run_id: str):
    start_time = time.time()
    log_lines = []
    try:
        with SessionLocal() as session:
            run = session.query(Run).filter_by(id=run_id).first()
            if not run:
                return
            run.status = 'RUNNING'
            run.started_at = datetime.utcnow()
            session.commit()

        log_lines.append(f'Run {run_id} started at {datetime.utcnow().isoformat()}Z')

        rec_resp = httpx.get(f'{GATEWAY_URL}/api/recordings/{run.recording_id}', timeout=10)
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

            trace_id = str(uuid.uuid4())

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

            baseline_url = f'{run.baseline_base_url}{path}'
            candidate_url = f'{run.candidate_base_url}{path}'

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
            'strict_tolerance': run.strict_tolerance or 0.05,
            'comparisons': comparisons,
        }
        diff_resp = httpx.post(f'{DIFF_ENGINE_URL}/diff', json=diff_payload, timeout=30)
        diff_resp.raise_for_status()
        diff_report = diff_resp.json()

        summary = diff_report.get('summary', {})

        evidence_link = f'/runs/{run_id}/artifacts/diff_report.json'
        gate_payload = {
            'run_id': run_id,
            'diff_summary': summary,
            'thresholds': run.thresholds or {},
            'evidence_link': evidence_link,
        }
        gate_resp = httpx.post(f'{GATE_URL}/evaluate', json=gate_payload, timeout=10)
        gate_resp.raise_for_status()
        verdict = gate_resp.json()

        run_dir = ARTIFACTS_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / 'diff_report.json').write_text(json.dumps(diff_report, indent=2), encoding='utf-8')
        (run_dir / 'gate_verdict.json').write_text(json.dumps(verdict, indent=2), encoding='utf-8')
        replay_stats = {
            'run_id': run_id,
            'total_requests': len(comparisons),
            'baseline_errors': baseline_errors,
            'candidate_errors': candidate_errors,
            'duration_ms': int((time.time() - start_time) * 1000),
        }
        (run_dir / 'replay_stats.json').write_text(json.dumps(replay_stats, indent=2), encoding='utf-8')
        (run_dir / 'replay_log.txt').write_text('\n'.join(log_lines), encoding='utf-8')

        with SessionLocal() as session:
            run = session.query(Run).filter_by(id=run_id).first()
            if run:
                run.status = 'COMPLETED'
                run.finished_at = datetime.utcnow()
                run.diff_summary = summary
                run.verdict = verdict
                session.commit()

    except Exception as exc:
        error_text = f'{exc}\n{traceback.format_exc()}'
        log_lines.append(error_text)
        run_dir = ARTIFACTS_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / 'replay_error.txt').write_text(error_text, encoding='utf-8')
        with SessionLocal() as session:
            run = session.query(Run).filter_by(id=run_id).first()
            if run:
                run.status = 'FAILED'
                run.error_message = error_text
                run.finished_at = datetime.utcnow()
                session.commit()


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
    wait_for_db()
    Base.metadata.create_all(bind=engine)
    ensure_run_schema()
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    main()

