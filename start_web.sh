#!/bin/bash
# Скрипт запуска веб-панели для Bonus Education

echo "🌐 Запуск веб-панели Bonus Education..."

# Переходим в директорию проекта
cd "$(dirname "$0")"

echo "🚀 Запуск веб-панели на http://localhost:8000"

# Запускаем веб-панель
python3 simple_web_panel.py

