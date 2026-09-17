# Control plane only. Workers are Railway sandboxes booted from a checkpoint
# (see scripts/checkpoint.sh); they never run this image.
FROM python:3.12-slim
WORKDIR /app
COPY korail2 ./korail2
COPY train ./train
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir ".[server]"
ENV PYTHONUNBUFFERED=1
CMD ["sh", "-c", "uvicorn train.server.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
