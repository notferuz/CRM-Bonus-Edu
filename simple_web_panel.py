#!/usr/bin/env python3
"""
Современная веб-панель CRM для Bonus Education с красивым UI/UX
"""

from fastapi import FastAPI, Request, Form, HTTPException, Depends, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from simple_crm import SimpleCRM
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json
import uvicorn
import csv
import io
import os
import hashlib
import secrets
from typing import Optional, List

app = FastAPI(title="Bonus Education CRM", version="2.0.0")

# Настройка шаблонов
templates = Jinja2Templates(directory="templates")

# Фильтр форматирования времени под Ташкент (Asia/Tashkent)
def format_tashkent_datetime(dt_str: str) -> str:
    try:
        if not dt_str:
            return "—"
        # Парсим ISO строку
        dt = datetime.fromisoformat(dt_str)
        tz = ZoneInfo("Asia/Tashkent")
        # Если без таймзоны — считаем, что это время Ташкента
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        else:
            dt = dt.astimezone(tz)
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return dt_str or "—"

templates.env.filters["tzdatetime"] = format_tashkent_datetime

# CRM система
crm = SimpleCRM()

# Система авторизации
security = HTTPBasic()

# Простое хранилище сессий (в реальном приложении используйте Redis или базу данных)
active_sessions = {}

def hash_password(password: str) -> str:
    """Хеширование пароля"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """Проверка пароля"""
    return hash_password(password) == hashed

def get_current_user(credentials: HTTPBasicCredentials = Depends(security)):
    """Получение текущего пользователя"""
    employees = crm.get_all_employees()
    for employee in employees:
        if employee["username"] == credentials.username:
            if verify_password(credentials.password, employee["password_hash"]):
                if employee["is_active"]:
                    return employee
                else:
                    raise HTTPException(status_code=401, detail="Аккаунт заблокирован")
            else:
                raise HTTPException(status_code=401, detail="Неверный пароль")
    raise HTTPException(status_code=401, detail="Пользователь не найден")

def check_permission(user, page: str) -> bool:
    """Проверка разрешения доступа к странице"""
    if not user or not user.get("permissions"):
        return False
    return page in user["permissions"] or "Администратор" in user.get("role", "")

def create_session(user_data: dict) -> str:
    """Создание сессии для пользователя"""
    session_id = secrets.token_urlsafe(32)
    active_sessions[session_id] = {
        "user": user_data,
        "created_at": datetime.now(),
        "last_activity": datetime.now()
    }
    return session_id

def get_user_from_session(session_id: str) -> Optional[dict]:
    """Получение пользователя по ID сессии"""
    if session_id in active_sessions:
        session = active_sessions[session_id]
        # Проверяем, не истекла ли сессия (24 часа)
        if datetime.now() - session["created_at"] < timedelta(hours=24):
            session["last_activity"] = datetime.now()
            return session["user"]
        else:
            # Удаляем истекшую сессию
            del active_sessions[session_id]
    return None

def destroy_session(session_id: str):
    """Уничтожение сессии"""
    if session_id in active_sessions:
        del active_sessions[session_id]

def get_current_user_from_request(request: Request) -> Optional[dict]:
    """Получение текущего пользователя из запроса"""
    session_id = request.cookies.get("session_id")
    if session_id:
        return get_user_from_session(session_id)
    return None

def require_auth(request: Request):
    """Проверка авторизации пользователя"""
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Необходима авторизация")
    return user

# Нормализация статуса пользователя к единому набору (как на Kanban)
def normalize_user_status(raw_status: str) -> str:
    """Нормализуем статус пользователя к расширенной воронке Канбан"""
    if not raw_status:
        return "new"
    s = str(raw_status).strip().lower()
    allowed = {
        "new", "call_success", "call_failed", "callback",
        "trial_booking", "online_trial_booking", "trial_completed",
        "prepayment", "waiting_group", "success", "failed"
    }
    legacy_map = {
        "active": "call_success",
        "converted": "success",
        "pending": "new",
        "inactive": "failed",
        "won": "success",
        "lost": "failed",
        "in_progress": "call_success",
    }
    if s in allowed:
        return s
    return legacy_map.get(s, "new")

# Нормализация статусов записей к набору Канбан
def normalize_booking_status(raw_status: str) -> str:
    """Приводит различные статусы бронирований к единому набору Канбан"""
    if not raw_status:
        return "new"
    s = str(raw_status).strip().lower()
    # Полный список столбцов в Kanban
    allowed = {
        "all", "new", "call_success", "call_failed", "callback",
        "trial_booking", "online_trial_booking", "trial_completed",
        "prepayment", "waiting_group", "success", "failed"
    }
    legacy_map = {
        # Из прежнего списка таблицы
        "pending": "new",
        "confirmed": "success",
        "cancelled": "failed",
        # Возможные другие синонимы
        "in_progress": "call_success",
        "won": "success",
        "lost": "failed",
        "active": "call_success",
        "inactive": "failed"
    }
    if s in allowed:
        return s
    return legacy_map.get(s, "new")

# Страница входа
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Страница входа в систему"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(
    username: str = Form(...),
    password: str = Form(...)
):
    """Обработка входа в систему"""
    employees = crm.get_all_employees()
    for employee in employees:
        if employee["username"] == username:
            if verify_password(password, employee["password_hash"]):
                if employee["is_active"]:
                    # Создаем сессию
                    session_id = create_session(employee)
                    response = RedirectResponse(url="/", status_code=303)
                    response.set_cookie(key="session_id", value=session_id)
                    return response
                else:
                    raise HTTPException(status_code=401, detail="Аккаунт заблокирован")
            else:
                raise HTTPException(status_code=401, detail="Неверный пароль")
    raise HTTPException(status_code=401, detail="Пользователь не найден")

@app.get("/logout")
async def logout(request: Request):
    """Выход из системы"""
    session_id = request.cookies.get("session_id")
    if session_id:
        destroy_session(session_id)
    # ВАЖНО: удаляем cookie у того ответа, который возвращаем
    redirect = RedirectResponse(url="/login", status_code=303)
    redirect.delete_cookie(key="session_id")
    return redirect

# Тестовая страница для проверки входа
@app.get("/test-login", response_class=HTMLResponse)
async def test_login_page():
    """Тестовая страница для проверки входа"""
    with open("test_login_browser.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

# Главная страница - дашборд
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Главная панель управления с красивым дизайном"""
    user = require_auth(request)
    stats = crm.get_statistics()
    recent_bookings = crm.get_recent_bookings(10)
    recent_conversations = crm.get_recent_conversations(5)
    active_users = crm.get_users_by_activity(7)
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "stats": stats,
        "current_user": user,
        "recent_bookings": recent_bookings,
        "recent_conversations": recent_conversations,
        "active_users": active_users
    })

