FROM python:3.12-slim
WORKDIR /app
COPY korail2 ./korail2
COPY SRT ./SRT
COPY train ./train
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir -e .
ENV PYTHONUNBUFFERED=1
# Override at deploy: train watch --carrier srt ...
CMD ["train", "doctor"]
