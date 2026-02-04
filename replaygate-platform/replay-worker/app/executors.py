from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from runner_registry import REGISTRY, RunnerContext, RunnerResult, build_reason, write_json

try:
    from kubernetes import client, config
except Exception:  # pragma: no cover - optional dependency
    client = None
    config = None


@dataclass
class ExecutionHandle:
    exec_id: str
    runner_name: str
    job_name: str | None = None
    result_path: Path | None = None


class Executor:
    def submit(self, ctx: RunnerContext, runner_name: str) -> ExecutionHandle:
        raise NotImplementedError

    def wait(self, handle: ExecutionHandle) -> str:
        raise NotImplementedError

    def fetch_artifacts(self, handle: ExecutionHandle) -> list[str]:
        raise NotImplementedError

    def fetch_result(self, handle: ExecutionHandle) -> RunnerResult:
        raise NotImplementedError


class LocalExecutor(Executor):
    def __init__(self):
        self._results: dict[str, RunnerResult] = {}

    def submit(self, ctx: RunnerContext, runner_name: str) -> ExecutionHandle:
        runner = REGISTRY.get(runner_name)
        if not runner:
            reason = build_reason('runner', 'not_found', runner_name, 'registered', '/', ctx.baseline_run_id)
            result = RunnerResult(name=runner_name, verdict='FAIL', reasons=[reason])
        else:
            result = runner(ctx)

        result_path = ctx.artifacts_dir / ctx.run_id / f'runner_result_{runner_name}.json'
        payload = {
            'name': result.name,
            'verdict': result.verdict,
            'reasons': result.reasons,
            'artifacts_files': result.artifacts_files,
            'metrics': result.metrics,
        }
        write_json(result_path, payload)

        exec_id = f'local-{uuid.uuid4()}'
        self._results[exec_id] = result
        return ExecutionHandle(exec_id=exec_id, runner_name=runner_name, result_path=result_path)

    def wait(self, handle: ExecutionHandle) -> str:
        return 'SUCCEEDED'

    def fetch_artifacts(self, handle: ExecutionHandle) -> list[str]:
        result = self._results.get(handle.exec_id)
        if not result:
            return []
        return result.artifacts_files

    def fetch_result(self, handle: ExecutionHandle) -> RunnerResult:
        return self._results[handle.exec_id]


