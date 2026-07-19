#!/usr/bin/env bash
# Ротация одного секрета PG Control Center «одной командой».
#
#   scripts/rotate_secret.sh <appdb|redis|rabbitmq|jwt|fernet>
#
# Что делает:
#   1) генерирует новый секрет (внутри backend-контейнера — без зависимости
#      от локального python и с нужными библиотеками для Fernet);
#   2) для appdb — выполняет ЖИВОЙ ALTER (том appdb_data не даёт переприменить
#      POSTGRES_PASSWORD, поэтому меняем пароль в работающей БД);
#   3) правит нужную переменную в .env (пароли — единственный источник правды,
#      полные URL собираются из них в app/config.py);
#   4) пересоздаёт затронутые сервисы.
#
# Запуск (из корня pgadmin-system или откуда угодно):
#   bash scripts/rotate_secret.sh redis
set -euo pipefail

cd "$(dirname "$0")/.."   # корень pgadmin-system

target="${1:-}"
case "$target" in
  appdb|redis|rabbitmq|jwt|fernet) ;;
  *)
    echo "Использование: $0 <appdb|redis|rabbitmq|jwt|fernet>" >&2
    exit 1
    ;;
esac

[ -f .env ] || { echo "Нет .env в $(pwd)" >&2; exit 1; }

# ── генерация секрета внутри backend-контейнера ──
gen() {
  local kind="$1"
  if [ "$kind" = "fernet" ]; then
    docker compose run --rm --no-deps -T backend \
      python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  else
    local len=24
    [ "$kind" = "jwt" ] && len=48
    docker compose run --rm --no-deps -T backend \
      python -c "import secrets; print(secrets.token_urlsafe($len))"
  fi
}

# ── заменить/добавить строку KEY=VALUE в .env ──
set_env() {
  local key="$1" val="$2"
  local esc
  esc=$(printf '%s' "$val" | sed -e 's/[&|\\]/\\&/g')   # экранируем для sed-замены
  if grep -q "^${key}=" .env; then
    sed -i.bak "s|^${key}=.*|${key}=${esc}|" .env && rm -f .env.bak
  else
    echo "${key}=${val}" >> .env
  fi
}

new="$(gen "$target" | tr -d '\r')"
[ -n "$new" ] || { echo "Не удалось сгенерировать секрет" >&2; exit 1; }
echo "Новый секрет для '$target' сгенерирован."

case "$target" in
  appdb)
    echo "Живой ALTER пароля pgadmin в appdb…"
    docker compose exec -T appdb psql -U pgadmin -d pgadmin \
      -c "ALTER USER pgadmin PASSWORD '${new}';"
    set_env APPDB_PASSWORD "$new"
    svc="appdb backend worker scheduler"
    ;;
  redis)
    set_env REDIS_PASSWORD "$new"
    svc="redis backend worker scheduler"
    ;;
  rabbitmq)
    set_env RABBITMQ_PASSWORD "$new"
    svc="rabbitmq backend worker scheduler"
    ;;
  jwt)
    set_env JWT_SECRET "$new"
    svc="backend"
    ;;
  fernet)
    echo "ВНИМАНИЕ: смена FERNET_KEY сделает НЕЧИТАЕМЫМИ уже сохранённые пароли серверов." >&2
    read -r -p "Точно продолжить? (yes/no) " ok
    [ "$ok" = "yes" ] || { echo "Отменено."; exit 1; }
    set_env FERNET_KEY "$new"
    svc="backend worker scheduler"
    ;;
esac

echo "Пересоздаю сервисы: $svc"
# shellcheck disable=SC2086
docker compose up -d --force-recreate $svc

echo "Готово: секрет '$target' обновлён."
[ "$target" = "jwt" ] && echo "Выданные JWT инвалидированы — пользователям нужен перелогин."
exit 0
