FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    MINORI_PROJECT_ROOT=/app
WORKDIR /app
COPY pyproject.toml requirements.lock README.md ./
COPY backend ./backend
COPY frontend ./frontend
COPY alembic.ini ./
RUN groupadd --gid 10001 minori && useradd --uid 10001 --gid minori --create-home minori \
    && mkdir -p /app/data/runtime && chown -R minori:minori /app/data

FROM base AS backend
RUN python -m pip install --constraint requirements.lock .
COPY data/dummy ./data/dummy
COPY scripts/seed_database.py scripts/check_database.py scripts/verify_matching.py ./scripts/
COPY scripts/verify_reminders.py scripts/reminder_worker.py ./scripts/
COPY scripts/diagnose_reminders.py scripts/prepare_reminder_demo.py scripts/verify_reminder_delivery.py ./scripts/
USER minori
EXPOSE 8000
CMD ["sh", "-c", "python -m alembic upgrade head && exec python -m uvicorn minori.main:create_app --factory --host 0.0.0.0 --port 8000"]

FROM backend AS reminder-test
USER root
RUN python -m pip install --constraint requirements.lock '.[dev,frontend]' \
    && mkdir -p /app/test-results && chown minori:minori /app/test-results
COPY scripts ./scripts
COPY tests ./tests
COPY data/demo ./data/demo
ENV RUFF_CACHE_DIR=/tmp/minori-ruff-cache \
    COVERAGE_FILE=/app/test-results/.coverage
RUN mkdir -p /app/.pytest_cache && chown minori:minori /app/.pytest_cache
USER minori

FROM base AS frontend
RUN python -m pip install --constraint requirements.lock '.[frontend]'
USER minori
WORKDIR /app/frontend
EXPOSE 8501
CMD ["python", "-m", "streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
