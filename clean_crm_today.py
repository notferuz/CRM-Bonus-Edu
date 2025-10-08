#!/usr/bin/env python3
"""
Cleanup CRM: keep only today's users, bookings, and conversations.
Makes a backup: crm_data.backup.json
"""
import json
from datetime import datetime
from pathlib import Path

CRM_PATH = Path("crm_data.json")
BACKUP_PATH = Path("crm_data.backup.json")

def iso_date(dt_str: str) -> str:
    if not dt_str:
        return ""
    # Accept either ISO datetime or date
    return dt_str[:10]

def main():
    today = datetime.now().date().isoformat()
    if not CRM_PATH.exists():
        print("❌ crm_data.json not found")
        return
    data = json.loads(CRM_PATH.read_text(encoding="utf-8"))

    # Backup
    BACKUP_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # Filter users by first_contact_date == today
    users = data.get("users", [])
    users_today = []
    keep_telegram_ids = set()
    for u in users:
        fcd = u.get("first_contact_date")
        if fcd and fcd == today:
            users_today.append(u)
            tid = u.get("telegram_id")
            if tid is not None:
                keep_telegram_ids.add(tid)

    # Filter conversations for today OR belonging to kept users and created today
    conversations = data.get("conversations", [])
    conversations_today = []
    for c in conversations:
        if iso_date(c.get("created_at")) == today:
            # additionally ensure user is kept if we filtered users by today
            if not keep_telegram_ids or c.get("telegram_id") in keep_telegram_ids:
                conversations_today.append(c)

    # Filter bookings created today OR user_id in kept users and created today
    bookings = data.get("bookings", [])
    bookings_today = []
    for b in bookings:
        if iso_date(b.get("created_at")) == today:
            if not keep_telegram_ids or b.get("user_id") in keep_telegram_ids:
                bookings_today.append(b)

    data["users"] = users_today
    data["conversations"] = conversations_today
    data["bookings"] = bookings_today

    # Update statistics
    stats = data.get("statistics", {})
    stats["total_users"] = len(users_today)
    stats["total_conversations"] = len(conversations_today)
    stats["total_bookings"] = len(bookings_today)
    data["statistics"] = stats

    CRM_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Cleaned. Users: {len(users_today)}, Conversations: {len(conversations_today)}, Bookings: {len(bookings_today)}")

if __name__ == "__main__":
    main()


