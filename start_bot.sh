#!/bin/bash
# Скрипт запуска AI-бота для Bonus Education

echo "🤖 Запуск AI-бота Bonus Education..."

# Переходим в директорию проекта
cd "$(dirname "$0")"

# Если TELEGRAM_BOT_TOKEN не задан в окружении/.env, берем из первого аргумента (делаем ДО проверок)
if [ -z "$TELEGRAM_BOT_TOKEN" ] && [ -n "$1" ]; then
  export TELEGRAM_BOT_TOKEN="$1"
  echo "ℹ️ Принял TELEGRAM_BOT_TOKEN из аргумента командной строки"
fi

# Если .env есть — подгружаем переменные (опционально)
if [ -f ".env" ]; then
  while IFS= read -r line; do
      [ -z "$line" ] && continue
      case "$line" in \#* ) continue ;; esac
      key="${line%%=*}"
      val="${line#*=}"
      key="${key%% }"; key="${key## }"
      [ -z "$key" ] && continue
      export "$key=$val"
  done < .env
else
  echo "⚠️  Файл .env не найден — продолжаю без него."
fi

# Проверяем токены
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "❌ TELEGRAM_BOT_TOKEN не найден в .env"
    exit 1
fi

if [ -z "$GOOGLE_AI_API_KEY" ]; then
    echo "ℹ️ GOOGLE_AI_API_KEY не найден — бот использует ключ по умолчанию из кода"
fi

echo "✅ Токены найдены"
MASKED_TOKEN="${TELEGRAM_BOT_TOKEN:0:6}******${TELEGRAM_BOT_TOKEN: -4}"
echo "🔐 TELEGRAM_BOT_TOKEN=${MASKED_TOKEN}"
echo "🚀 Запуск бота... (логи пишутся в bot.log)"

# Запускаем бота с прямой передачей stdout/stderr в консоль и файл
python3 -u final_bot.py 2>&1 | tee bot.log

