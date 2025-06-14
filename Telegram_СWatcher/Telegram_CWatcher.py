from telethon import TelegramClient, events
import aiohttp

import asyncio
import json
import sys
import io
import threading

# === Загрузка конфигурации ===
with open("config.json", encoding="utf-8") as f:
    config = json.load(f)

api_id = config["api_id"]
api_hash = config["api_hash"]
phone_number = config["phone_number"]
text_to_watch = config["text_to_watch"]
SEND_TO = config["send_to"]
DISCORD_WEBHOOK_URL = config["discord_webhook_url"]
DISCORD_PING_TEXT = config["discord_ping_text"]
TELEGRAM_TARGET = config.get("telegram_target", "me") # Если кто-то тупой и херь поставил сюда то по дефолту ставит 'me'

# === Фильтрация с языка <Ошибка 742389423> на потеряно соединение :) ===
class FilteredStderr(io.TextIOBase):
    def __init__(self, original_stderr):
        self.original_stderr = original_stderr
        self.lock = threading.Lock()

    def write(self, text):
        if "WinError 1236" in text or "WinError 10053" in text:
            with self.lock:
                self.original_stderr.write("\u2757 Потеря соединения с Telegram(telethon), можете игнорировать если у вас снова присутствует интернет\n")
        elif "WinError 5" in text:
            with self.lock:
                self.original_stderr.write("\u2757\u2757 Неудачная попытка подключения к Telegram(telethon), Доступ запрещен. \uD83D\uDD01Пробуем еще раз...\n")
        else:
            with self.lock:
                self.original_stderr.write(text)

    def flush(self):
        with self.lock:
            self.original_stderr.flush()

sys.stderr = FilteredStderr(sys.stderr)

# === Инициализация клиента ===
client = TelegramClient("session_name", api_id, api_hash)

# === Проверка на упоминания ===
def check_mentions(message):
    message_lower = message.lower()
    return any(username.lower() in message_lower for username in text_to_watch)

# === Получить ссылку на сообщение тг ===
async def get_channel_link(event):
    channel = await event.get_chat()
    if hasattr(channel, "username") and channel.username:
        return f"https://t.me/{channel.username}/{event.message.id}"
    return None

# === Отправка в тг ===
async def send_telegram_notification(text):
    await client.send_message(TELEGRAM_TARGET, text, link_preview=False)

# === Отправка в Дискорд ===
async def send_discord_notification(text):
    content = f"{DISCORD_PING_TEXT}\n{text}" if DISCORD_PING_TEXT else text
    async with aiohttp.ClientSession() as session:
        await session.post(DISCORD_WEBHOOK_URL, json={"content": content})

# === Уведомления ===
async def notify_all(prefix, event):
    message = event.message.message or ""
    if not check_mentions(message):
        return

    channel = await event.get_chat()
    link = await get_channel_link(event)
    channel_name = channel.title if hasattr(channel, "title") else "Без названия"

    text = f"🔔 {prefix} найдено в канале: {channel_name}\n"
    if link:
        text += f"🔗 {link}\n\n"
    else:
        text += f"(ID канала: {channel.id}, ID сообщения: {event.message.id})\n\n"
    text += f"{message[:1500]}"

    if "tg" in SEND_TO:
        await send_telegram_notification(text)
    if "dc" in SEND_TO:
        await send_discord_notification(text)

# === Обработка новых сообщений ===
@client.on(events.NewMessage)
async def new_message_handler(event):
    if event.is_channel:
        await notify_all("Новое упоминание", event)

# === Обработка редактированных сообщений ===
@client.on(events.MessageEdited)
async def edited_message_handler(event):
    if event.is_channel:
        await notify_all("Обновлённое упоминание", event)

# === Запуск проги ===
async def main():
    await client.start(phone=phone_number)
    print("▶️ Слежка за упоминаниями запущена...")
    await client.run_until_disconnected()

with client:
    client.loop.run_until_complete(main())