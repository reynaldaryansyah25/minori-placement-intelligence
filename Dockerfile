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
USER minori
EXPOSE 8000
CMD ["sh", "-c", "python -m alembic upgrade head && exec python -m uvicorn minori.main:create_app --factory --host 0.0.0.0 --port 8000"]

FROM base AS frontend
RUN python -m pip install --constraint requirements.lock '.[frontend]'
USER minori
WORKDIR /app/frontend
EXPOSE 8501
CMD ["python", "-m", "streamlit", "run", "minori_frontend/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
