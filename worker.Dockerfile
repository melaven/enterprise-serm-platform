# syntax=docker/dockerfile:1.7
# Образ ARQ-воркера со скрейперами на Playwright (Chromium). Отдельно от API-образа: браузер добавляет ~500 МБ,
# а API он не нужен.
# Debian bookworm зафиксирован намеренно: Playwright официально поддерживает конкретные релизы ОС, и
# `--with-deps` на «плавающем» slim может не найти пакеты.
ARG PYTHON_VERSION=3.12
# Версия playwright должна совпадать с той, что в requirements.txt (иначе скачаются бинарники не той сборки).
# Лучше закрепить её в requirements.txt (playwright==X.Y.Z); тогда этот ARG ничего не меняет.
# Переопределение: --build-arg PLAYWRIGHT_SPEC=playwright==X.Y.Z
ARG PLAYWRIGHT_SPEC=playwright

# ---- builder: компиляция и установка Python-зависимостей ----------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder
ARG PLAYWRIGHT_SPEC

ENV PIP_DISABLE_PIP_VERSION_CHECK=1

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update \
    && apt-get install -y --no-install-recommends gcc libffi-dev libssl-dev pkg-config

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --prefer-binary -r requirements.txt \
    && pip install --prefer-binary "${PLAYWRIGHT_SPEC}"

# ---- runtime ------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/srv \
    # Бинарники браузера в общий каталог, а не в ~/.cache root: иначе непривилегированный пользователь их не увидит.
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    # Корневая ФС в проде read-only; HOME (профиль/кэш Chromium) указывает на tmpfs.
    HOME=/tmp

COPY --from=builder /opt/venv /opt/venv

# --- ШАГ ОТ ROOT (до USER app): apt-зависимости браузера и скачивание Chromium ---
# `--with-deps` сам ставит системные библиотеки через apt-get (нужен root) и качает Chromium в PLAYWRIGHT_BROWSERS_PATH.
RUN apt-get update \
    && playwright install chromium --with-deps \
    && chmod -R a+rX /ms-playwright \
    && apt-get install -y --no-install-recommends libffi8 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

WORKDIR /srv
COPY --chown=app:app app ./app
COPY --chown=app:app sql ./sql
COPY --chown=app:app scripts ./scripts
RUN python -m compileall -q app

# Только теперь понижаем привилегии: воркер и Chromium работают не от root.
USER app

CMD ["arq", "app.worker.worker.WorkerSettings"]
