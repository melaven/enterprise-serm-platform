# Один образ для API и ARQ-воркера: команда запуска задаётся в docker-compose.yml.
ARG PYTHON_VERSION=3.12

# ---- builder: компилируем/ставим зависимости в venv ------------------------------
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Компилятор нужен только для пакетов без готовых wheel; в финальный образ не попадёт.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
# Сначала только requirements: слой с зависимостями кэшируется, пока файл не менялся.
COPY requirements.txt .
RUN pip install --prefer-binary -r requirements.txt

# ---- runtime: минимальный образ без компилятора, запуск не от root --------------------
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/srv

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home \
        --shell /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv

WORKDIR /srv
# Что попадает в образ, определяет .dockerignore (без .env, тестов, кэшей).
COPY --chown=app:app . .

USER app
EXPOSE 8000

# По умолчанию API. Воркер переопределяет command в docker-compose.yml.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
