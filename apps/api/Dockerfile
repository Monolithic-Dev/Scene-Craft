FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps needed by psycopg2 at build time.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src
RUN pip install .

COPY alembic.ini ./
COPY alembic ./alembic

# Cloud Run injects PORT; default to 8080 for local parity.
ENV PORT=8080
EXPOSE 8080

# Run migrations then start the server. In a real deployment this migrate
# step is usually a separate Cloud Run job/pre-deploy hook rather than
# baked into the container start command — kept inline here for the
# hackathon submission's single-command simplicity.
CMD ["sh", "-c", "python -m alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port ${PORT}"]
