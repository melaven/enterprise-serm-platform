# syntax=docker/dockerfile:1.7
# Образ ARQ-воркера без браузерной автоматизации.
ARG PYTHON_VERSION=3.12

# ---- builder: компиляция и установка Python-зависимостей ----------------------------
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update \
    && apt-get install -y --no-install-recommends gcc libffi-dev libssl-dev pkg-config

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY pyproject.toml .
COPY app ./app
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --prefer-binary .

# ---- runtime ------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/srv

COPY --from=builder /opt/venv /opt/venv

# libffi8: рантайм-библиотека для cffi/cryptography, если они собирались из исходников.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libffi8 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

WORKDIR /srv
COPY --chown=app:app app ./app
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app scripts ./scripts
RUN python -m compileall -q app

# Воркер работает не от root.
USER app

CMD ["arq", "app.infrastructure.queue.worker.worker.WorkerSettings"]
