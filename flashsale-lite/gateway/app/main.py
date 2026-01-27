import json
import os
import uuid
from datetime import datetime

import httpx
import redis
from fastapi import FastAPI, Header, HTTPException, Request

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
ORDER_SERVICE_URL = os.getenv('ORDER_SERVICE_URL', 'http://localhost:8001')
INVENTORY_SERVICE_URL = os.getenv('INVENTORY_SERVICE_URL', 'http://localhost:8002')
NOTIFY_SERVICE_URL = os.getenv('NOTIFY_SERVICE_URL', 'http://localhost:8003')

redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

app = FastAPI(title='FlashSale Gateway')

@app.get('/health')
def health():
    return {'status': 'ok'}

def record_if_needed(recording_id: str, request_payload: dict, response_payload: dict, replay_mode: bool):
    if replay_mode:
        return
    key = f'recording:{recording_id}'
    entry = {
        'id': str(uuid.uuid4()),
        'recorded_at': datetime.utcnow().isoformat() + 'Z',
        'request': request_payload,
        'response': response_payload,
    }
    redis_client.rpush(key, json.dumps(entry))

@app.post('/api/orders')
async def create_order(request: Request, x_run_id: str | None = Header(default=None), x_trace_id: str | None = Header(default=None), idempotency_key: str | None = Header(default=None), x_recording_id: str | None = Header(default='default'), x_app_version: str | None = Header(default='v1'), x_replay_mode: str | None = Header(default=None)):
    body = await request.json()
    if not idempotency_key:
        idempotency_key = f'gw-{uuid.uuid4()}'

    headers = {
        'Idempotency-Key': idempotency_key,
        'X-App-Version': x_app_version or 'v1',
    }
    if x_run_id:
        headers['X-Run-Id'] = x_run_id
    if x_trace_id:
        headers['X-Trace-Id'] = x_trace_id

    try:
        resp = httpx.post(f'{ORDER_SERVICE_URL}/orders', json=body, headers=headers, timeout=5)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f'order-service error: {exc}')

    response_payload = resp.json()
    record_if_needed(
        x_recording_id or 'default',
        {
            'method': 'POST',
            'path': '/api/orders',
            'headers': {'content-type': 'application/json'},
            'body': body,
        },
        {'status_code': resp.status_code, 'body': response_payload},
        replay_mode=(x_replay_mode == 'true'),
    )
    return response_payload

@app.get('/api/inventory/{sku}')
async def get_inventory(sku: str, x_recording_id: str | None = Header(default='default'), x_replay_mode: str | None = Header(default=None)):
    try:
        resp = httpx.get(f'{INVENTORY_SERVICE_URL}/inventory/{sku}', timeout=5)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f'inventory-service error: {exc}')

    response_payload = resp.json()
    record_if_needed(
        x_recording_id or 'default',
        {
            'method': 'GET',
            'path': f'/api/inventory/{sku}',
            'headers': {},
            'body': None,
        },
        {'status_code': resp.status_code, 'body': response_payload},
        replay_mode=(x_replay_mode == 'true'),
    )
    return response_payload

@app.get('/api/recordings/{recording_id}')
def get_recording(recording_id: str):
    key = f'recording:{recording_id}'
    entries = redis_client.lrange(key, 0, -1)
    return {'recording_id': recording_id, 'items': [json.loads(e) for e in entries]}

@app.post('/api/recordings/{recording_id}/clear')
def clear_recording(recording_id: str):
    key = f'recording:{recording_id}'
    redis_client.delete(key)
    return {'status': 'ok', 'recording_id': recording_id}
