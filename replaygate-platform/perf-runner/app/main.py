import json
import os
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

ARTIFACTS_DIR = Path(os.getenv('ARTIFACTS_DIR', '/artifacts'))
SCRIPT_PATH = Path(__file__).parent / 'scripts' / 'perf.js'

app = FastAPI(title='ReplayGate Perf Runner')


class PerfRequest(BaseModel):
    run_id: str
    target_url: str
    vus: int | None = 5
    duration: str | None = '5s'
    thresholds: dict | None = None


def parse_summary(summary_path: Path) -> dict:
    if not summary_path.exists():
        return {}
    return json.loads(summary_path.read_text(encoding='utf-8'))


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.post('/run')
def run_perf(req: PerfRequest):
    run_dir = ARTIFACTS_DIR / req.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / 'perf_summary.json'

    cmd = [
        'k6',
        'run',
        '--vus', str(req.vus or 5),
        '--duration', str(req.duration or '5s'),
        '--summary-export', str(summary_path),
        str(SCRIPT_PATH),
    ]

    env = os.environ.copy()
    env['TARGET_URL'] = req.target_url
    env['RUN_ID'] = req.run_id

    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        error_path = run_dir / 'perf_error.txt'
        error_path.write_text(result.stderr or result.stdout, encoding='utf-8')
        raise HTTPException(status_code=500, detail='k6 run failed')

    summary = parse_summary(summary_path)
    metrics = summary.get('metrics', {})
    error_rate = metrics.get('http_req_failed', {}).get('rate', 0.0) * 100.0
    p99_ms = metrics.get('http_req_duration', {}).get('values', {}).get('p(99)', 0.0)
    rps = metrics.get('http_reqs', {}).get('rate', 0.0)

    thresholds = req.thresholds or {}
    max_error_rate = thresholds.get('max_error_rate_pct', 0.5)
    max_p99 = thresholds.get('max_p99_ms', 500)

    reasons = []
    verdict = 'PASS'

    if error_rate > max_error_rate:
        verdict = 'FAIL'
        reasons.append({
            'domain': 'perf',
            'rule_or_metric': 'error_rate_pct',
            'observed': f'{error_rate:.3f}',
            'threshold': str(max_error_rate),
            'time_window': 'run',
            'evidence_link': '/runs/{}/artifacts/perf_report.json'.format(req.run_id),
        })

    if p99_ms > max_p99:
        verdict = 'FAIL'
        reasons.append({
            'domain': 'perf',
            'rule_or_metric': 'p99_ms',
            'observed': f'{p99_ms:.2f}',
            'threshold': str(max_p99),
            'time_window': 'run',
            'evidence_link': '/runs/{}/artifacts/perf_report.json'.format(req.run_id),
        })

    report = {
        'run_id': req.run_id,
        'target_url': req.target_url,
        'vus': req.vus or 5,
        'duration': req.duration or '5s',
        'summary': {
            'error_rate_pct': round(error_rate, 6),
            'p99_ms': round(p99_ms, 2),
            'rps': round(rps, 3),
        },
        'thresholds': {
            'max_error_rate_pct': max_error_rate,
            'max_p99_ms': max_p99,
        },
        'verdict': verdict,
        'reasons': reasons,
        'generated_at': datetime.utcnow().isoformat() + 'Z',
    }

    report_path = run_dir / 'perf_report.json'
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')

    return report
