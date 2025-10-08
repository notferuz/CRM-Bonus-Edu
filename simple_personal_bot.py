#!/usr/bin/env python3
"""
Простой персональный AI-ассистент для Telegram
Работает с вашим личным аккаунтом через Telethon
"""

import asyncio
import logging
import os
from datetime import datetime
from dotenv import load_dotenv
from personal_telegram_assistant import PersonalTelegramAssistant

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def main():
    """Главная функция для запуска персонального ассистента"""
    try:
        from telethon import TelegramClient, events
        from telethon.sessions import StringSession
        
        # Получаем данные из .env
        api_id = int(os.getenv('TELEGRAM_API_ID'))
        api_hash = os.getenv('TELEGRAM_API_HASH')
        phone_number = os.getenv('TELEGRAM_PHONE_NUMBER')
        
        if not all([api_id, api_hash, phone_number]):
            logger.error("❌ Не все Telegram API данные настроены в .env файле")
            return
        
        logger.info(f"📱 Подключение к аккаунту: {phone_number}")
        
        # Создаем клиент
        client = TelegramClient('personal_assistant_session', api_id, api_hash)
        
        # Инициализируем AI ассистента
        assistant = PersonalTelegramAssistant()
        
        # Запускаем клиент
        await client.start(phone=phone_number)
        
        # Получаем информацию о себе
        me = await client.get_me()
        logger.info(f"✅ Авторизован как: {me.first_name} {me.last_name or ''} (@{me.username or 'без username'})")
        logger.info(f"🆔 Ваш User ID: {me.id}")
        
        # Обновляем .env с вашим User ID
        env_content = ""
        with open('.env', 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        updated = False
        for i, line in enumerate(lines):
            if line.startswith('TELEGRAM_USER_ID='):
                lines[i] = f'TELEGRAM_USER_ID={me.id}\n'
                updated = True
                break
        
        if not updated:
            lines.append(f'TELEGRAM_USER_ID={me.id}\n')
        
        with open('.env', 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        logger.info("✅ User ID сохранен в .env файл")
        
        @client.on(events.NewMessage(incoming=True))
        async def handle_new_message(event):
            try:
                # Получаем данные сообщения
                message = event.message
                user_data = await event.get_sender()
                
                # Пропускаем сообщения от ботов
                if user_data.bot:
                    return
                
                # Пропускаем сообщения от себя
                if user_data.id == me.id:
                    return
                
                text = message.text
                if not text:
                    return
                
                logger.info(f"📨 Новое сообщение от {user_data.first_name}: {text[:50]}...")
                
                # Подготавливаем данные пользователя
                user_info = {
                    'id': user_data.id,
                    'first_name': user_data.first_name,
                    'last_name': user_data.last_name,
                    'username': user_data.username
                }
                
                # Показываем индикатор "печатает" пока формируется ответ
                async with client.action(event.chat_id, 'typing'):
                    response = assistant.process_message(user_info, text)

                # Отправляем ответ сразу после генерации
                await event.reply(response)
                logger.info(f"✅ Ответ отправлен: {response[:50]}...")
                
            except Exception as e:
                logger.error(f"❌ Ошибка обработки сообщения: {e}")
        
        logger.info("🚀 Персональный AI-ассистент запущен!")
        logger.info("📱 Ожидание сообщений...")
        logger.info("🛑 Для остановки нажмите Ctrl+C")
        
        # Запускаем клиент
        await client.run_until_disconnected()
        
    except ImportError:
        logger.error("❌ Telethon не установлен. Установите: pip3 install telethon")
    except Exception as e:
        logger.error(f"❌ Ошибка запуска: {e}")
        logger.error("Проверьте правильность API данных в .env файле")

if __name__ == "__main__":
    print("🤖 Персональный Telegram AI-ассистент для Bonus Education")
    print("📱 Работает как ваш личный аккаунт")
    print("")
    
    # Проверяем наличие необходимых переменных
    required_vars = ['TELEGRAM_API_ID', 'TELEGRAM_API_HASH', 'TELEGRAM_PHONE_NUMBER']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("❌ Отсутствуют необходимые переменные окружения:")
        for var in missing_vars:
            print(f"   - {var}")
        print("")
        print("📝 Проверьте файл .env")
        exit(1)
    
    # Запускаем бота
    asyncio.run(main())
