#!/usr/bin/env python3
"""
Упрощенная CRM система без SQLAlchemy для демонстрации
"""

import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional

class SimpleCRM:
    def __init__(self, data_file: str = "crm_data.json"):
        self.data_file = data_file
        self.data = self.load_data()
    
    def load_data(self) -> Dict:
        """Загрузить данные из файла"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Убеждаемся, что есть секция employees
                    if "employees" not in data:
                        data["employees"] = []
                    # Секция AI промптов
                    if "ai_prompts" not in data:
                        data["ai_prompts"] = {"system_prompt": None}
                    return data
            except:
                pass        
        # Инициализация с тестовыми данными
        return {
            "users": [],
            "courses": [
                {
                    "id": 1,
                    "name": "Турецкий язык A1 (Начальный уровень)",
                    "description": "Изучение турецкого языка с нуля. Основы грамматики, лексика, произношение",
                    "duration": "2 месяца",
                    "price": "Уточняется на консультации",
                    "is_active": True
                },
                {
                    "id": 2,
                    "name": "Турецкий язык A2 (Элементарный уровень)",
                    "description": "Продолжение изучения турецкого языка. Расширение словарного запаса и грамматики",
                    "duration": "2 месяца",
                    "price": "Уточняется на консультации",
                    "is_active": True
                },
                {
                    "id": 3,
                    "name": "Турецкий язык B1 (Средний уровень)",
                    "description": "Средний уровень турецкого языка. Сложные грамматические конструкции, разговорная практика",
                    "duration": "3 месяца",
                    "price": "Уточняется на консультации",
                    "is_active": True
                },
                {
                    "id": 4,
                    "name": "Турецкий язык B2 (Средне-продвинутый уровень)",
                    "description": "Продвинутый уровень турецкого языка. Свободное общение, понимание сложных текстов",
                    "duration": "3 месяца",
                    "price": "Уточняется на консультации",
                    "is_active": True
                },
                {
                    "id": 5,
                    "name": "Турецкий язык C1 (Продвинутый уровень)",
                    "description": "Профессиональный уровень турецкого языка. Деловое общение, специализированная лексика",
                    "duration": "4 месяца",
                    "price": "Уточняется на консультации",
                    "is_active": True
                },
                {
                    "id": 6,
                    "name": "Индивидуальные занятия",
                    "description": "Персональные уроки турецкого языка с опытным преподавателем",
                    "duration": "По договоренности",
                    "price": "Уточняется на консультации",
                    "is_active": True
                }
            ],
            "employees": [
                {
                    "id": 1,
                    "name": "Главный Администратор",
                    "role": "Супер Администратор",
                    "username": "bonusedu",
                    "password_hash": "a6958ecd9b0477cda81904b22e39d8f65cfd922c1ff733aa155c6e9bc62d5e78",  # password: "87654321b"
                    "email": "admin@bonuseducation.uz",
                    "phone": "+998901234567",
                    "permissions": ["dashboard", "users", "teachers", "courses", "bookings", "kanban", "analytics", "employees"],
                    "is_active": True,
                    "created_at": datetime.now().isoformat()
                },
                {
                    "id": 2,
                    "name": "Администратор",
                    "role": "Администратор",
                    "username": "admin",
                    "password_hash": "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8",  # password: "password"
                    "email": "admin2@bonuseducation.uz",
                    "phone": "+998901234568",
                    "permissions": ["dashboard", "users", "teachers", "courses", "bookings", "kanban", "analytics", "employees"],
                    "is_active": True,
                    "created_at": datetime.now().isoformat()
                }
            ],
            "teachers": [
                {
                    "id": 1,
                    "name": "Азиза Каримова",
                    "specialization": "Турецкий язык A1-A2",
                    "experience": "5 лет",
                    "languages": ["турецкий", "узбекский", "русский"],
                    "is_active": True
                },
                {
                    "id": 2,
                    "name": "Мухаммад Турсун",
                    "specialization": "Турецкий язык B1-C1",
                    "experience": "8 лет",
                    "languages": ["турецкий", "узбекский", "русский"],
                    "is_active": True
                }
            ],
            "bookings": [],
            "conversations": [],
            "statistics": {
                "total_users": 0,
                "total_conversations": 0,
                "total_bookings": 0,
                "active_courses": 6,
                "active_teachers": 2
            },
            "ai_prompts": {
                "system_prompt": None
            }
        }
    
    def save_data(self):
        """Сохранить данные в файл"""
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def add_user(self, user_data: Dict) -> int:
        """Добавить пользователя"""
        # Генерируем уникальный ID - находим максимальный существующий ID и добавляем 1
        existing_ids = [user.get("id", 0) for user in self.data["users"]]
        user_id = max(existing_ids, default=0) + 1
        
        user_data["id"] = user_id
        user_data["created_at"] = datetime.now().isoformat()
        user_data["last_activity"] = datetime.now().isoformat()
        self.data["users"].append(user_data)
        self.data["statistics"]["total_users"] = len(self.data["users"])
        self.save_data()
        return user_id
    
    def get_user(self, telegram_id: int) -> Optional[Dict]:
        """Получить пользователя по Telegram ID"""
        for user in self.data["users"]:
            if user.get("telegram_id") == telegram_id:
                return user
        return None
    
    def update_user_activity(self, telegram_id: int):
        """Обновить активность пользователя"""
        user = self.get_user(telegram_id)
        if user:
            user["last_activity"] = datetime.now().isoformat()
            self.save_data()
    
    def add_conversation(self, telegram_id: int, message: str, response: str):
        """Добавить диалог"""
        conversation = {
            "id": len(self.data["conversations"]) + 1,
            "telegram_id": telegram_id,
            "message": message,
            "response": response,
            "created_at": datetime.now().isoformat()
        }
        self.data["conversations"].append(conversation)
        
        # Инициализируем статистику если её нет
        if "statistics" not in self.data:
            self.data["statistics"] = {
                "total_users": len(self.data.get("users", [])),
                "total_conversations": len(self.data.get("conversations", [])),
                "total_bookings": len(self.data.get("bookings", [])),
                "active_courses": len([c for c in self.data.get("courses", []) if c.get("is_active", True)]),
                "active_teachers": len([t for t in self.data.get("teachers", []) if t.get("is_active", True)])
            }
        
        self.data["statistics"]["total_conversations"] = len(self.data["conversations"])
        self.save_data()
    
    def add_booking(self, booking_data: Dict) -> int:
        """Добавить запись на курс"""
        booking_id = len(self.data["bookings"]) + 1
        booking_data["id"] = booking_id
        booking_data["created_at"] = datetime.now().isoformat()
        booking_data["status"] = "pending"
        self.data["bookings"].append(booking_data)
        
        # Инициализируем статистику если её нет
        if "statistics" not in self.data:
            self.data["statistics"] = {
                "total_users": len(self.data.get("users", [])),
                "total_conversations": len(self.data.get("conversations", [])),
                "total_bookings": len(self.data.get("bookings", [])),
                "active_courses": len([c for c in self.data.get("courses", []) if c.get("is_active", True)]),
                "active_teachers": len([t for t in self.data.get("teachers", []) if t.get("is_active", True)])
            }
        
        self.data["statistics"]["total_bookings"] = len(self.data["bookings"])
        self.save_data()
        return booking_id
    
    def get_courses(self) -> List[Dict]:
        """Получить все курсы"""
        courses = []
        for course in self.data["courses"]:
            if course.get("is_active", True):
                # Нормализуем структуру курса
                normalized_course = {
                    "id": course.get("id"),
                    "name": course.get("name"),
                    "description": course.get("description"),
                    "duration": course.get("duration", f"{course.get('duration_months', 2)} месяца"),
                    "duration_months": course.get("duration_months", None),
                    "level": course.get("level"),
                    "status": course.get("status"),
                    "language": course.get("language", "Турецкий"),
                    "price": course.get("price", "Уточняется на консультации"),
                    "is_active": course.get("is_active", True),
                    # Новые поля расписания (необязательные)
                    "days": course.get("days", []),
                    "time_from": course.get("time_from"),
                    "time_to": course.get("time_to"),
                    "teacher_id": course.get("teacher_id"),
                    "teacher_name": course.get("teacher_name")
                }
                courses.append(normalized_course)
        return courses
    
    def get_course(self, course_id: int) -> Optional[Dict]:
        """Получить курс по ID"""
        for course in self.data["courses"]:
            if course["id"] == course_id:
                # Нормализуем структуру курса
                return {
                    "id": course.get("id"),
                    "name": course.get("name"),
                    "description": course.get("description"),
                    "duration": course.get("duration", f"{course.get('duration_months', 2)} месяца"),
                    "duration_months": course.get("duration_months", None),
                    "level": course.get("level"),
                    "status": course.get("status"),
                    "language": course.get("language", "Турецкий"),
                    "price": course.get("price", "Уточняется на консультации"),
                    "is_active": course.get("is_active", True),
                    "days": course.get("days", []),
                    "time_from": course.get("time_from"),
                    "time_to": course.get("time_to"),
                    "teacher_id": course.get("teacher_id"),
                    "teacher_name": course.get("teacher_name")
                }
        return None
    
    def get_teachers(self) -> List[Dict]:
        """Получить всех преподавателей"""
        teachers = []
        for teacher in self.data["teachers"]:
            if teacher.get("is_active", True):
                # Нормализуем структуру преподавателя
                # Нормализуем языки: допускаем как список, так и строку
                raw_languages = teacher.get("languages")
                if isinstance(raw_languages, list):
                    languages = raw_languages
                elif isinstance(raw_languages, str) and raw_languages.strip():
                    # Разбиваем по запятой, игнорируя пробелы
                    languages = [lng.strip() for lng in raw_languages.split(",") if lng.strip()]
                else:
                    languages = ["турецкий", "русский"]

                normalized_teacher = {
                    "id": teacher.get("id"),
                    "name": teacher.get("name"),
                    "specialization": teacher.get("specialization"),
                    "experience": f"{teacher.get('experience_years', 5)} лет",
                    "languages": languages,
                    "is_active": teacher.get("is_active", True)
                }
                teachers.append(normalized_teacher)
        return teachers
    
    def get_statistics(self) -> Dict:
        """Получить статистику (пересчёт при каждом вызове)"""
        try:
            # перечитываем свежие данные с диска, чтобы цифры совпадали со списками
            self.data = self.load_data()
        except Exception:
            pass
        stats = self.data.get("statistics", {}) or {}
        stats["total_users"] = len(self.data.get("users", []))
        stats["total_conversations"] = len(self.data.get("conversations", []))
        stats["total_bookings"] = len(self.data.get("bookings", []))
        stats["active_courses"] = len([c for c in self.data.get("courses", []) if c.get("is_active", True)])
        stats["active_teachers"] = len([t for t in self.data.get("teachers", []) if t.get("is_active", True)])
        self.data["statistics"] = stats
        return stats
    
    def get_recent_conversations(self, user_id: int = None, limit: int = 10) -> List[Dict]:
        """Получить последние диалоги"""
        conversations = self.data["conversations"]
        
        # Фильтруем по пользователю если указан
        if user_id:
            conversations = [conv for conv in conversations if conv.get("telegram_id") == user_id]
        
        return sorted(conversations, key=lambda x: x["created_at"], reverse=True)[:limit]
    
    def get_recent_bookings(self, limit: int = 10) -> List[Dict]:
        """Получить последние записи"""
        return sorted(self.data["bookings"], key=lambda x: x["created_at"], reverse=True)[:limit]
    
    def get_users_by_activity(self, days: int = 7) -> List[Dict]:
        """Получить активных пользователей за последние N дней"""
        cutoff_date = datetime.now() - timedelta(days=days)
        active_users = []
        
        for user in self.data["users"]:
            last_activity = datetime.fromisoformat(user.get("last_activity", "2020-01-01"))
            if last_activity > cutoff_date:
                active_users.append(user)
        
        return active_users
    
    def update_course(self, course_id: int, course_data: Dict) -> bool:
        """Обновить курс"""
        for i, course in enumerate(self.data["courses"]):
            if course["id"] == course_id:
                # Сохраняем расписание и преподавателя
                self.data["courses"][i].update(course_data)
                # Гарантируем наличие полей в хранилище
                if "days" in course_data and course_data["days"] is None:
                    self.data["courses"][i]["days"] = []
                if "time_from" in course_data and course_data["time_from"] is None:
                    self.data["courses"][i]["time_from"] = None
                if "time_to" in course_data and course_data["time_to"] is None:
                    self.data["courses"][i]["time_to"] = None
                self.save_data()
                return True
        return False
    
    def update_teacher(self, teacher_id: int, teacher_data: Dict) -> bool:
        """Обновить преподавателя"""
        for i, teacher in enumerate(self.data["teachers"]):
            if teacher["id"] == teacher_id:
                self.data["teachers"][i].update(teacher_data)
                self.save_data()
                return True
        return False
    
    def update_user(self, user_id: int, user_data: Dict) -> bool:
        """Обновить пользователя"""
        for i, user in enumerate(self.data["users"]):
            if user["id"] == user_id:
                self.data["users"][i].update(user_data)
                self.save_data()
                return True
        return False
    
    def delete_course(self, course_id: int) -> bool:
        """Удалить курс"""
        for i, course in enumerate(self.data["courses"]):
            if course["id"] == course_id:
                del self.data["courses"][i]
                self.save_data()
                return True
        return False
    
    def delete_teacher(self, teacher_id: int) -> bool:
        """Удалить преподавателя"""
        for i, teacher in enumerate(self.data["teachers"]):
            if teacher["id"] == teacher_id:
                del self.data["teachers"][i]
                self.save_data()
                return True
        return False
    
    def delete_user(self, user_id: int) -> bool:
        """Удалить пользователя"""
        for i, user in enumerate(self.data["users"]):
            if user["id"] == user_id:
                del self.data["users"][i]
                # Обновляем статистику
                self.data["statistics"]["total_users"] = len(self.data["users"])
                self.save_data()
                return True
        return False
    
    def get_booking(self, booking_id: int) -> Optional[Dict]:
        """Получить запись по ID"""
        for booking in self.data["bookings"]:
            if booking["id"] == booking_id:
                return booking
        return None
    
    def update_booking(self, booking_id: int, booking_data: Dict) -> bool:
        """Обновить запись"""
        for i, booking in enumerate(self.data["bookings"]):
            if booking["id"] == booking_id:
                self.data["bookings"][i].update(booking_data)
                self.save_data()
                return True
        return False
    
    def delete_booking(self, booking_id: int) -> bool:
        """Удалить запись"""
        for i, booking in enumerate(self.data["bookings"]):
            if booking["id"] == booking_id:
                del self.data["bookings"][i]
                self.save_data()
                return True
        return False
    
    def update_booking_status(self, booking_id: int, status: str) -> bool:
        """Обновить статус записи"""
        for i, booking in enumerate(self.data["bookings"]):
            if booking["id"] == booking_id:
                self.data["bookings"][i]["status"] = status
                self.data["bookings"][i]["updated_at"] = datetime.now().isoformat()
                self.save_data()
                return True
        return False

    def get_all_users(self):
        """Получить всех пользователей"""
        return self.data.get("users", [])

    def get_all_bookings(self):
        """Получить все записи"""
        return self.data.get("bookings", [])

    def get_all_courses(self):
        """Получить все курсы"""
        return self.data.get("courses", [])

    def get_all_teachers(self):
        """Получить всех преподавателей"""
        return self.data.get("teachers", [])

    def get_all_employees(self):
        """Получить всех сотрудников"""
        return self.data.get("employees", [])

    def delete_employee(self, employee_id: int) -> bool:
        """Удалить сотрудника"""
        for i, employee in enumerate(self.data.get("employees", [])):
            if employee["id"] == employee_id:
                del self.data["employees"][i]
                self.save_data()
                return True
        return False

    # ===== AI prompts =====
    def get_ai_system_prompt(self) -> Optional[str]:
        try:
            # всегда перечитываем файл, чтобы изменения из веб-панели применялись без перезапуска
            self.data = self.load_data()
            return (self.data.get("ai_prompts", {}) or {}).get("system_prompt")
        except Exception:
            return None

    def set_ai_system_prompt(self, prompt_text: str):
        if "ai_prompts" not in self.data or not isinstance(self.data["ai_prompts"], dict):
            self.data["ai_prompts"] = {}
        self.data["ai_prompts"]["system_prompt"] = prompt_text or None
        self.save_data()