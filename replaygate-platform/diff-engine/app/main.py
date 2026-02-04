from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title='ReplayGate Diff Engine')

@app.get('/health')
def health():
    return {'status': 'ok'}

class DiffRequest(BaseModel):
    run_id: str
    rules: dict = {}
    strict_tolerance: float | None = None
    comparisons: list[dict]


def flatten_json(value: Any, prefix: str = '') -> dict[str, Any]:
    items = {}
    if isinstance(value, dict):
        for key, val in value.items():
            path = f'{prefix}.{key}' if prefix else key
            items.update(flatten_json(val, path))
    elif isinstance(value, list):
        for idx, val in enumerate(value):
            path = f'{prefix}[{idx}]' if prefix else f'[{idx}]'
            items.update(flatten_json(val, path))
    else:
        items[prefix] = value
    return items


def path_matches(pattern: str, path: str) -> bool:
    if pattern.endswith('*'):
        return path.startswith(pattern[:-1])
    return path == pattern


def filter_keys(flat: dict[str, Any], ignore: list[str]) -> dict[str, Any]:
    if not ignore:
        return flat
    filtered = {}
    for path, val in flat.items():
        if any(path_matches(pattern, path) for pattern in ignore):
            continue
        filtered[path] = val
    return filtered


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


@app.post('/diff')
def diff(payload: DiffRequest):
    rules = payload.rules or {}
    global_ignore = rules.get('global_ignore', [])
    endpoint_rules = rules.get('endpoint_rules', {})
    global_tolerance = rules.get('numeric_tolerance', 0.0)
    strict_tolerance = payload.strict_tolerance if payload.strict_tolerance is not None else 0.05

    items = []
    total_fields = 0
    diff_fields = 0
    strict_mismatches = 0
    schema_breaking = 0
    numeric_drift = 0
    strict_max_drift = 0.0

    for comparison in payload.comparisons:
        req = comparison.get('request', {})
        path = req.get('path', '')
        rule = endpoint_rules.get(path, {})
        ignore = global_ignore + rule.get('ignore', [])
        strict_fields = set(rule.get('strict', []))
        tolerance = rule.get('numeric_tolerance', global_tolerance)

        baseline_body = comparison.get('baseline', {}).get('body')
        candidate_body = comparison.get('candidate', {}).get('body')
        baseline_status = comparison.get('baseline', {}).get('status_code')
        candidate_status = comparison.get('candidate', {}).get('status_code')

        diffs = []
        if baseline_status != candidate_status:
            diffs.append({
                'path': 'status_code',
                'baseline': baseline_status,
                'candidate': candidate_status,
                'type': 'status_mismatch',
            })

        base_flat = flatten_json(baseline_body) if isinstance(baseline_body, (dict, list)) else {'body': baseline_body}
        cand_flat = flatten_json(candidate_body) if isinstance(candidate_body, (dict, list)) else {'body': candidate_body}

        base_flat = filter_keys(base_flat, ignore)
        cand_flat = filter_keys(cand_flat, ignore)

        base_keys = set(base_flat.keys())
        cand_keys = set(cand_flat.keys())
        if base_keys != cand_keys:
            schema_breaking += 1
            diffs.append({
                'path': 'schema',
                'baseline_missing': sorted(list(base_keys - cand_keys)),
                'candidate_missing': sorted(list(cand_keys - base_keys)),
                'type': 'schema_breaking',
            })

        for key in sorted(base_keys & cand_keys):
            base_val = base_flat.get(key)
            cand_val = cand_flat.get(key)

            if key in strict_fields:
                if is_number(base_val) and is_number(cand_val):
                    denom = abs(base_val) if abs(base_val) > 1e-9 else 1.0
                    drift = abs(base_val - cand_val) / denom
                    if drift > strict_tolerance:
                        strict_mismatches += 1
                        strict_max_drift = max(strict_max_drift, drift)
                        diffs.append({
                            'path': key,
                            'baseline': base_val,
                            'candidate': cand_val,
                            'type': 'strict_mismatch',
                            'tolerance': strict_tolerance,
                        })
                    else:
                        strict_max_drift = max(strict_max_drift, drift)
                else:
                    if base_val != cand_val:
                        strict_mismatches += 1
                        diffs.append({
                            'path': key,
                            'baseline': base_val,
                            'candidate': cand_val,
                            'type': 'strict_mismatch',
                        })
                continue

            total_fields += 1
            if is_number(base_val) and is_number(cand_val):
                denom = abs(base_val) if abs(base_val) > 1e-9 else 1.0
                drift = abs(base_val - cand_val) / denom
                if drift > tolerance:
                    diff_fields += 1
                    numeric_drift += 1
                    diffs.append({
                        'path': key,
                        'baseline': base_val,
                        'candidate': cand_val,
                        'type': 'numeric_drift',
                        'tolerance': tolerance,
                    })
                continue

            if base_val != cand_val:
                diff_fields += 1
                diffs.append({
                    'path': key,
                    'baseline': base_val,
                    'candidate': cand_val,
                    'type': 'value_mismatch',
                })

        items.append({
            'path': path,
            'diffs': diffs,
            'diff_count': len(diffs),
            'schema_breaking': any(d.get('type') == 'schema_breaking' for d in diffs),
        })

    diff_rate = (diff_fields / total_fields) if total_fields else 0.0
    summary = {
        'diff_rate': round(diff_rate, 6),
        'total_fields': total_fields,
        'diff_fields': diff_fields,
        'strict_mismatches': strict_mismatches,
        'strict_max_drift': round(strict_max_drift, 6),
        'strict_tolerance_used': strict_tolerance,
        'schema_breaking': schema_breaking,
        'numeric_drift': numeric_drift,
        'total_requests': len(payload.comparisons),
    }

    return {'run_id': payload.run_id, 'summary': summary, 'items': items}