# Страница пользователей
@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request):
    """Страница управления пользователями"""
    user = require_auth(request)
    # Обновляем данные CRM из файла, чтобы видеть свежие диалоги/пользователей
    try:
        crm.data = crm.load_data()
    except Exception:
        pass
    users = crm.data["users"]
    active_users = crm.get_users_by_activity(7)
    stats = crm.get_statistics()

    # Подсчет метрик для каждого пользователя
    conversations = crm.data.get("conversations", [])
    bookings = crm.data.get("bookings", [])

    users_with_stats = []
    new_users_today = 0
    today_str = datetime.now().date().isoformat()
    for u in users:
        telegram_id = u.get("telegram_id")
        user_conversations = [c for c in conversations if c.get("telegram_id") == telegram_id]
        user_bookings = [b for b in bookings if b.get("user_id") == telegram_id]

        unique_course_ids = set()
        for b in user_bookings:
            course_id = b.get("course_id")
            if course_id is not None:
                unique_course_ids.add(course_id)

        enriched = dict(u)
        enriched["user_conversations_count"] = len(user_conversations)
        enriched["user_bookings_count"] = len(user_bookings)
        enriched["user_courses_count"] = len(unique_course_ids)
        enriched["status"] = normalize_user_status(enriched.get("status"))
        users_with_stats.append(enriched)

        # Подсчет новых пользователей за сегодня
        created_at = u.get("created_at")
        if isinstance(created_at, str) and created_at[:10] == today_str:
            new_users_today += 1
    return templates.TemplateResponse("users.html", {
        "request": request,
        "users": users_with_stats,
        "active_users": active_users,
        "current_user": user,
        "stats": stats,
        "new_users_today": new_users_today
    })

