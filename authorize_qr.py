#!/usr/bin/env python3
"""
Авторизация через QR-код (без ввода кода вручную)

Шаги на телефоне:
1) Откройте Telegram → Настройки → Устройства → Привязать устройство десктопа
2) Сканируйте QR, который появится в терминале
"""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def main():
    try:
        from telethon import TelegramClient

        api_id = int(os.getenv('TELEGRAM_API_ID'))
        api_hash = os.getenv('TELEGRAM_API_HASH')

        if not all([api_id, api_hash]):
            print("❌ Не заданы TELEGRAM_API_ID/TELEGRAM_API_HASH в .env")
            return

        client = TelegramClient('personal_assistant_session', api_id, api_hash)
        await client.connect()

        if await client.is_user_authorized():
            me = await client.get_me()
            print(f"✅ Уже авторизованы как: {me.first_name} {me.last_name or ''} (@{me.username or '—'})")
            print(f"🆔 User ID: {me.id}")
        else:
            print("📸 Готовлю QR для входа…")
            qr_login = await client.qr_login()

            # Печатаем QR в терминал, если доступен модуль qrcode
            try:
                import qrcode
                qr_obj = qrcode.QRCode(border=1)
                qr_obj.add_data(qr_login.url)
                qr_obj.make(fit=True)
                print("\nСканируйте этот QR в Telegram → Настройки → Устройства → Привязать устройство десктопа:\n")
                qr_obj.print_ascii(invert=True)
                print("")
            except Exception:
                # Если нет qrcode, печатаем URL
                print("⚠️ Библиотека qrcode не найдена. Печатаю URL:")
                print(qr_login.url)
                print("Откройте Telegram → Настройки → Устройства → Привязать устройство десктопа → Сканируйте URL как QR на экране.")

            # Ждём авторизацию (пока QR не будет подтверждён)
            print("⌛ Ожидаю подтверждение входа…")
            await qr_login.wait()

            me = await client.get_me()
            print(f"\n✅ Авторизован как: {me.first_name} {me.last_name or ''} (@{me.username or '—'})")
            print(f"🆔 User ID: {me.id}")

            # Сохраняем TELEGRAM_USER_ID в .env
            try:
                with open('.env', 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                key = 'TELEGRAM_USER_ID='
                updated = False
                for i, line in enumerate(lines):
                    if line.startswith(key):
                        lines[i] = f'{key}{me.id}\n'
                        updated = True
                        break
                if not updated:
                    lines.append(f'{key}{me.id}\n')
                with open('.env', 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                print("✅ TELEGRAM_USER_ID сохранён в .env")
            except Exception as e:
                print(f"⚠️ Не удалось сохранить USER_ID в .env: {e}")

        await client.disconnect()

    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == '__main__':
    print("🤖 Вход в Telegram через QR")
    print("Если QR не виден, я выведу URL. Сканируйте его в Telegram → Устройства.")
    asyncio.run(main())


