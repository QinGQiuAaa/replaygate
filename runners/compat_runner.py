import json
from pathlib import Path

import yaml

from runner_registry import RunnerResult, build_reason, get_thresholds, register_runner, write_json


def schema_type(schema: dict) -> str:
    if not isinstance(schema, dict):
        return 'unknown'
    if '$ref' in schema:
        return f"$ref:{schema.get('$ref')}"
    t = schema.get('type', 'object')
    if t == 'array':
        return f"array<{schema_type(schema.get('items', {}))}>"
    return t


def collect_schema_props(schema: dict) -> dict[str, str]:
    props = {}
    for name, prop_schema in (schema.get('properties') or {}).items():
        props[name] = schema_type(prop_schema)
    return props


def load_openapi(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding='utf-8')) or {}


def pick_baseline_path(ctx) -> Path | None:
    if not ctx.baseline_run_id:
        return None
    base_dir = ctx.artifacts_dir / ctx.baseline_run_id
    current = base_dir / 'openapi_current.yaml'
    baseline = base_dir / 'openapi_baseline.yaml'
    if current.exists():
        return current
    if baseline.exists():
        return baseline
    return None


@register_runner('compat')
def execute(ctx):
    run_id = ctx.run_id
    run_dir = ctx.artifacts_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    thresholds = get_thresholds(ctx.thresholds, 'compat')
    mode = thresholds.get('mode', 'strict')
    max_breaking = thresholds.get('max_breaking_changes', 0)

    source_path = ctx.contracts_dir / 'openapi.yaml'
    if not source_path.exists():
        report = {
            'run_id': run_id,
            'verdict': 'FAIL',
            'reasons': [build_reason('compat', 'openapi_missing', 'missing', 'exists', '/', ctx.baseline_run_id)],
        }
        write_json(run_dir / 'compat_report.json', report)
        return RunnerResult(name='compat', verdict='FAIL', reasons=report['reasons'], artifacts_files=['compat_report.json'])

    current_path = run_dir / 'openapi_current.yaml'
    current_path.write_text(source_path.read_text(encoding='utf-8'), encoding='utf-8')

    baseline_path = pick_baseline_path(ctx)
    if not baseline_path:
        baseline_path = run_dir / 'openapi_baseline.yaml'
        baseline_path.write_text(source_path.read_text(encoding='utf-8'), encoding='utf-8')

    baseline = load_openapi(baseline_path)
    current = load_openapi(current_path)

    baseline_schemas = (baseline.get('components') or {}).get('schemas') or {}
    current_schemas = (current.get('components') or {}).get('schemas') or {}

    breaking = []
    for schema_name, base_schema in baseline_schemas.items():
        curr_schema = current_schemas.get(schema_name)
        if not curr_schema:
            breaking.append({'type': 'schema_missing', 'schema': schema_name})
            continue
        base_props = collect_schema_props(base_schema)
        curr_props = collect_schema_props(curr_schema)
        for prop, base_type in base_props.items():
            if prop not in curr_props:
                breaking.append({'type': 'field_missing', 'schema': schema_name, 'field': prop, 'baseline': base_type})
            elif curr_props[prop] != base_type and mode == 'strict':
                breaking.append({
                    'type': 'field_type_changed',
                    'schema': schema_name,
                    'field': prop,
                    'baseline': base_type,
                    'current': curr_props[prop],
                })

    verdict = 'PASS'
    reasons = []
    if len(breaking) > max_breaking:
        verdict = 'FAIL'
        reasons.append(build_reason('compat', 'breaking_changes', str(len(breaking)), str(max_breaking), '/', ctx.baseline_run_id))

    report = {
        'run_id': run_id,
        'summary': {
            'breaking_changes': len(breaking),
            'max_breaking_changes': max_breaking,
            'mode': mode,
        },
        'baseline_run_id': ctx.baseline_run_id,
        'breaking_changes': breaking,
        'verdict': verdict,
        'reasons': reasons,
    }
    write_json(run_dir / 'compat_report.json', report)

    return RunnerResult(
        name='compat',
        verdict=verdict,
        reasons=reasons,
        artifacts_files=['compat_report.json', 'openapi_current.yaml', 'openapi_baseline.yaml'],
        metrics={'summary': report.get('summary', {})},
    )
