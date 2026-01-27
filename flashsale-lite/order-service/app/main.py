import json
import os
import time
import uuid
from datetime import datetime

import httpx
import redis
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint, create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql+psycopg2://postgres:postgres@localhost:5432/replaygate')
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
INVENTORY_SERVICE_URL = os.getenv('INVENTORY_SERVICE_URL', 'http://localhost:8002')
NOTIFY_SERVICE_URL = os.getenv('NOTIFY_SERVICE_URL', 'http://localhost:8003')

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()

redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

def wait_for_db():
    for _ in range(10):
        try:
            with engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            return
        except Exception:
            time.sleep(2)
    raise RuntimeError('Database not ready')

class Order(Base):
    __tablename__ = 'fs_orders'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    sku = Column(String, nullable=False)
    qty = Column(Integer, nullable=False)
    total_price = Column(Integer, nullable=False)
    status = Column(String, nullable=False)
    run_id = Column(String, nullable=True)
    trace_id = Column(String, nullable=True)
    idempotency_key = Column(String, nullable=False)
    app_version = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint('idempotency_key', name='uq_order_idemp'),)

class OrderRequest(BaseModel):
    sku: str
    qty: int
    user_id: str

app = FastAPI(title='FlashSale Order Service')

@app.on_event('startup')
def on_startup():
    wait_for_db()
    Base.metadata.create_all(bind=engine)

@app.get('/health')
def health():
    return {'status': 'ok'}

@app.post('/orders')
def create_order(req: OrderRequest, x_run_id: str | None = Header(default=None), x_trace_id: str | None = Header(default=None), idempotency_key: str | None = Header(default=None), x_app_version: str | None = Header(default='v1')):
    if not idempotency_key:
        raise HTTPException(status_code=400, detail='Idempotency-Key header required')

    cache_key = f'idemp:{idempotency_key}'
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    with SessionLocal() as session:
        existing = session.query(Order).filter_by(idempotency_key=idempotency_key).first()
        if existing:
            response = {
                'order_id': existing.id,
                'status': existing.status,
                'sku': existing.sku,
                'qty': existing.qty,
                'total_price': existing.total_price,
                'run_id': existing.run_id,
                'trace_id': existing.trace_id,
                'app_version': existing.app_version,
                'timestamp': existing.created_at.isoformat() + 'Z',
            }
            redis_client.set(cache_key, json.dumps(response), ex=86400)
            return response

        if req.qty <= 0:
            raise HTTPException(status_code=400, detail='qty must be > 0')

        inv_key = f'inv-{idempotency_key}'
        headers = {
            'Idempotency-Key': inv_key,
        }
        if x_run_id:
            headers['X-Run-Id'] = x_run_id
        if x_trace_id:
            headers['X-Trace-Id'] = x_trace_id
        try:
            inv_resp = httpx.post(f'{INVENTORY_SERVICE_URL}/reserve', json={'sku': req.sku, 'qty': req.qty}, headers=headers, timeout=5)
            inv_resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f'inventory error: {exc}')

        base_price = 100
        version = x_app_version or 'v1'
        if version == 'v2':
            total_price = int(base_price * req.qty * 1.1)
        else:
            total_price = int(base_price * req.qty)

        order = Order(
            user_id=req.user_id,
            sku=req.sku,
            qty=req.qty,
            total_price=total_price,
            status='CREATED',
            run_id=x_run_id,
            trace_id=x_trace_id,
            idempotency_key=idempotency_key,
            app_version=version,
        )
        session.add(order)
        session.commit()

        try:
            notify_headers = {}
            if x_run_id:
                notify_headers['X-Run-Id'] = x_run_id
            if x_trace_id:
                notify_headers['X-Trace-Id'] = x_trace_id
            httpx.post(
                f'{NOTIFY_SERVICE_URL}/notify',
                json={'event': 'order_created', 'payload': {'order_id': order.id, 'sku': order.sku, 'qty': order.qty}},
                headers=notify_headers,
                timeout=2,
            )
        except Exception:
            pass

        response = {
            'order_id': order.id,
            'status': order.status,
            'sku': order.sku,
            'qty': order.qty,
            'total_price': order.total_price,
            'run_id': order.run_id,
            'trace_id': order.trace_id,
            'app_version': order.app_version,
            'timestamp': order.created_at.isoformat() + 'Z',
        }
        redis_client.set(cache_key, json.dumps(response), ex=86400)
        return response

@app.post('/internal/cleanup/{run_id}')
def cleanup(run_id: str):
    with SessionLocal() as session:
        orders = session.query(Order).filter_by(run_id=run_id).all()
        count = len(orders)
        for order in orders:
            session.delete(order)
        session.commit()
    return {'status': 'ok', 'run_id': run_id, 'orders_deleted': count, 'cleaned_at': datetime.utcnow().isoformat() + 'Z'}

