FROM zaproxy/zap-stable
USER root
WORKDIR /app
COPY requirements.txt /tmp/requirements.txt
RUN apt-get update \
  && apt-get install -y --no-install-recommends python3-pip nodejs npm \
  && pip3 install --no-cache-dir --break-system-packages -r /tmp/requirements.txt \
  && pip3 install --no-cache-dir --break-system-packages bandit \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*
COPY app ./app
ENV PYTHONUNBUFFERED=1
EXPOSE 8094
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8094"]
