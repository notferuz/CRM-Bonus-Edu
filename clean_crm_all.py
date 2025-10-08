#!/usr/bin/env python3
"""
Hard cleanup CRM data: remove all users, bookings, conversations.
Keeps courses, teachers, schedule, analytics.
Creates backup: crm_data.backup.all.json
"""
import json
from pathlib import Path

CRM_PATH = Path("crm_data.json")
BACKUP_PATH = Path("crm_data.backup.all.json")

def main():
    if not CRM_PATH.exists():
        print("❌ crm_data.json not found")
        return

    data = json.loads(CRM_PATH.read_text(encoding="utf-8"))

    # backup
    BACKUP_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # wipe dynamic sets
    data["users"] = []
    data["bookings"] = []
    data["conversations"] = []

    # reset statistics
    stats = data.get("statistics", {})
    stats["total_users"] = 0
    stats["total_conversations"] = 0
    stats["total_bookings"] = 0
    # Keep active courses/teachers as-is if present
    data["statistics"] = stats

    # persist
    CRM_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("✅ All dynamic CRM data wiped (users, bookings, conversations). Backup saved to", BACKUP_PATH.name)

if __name__ == "__main__":
    main()