# Детали пользователя
@app.get("/users/{user_id}", response_class=HTMLResponse)
async def user_detail_page(request: Request, user_id: int):
    current = require_auth(request)
    # Обновляем данные CRM из файла для актуальной истории чатов
    try:
        crm.data = crm.load_data()
    except Exception:
        pass

    # Находим пользователя по ID
    target_user = None
    for u in crm.data.get("users", []):
        if u.get("id") == user_id:
            target_user = dict(u)
            target_user["status"] = normalize_user_status(target_user.get("status"))
            break

    if not target_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Считаем метрики пользователя
    telegram_id = target_user.get("telegram_id")
    all_conversations = crm.data.get("conversations", [])
    all_bookings = crm.data.get("bookings", [])

    user_conversations = [c for c in all_conversations if c.get("telegram_id") == telegram_id]
    user_bookings = [b for b in all_bookings if b.get("user_id") == telegram_id]

    unique_course_ids = set()
    for b in user_bookings:
        course_id = b.get("course_id")
        if course_id is not None:
            unique_course_ids.add(course_id)

    target_user["conversations_count"] = len(user_conversations)
    target_user["bookings_count"] = len(user_bookings)
    target_user["courses_count"] = len(unique_course_ids)

    # Формируем последние активности (до 10 шт.)
    recent_activities = []
    # Добавляем бронирования
    for b in sorted(user_bookings, key=lambda x: x.get("created_at", ""), reverse=True)[:5]:
        recent_activities.append({
            "type": "booking",
            "description": f"Заявка на курс: {b.get('course_name', 'Не указан')}",
            "date": b.get("created_at", "")
        })
    # Добавляем диалоги
    for c in sorted(user_conversations, key=lambda x: x.get("created_at", ""), reverse=True)[:5]:
        recent_activities.append({
            "type": "conversation",
            "description": f"Сообщение: {c.get('message', '')[:50]}",
            "date": c.get("created_at", "")
        })

    # Сортируем общий список по дате
    recent_activities = sorted(recent_activities, key=lambda x: x.get("date", ""), reverse=True)[:10]

    # Список диалогов по времени (вся история)
    conversations_sorted = sorted(user_conversations, key=lambda x: x.get("created_at", ""))

    return templates.TemplateResponse("user_detail.html", {
        "request": request,
        "user": target_user,
        "conversations": conversations_sorted,
        "recent_activities": recent_activities,
        "current_user": current
    })

# API: получить диалоги пользователя (по ID пользователя CRM)
@app.get("/api/user_conversations/{user_id}")
async def api_user_conversations(user_id: int):
    try:
        crm.data = crm.load_data()
    except Exception:
        pass

    # находим telegram_id по user_id
    telegram_id = None
    for u in crm.data.get("users", []):
        if u.get("id") == user_id:
            telegram_id = u.get("telegram_id")
            break

    if telegram_id is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    conversations = [c for c in crm.data.get("conversations", []) if c.get("telegram_id") == telegram_id]
    # сортируем по времени по возрастанию, чтобы рендерить сверху-вниз, а потом скроллить вниз
    conversations = sorted(conversations, key=lambda x: x.get("created_at", ""))
    return conversations

# Страница курсов
@app.get("/courses", response_class=HTMLResponse)
async def courses_page(request: Request):
    """Страница управления курсами"""
    user = require_auth(request)
    courses = crm.get_courses()
    teachers = crm.get_teachers()
    return templates.TemplateResponse("courses.html", {
        "request": request,
        "courses": courses,
        "teachers": teachers,
        "current_user": user
    })

