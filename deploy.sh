#!/usr/bin/env bash
# Релизный деплой Tenable SERM на Ubuntu VPS.
#
# Сделать исполняемым (один раз):   chmod +x deploy.sh
# Запуск:                           ./deploy.sh [--clean] [--no-migrate] [-h|--help]
#   --clean       пересобрать образы без кэша (--no-cache --pull) и удалить старые образы/кэш сборки
#   --no-migrate  пропустить накатку SQL-миграций
#
# Порядок: проверки -> build -> postgres/redis -> миграции -> up -d остальных сервисов -> проверка.
# Миграции идут ДО старта нового api/worker: новый код никогда не работает на старой схеме.

set -Eeuo pipefail

COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env"
ENV_TEMPLATE=".env.prod.example"
WAIT_TIMEOUT=180
# Без этих значений стек не стартует (совпадает с ${VAR:?} в compose + DATABASE_URL приложения).
REQUIRED_VARS=(SERVER_NAME TLS_CERT_DIR REDIS_PASSWORD POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB DATABASE_URL SUPABASE_URL BROWSERLESS_TOKEN)

# --- цвета (только в терминале) ---
if [[ -t 1 ]]; then
  RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[0;33m'; BLUE=$'\033[0;34m'; NC=$'\033[0m'
else
  RED=""; GREEN=""; YELLOW=""; BLUE=""; NC=""
fi
info() { echo "${BLUE}[..]${NC} $*"; }
ok()   { echo "${GREEN}[OK]${NC} $*"; }
warn() { echo "${YELLOW}[!!]${NC} $*" >&2; }
fail() { echo "${RED}[ERROR]${NC} $*" >&2; exit 1; }

on_error() {
  local code=$? line=$1
  echo "${RED}[ERROR] Деплой прерван (строка ${line}, код ${code}). Текущее состояние: docker compose -f ${COMPOSE_FILE} ps${NC}" >&2
  echo "${RED}        Логи: docker compose -f ${COMPOSE_FILE} logs --tail=100 api worker nginx${NC}" >&2
  exit "$code"
}
trap 'on_error $LINENO' ERR

CLEAN=0
MIGRATE=1
for arg in "$@"; do
  case "$arg" in
    --clean) CLEAN=1 ;;
    --no-migrate) MIGRATE=0 ;;
    -h|--help) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) fail "Неизвестный аргумент: $arg (см. --help)" ;;
  esac
done

cd "$(dirname "$(readlink -f "$0")")"

# Один деплой за раз.
exec 9>/tmp/tenable-deploy.lock
flock -n 9 || fail "Другой деплой уже выполняется."

# --- 1. окружение ---
command -v docker >/dev/null 2>&1 || fail "Docker не установлен."
docker compose version >/dev/null 2>&1 || fail "Нужен плагин docker compose v2 (apt install docker-compose-plugin)."
docker info >/dev/null 2>&1 || fail "Нет доступа к демону Docker (запусти от root/пользователя из группы docker)."
[[ -f "$COMPOSE_FILE" ]] || fail "Не найден $COMPOSE_FILE (запускай из корня проекта)."

if [[ ! -f "$ENV_FILE" ]]; then
  [[ -f "$ENV_TEMPLATE" ]] || fail "Нет ни $ENV_FILE, ни шаблона $ENV_TEMPLATE."
  cp "$ENV_TEMPLATE" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  warn "Создан $ENV_FILE из $ENV_TEMPLATE. Заполни ВСЕ значения (секреты, домен, DATABASE_URL) и запусти ./deploy.sh снова."
  exit 1
fi
chmod 600 "$ENV_FILE"

# Читаем значение из .env без исполнения файла: последнее вхождение, без комментария и кавычек.
env_get() {
  local line
  line=$(grep -E "^[[:space:]]*$1=" "$ENV_FILE" | tail -n1 || true)
  line="${line#*=}"
  line="${line%%[[:space:]]#*}"
  line="${line#"${line%%[![:space:]]*}"}"; line="${line%"${line##*[![:space:]]}"}"
  line="${line#\"}"; line="${line%\"}"; line="${line#\'}"; line="${line%\'}"
  printf '%s' "$line"
}

missing=()
for var in "${REQUIRED_VARS[@]}"; do
  [[ -n "$(env_get "$var")" ]] || missing+=("$var")
done
((${#missing[@]} == 0)) || fail "В $ENV_FILE не заполнено: ${missing[*]}"

[[ "$(env_get SERVER_NAME)" != *example.com* ]] || fail "SERVER_NAME всё ещё example.com: укажи свой домен."

cert_dir="$(env_get TLS_CERT_DIR)"
for f in fullchain.pem privkey.pem; do
  [[ -r "$cert_dir/$f" ]] || fail "Нет $cert_dir/$f: без сертификата nginx не стартует (выпусти через certbot --webroot -w ./nginx/acme)."
done
ok "Окружение проверено"

dc() { docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"; }
dc config -q
ok "Конфигурация compose валидна"

# --- 2. сборка ---
if ((CLEAN)); then
  info "Сборка без кэша (--clean)..."
  dc build --no-cache --pull
  info "Удаляю старые образы и кэш сборки..."
  docker image prune -f >/dev/null
  docker builder prune -f >/dev/null
else
  info "Сборка образов..."
  dc build
fi
ok "Образы собраны"

# --- 3. инфраструктура, затем миграции ---
info "Запуск postgres и redis..."
dc up -d --wait --wait-timeout "$WAIT_TIMEOUT" postgres redis
ok "postgres и redis healthy"

if ((MIGRATE)); then
  info "Накатка SQL-миграций (scripts/migrate.py)..."
  # run --rm --no-deps: одноразовый контейнер из свежесобранного образа; не зависит от того, запущен ли api.
  dc run --rm --no-deps -T api python scripts/migrate.py
  ok "Миграции применены"
else
  warn "Миграции пропущены (--no-migrate)"
fi

# --- 4. остальные сервисы ---
info "Запуск api, worker, nginx..."
dc up -d --remove-orphans --wait --wait-timeout "$WAIT_TIMEOUT"
ok "Все сервисы healthy"

# --- 5. проверка ---
dc ps
if command -v curl >/dev/null 2>&1; then
  curl -fsS --max-time 5 http://127.0.0.1/nginx-health >/dev/null \
    && ok "nginx отвечает на :80" \
    || fail "nginx не отвечает на 127.0.0.1:80"
fi

echo "${GREEN}[OK] Деплой завершён: https://$(env_get SERVER_NAME)${NC}"
