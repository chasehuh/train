FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir \
    "requests>=2.32.0" \
    "psycopg[binary]>=3.2.0" \
    "cryptography>=44.0.0" \
    "pycryptodome>=3.21.0"

COPY db/ ./db/
COPY src/ ./src/
COPY worker/ ./worker/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
ENV WORKER_MODE=queue

CMD ["python", "-m", "worker.main"]
