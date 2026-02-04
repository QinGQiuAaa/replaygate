FROM python:3.11-slim
WORKDIR /app
RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates curl \
  && curl -L https://github.com/grafana/k6/releases/download/v0.49.0/k6-v0.49.0-linux-amd64.tar.gz \
    | tar -xz -C /tmp \
  && mv /tmp/k6-v0.49.0-linux-amd64/k6 /usr/local/bin/k6 \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/* /tmp/k6-v0.49.0-linux-amd64
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
ENV PYTHONUNBUFFERED=1
EXPOSE 8093
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8093"]
