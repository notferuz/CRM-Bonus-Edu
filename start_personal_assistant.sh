#!/bin/bash
# Скрипт запуска персонального AI-ассистента Bonus Education

echo "🚀 Запуск персонального AI-ассистента Bonus Education..."

# Переходим в директорию проекта
cd "$(dirname "$0")"

# Проверяем наличие .env файла
if [ ! -f ".env" ]; then
    echo "❌ Файл .env не найден!"
    echo "Создайте файл .env с API данными Telegram"
    exit 1
fi

echo "✅ Конфигурация найдена"

# Проверяем наличие необходимых зависимостей
echo "🔍 Проверка зависимостей..."

if ! python3 -c "import telethon" 2>/dev/null; then
    echo "📦 Установка Telethon..."
    pip3 install telethon
fi

if ! python3 -c "import google.generativeai" 2>/dev/null; then
    echo "📦 Установка Google AI..."
    pip3 install google-generativeai
fi

if ! python3 -c "import dotenv" 2>/dev/null; then
    echo "📦 Установка python-dotenv..."
    pip3 install python-dotenv
fi

echo "✅ Все зависимости установлены"

# Запускаем веб-панель в фоне
echo "🌐 Запуск веб-панели..."
python3 simple_web_panel.py &
WEB_PID=$!

# Ждем немного
sleep 3

# Запускаем персональный AI-ассистент
echo "🤖 Запуск персонального AI-ассистента..."
python3 simple_personal_bot.py &
BOT_PID=$!

echo "✅ Система запущена!"
echo "🌐 Веб-панель: http://localhost:8000"
echo "🤖 Персональный AI-ассистент работает в Telegram"
echo ""
echo "📱 Ваш аккаунт будет автоматически отвечать на сообщения"
echo "🛑 Для остановки нажмите Ctrl+C"

# Обработка сигнала остановки
trap "echo '🛑 Остановка системы...'; kill $WEB_PID $BOT_PID 2>/dev/null; exit" INT

# Ждем завершения
wait
