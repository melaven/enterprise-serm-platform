# syntax=docker/dockerfile:1.7
# Один образ для API и ARQ-воркера: команда запуска задаётся в docker-compose.prod.yml.
ARG PYTHON_VERSION=3.12

# ---- builder: компиляция и установка зависимостей в venv --------------------------
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=0

# Компилятор и заголовки нужны только пакетам без готового wheel (cryptography/cffi и т.п.).
# В финальный образ не попадают.
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

# ---- runtime: без компилятора, запуск не от root ------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime

# libffi8: рантайм-библиотека для cffi/cryptography, если они собирались из исходников.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libffi8 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/srv

COPY --from=builder /opt/venv /opt/venv

WORKDIR /srv
# Состав образа определяет .dockerignore (без .env, тестов, кэшей).
COPY --chown=app:app app ./app
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app scripts ./scripts
# Байт-код собираем на этапе сборки: корневая ФС в проде read-only, во время работы .pyc писать некуда.
RUN python -m compileall -q app

USER app
EXPOSE 8000

# Healthcheck образа (compose может переопределить): TCP-порт API.
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD ["python", "-c", "import socket; socket.create_connection(('127.0.0.1', 8000), 3).close()"]

# По умолчанию API; воркер переопределяет command в compose.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
