#!/usr/bin/env python3
"""
Персональный Telegram AI-ассистент
Работает с вашим личным аккаунтом через Telegram API
"""

import asyncio
import logging
import os
import json
from datetime import datetime
from dotenv import load_dotenv
from personal_telegram_assistant import PersonalTelegramAssistant
import aiohttp
import time

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class PersonalTelegramBot:
    def __init__(self):
        # API данные для работы с Telegram
        self.api_id = os.getenv('TELEGRAM_API_ID')
        self.api_hash = os.getenv('TELEGRAM_API_HASH')
        self.phone_number = os.getenv('TELEGRAM_PHONE_NUMBER')
        
        # Проверяем наличие необходимых данных
        if not all([self.api_id, self.api_hash, self.phone_number]):
            logger.error("❌ Не все Telegram API данные настроены в .env файле")
            logger.error("Нужны: TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE_NUMBER")
            raise ValueError("Не все Telegram API данные настроены")
        
        # Инициализируем AI ассистента
        self.assistant = PersonalTelegramAssistant()
        
        # Состояние сессии
        self.session_file = "telegram_session.json"
        self.session_data = self.load_session()
        
        # Последний обработанный update_id
        self.last_update_id = self.session_data.get('last_update_id', 0)
        
        logger.info("✅ Персональный Telegram AI-ассистент инициализирован")
    
    def load_session(self):
        """Загрузить данные сессии"""
        try:
            if os.path.exists(self.session_file):
                with open(self.session_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Не удалось загрузить сессию: {e}")
        
        return {
            'last_update_id': 0,
            'authorized': False
        }
    
    def save_session(self):
        """Сохранить данные сессии"""
        try:
            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(self.session_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Не удалось сохранить сессию: {e}")
    
    async def get_updates(self):
        """Получить обновления от Telegram"""
        try:
            url = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/getUpdates"
            params = {
                'offset': self.last_update_id + 1,
                'timeout': 30
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('result', [])
                    else:
                        logger.error(f"Ошибка получения обновлений: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Ошибка при получении обновлений: {e}")
            return []
    
    async def send_message(self, chat_id, text):
        """Отправить сообщение"""
        try:
            url = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'HTML'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    if response.status == 200:
                        logger.info(f"✅ Сообщение отправлено в чат {chat_id}")
                        return True
                    else:
                        logger.error(f"Ошибка отправки сообщения: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения: {e}")
            return False
    
    async def process_message(self, update):
        """Обработать входящее сообщение"""
        try:
            message = update.get('message', {})
            if not message:
                return
            
            chat_id = message.get('chat', {}).get('id')
            user_data = message.get('from', {})
            text = message.get('text', '')
            
            if not all([chat_id, user_data, text]):
                return
            
            # Пропускаем сообщения от ботов
            if user_data.get('is_bot', False):
                return
            
            # Пропускаем сообщения от себя (если это ваш аккаунт)
            if user_data.get('id') == int(os.getenv('TELEGRAM_USER_ID', '0')):
                return
            
            logger.info(f"📨 Новое сообщение от {user_data.get('first_name', 'Unknown')}: {text[:50]}...")
            
            # Получаем ответ от AI ассистента
            response = self.assistant.process_message(user_data, text)
            
            # Отправляем ответ
            await self.send_message(chat_id, response)
            
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения: {e}")
    
    async def run(self):
        """Основной цикл работы"""
        logger.info("🚀 Запуск персонального Telegram AI-ассистента...")
        logger.info("📱 Ожидание сообщений...")
        
        while True:
            try:
                # Получаем обновления
                updates = await self.get_updates()
                
                for update in updates:
                    update_id = update.get('update_id', 0)
                    
                    # Обновляем последний обработанный ID
                    if update_id > self.last_update_id:
                        self.last_update_id = update_id
                        self.session_data['last_update_id'] = update_id
                        self.save_session()
                    
                    # Обрабатываем сообщение
                    await self.process_message(update)
                
                # Небольшая пауза между проверками
                await asyncio.sleep(1)
                
            except KeyboardInterrupt:
                logger.info("🛑 Получен сигнал остановки")
                break
            except Exception as e:
                logger.error(f"Ошибка в основном цикле: {e}")
                await asyncio.sleep(5)  # Пауза при ошибке
        
        logger.info("✅ Персональный Telegram AI-ассистент остановлен")


# Альтернативная версия с использованием Telethon (более продвинутая)
class PersonalTelegramBotTelethon:
    def __init__(self):
        try:
            from telethon import TelegramClient, events
            from telethon.sessions import StringSession
            
            self.api_id = os.getenv('TELEGRAM_API_ID')
            self.api_hash = os.getenv('TELEGRAM_API_HASH')
            self.phone_number = os.getenv('TELEGRAM_PHONE_NUMBER')
            self.session_string = os.getenv('TELEGRAM_SESSION_STRING')
            
            if not all([self.api_id, self.api_hash, self.phone_number]):
                raise ValueError("Не все Telegram API данные настроены")
            
            # Создаем клиент
            if self.session_string:
                self.client = TelegramClient(StringSession(self.session_string), self.api_id, self.api_hash)
            else:
                self.client = TelegramClient('personal_assistant', self.api_id, self.api_hash)
            
            # Инициализируем AI ассистента
            self.assistant = PersonalTelegramAssistant()
            
            logger.info("✅ PersonalTelegramBotTelethon инициализирован")
            
        except ImportError:
            logger.error("❌ Telethon не установлен. Установите: pip install telethon")
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Telethon: {e}")
            raise
    
    async def start(self):
        """Запуск бота с Telethon"""
        await self.client.start(phone=self.phone_number)
        
        logger.info("🚀 Персональный Telegram AI-ассистент запущен (Telethon)")
        logger.info(f"📱 Авторизован как: {await self.client.get_me()}")
        
        @self.client.on(events.NewMessage(incoming=True))
        async def handle_new_message(event):
            try:
                # Получаем данные сообщения
                message = event.message
                user_data = await event.get_sender()
                
                # Пропускаем сообщения от ботов
                if user_data.bot:
                    return
                
                # Пропускаем сообщения от себя
                if user_data.id == (await self.client.get_me()).id:
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
                
                # Получаем ответ от AI ассистента
                response = self.assistant.process_message(user_info, text)
                
                # Отправляем ответ
                await event.reply(response)
                
            except Exception as e:
                logger.error(f"Ошибка обработки сообщения: {e}")
        
        # Запускаем клиент
        await self.client.run_until_disconnected()


async def main():
    """Главная функция"""
    try:
        # Пробуем использовать Telethon (более надежно)
        bot = PersonalTelegramBotTelethon()
        await bot.start()
        
    except Exception as e:
        logger.error(f"Ошибка с Telethon: {e}")
        logger.info("Пробуем альтернативный метод...")
        
        # Альтернативный метод через Bot API
        bot = PersonalTelegramBot()
        await bot.run()


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
        print("📝 Добавьте их в файл .env:")
        print("TELEGRAM_API_ID=ваш_api_id")
        print("TELEGRAM_API_HASH=ваш_api_hash")
        print("TELEGRAM_PHONE_NUMBER=+998xxxxxxxxx")
        print("")
        print("🔗 Получить API данные можно на: https://my.telegram.org/apps")
        exit(1)
    
    # Запускаем бота
    asyncio.run(main())
