FROM python:3.12-slim
WORKDIR /srv
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .
COPY alembic.ini ./
COPY migrations ./migrations
COPY scripts ./scripts
# Migrate, index the pinned Rule 21 text (the hash-verified PDF if mounted at /data/rules, else the sheet fixture), serve.
CMD ["sh", "-c", "alembic upgrade head && python -m scripts.ingest_rules && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