# Страница преподавателей
@app.get("/teachers", response_class=HTMLResponse)
async def teachers_page(request: Request):
    """Страница управления преподавателями"""
    user = require_auth(request)
    # Перечитываем данные, чтобы подтянуть свежие изменения
    try:
        crm.data = crm.load_data()
    except Exception:
        pass
    # Берем оригинальные данные и обогащаем полями для списка
    raw_teachers = [t for t in crm.data.get("teachers", []) if t.get("is_active", True)]
    enriched_teachers = []
    from datetime import datetime
    for t in raw_teachers:
        # Опыт в годах: берем явный, иначе считаем по created_at
        exp_years = t.get("experience_years")
        try:
            exp_years = int(exp_years) if exp_years is not None else None
        except Exception:
            exp_years = None
        if exp_years is None:
            created_at = t.get("created_at")
            if created_at:
                try:
                    exp_years = max(0, datetime.now().year - datetime.fromisoformat(created_at).year)
                except Exception:
                    exp_years = None
        # Нормализация языков в список
        raw_langs = t.get("languages")
        if isinstance(raw_langs, list):
            langs = raw_langs
        elif isinstance(raw_langs, str) and raw_langs.strip():
            langs = [lng.strip() for lng in raw_langs.split(",") if lng.strip()]
        else:
            langs = []

        enriched = dict(t)
        enriched["experience_years_display"] = exp_years
        enriched["languages"] = langs
        enriched_teachers.append(enriched)

    return templates.TemplateResponse("teachers.html", {
        "request": request,
        "teachers": enriched_teachers,
        "current_user": user
    })

# Детали преподавателя
@app.get("/teachers/{teacher_id}", response_class=HTMLResponse)
async def teacher_detail_page(request: Request, teacher_id: int):
    user = require_auth(request)
    # Берем оригинальные данные преподавателя из хранилища, а не нормализованные
    teacher = next((t for t in crm.data.get('teachers', []) if t.get('id') == teacher_id), None)
    if not teacher:
        raise HTTPException(status_code=404, detail="Преподаватель не найден")
    # Авто-расчет опыта по дате создания, если нет experience_years
    exp_years = teacher.get('experience_years')
    try:
        exp_years = int(exp_years) if exp_years is not None else None
    except Exception:
        exp_years = None
    if exp_years is None:
        try:
            created_at = next((t.get('created_at') for t in crm.data.get('teachers', []) if t.get('id') == teacher_id), None)
            if created_at:
                from datetime import datetime
                years = datetime.now().year - datetime.fromisoformat(created_at).year
                exp_years = years if years >= 0 else None
        except Exception:
            exp_years = None
    return templates.TemplateResponse("teacher_detail.html", {
        "request": request,
        "teacher": teacher,
        "experience_years_display": exp_years,
        "current_user": user
    })

# Страница записей
@app.get("/bookings", response_class=HTMLResponse)
async def bookings_page(request: Request):
    """Страница управления записями"""
    user = require_auth(request)
    bookings = crm.get_recent_bookings(50)
    # Добавляем форматированные даты по Ташкенту
    enriched = []
    for b in bookings:
        item = dict(b)
        item["created_at_fmt"] = format_tashkent_datetime(b.get("created_at"))
        item["updated_at_fmt"] = format_tashkent_datetime(b.get("updated_at"))
        # Приводим статус к единому набору для согласованности с Kanban
        item["status"] = normalize_booking_status(b.get("status"))
        enriched.append(item)
    return templates.TemplateResponse("bookings.html", {
        "request": request,
        "bookings": enriched,
        "current_user": user
    })

# Детали записи
@app.get("/bookings/{booking_id}", response_class=HTMLResponse)
async def booking_detail_page(request: Request, booking_id: int):
    """Детальная страница записи"""
    user = require_auth(request)
    # Перечитываем данные для актуальности
    try:
        crm.data = crm.load_data()
    except Exception:
        pass
    booking = crm.get_booking(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    # Подтягиваем пользователя и курс/преподавателя при наличии
    related_user = None
    for u in crm.data.get("users", []):
        if u.get("telegram_id") == booking.get("user_id"):
            related_user = u
            break

    course = None
    if booking.get("course_id"):
        course = crm.get_course(booking.get("course_id"))

    teacher = None
    if booking.get("teacher_id"):
        for t in crm.data.get("teachers", []):
            if t.get("id") == booking.get("teacher_id"):
                teacher = t
                break

    return templates.TemplateResponse("booking_detail.html", {
        "request": request,
        "booking": booking,
        "created_at_fmt": format_tashkent_datetime(booking.get("created_at")),
        "updated_at_fmt": format_tashkent_datetime(booking.get("updated_at")),
        "related_user": related_user,
        "course": course,
        "teacher": teacher,
        "current_user": user
    })

# Страница аналитики
@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request):
    """Страница аналитики и отчетов"""
    user = require_auth(request)
    stats = crm.get_statistics()
    recent_bookings = crm.get_recent_bookings(20)
    active_users = crm.get_users_by_activity(30)
    
    return templates.TemplateResponse("analytics.html", {
        "request": request,
        "stats": stats,
        "recent_bookings": recent_bookings,
        "active_users": active_users,
        "current_user": user
    })

