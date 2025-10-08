#!/usr/bin/env python3
"""
Персональный AI-ассистент для Telegram аккаунта
Работает как ваш личный аккаунт, автоматически отвечая на сообщения
"""

import logging
import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai
from simple_crm import SimpleCRM
import json
import re

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Настройка Google AI
_DEFAULT_GOOGLE_AI_API_KEY = 'AIzaSyDMU1syLbz7kKWozbYIwZ-SPdClpVQ4ako'
genai.configure(api_key=os.getenv('GOOGLE_AI_API_KEY') or _DEFAULT_GOOGLE_AI_API_KEY)

class PersonalTelegramAssistant:
    def __init__(self):
        # Создаем модель Gemini
        self.model = genai.GenerativeModel('models/gemini-2.0-flash')
        
        # CRM сервис
        self.crm = SimpleCRM()
        
        # Состояния диалогов
        self.user_states = {}
        
        # Системный промпт для персонального ассистента (мультиязычные направления)
        self.system_prompt = """
        Ты — персональный AI-ассистент владельца учебного центра Bonus Education.

        Твоя задача:
        1) Отвечать как владелец центра (пиши от первого лица: "я", "мы").
        2) Быстро выяснять потребности и предлагать программы.
        3) Вести к записи на консультацию/курс.

        Наши направления: Турецкий 🇹🇷, Английский 🇬🇧, Корейский 🇰🇷.
        Политика рекомендаций: всегда фокус на Турецком (как основном продукте). Другие языки упоминай, что они есть, но мягко направляй в сторону Турецкого (быстрее результат 3–4 месяца против 6–24 месяцев у др. языков, высокая разговорная практика, хорошие результаты).
        Уровни: A1–C1, групповые и индивидуальные, онлайн/офлайн.
        Опыт 10 лет, 3000+ выпускников.

        Правила общения:
        - Короткие сообщения, один вопрос за раз.
        - НЕ давай контакты без запроса.
        - Если язык не указан — уточни, какой интересует, и предложи рассмотреть Турецкий как самый быстрый по результату.
        - Если клиент спросил про Английский/Корейский — дай краткую инфо, но предложи рассмотреть Турецкий как более быстрый и практичный путь, с опцией консультации.
        - Не повторяй один и тот же вопрос дважды (например, про «группа или индивидуально» и «онлайн или офлайн»). Если информация уже известна — не переспроси её снова.
        - Тон: дружелюбный, полезный, продающий, без воды.

        Всегда предлагай следующий шаг: консультация/пробный урок/запись.
        """
    
    def detect_preferred_language(self, text: str) -> str | None:
        """Определение желаемого языка обучения"""
        if not text:
            return None
        t = text.lower()
        
        if any(k in t for k in ["турецк", "turkish", "турк dili", "turk dili", "turk", "🇹🇷"]):
            return "Турецкий"
        if any(k in t for k in ["англ", "english", "ingliz", "inglizcha", "🇬🇧", "🇺🇸"]):
            return "Английский"
        if any(k in t for k in ["корей", "korean", "han'guk", "hanguk", "한국", "🇰🇷"]):
            return "Корейский"
        return None
    
    def parse_schedule(self, text: str) -> dict:
        """Парсер предпочитаемых дней и времени"""
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
        m = re.search(r"(\d{1,2})[\s:\.]?(\d{2})?\s*(?:-|–|до|\-)\s*(\d{1,2})[\s:\.]?(\d{2})?", t)
        if m:
            h1, m1, h2, m2 = m.group(1), m.group(2) or '00', m.group(3), m.group(4) or '00'
            time_from = f"{int(h1):02d}:{int(m1):02d}"
            time_to = f"{int(h2):02d}:{int(m2):02d}"
        else:
            m2 = re.search(r"(\d{1,2})[\s:\.]?(\d{2})", t)
            if m2:
                h, mm = m2.group(1), m2.group(2)
                time_from = f"{int(h):02d}:{int(mm):02d}"
        
        if 'после обеда' in t and not time_from:
            time_from = '16:00'
            
        return {"days": days or None, "time_from": time_from, "time_to": time_to}
    
    async def register_user(self, user_data):
        """Регистрация пользователя в CRM"""
        try:
            logger.info(f"Проверяем пользователя: {user_data.get('first_name', 'Unknown')} (ID: {user_data.get('id')})")
            
            # Проверяем, есть ли пользователь уже в CRM
            existing_user = self.crm.get_user(user_data.get('id'))
            
            if not existing_user:
                # Создаем нового пользователя
                user_info = {
                    "telegram_id": user_data.get('id'),
                    "username": user_data.get('username'),
                    "first_name": user_data.get('first_name'),
                    "last_name": user_data.get('last_name'),
                    "phone": None,
                    "instagram_username": None,
                    "level": None,
                    "source": "telegram_personal",
                    "status": "active",
                    "first_contact_date": datetime.now().strftime("%Y-%m-%d"),
                    "is_active": True
                }
                user_id = self.crm.add_user(user_info)
                logger.info(f"✅ НОВЫЙ пользователь зарегистрирован: {user_data.get('first_name')} (ID: {user_data.get('id')}) -> CRM ID: {user_id}")
            else:
                # Обновляем активность существующего пользователя
                self.crm.update_user_activity(user_data.get('id'))
                logger.info(f"🔄 Пользователь обновлен: {user_data.get('first_name')} (ID: {user_data.get('id')})")
                
        except Exception as e:
            logger.error(f"❌ Ошибка при регистрации пользователя: {e}")
    
    def process_message(self, user_data, message_text):
        """Обработка входящего сообщения"""
        try:
            user_id = user_data.get('id')
            user_message = message_text.lower()
            original_text = message_text
            
            logger.info(f"📨 Получено сообщение от {user_data.get('first_name', 'Unknown')} (ID: {user_id}): {user_message[:50]}...")
            
            # Регистрируем пользователя в CRM
            asyncio.create_task(self.register_user(user_data))
            
            # Авто-определение предпочитаемого языка
            try:
                detected_lang = self.detect_preferred_language(original_text)
                if detected_lang:
                    existing = self.crm.get_user(user_id) or {}
                    if existing.get("preferred_language") != detected_lang:
                        self.crm.update_user(existing.get("id") or existing.get("telegram_id") or user_id, {"preferred_language": detected_lang})
                        logger.info(f"🌐 Обновлен preferred_language: {detected_lang} для пользователя {user_id}")
            except Exception as e:
                logger.warning(f"Не удалось обновить preferred_language: {e}")
            
            # Проверяем запрос контактов
            phone_regex = r"(?:\+?998|\+?7|\+?90)?[\s\-\(\)]?\d{2,3}[\s\-\)]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"
            is_in_booking = bool(self.user_states.get(user_id))
            asks_contacts = any(kw in user_message for kw in ['контакты', 'дай контакты', 'как связаться', 'связаться с вами', 'адрес', 'где находитесь', 'ваш номер'])
            contains_phone = bool(re.search(phone_regex, message_text))
            
            if asks_contacts and not is_in_booking and not contains_phone:
                contact_info = """📞 Мои контакты:

📱 Телефон: +998 94 843 5105 / +998 93 843 5105
💬 Telegram: @tash_turkdiliuz
📷 Instagram: @turkdili.uz
📍 Адрес: г. Ташкент, Мирободский район, ул. Нуронийлар, 19"""
                return contact_info
            
            # Если спрашивают, кто создал — отвечаем явно и не повторяем без запроса
            creator_keywords = [
                'кто тебя создал', 'кто создал', 'твой создател', 'создатель', 'who created you', 'your creator'
            ]
            if any(k in user_message for k in creator_keywords):
                reply_creator = "Меня создали разработчики Bonus Education."
                # Сохраняем диалог и отвечаем
                try:
                    self.crm.add_conversation(user_id, original_text, reply_creator)
                except Exception:
                    pass
                return reply_creator

            # Обработка записи на курс
            booking_keywords = [
                'запис', 'запиш', 'хочу курс', 'хочу записаться', 'хочу записат', 'готов начать',
                'консультаци', 'пробный урок', 'начать обучение'
            ]
            
            user_state = self.user_states.get(user_id)
            if not user_state:
                user_state = {}
                self.user_states[user_id] = user_state

            # Эвристически сохраняем предпочитаемые формат/режим/уровень, чтобы не переспрашивать
            if any(k in user_message for k in ['индивидуал', 'персональ']):
                user_state['format'] = 'individual'
            if 'групп' in user_message:
                user_state['format'] = 'group'
            if 'онлайн' in user_message:
                user_state['mode'] = 'online'
            if 'офлайн' in user_message or 'в классе' in user_message:
                user_state['mode'] = 'offline'
            if re.search(r'\ba\s*1\b|\ba1\b', user_message):
                user_state['level'] = 'A1'
            
            # Если пользователь в процессе записи
            if user_state and user_state.get('intent') == 'booking':
                sched = self.parse_schedule(message_text)
                if sched.get('days'):
                    user_state['days'] = sched['days']
                if sched.get('time_from'):
                    user_state['time_from'] = sched['time_from']
                if sched.get('time_to'):
                    user_state['time_to'] = sched['time_to']
                
                if not user_state.get('name') and not re.search(phone_regex, message_text):
                    user_state['name'] = message_text.strip().title()
                    return "Отлично! Теперь отправьте номер телефона для связи (например: +998 90 123 45 67)"
                
                if not user_state.get('phone'):
                    m = re.search(phone_regex, message_text)
                    if m:
                        user_state['phone'] = m.group(0)
                    else:
                        return "Пожалуйста, отправьте номер телефона в формате +998 ..."
                
                if user_state.get('name') and user_state.get('phone'):
                    booking_data = {
                        "user_id": user_id,
                        "user_name": user_state['name'],
                        "user_phone": user_state['phone'],
                        "course_id": None,
                        "course_name": "Будет уточнено",
                        "teacher_id": None,
                        "teacher_name": "Будет назначен",
                        "status": "pending",
                        "notes": "Заявка из личного чата: авто-создание"
                    }
                    
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
                    self.user_states.pop(user_id, None)
                    
                    confirmation = (
                        "✅ Заявка создана!\n\n"
                        f"Имя: {booking_data['user_name']}\n"
                        f"Телефон: {booking_data['user_phone']}\n"
                        "Статус: ожидает подтверждения.\n\n"
                        + (f"Предпочтения: {', '.join(user_state.get('days', []))} " if user_state.get('days') else "")
                        + (f"{user_state.get('time_from','')}{('-'+user_state.get('time_to')) if user_state.get('time_to') else ''}\n\n" if (user_state.get('time_from') or user_state.get('time_to')) else "")
                        + "Я свяжусь с вами в течение 15–30 минут в рабочее время (Пн–Пт 9:00–18:00).\n"
                        + "\n📍 Адрес: г. Ташкент, Мирободский район, ул. Нуронийлар, 19\n"
                        + "📞 Телефон: +998 94 843 5105 / +998 93 843 5105\n"
                        + "💬 Telegram: @tash_turkdiliuz\n"
                        + "\nЕсли удобно, напишите предпочитаемое время звонка."
                    )
                    return confirmation
            
            # Если пользователь явно просит записать
            if any(k in user_message for k in booking_keywords):
                self.user_states[user_id] = {"intent": "booking", "name": None, "phone": None, "course": None}
                return "Супер! Запишу вас. Как вас зовут?"
            
            # Если прислали номер телефона
            if re.search(phone_regex, message_text):
                m = re.search(phone_regex, message_text)
                phone_val = m.group(0)
                name_guess = message_text.replace(phone_val, '').strip().title() or (user_data.get('first_name') or '').strip()
                sched = self.parse_schedule(message_text)
                self.user_states[user_id] = {"intent": "booking", "name": name_guess, "phone": phone_val, "course": None,
                                              "days": sched.get('days'), "time_from": sched.get('time_from'), "time_to": sched.get('time_to')}
                
                if name_guess:
                    booking_data = {
                        "user_id": user_id,
                        "user_name": name_guess,
                        "user_phone": phone_val,
                        "course_id": None,
                        "course_name": "Будет уточнено",
                        "teacher_id": None,
                        "teacher_name": "Будет назначен",
                        "status": "pending",
                        "notes": "Заявка из личного чата: авто-создание (имя и телефон одним сообщением)"
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
                    self.user_states.pop(user_id, None)
                    
                    confirmation = (
                        "✅ Заявка создана!\n\n"
                        f"Имя: {booking_data['user_name']}\n"
                        f"Телефон: {booking_data['user_phone']}\n"
                        "Статус: ожидает подтверждения.\n\n"
                        + (f"Предпочтения: {', '.join(sched.get('days', []))} " if sched.get('days') else "")
                        + (f"{sched.get('time_from','')}{('-'+sched.get('time_to')) if sched.get('time_to') else ''}\n\n" if (sched.get('time_from') or sched.get('time_to')) else "")
                        + "Я свяжусь с вами в течение 15–30 минут в рабочее время (Пн–Пт 9:00–18:00).\n"
                        + "\n📍 Адрес: г. Ташкент, Мирободский район, ул. Нуронийлар, 19\n"
                        + "📞 Телефон: +998 94 843 5105 / +998 93 843 5105\n"
                        + "💬 Telegram: @tash_turkdiliuz\n"
                        + "\nЕсли удобно, напишите предпочитаемое время звонка."
                    )
                    return confirmation
                else:
                    return "Спасибо! Записал номер. Уточните, пожалуйста, ваше полное имя."
            
            # Получаем ответ от AI
            try:
                recent_conversations = self.crm.get_recent_conversations(user_id, 3)
                context = ""
                if recent_conversations:
                    context = "\n\nКонтекст предыдущих сообщений:\n"
                    for conv in reversed(recent_conversations[-2:]):
                        context += f"Пользователь: {conv['message']}\n"
                        context += f"Бот: {conv['response']}\n"
                
                # Добавляем известные предпочтения, чтобы модель не переспрашивала одно и то же
                known_prefs = []
                if user_state.get('level'):
                    known_prefs.append(f"уровень: {user_state['level']}")
                if user_state.get('format'):
                    known_prefs.append(f"формат: {'индивидуально' if user_state['format']=='individual' else 'группа'}")
                if user_state.get('mode'):
                    known_prefs.append(f"режим: {'онлайн' if user_state['mode']=='online' else 'офлайн'}")
                prefs_note = ("\n\nИзвестные предпочтения клиента: " + ", ".join(known_prefs)) if known_prefs else ""

                # Динамически собираем доступные направления из CRM и добавляем в подсказку,
                # чтобы ассистент всегда упоминал Турецкий/Английский/Корейский, если язык не указан
                available_langs = []
                try:
                    for c in self.crm.get_courses():
                        lng = (c.get("language") or "").strip()
                        if lng and lng not in available_langs:
                            available_langs.append(lng)
                except Exception:
                    pass

                lang_for_prompt = self.detect_preferred_language(original_text)
                language_note = ""
                if lang_for_prompt and lang_for_prompt != "Турецкий":
                    language_note = (
                        f"\n\nВажно: Клиента интересует обучение по языку '{lang_for_prompt}'. "
                        f"Дай информацию применительно к '{lang_for_prompt}' (уровни A1–C1, форматы, без выдумывания фактов)."
                    )
                elif available_langs:
                    language_note = (
                        "\n\nВажно: В центре есть направления по языкам: "
                        + ", ".join(available_langs)
                        + ". Если язык клиента не указан — вначале уточни язык (Турецкий/Английский/Корейский), затем предлагай уровни A1–C1 и форматы."
                    )
                
                # CRM system prompt приоритетнее встроенного
                crm_prompt = self.crm.get_ai_system_prompt() if hasattr(self.crm, 'get_ai_system_prompt') else None
                base_prompt = (crm_prompt.strip() + "\n\n") if crm_prompt else self.system_prompt
                full_prompt = f"{base_prompt}{language_note}{prefs_note}{context}\n\nТекущий вопрос пользователя: {user_message}\n\nОтветь естественно, учитывая контекст диалога. НЕ здоровайся заново, если это продолжение разговора. Не переспрашивай уже известные предпочтения."
                response = self.model.generate_content(full_prompt)
                ai_response = response.text.strip()
                
                # Сохраняем диалог в CRM
                self.crm.add_conversation(user_id, user_message, ai_response)
                
            except Exception as e:
                logger.error(f"❌ Ошибка AI API: {e}")
                
                # Fallback ответы
                if any(word in user_message for word in ['курс', 'уровень', 'изуч', 'учит', 'обуч']):
                    ai_response = """🇹🇷 Отлично, что интересуетесь турецким языком!

📚 Мои курсы:
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
                    ai_response = (
                        "Привет! Я владелец Bonus Education. "
                        "У нас есть курсы Турецкого 🇹🇷, Английского 🇬🇧 и Корейского 🇰🇷 (уровни A1–C1, группы/индивидуально, онлайн/офлайн). "
                        "Какой язык вам интересен?"
                    )
                
                # Сохраняем диалог с fallback ответом
                self.crm.add_conversation(user_id, user_message, ai_response)
            
            return ai_response
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки сообщения: {e}")
            return "Извините, произошла ошибка. Попробуйте позже."


# Пример использования для тестирования
if __name__ == "__main__":
    assistant = PersonalTelegramAssistant()
    
    # Тестовые данные пользователя
    test_user = {
        "id": 123456789,
        "first_name": "Тест",
        "last_name": "Пользователь",
        "username": "test_user"
    }
    
    # Тестовое сообщение
    test_message = "Привет! Хочу изучить турецкий язык"
    
    # Обработка сообщения
    response = assistant.process_message(test_user, test_message)
    print(f"Ответ: {response}")