class K8sJobExecutor(Executor):
    def __init__(self, namespace: str):
        if not config or not client:
            raise RuntimeError('kubernetes client not available')
        kubeconfig = os.getenv('KUBECONFIG')
        if kubeconfig:
            config.load_kube_config(config_file=kubeconfig)
        else:
            try:
                config.load_kube_config()
            except Exception:
                config.load_incluster_config()
        self._batch = client.BatchV1Api()
        self._namespace = namespace
        self._results: dict[str, RunnerResult] = {}

    def submit(self, ctx: RunnerContext, runner_name: str) -> ExecutionHandle:
        exec_id = f'k8s-{uuid.uuid4()}'
        job_name = f'rg-{runner_name}-{ctx.run_id[:6]}-{exec_id[-4:]}'.lower()

        ctx_payload = self._build_payload(ctx)
        image = os.getenv('RUNNER_JOB_IMAGE', 'replaygate-runner-job:latest')
        artifacts_host_path = os.getenv('K8S_ARTIFACTS_HOST_PATH', '/artifacts')

        container = client.V1Container(
            name='runner',
            image=image,
            command=['python', '/app/runner_job.py'],
            env=[
                client.V1EnvVar(name='RUNNER_NAME', value=runner_name),
                client.V1EnvVar(name='RUN_CONTEXT_JSON', value=json.dumps(ctx_payload)),
            ],
            volume_mounts=[
                client.V1VolumeMount(name='artifacts', mount_path='/artifacts'),
            ],
        )

        volumes = [
            client.V1Volume(
                name='artifacts',
                host_path=client.V1HostPathVolumeSource(path=artifacts_host_path),
            )
        ]

        pod_spec = client.V1PodSpec(
            restart_policy='Never',
            containers=[container],
            volumes=volumes,
        )
        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels={'app': 'replaygate-runner', 'runner': runner_name}),
            spec=pod_spec,
        )
        job_spec = client.V1JobSpec(template=template, backoff_limit=0, ttl_seconds_after_finished=300)
        job = client.V1Job(
            api_version='batch/v1',
            kind='Job',
            metadata=client.V1ObjectMeta(name=job_name),
            spec=job_spec,
        )

        self._batch.create_namespaced_job(namespace=self._namespace, body=job)
        result_path = ctx.artifacts_dir / ctx.run_id / f'runner_result_{runner_name}.json'
        return ExecutionHandle(exec_id=exec_id, runner_name=runner_name, job_name=job_name, result_path=result_path)

    def wait(self, handle: ExecutionHandle) -> str:
        for _ in range(90):
            job = self._batch.read_namespaced_job_status(handle.job_name, self._namespace)
            status = job.status
            if status.succeeded:
                return 'SUCCEEDED'
            if status.failed:
                return 'FAILED'
            time.sleep(2)
        return 'TIMEOUT'

    def fetch_artifacts(self, handle: ExecutionHandle) -> list[str]:
        result = self._results.get(handle.exec_id)
        if not result and handle.result_path and handle.result_path.exists():
            result = self._load_result(handle)
        return result.artifacts_files if result else []

    def fetch_result(self, handle: ExecutionHandle) -> RunnerResult:
        result = self._results.get(handle.exec_id)
        if result:
            return result
        result = self._load_result(handle)
        self._results[handle.exec_id] = result
        return result

    def _load_result(self, handle: ExecutionHandle) -> RunnerResult:
        if not handle.result_path or not handle.result_path.exists():
            return RunnerResult(
                name=handle.runner_name,
                verdict='FAIL',
                reasons=[build_reason('executor', 'result_missing', 'missing', 'exists', '/')],
            )
        payload = json.loads(handle.result_path.read_text(encoding='utf-8'))
        return RunnerResult(
            name=payload.get('name', handle.runner_name),
            verdict=payload.get('verdict', 'FAIL'),
            reasons=payload.get('reasons', []),
            artifacts_files=payload.get('artifacts_files', []),
            metrics=payload.get('metrics', {}),
        )

    def _build_payload(self, ctx: RunnerContext) -> dict[str, Any]:
        run = ctx.run
        run_dict = {
            'id': run.id,
            'name': run.name,
            'recording_id': run.recording_id,
            'baseline_base_url': run.baseline_base_url,
            'candidate_base_url': run.candidate_base_url,
            'baseline_version': run.baseline_version,
            'candidate_version': run.candidate_version,
            'rules': run.rules,
        }

        base_host_override = os.getenv('K8S_BASE_URL_HOST')
        if base_host_override:
            run_dict['baseline_base_url'] = _rewrite_host(run_dict['baseline_base_url'], base_host_override)
            run_dict['candidate_base_url'] = _rewrite_host(run_dict['candidate_base_url'], base_host_override)

        payload = {
            'run_id': ctx.run_id,
            'run': run_dict,
            'thresholds': ctx.thresholds,
            'strict_tolerance': ctx.strict_tolerance,
            'artifacts_dir': '/artifacts',
            'gateway_url': os.getenv('K8S_GATEWAY_URL', ctx.gateway_url),
            'diff_engine_url': os.getenv('K8S_DIFF_ENGINE_URL', ctx.diff_engine_url),
            'gate_url': os.getenv('K8S_GATE_URL', ctx.gate_url),
            'perf_runner_url': os.getenv('K8S_PERF_RUNNER_URL', ctx.perf_runner_url),
            'security_runner_url': os.getenv('K8S_SECURITY_RUNNER_URL', ctx.security_runner_url),
            'contracts_dir': os.getenv('K8S_CONTRACTS_DIR', '/contracts'),
            'baseline_run_id': ctx.baseline_run_id,
        }
        return payload


def _rewrite_host(url: str, host: str) -> str:
    if not url:
        return url
    if url.startswith('http://localhost'):
        return url.replace('http://localhost', f'http://{host}')
    if url.startswith('http://127.0.0.1'):
        return url.replace('http://127.0.0.1', f'http://{host}')
    if url.startswith('https://localhost'):
        return url.replace('https://localhost', f'https://{host}')
    if url.startswith('https://127.0.0.1'):
        return url.replace('https://127.0.0.1', f'https://{host}')
    return url


def select_executor(
    run_executor: str | None,
    runner_name: str,
    k8s_executor: K8sJobExecutor | None,
    local_executor: LocalExecutor,
) -> Executor:
    if run_executor == 'k8s' and runner_name in {'replay', 'perf'} and k8s_executor:
        return k8s_executor
    if run_executor == 'k8s' and runner_name not in {'replay', 'perf'}:
        # TODO: route security/compat to k8s job when images are ready.
        return local_executor
    return local_executor
