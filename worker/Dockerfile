# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS builder

ENV RUSTUP_HOME=/opt/rustup \
	CARGO_HOME=/opt/cargo \
	PATH=/opt/cargo/bin:${PATH} \
	PIP_DEFAULT_TIMEOUT=300 \
	PIP_DISABLE_PIP_VERSION_CHECK=1 \
	PIP_RETRIES=10

WORKDIR /build

RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
		build-essential \
		cmake \
		curl \
		gfortran \
		libopenblas-dev \
	&& rm -rf /var/lib/apt/lists/*

RUN curl -sSfL https://sh.rustup.rs -o /tmp/rustup-init.sh \
	&& sh /tmp/rustup-init.sh -y --profile minimal --default-toolchain stable \
	&& rm -f /tmp/rustup-init.sh

COPY worker/requirements.lock .
RUN --mount=type=cache,target=/root/.cache/pip \
	python -m pip wheel --wheel-dir /wheels -r requirements.lock

FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	PYTHONPATH=/app \
	PIP_DEFAULT_TIMEOUT=300 \
	PIP_DISABLE_PIP_VERSION_CHECK=1 \
	PIP_RETRIES=10

RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
		libgfortran5 \
		libgomp1 \
		libopenblas0-pthread \
	&& rm -rf /var/lib/apt/lists/*

COPY worker/requirements.lock .
COPY shared /app/shared
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.lock \
	&& rm -rf /wheels

COPY worker/. /app/worker
COPY worker/docker-entrypoint.sh /app/docker-entrypoint.sh
RUN groupadd --gid 10001 appuser \
	&& useradd --uid 10001 --gid appuser --home-dir /app --shell /usr/sbin/nologin appuser \
	&& mkdir -p /app/local-state \
	&& chmod +x /app/docker-entrypoint.sh \
	&& chown -R appuser:appuser /app

USER appuser

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "-m", "worker.main"]
