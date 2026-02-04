import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

ARTIFACTS_DIR = Path(os.getenv('ARTIFACTS_DIR', '/artifacts'))
WORKSPACE_DIR = Path(os.getenv('WORKSPACE_DIR', '/workspace'))

app = FastAPI(title='ReplayGate Security Runner')


class SecurityRequest(BaseModel):
    run_id: str
    target_url: str
    thresholds: dict | None = None


def run_cmd(cmd: list[str], cwd: Path | None = None, timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True, timeout=timeout)


def extract_zap_counts(payload: dict) -> dict:
    counts = {'high': 0, 'medium': 0, 'low': 0, 'info': 0}

    def visit(obj):
        if isinstance(obj, dict):
            riskcode = obj.get('riskcode')
            riskdesc = obj.get('riskdesc')
            if riskcode is not None:
                code = str(riskcode)
                if code == '3':
                    counts['high'] += 1
                elif code == '2':
                    counts['medium'] += 1
                elif code == '1':
                    counts['low'] += 1
                elif code == '0':
                    counts['info'] += 1
            if isinstance(riskdesc, str):
                text = riskdesc.lower()
                if text.startswith('high'):
                    counts['high'] += 1
                elif text.startswith('medium'):
                    counts['medium'] += 1
                elif text.startswith('low'):
                    counts['low'] += 1
                elif text.startswith('informational'):
                    counts['info'] += 1
            for value in obj.values():
                visit(value)
        elif isinstance(obj, list):
            for item in obj:
                visit(item)

    visit(payload)
    return counts


def run_zap(run_dir: Path, target_url: str) -> dict:
    zap_report = run_dir / 'zap_report.json'
    cmd = ['zap-baseline.py', '-t', target_url, '-J', str(zap_report), '-m', '1']
    result = run_cmd(cmd, timeout=300)
    if not zap_report.exists():
        return {'status': 'error', 'error': result.stderr or result.stdout}
    payload = json.loads(zap_report.read_text(encoding='utf-8'))
    counts = extract_zap_counts(payload)
    return {'status': 'ok', 'counts': counts}


def run_bandit(run_dir: Path) -> dict:
    bandit_report = run_dir / 'bandit_report.json'
    targets = []
    for folder in ['flashsale-lite', 'replaygate-platform']:
        path = WORKSPACE_DIR / folder
        if path.exists():
            targets.append(str(path))
    if not targets:
        return {'status': 'skipped', 'counts': {'high': 0, 'medium': 0}}

    cmd = ['bandit', '-r', *targets, '-f', 'json', '-o', str(bandit_report)]
    result = run_cmd(cmd)
    if not bandit_report.exists():
        return {'status': 'error', 'error': result.stderr or result.stdout}

    payload = json.loads(bandit_report.read_text(encoding='utf-8'))
    results = payload.get('results', [])
    counts = {'high': 0, 'medium': 0, 'low': 0}
    for item in results:
        sev = str(item.get('issue_severity', '')).lower()
        if sev == 'high':
            counts['high'] += 1
        elif sev == 'medium':
            counts['medium'] += 1
        elif sev == 'low':
            counts['low'] += 1
    return {'status': 'ok', 'counts': counts}


def run_npm_audit(run_dir: Path) -> dict:
    npm_dir = WORKSPACE_DIR / 'console-web'
    if not npm_dir.exists():
        return {'status': 'skipped', 'counts': {'high': 0, 'medium': 0}}

    package_lock = npm_dir / 'package-lock.json'
    if not package_lock.exists():
        run_cmd(['npm', 'install', '--package-lock-only'], cwd=npm_dir, timeout=300)

    result = run_cmd(['npm', 'audit', '--json'], cwd=npm_dir, timeout=300)
    audit_path = run_dir / 'npm_audit.json'
    audit_path.write_text(result.stdout or '{}', encoding='utf-8')

    try:
        payload = json.loads(result.stdout or '{}')
    except json.JSONDecodeError:
        payload = {}

    meta = payload.get('metadata', {}).get('vulnerabilities', {})
    counts = {
        'high': int(meta.get('high', 0)),
        'medium': int(meta.get('moderate', 0)),
        'low': int(meta.get('low', 0)),
    }
    return {'status': 'ok', 'counts': counts}


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.post('/scan')
def scan(req: SecurityRequest):
    run_dir = ARTIFACTS_DIR / req.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    zap_result = run_zap(run_dir, req.target_url)
    bandit_result = run_bandit(run_dir)
    npm_result = run_npm_audit(run_dir)

    high_total = zap_result.get('counts', {}).get('high', 0) + bandit_result.get('counts', {}).get('high', 0) + npm_result.get('counts', {}).get('high', 0)
    medium_total = zap_result.get('counts', {}).get('medium', 0) + bandit_result.get('counts', {}).get('medium', 0) + npm_result.get('counts', {}).get('medium', 0)

    thresholds = req.thresholds or {}
    max_high = thresholds.get('max_high', 0)
    max_medium = thresholds.get('max_medium', 0)

    reasons = []
    verdict = 'PASS'

    if high_total > max_high:
        verdict = 'FAIL'
        reasons.append({
            'domain': 'security',
            'rule_or_metric': 'high',
            'observed': str(high_total),
            'threshold': str(max_high),
            'time_window': 'run',
            'evidence_link': f'/runs/{req.run_id}/artifacts/security_report.json',
        })

    if medium_total > max_medium:
        verdict = 'FAIL'
        reasons.append({
            'domain': 'security',
            'rule_or_metric': 'medium',
            'observed': str(medium_total),
            'threshold': str(max_medium),
            'time_window': 'run',
            'evidence_link': f'/runs/{req.run_id}/artifacts/security_report.json',
        })

    report = {
        'run_id': req.run_id,
        'target_url': req.target_url,
        'zap': zap_result,
        'bandit': bandit_result,
        'npm_audit': npm_result,
        'summary': {
            'high': high_total,
            'medium': medium_total,
        },
        'thresholds': {
            'max_high': max_high,
            'max_medium': max_medium,
        },
        'verdict': verdict,
        'reasons': reasons,
        'generated_at': datetime.utcnow().isoformat() + 'Z',
    }

    report_path = run_dir / 'security_report.json'
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')

    return report
