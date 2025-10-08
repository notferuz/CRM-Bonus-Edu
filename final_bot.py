#!/usr/bin/env python3
"""
AI-бот с полной интеграцией CRM для Bonus Education
"""

import logging
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import google.generativeai as genai
from datetime import datetime, timedelta
from simple_crm import SimpleCRM
import json

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Настройка Google AI (с безопасным fallback на заданный ключ)
_DEFAULT_GOOGLE_AI_API_KEY = 'AIzaSyDMU1syLbz7kKWozbYIwZ-SPdClpVQ4ako'
genai.configure(api_key=os.getenv('GOOGLE_AI_API_KEY') or _DEFAULT_GOOGLE_AI_API_KEY)

class FinalBonusEducationBot:
    def __init__(self):
        self.application = Application.builder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()
        self.setup_handlers()
        
        # Создаем модель Gemini 2.0 Flash (по запросу)
        self.model = genai.GenerativeModel('models/gemini-2.0-flash')
        
        # CRM сервис
        self.crm = SimpleCRM()

        # Простейшее состояние диалога для оформления записи
        # user_id -> {"intent": "booking", "name": str|None, "phone": str|None, "course": str|None,
        #             "days": list[str]|None, "time_from": str|None, "time_to": str|None}
        self.user_states = {}

        # Системный промпт (инструкции для модели)
        self.system_prompt = """
        Ты — AI-менеджер учебного центра Bonus Education.
        Задача: быстро выявлять потребности, предлагать подходящие программы и доводить до записи.
        Важная политика рекомендаций: фокус на Турецком языке (как основном продукте). Английский/Корейский упоминай, что есть, но мягко перенаправляй на Турецкий (быстрее результат за 3–4 месяца против 6–24 у др. языков; высокая разговорная практика).

        Контекст услуг:
        - Языки обучения: Турецкий (основной), а также Английский, Корейский.
        - Уровни: A1–C1, групповые и индивидуальные занятия, онлайн/офлайн.
        - Важно: Отвечай на русском, дружелюбно, продающе, с фокусом на следующем шаге.

        Стиль и формат:
        - Короткие фразы, один вопрос за раз.
        - Списки по делу, без «воды». 2–5 пунктов максимум.
        - Предлагай конкретный следующий шаг: пробный урок/консультация/запись.
        - Контакты не давай, пока явно не попросят.
        - Уточняй интересующий язык (Турецкий/Английский/Корейский), уровень и формат.
        """

    def detect_preferred_language(self, text: str) -> str | None:
        """Простейшее определение желаемого языка обучения из текста.
        Возвращает одно из: 'Турецкий' | 'Английский' | 'Корейский' | None
        """
        if not text:
            return None
        t = text.lower()
        # Турецкий
        if any(k in t for k in ["турецк", "turkish", "турк dili", "turk dili", "turk", "🇹🇷"]):
            return "Турецкий"
        # Английский
        if any(k in t for k in ["англ", "english", "ingliz", "inglizcha", "🇬🇧", "🇺🇸"]):
            return "Английский"
        # Корейский
        if any(k in t for k in ["корей", "korean", "han'guk", "hanguk", "한국", "🇰🇷"]):
            return "Корейский"
        return None

    def parse_schedule(self, text: str) -> dict:
        """Грубый парсер предпочитаемых дней и времени из свободного текста на русском.
        Возвращает {days: [..], time_from: 'HH:MM'|None, time_to: 'HH:MM'|None}
        """
        import re
        t = text.lower()
        # Дни недели
        day_aliases = {
            'понедельник': ['пн', 'пон', 'понедельник'],
            'вторник': ['вт', 'втор', 'вторник'],
            'среда': ['ср', 'сред', 'среда'],
            'четверг': ['чт', 'четв', 'четверг'],
            'пятница': ['пт', 'пятн', 'пятница'],
            'суббота': ['сб', 'суб', 'суббота'],
            'воскресенье': ['вс', 'воскр', 'воскресенье']
        }
        days = []
        for day, keys in day_aliases.items():
            if any(k in t for k in keys):
                days.append(day)

        # Время
        time_from = time_to = None
        # диапазон: 16 00 до 17 00, 16:00-17:00 и т.п.
        m = re.search(r"(\d{1,2})[\s:\.]?(\d{2})?\s*(?:-|–|до|\-)\s*(\d{1,2})[\s:\.]?(\d{2})?", t)
        if m:
            h1, m1, h2, m2 = m.group(1), m.group(2) or '00', m.group(3), m.group(4) or '00'
            time_from = f"{int(h1):02d}:{int(m1):02d}"
            time_to = f"{int(h2):02d}:{int(m2):02d}"
        else:
            # одиночное время, например 16:00
            m2 = re.search(r"(\d{1,2})[\s:\.]?(\d{2})", t)
            if m2:
                h, mm = m2.group(1), m2.group(2)
                time_from = f"{int(h):02d}:{int(mm):02d}"

        # эвристика: "после обеда" => с 16:00
        if 'после обеда' in t and not time_from:
            time_from = '16:00'
        return {"days": days or None, "time_from": time_from, "time_to": time_to}
        
        # Системный промпт с продажными скриптами
        self.system_prompt = """
        Ты - AI-менеджер по продажам учебного центра "Bonus Education" по изучению турецкого языка. 
        Твоя задача - не просто отвечать на вопросы, а ПРОДАВАТЬ курсы и ЗАПИСЫВАТЬ клиентов.
        
        Информация о центре:
        - Название: Bonus Education
        - Специализация: Изучение турецкого языка с нуля до профессионального уровня
        - Опыт: 10 лет работы
        - Студенты: 3000+ выпускников
        - Форматы обучения: онлайн и офлайн
        - Языки преподавания: турецкий, узбекский, русский
        
        Уровни обучения:
        1. A1 - Начальный уровень (2 месяца) - Изучение турецкого языка с нуля
        2. A2 - Элементарный уровень (2 месяца) - Продолжение изучения
        3. B1 - Средний уровень (3 месяца) - Сложные грамматические конструкции
        4. B2 - Средне-продвинутый уровень (3 месяца) - Свободное общение
        5. C1 - Продвинутый уровень (4 месяца) - Профессиональный уровень
        6. Индивидуальные занятия - Персональные уроки
        
        Особенности:
        - Групповые и индивидуальные занятия
        - Опытные преподаватели (на турецком, узбекском и русском языках)
        - Онлайн и офлайн варианты
        - Сертификат по окончании
        - Практические занятия
        - Небольшие группы (4-8 человек)
        
        Контакты (ДАВАЙ ТОЛЬКО КОГДА СПРОСЯТ):
        - Телефон: +998 94 843 5105 / +998 93 843 5105 / +998 90 321 1453
        - Telegram: @tash_turkdiliuz
        - Instagram: @turkdili.uz | @bonus_education
        - WhatsApp: +998 90 994 3433
        - Адрес: г. Ташкент, Мирободский район, ул. Нуронийлар, 19
        
        Твои принципы:
        - Отвечай дружелюбно и профессионально
        - Предоставляй точную информацию о курсах турецкого языка
        - Если не знаешь ответа, честно скажи об этом
        - НЕ ДАВАЙ КОНТАКТЫ В КАЖДОМ СООБЩЕНИИ - только когда клиент спросит
        - Используй эмодзи для более живого общения
        - Отвечай на русском языке, если вопрос задан на русском
        - Подчеркивай преимущества изучения турецкого языка
        - ВСЕГДА предлагай записаться на консультацию или курс
        
        ВАЖНО! Форматирование сообщений:
        - Делай КОРОТКИЕ сообщения
        - Задавай ОДИН вопрос в строку
        - НЕ пиши длинные абзацы
        - Используй простые предложения
        - Примеры хорошего форматирования:
          "Привет! Как дела?"
          "У нас есть уроки турецкого языка"
          "Можете записаться на пробный урок"
          "Какой уровень вам интересен?"
        - НЕ используй звездочки (*) или подчеркивания (_) для жирного текста
        - НЕ используй **жирный текст** или _курсив_
        - Используй только эмодзи и отступы для красивого оформления
        - Добавляй эмодзи для каждого уровня курса: 🇹🇷 A1, 🎯 A2, ⭐ B1, 🚀 B2, 👑 C1
        """
    
    def setup_handlers(self):
        """Настройка обработчиков команд и сообщений"""
        # Команды
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("courses", self.courses_command))
        self.application.add_handler(CommandHandler("contact", self.contact_command))
        self.application.add_handler(CommandHandler("about", self.about_command))
        self.application.add_handler(CommandHandler("book", self.book_command))
        
        # Обработка текстовых сообщений
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Обработка callback запросов
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        
        # Регистрируем пользователя в CRM
        await self.register_user(user)
        
        welcome_message = """
        🇹🇷 Привет! Добро пожаловать в Bonus Education!

        Я помогу вам с курсами по Турецкому, Английскому и Корейскому языкам.

        Что вас интересует?
        """
        
        keyboard = [
            [InlineKeyboardButton("🇹🇷 Наши курсы", callback_data="courses")],
            [InlineKeyboardButton("📞 Контакты", callback_data="contact")],
            [InlineKeyboardButton("ℹ️ О нас", callback_data="about")],
            [InlineKeyboardButton("📝 Записаться на курс", callback_data="book_course")],
            [InlineKeyboardButton("📱 Telegram", url="https://t.me/tash_turkdiliuz")],
            [InlineKeyboardButton("📷 Instagram", url="https://www.instagram.com/turkdili.uz/")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    
    async def register_user(self, user):
        """Регистрация пользователя в CRM"""
        try:
            logger.info(f"Проверяем пользователя: {user.first_name} (ID: {user.id})")
            
            # Проверяем, есть ли пользователь уже в CRM
            existing_user = self.crm.get_user(user.id)
            
            if not existing_user:
                # Создаем нового пользователя с расширенными полями
                user_data = {
                    "telegram_id": user.id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "phone": None,
                    "instagram_username": None,
                    "level": None,
                    "source": "telegram",
                    "status": "active",
                    "first_contact_date": datetime.now().strftime("%Y-%m-%d"),
                    "first_call_response": None,
                    "first_call_date": None,
                    "second_contact_response": None,
                    "second_contact_date": None,
                    "decision": None,
                    "decision_date": None,
                    "result": None,
                    "is_active": True
                }
                user_id = self.crm.add_user(user_data)
                logger.info(f"✅ НОВЫЙ пользователь зарегистрирован: {user.first_name} (ID: {user.id}) -> CRM ID: {user_id}")
                logger.info(f"Всего пользователей в CRM: {len(self.crm.data['users'])}")
            else:
                # Обновляем активность существующего пользователя
                self.crm.update_user_activity(user.id)
                logger.info(f"🔄 Пользователь обновлен: {user.first_name} (ID: {user.id})")
                
        except Exception as e:
            logger.error(f"❌ Ошибка при регистрации пользователя: {e}")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """
        📋 Доступные команды:
        
        /start - Начать работу с ботом
        /help - Показать это сообщение
        /courses - Посмотреть все курсы
        /contact - Контактная информация
        /about - О нашем учебном центре
        /book - Записаться на курс
        
        💬 Просто напишите любой вопрос, и я отвечу!
        
        Примеры вопросов:
        • "Какие уровни турецкого языка у вас есть?"
        • "Сколько стоят курсы?"
        • "Когда начинается следующий набор?"
        • "Есть ли онлайн обучение?"
        • "Хочу записаться на курс A1"
        """
        
        await update.message.reply_text(help_text)
    
    async def courses_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /courses"""
        courses = self.crm.get_courses()
        # Группируем по языку
        by_lang = {}
        for c in courses:
            lang = (c.get("language") or "Другое").strip()
            by_lang.setdefault(lang, []).append(c)

        courses_text = "Наши курсы:\n\n"
        for lang, items in by_lang.items():
            lang_flag = "🇹🇷" if "тур" in lang.lower() else ("🇬🇧" if "англ" in lang.lower() else ("🇰🇷" if "коре" in lang.lower() else "🎓"))
            courses_text += f"{lang_flag} {lang}:\n"
            for course in items:
                level_emoji = "🇹🇷" if "A1" in course["name"] else \
                             "🎯" if "A2" in course["name"] else \
                             "⭐" if "B1" in course["name"] else \
                             "🚀" if "B2" in course["name"] else \
                             "👑" if "C1" in course["name"] else "🎓"
                courses_text += f"  {level_emoji} {course['name']}\n"
                if course.get('description'):
                    courses_text += f"     {course['description']}\n"
                if course.get('duration'):
                    courses_text += f"     ⏱ {course['duration']}\n"
                if course.get('price'):
                    courses_text += f"     💰 {course['price']}\n"
            courses_text += "\n"

        courses_text += "📝 Хотите записаться на курс? Используйте /book или нажмите кнопку ниже!"
        
        keyboard = [
            [InlineKeyboardButton("📝 Записаться на курс", callback_data="book_course")],
            [InlineKeyboardButton("📞 Связаться с менеджером", callback_data="contact_manager")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(courses_text, reply_markup=reply_markup)
    
    async def contact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /contact"""
        contact_info = """
        📞 Контактная информация Bonus Education:
        
        🏢 Bonus Education - Турецкий язык
        📱 Телефон: +998 94 843 5105 / +998 93 843 5105 / +998 90 321 1453
        📱 WhatsApp: +998 90 994 3433
        
        📱 Социальные сети:
        • Telegram: @tash_turkdiliuz
        • Instagram: @turkdili.uz | @bonus_education
        • YouTube: Bonus Education
        
        🕒 Время работы:
        Пн-Пт: 9:00 - 18:00
        Сб: 10:00 - 16:00
        Вс: выходной
        
        📍 Адрес: г. Ташкент, Мирободский район, ул. Нуронийлар, 19
        🗺 Ориентиры: здание Сената, УзНефтГаз, школа №110, ЦУМ, Центральный банк
        
        💬 Или просто напишите мне - я отвечу в течение нескольких минут!
        """
        
        keyboard = [
            [InlineKeyboardButton("📝 Записаться на курс", callback_data="book_course")],
            [InlineKeyboardButton("📱 Позвонить", url="tel:+998948435105")],
            [InlineKeyboardButton("💬 WhatsApp", url="https://wa.me/998909943433")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(contact_info, reply_markup=reply_markup)
    
    async def about_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /about"""
        about_text = """
        🇹🇷 О нашем учебном центре Bonus Education:
        
        Мы обучаем: Турецкому, Английскому и Корейскому языкам. 10 лет опыта работы.
        
        🚀 Наши преимущества:
        • 10 лет опыта преподавания
        • 3000+ успешных выпускников
        • Опытные преподаватели (турецкий, английский, корейский; также узбекский и русский)
        • Небольшие группы (4-8 человек)
        • Онлайн и офлайн форматы
        • Сертификаты по окончании
        • Практические занятия
        
        📊 Статистика:
        • 3000+ студентов
        • 10 лет опыта
        • Уровни A1–C1 по каждому языку
        • Групповые и индивидуальные занятия
        
        🎯 Наша миссия - сделать изучение турецкого языка доступным и эффективным для всех!
        
        📍 Адрес: г. Ташкент, Мирободский район, ул. Нуронийлар, 19
        """
        
        keyboard = [
            [InlineKeyboardButton("📝 Записаться на курс", callback_data="book_course")],
            [InlineKeyboardButton("📞 Связаться с нами", callback_data="contact_manager")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(about_text, reply_markup=reply_markup)
    
    async def book_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /book"""
        await self.show_booking_menu(update, context)
    
    async def show_booking_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать меню записи на курсы"""
        courses = self.crm.get_courses()
        
        keyboard = []
        for course in courses:
            level_emoji = "🇹🇷" if "A1" in course["name"] else \
                         "🎯" if "A2" in course["name"] else \
                         "⭐" if "B1" in course["name"] else \
                         "🚀" if "B2" in course["name"] else \
                         "👑" if "C1" in course["name"] else "🎓"
            
            keyboard.append([InlineKeyboardButton(
                f"{level_emoji} {course['name']}", 
                callback_data=f"book_{course['id']}"
            )])
        
        keyboard.append([InlineKeyboardButton("📞 Связаться с менеджером", callback_data="contact_manager")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = "📝 Выберите курс для записи:"
        
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        original_text = update.message.text or ""
        user_message = original_text.lower()
        user = update.effective_user
        
        logger.info(f"📨 Получено сообщение от {user.first_name} (ID: {user.id}): {user_message[:50]}...")
        
        # Регистрируем пользователя в CRM (если его еще нет)
        try:
            await self.register_user(user)
            logger.info(f"✅ Пользователь {user.first_name} (ID: {user.id}) обработан")
        except Exception as e:
            logger.error(f"❌ Ошибка при регистрации пользователя {user.first_name}: {e}")

        # Авто-определение предпочитаемого языка из сообщения и сохранение в CRM
        try:
            detected_lang = self.detect_preferred_language(original_text)
            if detected_lang:
                # Обновляем только при изменении или отсутствии значения
                existing = self.crm.get_user(user.id) or {}
                if existing.get("preferred_language") != detected_lang:
                    self.crm.update_user(existing.get("id") or existing.get("telegram_id") or user.id, {"preferred_language": detected_lang})
                    logger.info(f"🌐 Обновлен preferred_language: {detected_lang} для пользователя {user.id}")
        except Exception as e:
            logger.warning(f"Не удалось обновить preferred_language: {e}")
        
        # Проверяем, не спрашивает ли пользователь ОТДЕЛЬНО про контакты (более точные формулировки)
        # И ЛИШЬ если не в процессе записи и нет номера в сообщении
        import re as _re
        phone_regex = r"(?:\+?998|\+?7|\+?90)?[\s\-\(\)]?\d{2,3}[\s\-\)]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"
        is_in_booking = bool(self.user_states.get(user.id))
        asks_contacts = any(kw in user_message for kw in ['контакты', 'дай контакты', 'как связаться', 'связаться с вами', 'адрес', 'где находитесь', 'ваш номер'])
        contains_phone = bool(_re.search(phone_regex, update.message.text))
        if asks_contacts and not is_in_booking and not contains_phone:
            contact_info = """
📞 Наши контакты:

📱 Телефон: +998 94 843 5105 / +998 93 843 5105
💬 Telegram: @tash_turkdiliuz
📷 Instagram: @turkdili.uz
📍 Адрес: г. Ташкент, Мирободский район, ул. Нуронийлар, 19
"""
            await update.message.reply_text(contact_info)
            return
        
        # Пробуем заметить намерение записи на курс до вызова AI
        booking_keywords = [
            'запис', 'запиш', 'хочу курс', 'хочу записаться', 'хочу записат', 'готов начать',
            'консультаци', 'пробный урок', 'начать обучение'
        ]
        # phone_regex определен выше

        user_state = self.user_states.get(user.id)

        # Если пользователь в процессе записи – собираем недостающие данные
        if user_state and user_state.get('intent') == 'booking':
            # Если нет имени – берём из сообщения всё, что не похоже на номер
            import re
            # Обновляем расписание из текста на каждом шаге
            sched = self.parse_schedule(update.message.text)
            if sched.get('days'):
                user_state['days'] = sched['days']
            if sched.get('time_from'):
                user_state['time_from'] = sched['time_from']
            if sched.get('time_to'):
                user_state['time_to'] = sched['time_to']

            if not user_state.get('name') and not re.search(phone_regex, update.message.text):
                user_state['name'] = update.message.text.strip().title()
                await update.message.reply_text("Отлично! Теперь отправьте номер телефона для связи (например: +998 90 123 45 67)")
                return
            # Если нет телефона – пытаемся извлечь
            if not user_state.get('phone'):
                import re
                m = re.search(phone_regex, update.message.text)
                if m:
                    user_state['phone'] = m.group(0)
                else:
                    await update.message.reply_text("Пожалуйста, отправьте номер телефона в формате +998 ...")
                    return
            # Есть всё – создаём запись
            if user_state.get('name') and user_state.get('phone'):
                booking_data = {
                    "user_id": user.id,
                    "user_name": user_state['name'],
                    "user_phone": user_state['phone'],
                    "course_id": None,
                    "course_name": "Будет уточнено",
                    "teacher_id": None,
                    "teacher_name": "Будет назначен",
                    "status": "pending",
                    "notes": "Заявка из чата: авто-создание"
                }
                # Добавляем предпочтения по времени/дням, если указаны
                notes_extra = []
                if user_state.get('days'):
                    notes_extra.append("Дни: " + ", ".join(user_state['days']))
                if user_state.get('time_from') or user_state.get('time_to'):
                    tf = user_state.get('time_from') or ''
                    tt = user_state.get('time_to')
                    if tt:
                        notes_extra.append(f"Время: {tf}-{tt}")
                    else:
                        notes_extra.append(f"Время: {tf}")
                if notes_extra:
                    booking_data['notes'] += " | " + "; ".join(notes_extra)
                booking_id = self.crm.add_booking(booking_data)
                # очищаем состояние
                self.user_states.pop(user.id, None)
                confirmation = (
                    "✅ Заявка создана!\n\n"
                    f"Имя: {booking_data['user_name']}\n"
                    f"Телефон: {booking_data['user_phone']}\n"
                    "Статус: ожидает подтверждения.\n\n"
                    + (f"Предпочтения: {', '.join(user_state.get('days', []))} " if user_state.get('days') else "")
                    + (f"{user_state.get('time_from','')}{('-'+user_state.get('time_to')) if user_state.get('time_to') else ''}\n\n" if (user_state.get('time_from') or user_state.get('time_to')) else "")
                    + "Мы свяжемся с вами в течение 15–30 минут в рабочее время (Пн–Пт 9:00–18:00).\n"
                    + "\n📍 Адрес: г. Ташкент, Мирободский район, ул. Нуронийлар, 19\n"
                    + "📞 Телефон: +998 94 843 5105 / +998 93 843 5105\n"
                    + "💬 Telegram: @tash_turkdiliuz\n"
                    + "\nЕсли удобно, напишите предпочитаемое время звонка."
                )
                await update.message.reply_text(confirmation)
                return

        # Если пользователь явно просит записать – запускаем сценарий записи
        if any(k in user_message for k in booking_keywords):
            self.user_states[user.id] = {"intent": "booking", "name": None, "phone": None, "course": None}
            await update.message.reply_text("Супер! Запишу вас. Как вас зовут?")
            return

        # Если прислали номер телефона вне контекста – предложим оформить запись
        import re
        if re.search(phone_regex, update.message.text):
            # Извлекаем и имя, если оно есть вместе с номером
            m = re.search(phone_regex, update.message.text)
            phone_val = m.group(0)
            # Простая эвристика: удаляем номер из текста и берем остаток как имя
            name_guess = update.message.text.replace(phone_val, '').strip().title() or (user.first_name or '').strip()
            sched = self.parse_schedule(update.message.text)
            self.user_states[user.id] = {"intent": "booking", "name": name_guess, "phone": phone_val, "course": None,
                                          "days": sched.get('days'), "time_from": sched.get('time_from'), "time_to": sched.get('time_to')}
            if name_guess:
                await update.message.reply_text("Принял! Создаю заявку…")
                # Завершаем сразу без дополнительных шагов
                booking_data = {
                    "user_id": user.id,
                    "user_name": name_guess,
                    "user_phone": phone_val,
                    "course_id": None,
                    "course_name": "Будет уточнено",
                    "teacher_id": None,
                    "teacher_name": "Будет назначен",
                    "status": "pending",
                    "notes": "Заявка из чата: авто-создание (имя и телефон одним сообщением)"
                }
                extras = []
                if sched.get('days'):
                    extras.append("Дни: " + ", ".join(sched['days']))
                if sched.get('time_from') or sched.get('time_to'):
                    tf = sched.get('time_from') or ''
                    tt = sched.get('time_to')
                    if tt:
                        extras.append(f"Время: {tf}-{tt}")
                    else:
                        extras.append(f"Время: {tf}")
                if extras:
                    booking_data['notes'] += " | " + "; ".join(extras)
                self.crm.add_booking(booking_data)
                self.user_states.pop(user.id, None)
                confirmation = (
                    "✅ Заявка создана!\n\n"
                    f"Имя: {booking_data['user_name']}\n"
                    f"Телефон: {booking_data['user_phone']}\n"
                    "Статус: ожидает подтверждения.\n\n"
                    + (f"Предпочтения: {', '.join(sched.get('days', []))} " if sched.get('days') else "")
                    + (f"{sched.get('time_from','')}{('-'+sched.get('time_to')) if sched.get('time_to') else ''}\n\n" if (sched.get('time_from') or sched.get('time_to')) else "")
                    + "Мы свяжемся с вами в течение 15–30 минут в рабочее время (Пн–Пт 9:00–18:00).\n"
                    + "\n📍 Адрес: г. Ташкент, Мирободский район, ул. Нуронийлар, 19\n"
                    + "📞 Телефон: +998 94 843 5105 / +998 93 843 5105\n"
                    + "💬 Telegram: @tash_turkdiliuz\n"
                    + "\nЕсли удобно, напишите предпочитаемое время звонка."
                )
                await update.message.reply_text(confirmation)
            else:
                await update.message.reply_text("Спасибо! Записал номер. Уточните, пожалуйста, ваше полное имя.")
            return

        # Показываем, что бот печатает
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        try:
            # Получаем последние диалоги для контекста
            recent_conversations = self.crm.get_recent_conversations(user.id, 3)
            context = ""
            if recent_conversations:
                context = "\n\nКонтекст предыдущих сообщений:\n"
                for conv in reversed(recent_conversations[-2:]):  # Берем последние 2 диалога
                    context += f"Пользователь: {conv['message']}\n"
                    context += f"Бот: {conv['response']}\n"
            
            # Получаем ответ от AI с контекстом
            # Динамическая адаптация под язык обучения, если обнаружен не-турецкий
            lang_for_prompt = self.detect_preferred_language(original_text)
            language_note = ""
            if lang_for_prompt and lang_for_prompt != "Турецкий":
                language_note = (\
                    f"\n\nВажно: Клиента интересует обучение по языку '{lang_for_prompt}'. "
                    f"Дай информацию и предложения применительно к '{lang_for_prompt}' (структура курсов, формат, цены как в центре аналогично турецкому направлению, без выдумывания несуществующих фактов)."\
                )
            # Подхватываем системный промпт из CRM, если задан — онГлавнее встроенного
            crm_prompt = self.crm.get_ai_system_prompt() if hasattr(self.crm, 'get_ai_system_prompt') else None
            base_prompt = crm_prompt.strip() + "\n\n" if crm_prompt else self.system_prompt
            full_prompt = f"{base_prompt}{language_note}{context}\n\nТекущий вопрос пользователя: {user_message}\n\nОтветь естественно, учитывая контекст диалога. НЕ здоровайся заново, если это продолжение разговора."
            response = self.model.generate_content(full_prompt)
            ai_response = response.text.strip()
            
            # Сохраняем диалог в CRM
            self.crm.add_conversation(user.id, user_message, ai_response)
            
        except Exception as e:
            logger.error(f"❌ Ошибка AI API: {e}")
            
            # Обработка различных типов ошибок
            if "quota" in str(e).lower() or "429" in str(e):
                # Умные fallback ответы на основе ключевых слов в сообщении
                if any(word in user_message for word in ['курс', 'уровень', 'изуч', 'учит', 'обуч']):
                    ai_response = """🇹🇷 Отлично, что интересуетесь турецким языком!

📚 Наши курсы:
🇹🇷 A1 - Начальный (2 мес)
🎯 A2 - Элементарный (2 мес) 
⭐ B1 - Средний (3 мес)
🚀 B2 - Продвинутый (3 мес)
👑 C1 - Профессиональный (4 мес)

Какой уровень вас интересует?"""
                elif any(word in user_message for word in ['цена', 'стоит', 'стоимость', 'деньг', 'оплат']):
                    ai_response = """💰 Стоимость курсов:

🇹🇷 A1-A2: 150,000 сум/месяц
⭐ B1-B2: 200,000 сум/месяц  
👑 C1: 250,000 сум/месяц
👤 Индивидуально: 300,000 сум/месяц

Есть скидки при оплате за весь курс!"""
                elif any(word in user_message for word in ['начал', 'старт', 'когда', 'дата']):
                    ai_response = """📅 Новые группы стартуют каждый месяц!

🗓 Ближайшие даты:
• A1: 1 октября
• B1: 5 октября  
• A2: 10 октября

Хотите записаться на конкретный курс?"""
                else:
                    # Не выдаём контакты автоматически, если их не спросили
                    ai_response = """🇹🇷 Привет! Я помогу с изучением турецкого языка.

Могу рассказать о курсах и записать вас на консультацию. Что вас интересует?"""
            else:
                ai_response = """🇹🇷 Привет! К сожалению, AI временно недоступен.

Но я все равно помогу! Вот основная информация:

📚 Курсы турецкого языка A1-C1
💰 От 150,000 сум/месяц
📞 +998 94 843 5105
💬 @tash_turkdiliuz

Что вас интересует?"""
            
                logger.error(f"AI Error: {e}")
        
            # Сохраняем диалог с fallback ответом
            self.crm.add_conversation(user.id, user_message, ai_response)
        
        # Отправляем ответ
        await update.message.reply_text(ai_response)
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик callback запросов от inline кнопок"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "courses":
            await self.send_courses_info(query)
        elif query.data == "contact":
            await self.send_contact_info(query)
        elif query.data == "about":
            await self.send_about_info(query)
        elif query.data == "book_course":
            await self.show_booking_menu(update, context)
        elif query.data == "contact_manager":
            await self.contact_manager(query)
        elif query.data == "back_to_main":
            await self.back_to_main(query)
        elif query.data.startswith("book_"):
            course_id = int(query.data.split("_")[1])
            await self.handle_course_booking(query, course_id)
    
    async def handle_course_booking(self, query, course_id):
        """Обработка записи на курс"""
        course = self.crm.get_course(course_id)
        
        if not course:
            await query.edit_message_text("❌ Курс не найден. Попробуйте еще раз.")
            return
        
        # Создаем запись в CRM
        booking_data = {
            "user_id": query.from_user.id,
            "user_name": f"{query.from_user.first_name} {query.from_user.last_name or ''}".strip(),
            "user_phone": "Не указан",
            "course_id": course_id,
            "course_name": course["name"],
            "teacher_id": None,
            "teacher_name": "Будет назначен",
            "status": "pending",
            "notes": "Запись через Telegram бота"
        }
        
        booking_id = self.crm.add_booking(booking_data)
        
        success_message = f"""
        ✅ Заявка на запись принята!
        
        📚 Курс: {course['name']}
        👤 Имя: {query.from_user.first_name} {query.from_user.last_name or ''}
        📅 Дата подачи: {datetime.now().strftime('%d.%m.%Y %H:%M')}
        
        📞 Наш менеджер свяжется с вами в ближайшее время для подтверждения записи.
        
        Контакты для связи:
        • Телефон: +998 94 843 5105
        • Telegram: @tash_turkdiliuz
        • WhatsApp: +998 90 994 3433
        """
        
        keyboard = [
            [InlineKeyboardButton("📞 Связаться с менеджером", callback_data="contact_manager")],
            [InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(success_message, reply_markup=reply_markup)
        
        # Логируем запись
        logger.info(f"Новая запись на курс: {course['name']} от пользователя {query.from_user.first_name} (ID: {query.from_user.id})")
    
    async def contact_manager(self, query):
        """Связаться с менеджером"""
        contact_text = """
        📞 Свяжитесь с нашим менеджером:
        
        📱 Телефон: +998 94 843 5105 / +998 93 843 5105
        💬 WhatsApp: +998 90 994 3433
        📧 Telegram: @tash_turkdiliuz
        
        🕒 Время работы:
        Пн-Пт: 9:00 - 18:00
        Сб: 10:00 - 16:00
        
        Мы ответим в течение 15 минут! 😊
        """
        
        keyboard = [
            [InlineKeyboardButton("📱 Позвонить", url="tel:+998948435105")],
            [InlineKeyboardButton("💬 WhatsApp", url="https://wa.me/998909943433")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(contact_text, reply_markup=reply_markup)
    
    async def back_to_main(self, query):
        """Вернуться в главное меню"""
        welcome_message = """
        🇹🇷 Добро пожаловать в Bonus Education - Турецкий язык!
        
        Я - ваш персональный AI-ассистент по изучению турецкого языка, готовый помочь с любыми вопросами о наших курсах.
        
        🎯 Что я могу:
        • Рассказать о всех уровнях турецкого языка (A1-C1)
        • Ответить на вопросы о программах обучения
        • Помочь выбрать подходящий уровень
        • Предоставить информацию о ценах и расписании
        • Рассказать о форматах обучения (онлайн/офлайн)
        • Записать вас на консультацию или курс
        
        Просто напишите ваш вопрос, и я с радостью помогу! 😊
        """
        
        keyboard = [
            [InlineKeyboardButton("🇹🇷 Наши курсы", callback_data="courses")],
            [InlineKeyboardButton("📞 Контакты", callback_data="contact")],
            [InlineKeyboardButton("ℹ️ О нас", callback_data="about")],
            [InlineKeyboardButton("📝 Записаться на курс", callback_data="book_course")],
            [InlineKeyboardButton("📱 Telegram", url="https://t.me/tash_turkdiliuz")],
            [InlineKeyboardButton("📷 Instagram", url="https://www.instagram.com/turkdili.uz/")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(welcome_message, reply_markup=reply_markup)
    
    async def send_courses_info(self, query):
        """Отправляет информацию о курсах через callback query"""
        courses = self.crm.get_courses()
        by_lang = {}
        for c in courses:
            lang = (c.get("language") or "Другое").strip()
            by_lang.setdefault(lang, []).append(c)

        courses_text = "Наши курсы:\n\n"
        for lang, items in by_lang.items():
            lang_flag = "🇹🇷" if "тур" in lang.lower() else ("🇬🇧" if "англ" in lang.lower() else ("🇰🇷" if "коре" in lang.lower() else "🎓"))
            courses_text += f"{lang_flag} {lang}:\n"
            for course in items:
                level_emoji = "🇹🇷" if "A1" in course["name"] else \
                             "🎯" if "A2" in course["name"] else \
                             "⭐" if "B1" in course["name"] else \
                             "🚀" if "B2" in course["name"] else \
                             "👑" if "C1" in course["name"] else "🎓"
                courses_text += f"  {level_emoji} {course['name']}\n"
                if course.get('description'):
                    courses_text += f"     {course['description']}\n"
                if course.get('duration'):
                    courses_text += f"     ⏱ {course['duration']}\n"
                if course.get('price'):
                    courses_text += f"     💰 {course['price']}\n"
            courses_text += "\n"

        courses_text += "📝 Хотите записаться на курс? Нажмите кнопку ниже!"
        
        keyboard = [
            [InlineKeyboardButton("📝 Записаться на курс", callback_data="book_course")],
            [InlineKeyboardButton("📞 Связаться с менеджером", callback_data="contact_manager")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(courses_text, reply_markup=reply_markup)
    
    async def send_contact_info(self, query):
        """Отправляет контактную информацию через callback query"""
        contact_info = """
        📞 Контактная информация Bonus Education:
        
        🏢 Bonus Education - Турецкий язык
        📱 Телефон: +998 94 843 5105 / +998 93 843 5105 / +998 90 321 1453
        📱 WhatsApp: +998 90 994 3433
        
        📱 Социальные сети:
        • Telegram: @tash_turkdiliuz
        • Instagram: @turkdili.uz | @bonus_education
        • YouTube: Bonus Education
        
        🕒 Время работы:
        Пн-Пт: 9:00 - 18:00
        Сб: 10:00 - 16:00
        Вс: выходной
        
        📍 Адрес: г. Ташкент, Мирободский район, ул. Нуронийлар, 19
        🗺 Ориентиры: здание Сената, УзНефтГаз, школа №110, ЦУМ, Центральный банк
        
        💬 Или просто напишите мне - я отвечу в течение нескольких минут!
        """
        
        keyboard = [
            [InlineKeyboardButton("📝 Записаться на курс", callback_data="book_course")],
            [InlineKeyboardButton("📱 Позвонить", url="tel:+998948435105")],
            [InlineKeyboardButton("💬 WhatsApp", url="https://wa.me/998909943433")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(contact_info, reply_markup=reply_markup)
    
    async def send_about_info(self, query):
        """Отправляет информацию о центре через callback query"""
        about_text = """
        🇹🇷 О нашем учебном центре Bonus Education:
        
        Bonus Education - это специализированный центр по изучению турецкого языка с 10-летним опытом работы.
        
        🚀 Наши преимущества:
        • 10 лет опыта преподавания
        • 3000+ успешных выпускников
        • Опытные преподаватели (турецкий, узбекский, русский)
        • Небольшие группы (4-8 человек)
        • Онлайн и офлайн форматы
        • Сертификаты по окончании
        • Практические занятия
        
        📊 Статистика:
        • 3000+ студентов
        • 10 лет опыта
        • 5 уровней обучения (A1-C1)
        • Групповые и индивидуальные занятия
        
        🎯 Наша миссия - сделать изучение турецкого языка доступным и эффективным для всех!
        
        📍 Адрес: г. Ташкент, Мирободский район, ул. Нуронийлар, 19
        """
        
        keyboard = [
            [InlineKeyboardButton("📝 Записаться на курс", callback_data="book_course")],
            [InlineKeyboardButton("📞 Связаться с нами", callback_data="contact_manager")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(about_text, reply_markup=reply_markup)
    
    def run(self):
        """Запускает бота"""
        logger.info("Запуск Bonus Education Bot с CRM интеграцией...")
        self.application.run_polling()

if __name__ == "__main__":
    try:
        # Проверяем переменные окружения
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not token:
            print("❌ TELEGRAM_BOT_TOKEN не найден в переменных окружения")
            exit(1)
        masked = f"{token[:6]}******{token[-4:]}"
        print(f"🔐 TELEGRAM_BOT_TOKEN={masked}")

        if not os.getenv('GOOGLE_AI_API_KEY'):
            print("⚠️ GOOGLE_AI_API_KEY не найден в .env — использую ключ по умолчанию из кода")

        bot = FinalBonusEducationBot()
        bot.run()
    except Exception as e:
        import traceback
        print("❌ Критическая ошибка при запуске бота:")
        traceback.print_exc()
        exit(1)