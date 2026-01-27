from datetime import datetime

from fastapi import FastAPI, Header
from pydantic import BaseModel

app = FastAPI(title='FlashSale Notify Service')

class NotifyRequest(BaseModel):
    event: str
    payload: dict

@app.get('/health')
def health():
    return {'status': 'ok'}

@app.post('/notify')
def notify(req: NotifyRequest, x_run_id: str | None = Header(default=None), x_trace_id: str | None = Header(default=None)):
    return {
        'status': 'accepted',
        'run_id': x_run_id,
        'trace_id': x_trace_id,
        'event': req.event,
        'received_at': datetime.utcnow().isoformat() + 'Z',
    }
