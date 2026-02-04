FROM python:3.11-slim

WORKDIR /app

COPY replaygate-platform/runner-job/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY replaygate-platform/runner-job/app/runner_job.py /app/runner_job.py
COPY replaygate-platform/replay-worker/app/runner_registry.py /app/runner_registry.py
COPY runners /app/runners

ENV PYTHONPATH=/app

CMD ["python", "/app/runner_job.py"]
