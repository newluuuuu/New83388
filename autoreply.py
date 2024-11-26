from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telethon.sync import TelegramClient
from telethon import TelegramClient, events
from telethon.tl.types import User, Chat
from telethon.errors.rpcerrorlist import AuthKeyUnregisteredError
import re
import os
import json
from datetime import datetime, timedelta
import datetime
import asyncio
import json
import logging
from dotenv import load_dotenv
load_dotenv()
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "devscottreal")

active_clients = {}
last_reply_time = {}

def load_user_data():
    try:
        with open("config.json", "r") as f:
            data = json.load(f)
            if "users" not in data:
                data["users"] = {}  
            return data
    except FileNotFoundError:
        return {"users": {}}  
    except json.JSONDecodeError:
        return {"users": {}}  

def save_user_data(data):
    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def set_word(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id).strip()
    from main import is_authorized
    if not await is_authorized(user_id):
        await update.message.reply_text(f"🔒 <b>Access Restricted</b>\n\n❌ No active subscription found\n✨ Please contact <a href=\"tg://resolve?domain={ADMIN_USERNAME}\">Admin</a> for access", parse_mode="HTML")
        return

    try:
        message = ' '.join(context.args).split('|')
        keyword = message[0].strip()
        response = message[1].strip().replace('\\n', '\n')

        data = load_user_data()

        if user_id not in data["users"]:
            data["users"][user_id] = {"keywords": {}}

        if "keywords" not in data["users"][user_id]:
            data["users"][user_id]["keywords"] = {}

        data["users"][user_id]["keywords"][keyword] = response
        save_user_data(data)

        await update.message.reply_text(f"Keyword:\n<pre>{keyword}</pre> has been set with the response:\n <pre>{response}</pre>", parse_mode="HTML")

    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ *Invalid Format*\n\n📝 Please use:\n`/set_word keyword | response`", parse_mode="Markdown")


async def keyword_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.callback_query.from_user.id).strip()

    from main import is_authorized
    if not await is_authorized(user_id):
        await update.callback_query.edit_message_text(
            f"🔒 <b>Access Restricted</b>\n\n❌ No active subscription found\n✨ Please contact <a href=\"tg://resolve?domain={ADMIN_USERNAME}\">Admin</a> for access",
            parse_mode="HTML"
        )
        return

    # Load user data
    data = load_user_data()
    user_data = data["users"].get(user_id, {})

   
    match_option = user_data.get("match_option", "exact")
    auto_reply_status = "Enabled ✅" if user_data.get("auto_reply_status", False) else "Disabled ❌"
    auto_reply_text = "Disable 🔴" if user_data.get("auto_reply_status", False) else "Enable 🟢"
    responder_option = user_data.get("responder_option", "PM") 

    keyboard = [
        [InlineKeyboardButton("━━━━⊱MATCH OPTIONS⊰━━━", callback_data="pass")],
        [InlineKeyboardButton(f"Exact Match {'✅' if match_option == 'exact' else '❌'}", callback_data='set_exact')],
        [InlineKeyboardButton(f"Partial Match {'✅' if match_option == 'partial' else '❌'}", callback_data='set_partial')],
        [InlineKeyboardButton(f"Case Insensitive {'✅' if match_option == 'case_insensitive' else '❌'}", callback_data='set_case_insensitive')],
        [InlineKeyboardButton("━━━━⊱RESPONSE SETTINGS⊰━━━", callback_data="pass")],
        [InlineKeyboardButton(f"PM {'✅' if responder_option == 'PM' else '❌'}", callback_data='set_pm'),
         InlineKeyboardButton(f"GC {'✅' if responder_option == 'GC' else '❌'}", callback_data='set_gc'),
         InlineKeyboardButton(f"All {'✅' if responder_option == 'All' else '❌'}", callback_data='set_all')],
        [InlineKeyboardButton(f"{auto_reply_text}", callback_data='toggle_auto_reply')],
        [InlineKeyboardButton("📝 My Keywords", callback_data='words')],
        [InlineKeyboardButton("🔙 Back", callback_data='back')]
    ]
    respond_display = {
        'PM': 'Private Chat',
        'GC': 'Groups',
        'All': 'DMs & Groups'
    }.get(responder_option, responder_option)

   
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        "⚙️ <b>AUTO-REPLY SETTINGS</b>\n\n"
        "━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Match Mode:</b> <code>{match_option}</code>\n"
        f"📊 <b>Status:</b> <code>{auto_reply_status}</code>\n"
        f"🌐 <b>Respond In:</b> <code>{respond_display}</code>\n"
        "━━━━━━━━━━━━━━━",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )


