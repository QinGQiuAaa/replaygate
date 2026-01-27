import json
import os
import time
import uuid
from datetime import datetime

import redis
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint, create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql+psycopg2://postgres:postgres@localhost:5432/replaygate')
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

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

class Inventory(Base):
    __tablename__ = 'fs_inventory'
    sku = Column(String, primary_key=True)
    qty = Column(Integer, nullable=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

class InventoryMovement(Base):
    __tablename__ = 'fs_inventory_movements'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    sku = Column(String, nullable=False)
    qty = Column(Integer, nullable=False)
    inventory_after = Column(Integer, nullable=True)
    run_id = Column(String, nullable=True)
    trace_id = Column(String, nullable=True)
    idempotency_key = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint('idempotency_key', name='uq_inventory_idemp'),)

class ReserveRequest(BaseModel):
    sku: str
    qty: int

app = FastAPI(title='FlashSale Inventory Service')

@app.on_event('startup')
def on_startup():
    wait_for_db()
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        if not session.query(Inventory).filter_by(sku='SKU-1').first():
            session.add(Inventory(sku='SKU-1', qty=1000))
            session.commit()

@app.get('/health')
def health():
    return {'status': 'ok'}

@app.get('/inventory/{sku}')
def get_inventory(sku: str):
    with SessionLocal() as session:
        inv = session.query(Inventory).filter_by(sku=sku).first()
        if not inv:
            raise HTTPException(status_code=404, detail='SKU not found')
        return {'sku': inv.sku, 'qty': inv.qty}

@app.post('/reserve')
def reserve(req: ReserveRequest, x_run_id: str | None = Header(default=None), x_trace_id: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)):
    if not idempotency_key:
        raise HTTPException(status_code=400, detail='Idempotency-Key header required')

    cache_key = f'idemp:{idempotency_key}'
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    with SessionLocal() as session:
        existing = session.query(InventoryMovement).filter_by(idempotency_key=idempotency_key).first()
        if existing:
            response = {
                'reservation_id': existing.id,
                'sku': existing.sku,
                'qty_reserved': existing.qty,
                'inventory_after': existing.inventory_after,
                'run_id': existing.run_id,
                'trace_id': existing.trace_id,
                'timestamp': existing.created_at.isoformat() + 'Z',
            }
            redis_client.set(cache_key, json.dumps(response), ex=86400)
            return response

        inv = session.query(Inventory).filter_by(sku=req.sku).with_for_update().first()
        if not inv:
            raise HTTPException(status_code=404, detail='SKU not found')
        if req.qty <= 0:
            raise HTTPException(status_code=400, detail='qty must be > 0')
        if inv.qty < req.qty:
            raise HTTPException(status_code=409, detail='insufficient inventory')

        inv.qty -= req.qty
        inv.updated_at = datetime.utcnow()
        movement = InventoryMovement(
            sku=req.sku,
            qty=req.qty,
            inventory_after=inv.qty,
            run_id=x_run_id,
            trace_id=x_trace_id,
            idempotency_key=idempotency_key,
        )
        session.add(movement)
        session.commit()

        response = {
            'reservation_id': movement.id,
            'sku': movement.sku,
            'qty_reserved': movement.qty,
            'inventory_after': inv.qty,
            'run_id': movement.run_id,
            'trace_id': movement.trace_id,
            'timestamp': movement.created_at.isoformat() + 'Z',
        }
        redis_client.set(cache_key, json.dumps(response), ex=86400)
        return response

@app.post('/internal/cleanup/{run_id}')
def cleanup(run_id: str):
    with SessionLocal() as session:
        movements = session.query(InventoryMovement).filter_by(run_id=run_id).all()
        restored = 0
        for mv in movements:
            inv = session.query(Inventory).filter_by(sku=mv.sku).with_for_update().first()
            if inv:
                inv.qty += mv.qty
                inv.updated_at = datetime.utcnow()
                restored += mv.qty
            session.delete(mv)
        session.commit()
    return {'status': 'ok', 'run_id': run_id, 'restored_qty': restored, 'cleaned_at': datetime.utcnow().isoformat() + 'Z'}

