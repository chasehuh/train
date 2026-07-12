FROM python:3.11-slim

WORKDIR /app

# Install runtime deps (requests + transitive). Keep image lean.
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir "requests>=2.32.0"

# Vendored SRT client + smoke worker
COPY src/ ./src/
COPY worker/ ./worker/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

# Worker process (not HTTP). Optional health on $PORT if Railway sets it.
CMD ["python", "-m", "worker.main"]
