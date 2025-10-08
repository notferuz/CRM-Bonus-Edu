#!/usr/bin/env python3
"""
Скрипт для синхронизации пользователей из conversations с CRM
"""

import json
from datetime import datetime
from simple_crm import SimpleCRM

def sync_users_from_conversations():
    """Синхронизирует пользователей из conversations с users"""
    crm = SimpleCRM()
    
    # Получаем все уникальные telegram_id из conversations
    conversation_users = set()
    for conv in crm.data["conversations"]:
        conversation_users.add(conv["telegram_id"])
    
    # Получаем всех существующих пользователей
    existing_users = set()
    for user in crm.data["users"]:
        existing_users.add(user["telegram_id"])
    
    # Находим пользователей, которые есть в conversations, но нет в users
    missing_users = conversation_users - existing_users
    
    print(f"Найдено {len(missing_users)} пользователей в conversations, которых нет в users:")
    
    for telegram_id in missing_users:
        # Находим первое сообщение этого пользователя
        first_conversation = None
        for conv in crm.data["conversations"]:
            if conv["telegram_id"] == telegram_id:
                first_conversation = conv
                break
        
        if first_conversation:
            # Создаем нового пользователя
            user_data = {
                "telegram_id": telegram_id,
                "username": None,  # Не знаем username
                "first_name": f"Пользователь {telegram_id}",  # Временное имя
                "last_name": None,
                "phone": None,
                "instagram_username": None,
                "level": None,
                "source": "telegram",
                "status": "active",
                "first_contact_date": first_conversation["created_at"][:10],
                "first_call_response": None,
                "first_call_date": None,
                "second_contact_response": None,
                "second_contact_date": None,
                "decision": None,
                "decision_date": None,
                "result": None,
                "is_active": True,
                "created_at": first_conversation["created_at"],
                "last_activity": first_conversation["created_at"]
            }
            
            # Добавляем пользователя
            user_id = crm.add_user(user_data)
            print(f"  - Добавлен пользователь ID {telegram_id} как пользователь #{user_id}")
    
    # Обновляем статистику
    crm.data["statistics"]["total_users"] = len(crm.data["users"])
    crm.save_data()
    
    print(f"\nСинхронизация завершена. Теперь в CRM {len(crm.data['users'])} пользователей.")

if __name__ == "__main__":
    sync_users_from_conversations()

