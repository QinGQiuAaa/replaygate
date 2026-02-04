from __future__ import annotations

import importlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

REGISTRY: dict[str, Callable[['RunnerContext'], 'RunnerResult']] = {}


@dataclass
class RunnerResult:
    name: str
    verdict: str
    reasons: list[dict] = field(default_factory=list)
    artifacts_files: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


@dataclass
class RunnerContext:
    run_id: str
    run: Any
    thresholds: dict
    strict_tolerance: float
    artifacts_dir: Path
    gateway_url: str
    diff_engine_url: str
    gate_url: str
    perf_runner_url: str
    security_runner_url: str
    contracts_dir: Path
    baseline_run_id: str | None = None


def register_runner(name: str):
    def decorator(func: Callable[[RunnerContext], RunnerResult]):
        REGISTRY[name] = func
        return func
    return decorator


def discover_runners(runners_dir: Path):
    if not runners_dir.exists():
        return
    if str(runners_dir) not in sys.path:
        sys.path.insert(0, str(runners_dir))
    app_dir = Path(__file__).parent
    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))
    for path in runners_dir.glob('*.py'):
        if path.name.startswith('_'):
            continue
        module_name = path.stem
        if module_name in sys.modules:
            continue
        importlib.import_module(module_name)


def build_reason(domain: str, rule: str, observed: str, threshold: str, evidence_link: str, baseline_run_id: str | None = None) -> dict:
    reason = {
        'domain': domain,
        'rule_or_metric': rule,
        'observed': observed,
        'threshold': threshold,
        'time_window': 'run',
        'evidence_link': evidence_link,
    }
    if baseline_run_id:
        reason['baseline_run_id'] = baseline_run_id
    return reason


def write_json(path: Path, payload: dict):
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')


def get_thresholds(thresholds: dict | None, key: str) -> dict:
    if not thresholds:
        return {}
    if isinstance(thresholds, dict):
        if key in thresholds and isinstance(thresholds.get(key), dict):
            return thresholds.get(key) or {}
        if key == 'replay':
            return thresholds
    return {}
