#!/bin/bash
# Скрипт запуска всей системы Bonus Education

echo "🚀 Запуск полной системы Bonus Education..."

# Переходим в директорию проекта
cd "$(dirname "$0")"

# Проверяем наличие .env файла
if [ ! -f ".env" ]; then
    echo "❌ Файл .env не найден!"
    echo "Создайте файл .env с токенами:"
    echo "TELEGRAM_BOT_TOKEN=ваш_токен"
    echo "GOOGLE_AI_API_KEY=ваш_ключ"
    exit 1
fi

echo "✅ Конфигурация найдена"
echo "🚀 Запуск системы..."

# Запускаем веб-панель в фоне
echo "🌐 Запуск веб-панели..."
python3 simple_web_panel.py &
WEB_PID=$!

# Ждем немного
sleep 3

# Запускаем бота
echo "🤖 Запуск AI-бота..."
# Безопасная загрузка .env (поддержка пробелов и спецсимволов, без eval)
while IFS= read -r line; do
    [ -z "$line" ] && continue
    case "$line" in \#* ) continue ;; esac
    key="${line%%=*}"
    val="${line#*=}"
    # Обрезаем пробелы вокруг ключа
    key="${key%% }"; key="${key## }"
    [ -z "$key" ] && continue
    export "$key=$val"
done < .env
python3 final_bot.py &
BOT_PID=$!

echo "✅ Система запущена!"
echo "🌐 Веб-панель: http://localhost:8000"
echo "🤖 Бот работает в Telegram"
echo ""
echo "Для остановки нажмите Ctrl+C"

# Обработка сигнала остановки
trap "echo '🛑 Остановка системы...'; kill $WEB_PID $BOT_PID; exit" INT

# Ждем завершения
wait

