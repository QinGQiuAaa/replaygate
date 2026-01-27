from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title='ReplayGate Gate')

class GateRequest(BaseModel):
    run_id: str
    diff_summary: dict
    thresholds: dict | None = None
    evidence_link: str | None = None

@app.get('/health')
def health():
    return {'status': 'ok'}

@app.post('/evaluate')
def evaluate(req: GateRequest):
    thresholds = req.thresholds or {}
    max_diff_rate = thresholds.get('max_diff_rate', 0.05)
    max_schema_breaking = thresholds.get('max_schema_breaking', 0)
    max_strict_mismatches = thresholds.get('max_strict_mismatches', 0)

    diff_rate = req.diff_summary.get('diff_rate', 0)
    schema_breaking = req.diff_summary.get('schema_breaking', 0)
    strict_mismatches = req.diff_summary.get('strict_mismatches', 0)
    strict_max_drift = req.diff_summary.get('strict_max_drift')
    strict_tolerance_used = req.diff_summary.get('strict_tolerance_used')

    reasons = []
    verdict = 'PASS'

    if diff_rate > max_diff_rate:
        verdict = 'FAIL'
        reasons.append({
            'domain': 'diff_engine',
            'rule_or_metric': 'diff_rate',
            'observed': str(diff_rate),
            'threshold': str(max_diff_rate),
            'time_window': 'run',
            'evidence_link': req.evidence_link or '',
        })

    if schema_breaking > max_schema_breaking:
        verdict = 'FAIL'
        reasons.append({
            'domain': 'diff_engine',
            'rule_or_metric': 'schema_breaking',
            'observed': str(schema_breaking),
            'threshold': str(max_schema_breaking),
            'time_window': 'run',
            'evidence_link': req.evidence_link or '',
        })

    if strict_mismatches > max_strict_mismatches:
        verdict = 'FAIL'
        reasons.append({
            'domain': 'diff_engine',
            'rule_or_metric': 'strict_mismatches',
            'observed': str(strict_mismatches),
            'threshold': str(max_strict_mismatches),
            'time_window': 'run',
            'evidence_link': req.evidence_link or '',
        })

    if strict_tolerance_used is not None:
        reasons.append({
            'domain': 'diff_engine',
            'rule_or_metric': 'strict_tolerance',
            'observed': str(strict_max_drift if strict_max_drift is not None else ''),
            'threshold': str(strict_tolerance_used),
            'time_window': 'run',
            'evidence_link': req.evidence_link or '',
        })

    return {'verdict': verdict, 'reasons': reasons}