async def start_telethon_client(user_id, context=None):
    data = load_user_data()
    user_data = data["users"].get(user_id)

    if not user_data or not user_data.get("auto_reply_status"):
        return

    user_data["client_active"] = True
    save_user_data(data)

    session_file = f"{user_id}.session"
    if not os.path.exists(session_file):
        print(f"Session file for {user_id} does not exist. Ask the user to log in.")
        try:
            if context:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="⚠️ <b>Session Error</b>\n\n❌ Your session file is missing\n📝 Please log in again to continue",
                    parse_mode="HTML"
                )
            user_data["auto_reply_status"] = False
            save_user_data(data)
        except Exception as e:
            print(f"Error sending message: {e}")
        return

    api_id = user_data.get("api_id")
    api_hash = user_data.get("api_hash")

    client = TelegramClient(session_file, api_id, api_hash)

    try:

        await client.connect()

        if not await client.is_user_authorized():

            await client.disconnect()
            if os.path.exists(session_file):  
                os.remove(session_file)
            await context.bot.send_message(
                chat_id=user_id,
                text="🔒 *Authorization Failed*\n\n❌ Your session was terminated\n📝 Please log in again to continue",
                parse_mode="Markdown"
            )
            user_data["auto_reply_status"] = False
            save_user_data(data)
            return

        await client.disconnect()
        await asyncio.sleep(3)

        await client.start()
    
    except AuthKeyUnregisteredError as e:
        print(f"Authorization error for user {user_id}: {e}")
        await client.disconnect()
        if os.path.exists(session_file): 
            os.remove(session_file)
        if context:
            await context.bot.send_message(
                chat_id=user_id,
                text="🔒 *Authorization Failed*\n\n❌ Your session was terminated\n📝 Please log in again to continue",
                parse_mode="Markdown"
            )
        user_data["auto_reply_status"] = False
        save_user_data(data)
        return

    except Exception as e:
        print(f"Error starting Telethon client for user {user_id}: {e}")
        user_data["client_active"] = False
        save_user_data(data)
        return

    @client.on(events.NewMessage)
    async def handler(event):
        try:
            chat = await event.get_chat()
            chat_id = chat.id
            chat_name = chat.title if hasattr(chat, 'title') else chat.username or chat_id
            message_text = event.message.message

            print(f"📥 Received message in {chat_name}")

            keywords = user_data.get("keywords", {})
            match_option = user_data.get("match_option", "exact").lower()
            responder_option = user_data.get("responder_option", "PM") 

            for keyword, response in keywords.items():
                if match_option == "exact":
                    pattern = r"^" + re.escape(keyword) + r"$"
                    if re.match(pattern, message_text, re.IGNORECASE):
                        print(f"✨ Exact match found in {chat_name}: {keyword}")
                elif match_option == "partial":
                    pattern = r"\b" + re.escape(keyword) + r"\b"
                    if re.search(pattern, message_text, re.IGNORECASE):
                        print(f"✨ Partial match found in {chat_name}: {keyword}")
                elif match_option == "case_insensitive":
                    if keyword.lower() in message_text.lower():
                        print(f"✨ Case-insensitive match found in {chat_name}: {keyword}")

                if match_option in ["exact", "partial", "case_insensitive"] and (
                    (match_option == "exact" and re.match(pattern, message_text, re.IGNORECASE)) or
                    (match_option == "partial" and re.search(pattern, message_text, re.IGNORECASE)) or
                    (match_option == "case_insensitive" and keyword.lower() in message_text.lower())
                ):
                    if responder_option == "PM" and isinstance(chat, User):
                        if chat_id in last_reply_time and (asyncio.get_event_loop().time() - last_reply_time[chat_id]) < 10:
                            print(f"⏳ Cooldown active in {chat_name}")
                            return

                        await asyncio.sleep(1)

                        if response.startswith("https://t.me/"):
                            await send_message_from_link(client, event, response)
                        else:
                            await event.reply(response)

                        print(f"📤 Replied with: {response}")

                        last_reply_time[chat_id] = asyncio.get_event_loop().time()

                        await asyncio.sleep(10)
                    elif responder_option == "GC" and isinstance(chat, Chat):
                        if chat_id in last_reply_time and (asyncio.get_event_loop().time() - last_reply_time[chat_id]) < 10:
                            print(f"⏳ Cooldown active in {chat_name}")
                            return

                        await asyncio.sleep(1)

                        if response.startswith("https://t.me/"):
                            await send_message_from_link(client, event, response)
                        else:
                            await event.reply(response)

                        print(f"📤 Replied with: {response}")

                        last_reply_time[chat_id] = asyncio.get_event_loop().time()

                        await asyncio.sleep(10)

                    elif responder_option == "All":  # Respond in both PM and GC
                        if chat_id in last_reply_time and (asyncio.get_event_loop().time() - last_reply_time[chat_id]) < 10:
                            print(f"⏳ Cooldown active in {chat_name}")
                            return

                        await asyncio.sleep(1)

                        if response.startswith("https://t.me/"):
                            await send_message_from_link(client, event, response)
                        else:
                            await event.reply(response)

                        print(f"📤 Replied with: {response}")

                        last_reply_time[chat_id] = asyncio.get_event_loop().time()

                        await asyncio.sleep(10)
                    return

        except AuthKeyUnregisteredError as e:
            print(f"Authorization error for user {user_id}: {e}")
            await client.disconnect()
            if os.path.exists(session_file): 
                os.remove(session_file)
            if context:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="🔒 *Authorization Failed*\n\n❌ Your session was terminated\n📝 Please log in again to continue",
                    parse_mode="Markdown"
                )
            user_data["auto_reply_status"] = False
            save_user_data(data)
            return

        except Exception as e:
            print(f"Unexpected error while handling message: {e}")
            await client.disconnect()
            if os.path.exists(session_file):
                os.remove(session_file)
            if context:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="⚠️ *Unexpected Error*\n\n❌ Your session was terminated unexpectedly\n📝 Please log in again to continue",
                    parse_mode="Markdown"
                )
            user_data["auto_reply_status"] = False
            save_user_data(data)
            return

    try:
        print(f"✅ Telethon client started successfully for user {user_id}")
        user_data["client_active"] = True
        save_user_data(data)

        active_clients[user_id] = client

        asyncio.create_task(client.run_until_disconnected())

    except Exception as e:
        print(f"❌ Error starting Telethon client for user {user_id}: {e}")
        user_data["client_active"] = False
        save_user_data(data)
        
async def send_message_from_link(client, event, link):

    pattern = r"https://t.me/([a-zA-Z0-9_]+)/(\d+)"
    match = re.match(pattern, link)
    if match:
        chat_id = match.group(1)
        message_id = int(match.group(2))
        try:

            message = await client.get_messages(chat_id, ids=message_id)
            if message:

                await client.forward_messages(event.chat_id, message)
            else:
                await event.reply("Message not found.")
        except Exception as e:
            await event.reply(f"Error retrieving message: {e}")
    else:
        await event.reply("Invalid message link.")

async def stop_telethon_client(user_id):
    data = load_user_data()
    user_data = data["users"].get(user_id)

    client = active_clients.get(user_id)

    if client is None:
        print(f"No active Telethon client found for user {user_id}")
        return

    try:
        if client.is_connected():
            print(f"Disconnecting Telethon client for user {user_id}")
            await client.disconnect()
            print(f"Telethon client disconnected for user {user_id}")

        user_data["client_active"] = False
        save_user_data(data)
        del active_clients[user_id]

    except Exception as e:
        print(f"Error stopping Telethon client for user {user_id}: {e}")

    finally:
        if client.is_connected():
            await client.disconnect()
        print(f"Client status after disconnection for user {user_id}: {client.is_connected()}")