# ===== AI Training (Prompts) =====
@app.get("/ai-training", response_class=HTMLResponse)
async def ai_training_page(request: Request):
    user = require_auth(request)
    current_prompt = crm.get_ai_system_prompt() or ""
    return templates.TemplateResponse("ai_training.html", {
        "request": request,
        "current_user": user,
        "system_prompt": current_prompt
    })

@app.post("/ai-training/save")
async def ai_training_save(request: Request):
    user = require_auth(request)
    form = await request.form()
    system_prompt = form.get('system_prompt') or ""
    crm.set_ai_system_prompt(system_prompt)
    return RedirectResponse(url="/ai-training", status_code=303)

# Kanban доска
@app.get("/kanban", response_class=HTMLResponse)
async def kanban_page(request: Request):
    """Kanban доска: отображаем пользователей как карточки с их статусом"""
    user = require_auth(request)
    # Перечитываем актуальные данные
    try:
        crm.data = crm.load_data()
    except Exception:
        pass
    # Преобразуем пользователей в вид "bookings" для текущего шаблона
    users_raw = crm.data.get("users", [])
    bookings_like = []
    for u in users_raw:
        status_raw = normalize_user_status(u.get("status"))
        # Используем статус как есть — колонки в шаблоне покрывают всю воронку
        mapped_status = status_raw
        full_name = ((u.get("first_name") or "").strip() + " " + (u.get("last_name") or "").strip()).strip()
        display_name = full_name or (u.get("username") or "Не указано")
        booking_card = {
            "id": u.get("id") or u.get("telegram_id"),
            "user_name": display_name,
            "user_phone": u.get("phone") or "Не указан",
            "course_name": "—",
            "status": mapped_status,
            "created_at": u.get("last_activity")
        }
        bookings_like.append(booking_card)
    return templates.TemplateResponse("kanban.html", {
        "request": request,
        "bookings": bookings_like,
        "current_user": user
    })

# Страница сотрудников
@app.get("/employees", response_class=HTMLResponse)
async def employees_page(request: Request):
    """Страница управления сотрудниками"""
    user = require_auth(request)
    employees = crm.get_all_employees()
    return templates.TemplateResponse("employees.html", {
        "request": request,
        "employees": employees,
        "current_user": user
    })

# API endpoints
@app.post("/api/add_course")
async def add_course(
    name: str = Form(...),
    description: str = Form(...),
    price: str = Form(...),
    # Дополнительно
    duration: str = Form(None),
    duration_months: int = Form(None),
    level: str = Form(None),
    status: str = Form(None),
    language: str = Form("Турецкий"),
    teacher_id: int = Form(None),
    time_from: str = Form(None),
    time_to: str = Form(None),
    days: List[str] = Form(None)
):
    """API для добавления курса (расширенные поля)"""
    course = {
        "id": len(crm.data["courses"]) + 1,
        "name": name,
        "description": description,
        "duration": duration or (f"{duration_months} месяца" if duration_months else None),
        "duration_months": duration_months,
        "price": price,
        "level": level,
        "status": status,
        "language": language or "Турецкий",
        "days": [d for d in (days or []) if d],
        "time_from": time_from or None,
        "time_to": time_to or None,
        "is_active": True,
        "created_at": datetime.now().isoformat()
    }
    if teacher_id:
        for t in crm.data.get("teachers", []):
            if t.get("id") == teacher_id:
                course["teacher_id"] = teacher_id
                course["teacher_name"] = t.get("name")
                break
    crm.data["courses"].append(course)
    crm.save_data()
    return {"success": True, "message": "Курс успешно добавлен"}

