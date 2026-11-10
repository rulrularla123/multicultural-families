FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY pyproject.toml ./
COPY app ./app
COPY ingest ./ingest
COPY scripts ./scripts
COPY data ./data
RUN pip install -e .
COPY alembic.ini ./
COPY alembic ./alembic
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
