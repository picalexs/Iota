# syntax=docker/dockerfile:1.7

FROM python:3.12-slim

ENV PIP_DEFAULT_TIMEOUT=300 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_RETRIES=10 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

ENV PYTHONPATH=/app

COPY backend/requirements.txt .
COPY shared /app/shared
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install -r requirements.txt

COPY backend/. .

RUN chmod +x /app/entrypoint.sh \
    && groupadd --gid 10001 appuser \
    && useradd --uid 10001 --gid appuser --home-dir /app --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/local-state /app/local-operator \
    && chown -R appuser:appuser /app

EXPOSE 8000

USER appuser

# entrypoint.sh runs DB init (migrations + seed) then execs CMD.
ENTRYPOINT ["/app/entrypoint.sh"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