@app.post("/add_teacher")
async def add_teacher(
    name: str = Form(...),
    telegram_contact: str = Form(...),
    certificate_level: str = Form(...),
    experience_years: int = Form(...),
    specialization: str = Form(...),
    work_time_start: str = Form(None),
    work_time_end: str = Form(None),
    advantages: str = Form(None),
    disadvantages: str = Form(None)
):
    """Добавление преподавателя"""
    teacher = {
        "id": len(crm.data["teachers"]) + 1,
        "name": name,
        "telegram_contact": telegram_contact,
        "certificate_level": certificate_level,
        "experience_years": experience_years,
        "specialization": specialization,
        "work_time_start": work_time_start,
        "work_time_end": work_time_end,
        "advantages": advantages,
        "disadvantages": disadvantages,
        "is_active": True,
        "created_at": datetime.now().isoformat()
    }
    crm.data["teachers"].append(teacher)
    crm.save_data()
    return RedirectResponse(url="/teachers", status_code=303)

# Маршруты для сотрудников
@app.post("/add_employee")
async def add_employee(
    name: str = Form(...),
    role: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    email: str = Form(None),
    phone: str = Form(None),
    permissions: list = Form(...),
    is_active: bool = Form(True)
):
    """Добавление сотрудника"""
    # Проверяем уникальность логина
    employees = crm.get_all_employees()
    for emp in employees:
        if emp["username"] == username:
            raise HTTPException(status_code=400, detail="Пользователь с таким логином уже существует")
    
    employee = {
        "id": len(employees) + 1,
        "name": name,
        "role": role,
        "username": username,
        "password_hash": hash_password(password),
        "email": email,
        "phone": phone,
        "permissions": permissions,
        "is_active": is_active,
        "created_at": datetime.now().isoformat()
    }
    crm.data["employees"].append(employee)
    crm.save_data()
    return RedirectResponse(url="/employees", status_code=303)

@app.post("/update_employee/{employee_id}")
async def update_employee(
    employee_id: int,
    name: str = Form(...),
    role: str = Form(...),
    username: str = Form(...),
    email: str = Form(None),
    phone: str = Form(None),
    permissions: list = Form(...),
    is_active: bool = Form(True)
):
    """Обновление сотрудника"""
    employees = crm.get_all_employees()
    for i, emp in enumerate(employees):
        if emp["id"] == employee_id:
            # Проверяем уникальность логина (кроме текущего пользователя)
            for emp2 in employees:
                if emp2["username"] == username and emp2["id"] != employee_id:
                    raise HTTPException(status_code=400, detail="Пользователь с таким логином уже существует")
            
            employee_data = {
                "name": name,
                "role": role,
                "username": username,
                "email": email,
                "phone": phone,
                "permissions": permissions,
                "is_active": is_active,
                "updated_at": datetime.now().isoformat()
            }
            crm.data["employees"][i].update(employee_data)
            crm.save_data()
            return RedirectResponse(url="/employees", status_code=303)
    
    raise HTTPException(status_code=404, detail="Сотрудник не найден")

@app.post("/delete_employee/{employee_id}", response_class=RedirectResponse)
async def delete_employee(employee_id: int):
    """Удаление сотрудника"""
    crm.delete_employee(employee_id)
    return RedirectResponse(url="/employees", status_code=303)

@app.get("/api/stats")
async def get_stats(request: Request):
    """API для получения статистики"""
    require_auth(request)
    return crm.get_statistics()

@app.get("/api/users")
async def get_users():
    """API для получения пользователей"""
    return crm.data["users"]

@app.get("/api/courses")
async def get_courses():
    """API для получения курсов"""
    return crm.get_courses()

@app.get("/api/bookings")
async def get_bookings():
    """API для получения записей"""
    return crm.get_recent_bookings(50)

@app.get("/api/analytics")
async def get_analytics():
    """API для получения аналитики"""
    stats = crm.get_statistics()
    recent_bookings = crm.get_recent_bookings(20)
    active_users = crm.get_users_by_activity(30)
    
    return {
        "stats": stats,
        "recent_bookings": recent_bookings,
        "active_users": active_users
    }

@app.post("/update_booking_status/{booking_id}", response_class=RedirectResponse)
async def update_booking_status(
    booking_id: int,
    status: str = Form(...)
):
    crm.update_booking_status(booking_id, status)
    return RedirectResponse(url="/bookings", status_code=303)

@app.post("/edit_course/{course_id}", response_class=RedirectResponse)
async def edit_course(course_id: int, request: Request):
    form = await request.form()
    # Читаем поля из формы вручную, чтобы корректно обработать множественный выбор
    name = form.get('name')
    description = form.get('description')
    # duration отображаем как months; при сохранении соберем строку тоже
    duration_months = form.get('duration_months')
    price = form.get('price')
    level = form.get('level')
    # множественные чекбоксы
    days = form.getlist('days') if hasattr(form, 'getlist') else [v for k, v in form.multi_items() if k == 'days']
    time_from = form.get('time_from')
    time_to = form.get('time_to')
    teacher_id_raw = form.get('teacher_id')
    status = form.get('status')
    language = form.get('language')
    course_data = {
        "name": name,
        "description": description,
        "duration_months": int(duration_months) if duration_months else None,
        "duration": f"{duration_months} месяца" if duration_months else None,
        "price": price,
        "level": level,
        "days": [d for d in (days or []) if d],
        "time_from": time_from or None,
        "time_to": time_to or None,
        "status": status or None,
        "language": language or 'Турецкий'
    }
    if teacher_id_raw:
        try:
            teacher_id = int(teacher_id_raw)
            for t in crm.data.get("teachers", []):
                if t.get("id") == teacher_id:
                    course_data["teacher_id"] = teacher_id
                    course_data["teacher_name"] = t.get("name")
                    break
        except ValueError:
            pass
    crm.update_course(course_id, course_data)
    return RedirectResponse(url="/courses", status_code=303)

@app.post("/update_teacher/{teacher_id}", response_class=RedirectResponse)
async def update_teacher(
    teacher_id: int,
    name: str = Form(...),
    specialization: str = Form(...),
    phone: str = Form(None),
    email: str = Form(None),
    experience: str = Form(None),
    hours_per_week: int = Form(None),
    education: str = Form(None),
    languages: List[str] = Form(None),
    rating: float = Form(None),
    # Дополнительные поля
    telegram_contact: str = Form(None),
    certificate_level: str = Form(None),
    work_time_start: str = Form(None),
    work_time_end: str = Form(None),
    advantages: str = Form(None),
    disadvantages: str = Form(None)
):
    # Обрабатываем языки как список из чекбоксов
    languages_list = []
    if languages:
        languages_list = [lang.strip() for lang in languages if lang and lang.strip()]
    
    teacher_data = {
        "name": name,
        "specialization": specialization,
        "phone": phone,
        "email": email,
        "experience": experience,
        "hours_per_week": hours_per_week,
        "education": education,
        "languages": languages_list,
        "rating": rating,
        "telegram_contact": telegram_contact,
        "certificate_level": certificate_level,
        "work_time_start": work_time_start,
        "work_time_end": work_time_end,
        "advantages": advantages,
        "disadvantages": disadvantages
    }
    crm.update_teacher(teacher_id, teacher_data)
    # Возвращаемся на страницу деталей
    return RedirectResponse(url=f"/teachers/{teacher_id}", status_code=303)

@app.post("/edit_user/{user_id}", response_class=RedirectResponse)
async def edit_user(user_id: int, request: Request):
    # Читаем все поля формы и обновляем только переданные
    form = await request.form()
    allowed_fields = {
        "first_name", "last_name", "phone", "email", "username", "instagram_username",
        "level", "source", "status", "first_contact_date", "first_call_response",
        "first_call_date", "second_contact_response", "second_contact_date",
        "decision", "decision_date", "preferred_language"
    }
    update_data = {}
    for key in allowed_fields:
        if key in form:
            val = form.get(key)
            # Пустые строки сохраняем как None
            update_data[key] = val if (val is not None and str(val).strip() != "") else None
    if update_data:
        crm.update_user(user_id, update_data)
    return RedirectResponse(url=f"/users/{user_id}", status_code=303)

@app.post("/delete_course/{course_id}", response_class=RedirectResponse)
async def delete_course(course_id: int):
    crm.delete_course(course_id)
    return RedirectResponse(url="/courses", status_code=303)

@app.post("/delete_teacher/{teacher_id}", response_class=RedirectResponse)
async def delete_teacher(teacher_id: int):
    crm.delete_teacher(teacher_id)
    return RedirectResponse(url="/teachers", status_code=303)

@app.post("/delete_user/{user_id}", response_class=RedirectResponse)
async def delete_user(user_id: int):
    crm.delete_user(user_id)
    return RedirectResponse(url="/users", status_code=303)

# Удаление записи (booking)
@app.post("/delete_booking/{booking_id}", response_class=RedirectResponse)
async def delete_booking(booking_id: int):
    """Удаление записи и возврат на список записей"""
    try:
        crm.delete_booking(booking_id)
    finally:
        # В любом случае возвращаемся на список
        return RedirectResponse(url="/bookings", status_code=303)

# API для обновления статуса записи (для Kanban доски)
@app.post("/update_booking_status/{booking_id}")
async def update_booking_status(booking_id: int, status: str = Form(...)):
    """Обновить статус записи; если записи нет, обновляем статус пользователя с таким ID"""
    try:
        updated = crm.update_booking_status(booking_id, status)
        if updated:
            return JSONResponse({"success": True, "message": "Статус записи обновлен"})
        # Пытаемся обновить пользователя, если запись не найдена
        for i, u in enumerate(crm.data.get("users", [])):
            if u.get("id") == booking_id or u.get("telegram_id") == booking_id:
                crm.data["users"][i]["status"] = status
                crm.data["users"][i]["updated_at"] = datetime.now().isoformat()
                crm.save_data()
                return JSONResponse({"success": True, "message": "Статус пользователя обновлен"})
        return JSONResponse({"success": False, "message": "Ни запись, ни пользователь не найдены"}, status_code=404)
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)}, status_code=400)

# API: обновить статус пользователя (для Kanban по пользователям)
@app.post("/update_user_status/{user_id}")
async def update_user_status(user_id: int, status: str = Form(...)):
    try:
        # Находим пользователя по CRM id (telegram_id хранится как user_id в заявках)
        for i, u in enumerate(crm.data.get("users", [])):
            if u.get("id") == user_id or u.get("telegram_id") == user_id:
                crm.data["users"][i]["status"] = status
                crm.data["users"][i]["updated_at"] = datetime.now().isoformat()
                crm.save_data()
                return JSONResponse({"success": True, "message": "Статус пользователя обновлен"})
        return JSONResponse({"success": False, "message": "Пользователь не найден"}, status_code=404)
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)}, status_code=400)

# Маршруты для экспорта в CSV
@app.get("/export/{data_type}")
async def export_to_csv(data_type: str):
    """Экспорт данных в CSV"""
    try:
        if data_type == "users":
            data = crm.get_all_users()
            filename = f"users_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
        elif data_type == "bookings":
            data = crm.get_all_bookings()
            filename = f"bookings_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
        elif data_type == "courses":
            data = crm.get_all_courses()
            filename = f"courses_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
        elif data_type == "teachers":
            data = crm.get_all_teachers()
            filename = f"teachers_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
        else:
            raise HTTPException(status_code=400, detail="Неверный тип данных")
        
        if not data:
            raise HTTPException(status_code=404, detail="Данные не найдены")
        
        # Создаем CSV файл в памяти
        output = io.StringIO()
        if data:
            fieldnames = data[0].keys()
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        
        output.seek(0)
        csv_content = output.getvalue()
        
        # Конвертируем в bytes для FileResponse
        csv_bytes = io.BytesIO(csv_content.encode('utf-8'))
        csv_bytes.seek(0)
        
        return FileResponse(
            path=csv_bytes,
            filename=filename,
            media_type='text/csv'
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка экспорта: {str(e)}")

if __name__ == "__main__":
    print("🌐 Запуск современной веб-панели Bonus Education...")
    print("📍 Адрес: http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)