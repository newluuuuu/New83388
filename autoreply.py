
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telethon.sync import TelegramClient
from telethon import TelegramClient, events
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
# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)



async def set_word(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id).strip()
    from main import is_authorized
    if not await is_authorized(user_id):
        await update.message.reply_text(f"<b>No Active Subscription, Please contact</b> <a href=\"tg://resolve?domain={ADMIN_USERNAME}\">Admin</a>", parse_mode="HTML")
        return
    
    try:
        message = ' '.join(context.args).split('|')
        keyword = message[0].strip()
        response = message[1].strip()

        data = load_user_data()
        
        if user_id not in data["users"]:
            data["users"][user_id] = {"keywords": {}}
        
        if "keywords" not in data["users"][user_id]:
            data["users"][user_id]["keywords"] = {}
        
        data["users"][user_id]["keywords"][keyword] = response
        save_user_data(data)

        await update.message.reply_text(f"Keyword:\n<pre>{keyword}</pre> has been set with the response:\n <pre>{response}</pre>", parse_mode="HTML")
    
    except (IndexError, ValueError):
        await update.message.reply_text("Please use the correct format:\n `/set_word keyword | response`", parse_mode="Markdown")



async def keyword_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id).strip()
    # Check if the user is authorized
    from main import is_authorized
    if not await is_authorized(user_id):
        await update.message.reply_text(f"<b>No Active Subscription, Please contact</b> <a href=\"tg://resolve?domain={ADMIN_USERNAME}\">Admin</a>", parse_mode="HTML")
        return

    # Load user data
    data = load_user_data()
    user_data = data["users"].get(user_id, {})

    # Check if auto-reply is turned on for the user
    if not user_data.get("auto_reply_on", False):
        return

    # Rate limit: If the user replied within the last 10 seconds, ignore this message
    if "last_reply_time" in user_data:
        last_reply_time = user_data["last_reply_time"]
        if datetime.now() - datetime.strptime(last_reply_time, '%Y-%m-%d %H:%M:%S') < timedelta(seconds=10):
            return

    # Extract matching options
    match_option = user_data.get("match_option", "exact").lower()
    
    message_text = update.message.text

    # Check if any stored keywords match the message
    for keyword, response in user_data.get("keywords", {}).items():
        if match_option == "exact" and message_text.strip() == keyword.strip():
            await reply_with_telethon(user_id, response, context)
            return
        elif match_option == "partial" and keyword in message_text:
            await reply_with_telethon(user_id, response, context)
            return
        elif match_option == "case_insensitive" and keyword.lower() in message_text.lower():
            await reply_with_telethon(user_id, response, context)
            return
async def keyword_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.callback_query.from_user.id).strip()
    # Check if the user is authorized
    from main import is_authorized
    if not await is_authorized(user_id):
        await update.callback_query.edit_message_text(f"<b>No Active Subscription, Please contact</b> <a href=\"tg://resolve?domain={ADMIN_USERNAME}\">Admin</a>", parse_mode="HTML")
        return

    # Load user data
    data = load_user_data()
    user_data = data["users"].get(user_id, {})

    match_option = user_data["match_option"]
    auto_reply_status = "On" if user_data.get("auto_reply_status", False) else "Off"
    auto_reply_text = "Off" if user_data.get("auto_reply_status", False) else "On"

    keyboard = [
        [InlineKeyboardButton(f"Exact Match {'✅' if match_option == 'exact' else ''}", callback_data='set_exact')],
        [InlineKeyboardButton(f"Partial Match {'✅' if match_option == 'partial' else ''}", callback_data='set_partial')],
        [InlineKeyboardButton(f"Case Insensitive {'✅' if match_option == 'case_insensitive' else ''}", callback_data='set_case_insensitive')],
        [InlineKeyboardButton(f"Turn {auto_reply_text}", callback_data='toggle_auto_reply')],
        [InlineKeyboardButton("My Keywords", callback_data='words')],
        [InlineKeyboardButton("🔙", callback_data='back')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        f"Your Auto-reply settings\n\n*Match Option: {match_option}✅*\n*Mode: {auto_reply_status}✅*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def reply_with_telethon(user_id, message, context=None):
    data = load_user_data()
    user_data = data["users"].get(user_id, {})
    session_file = f'{user_id}.session'

    if not os.path.exists(session_file):
        # Inform the user that they need to log in
        print(f"Session file for {user_id} does not exist. Ask the user to log in.")
        try:
            # Use the context or update object to send the message
            if context:  # If context is available
                await context.bot.send_message(
                    chat_id=user_id,
                    text="<b>Your session file is missing. Please log in again.</b>",
                    parse_mode="HTML"
                )
            else:
                print("Context not available, unable to send message.")
                
        except Exception as e:
            print(f"Error sending message: {e}")

    try:
        client = TelegramClient(session_file, user_data["api_id"], user_data["api_hash"])
        await client.connect()

        if not await client.is_user_authorized():
            print(f"User {user_id} is not authorized. Ask them to log in.")
            return

        recipient_id = user_data.get("recipient_id")  
        await client.send_message(recipient_id, message)

    except Exception as e:
        print(f"Error sending message: {e}")
    finally:
        if client.is_connected():
            await client.disconnect()




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
                    text="<b>Your session file is missing. Please log in again.</b>",
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
        # Connect the client
        await client.connect()

        # Check if the client is authorized (session is still active)
        if not await client.is_user_authorized():
            # If the session is no longer valid, delete the session file
            await client.disconnect()
            os.remove(session_file)
            await context.bot.send_message(
                chat_id=user_id,
                text="*Your session was terminated. Please log in again ❌*",
                parse_mode="Markdown"
            )
            user_data["auto_reply_status"] = False
            save_user_data(data)
            return

        await client.disconnect()
        await asyncio.sleep(3)

        await client.start()

    except Exception as e:
        print(f"Error starting Telethon client for user {user_id}: {e}")
        user_data["client_active"] = False
        save_user_data(data)
        return

    @client.on(events.NewMessage)
    async def handler(event):
        # Extract chat info and message
        chat = await event.get_chat()
        chat_id = chat.id
        chat_name = chat.title if hasattr(chat, 'title') else chat.username or chat_id
        message_text = event.message.message

        # Log the received message
        print(f"Received message in {chat_name}")

        # Fetch user-specific keywords and match option
        keywords = user_data.get("keywords", {})
        match_option = user_data.get("match_option", "exact").lower()

        # Check if the message matches any keywords
        for keyword, response in keywords.items():
            # Check if the message matches the keyword based on the match option
            if (
                (match_option == "exact" and message_text.lower() == keyword.lower()) or
                (match_option == "partial" and keyword in message_text) or
                (match_option == "case_insensitive" and keyword.lower() in message_text.lower())
            ):
                print(f"Keyword match found in {chat_name}: {keyword}")

                # If the last reply was within 10 seconds, skip replying
                if chat_id in last_reply_time and (asyncio.get_event_loop().time() - last_reply_time[chat_id]) < 10:
                    print(f"Skipping reply in {chat_name} due to 10-second cooldown.")
                    return

                await asyncio.sleep(1)
                
                if response.startswith("https://t.me/"):
                    await send_message_from_link(client, event, response)
                else:
                    await event.reply(response)
                
                print(f"Replied with: {response}")

                last_reply_time[chat_id] = asyncio.get_event_loop().time()
                
                await asyncio.sleep(10)
                
                return
    try:
        print(f"Telethon client started successfully for user {user_id}")
        user_data["client_active"] = True
        save_user_data(data)

        # Store the running client in the global dictionary
        active_clients[user_id] = client

        # Run the client until disconnected
        asyncio.create_task(client.run_until_disconnected())

    except Exception as e:
        print(f"Error starting Telethon client for user {user_id}: {e}")
        user_data["client_active"] = False
        save_user_data(data)



async def send_message_from_link(client, event, link):
    # Regex pattern to extract chat ID and message ID from the Telegram link
    pattern = r"https://t.me/([a-zA-Z0-9_]+)/(\d+)"
    match = re.match(pattern, link)
    if match:
        chat_id = match.group(1)
        message_id = int(match.group(2))
        try:
            # Fetch the message using the chat ID and message ID
            message = await client.get_messages(chat_id, ids=message_id)
            if message:
                # Forward the message to the user who triggered the event
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

    # Retrieve the running client from the dictionary
    client = active_clients.get(user_id)

    if client is None:
        print(f"No active Telethon client found for user {user_id}")
        return

    try:
        if client.is_connected():
            print(f"Disconnecting Telethon client for user {user_id}")
            await client.disconnect()
            print(f"Telethon client disconnected for user {user_id}")

        # Mark the client as inactive and remove it from the dictionary
        user_data["client_active"] = False
        save_user_data(data)
        del active_clients[user_id]

    except Exception as e:
        print(f"Error stopping Telethon client for user {user_id}: {e}")

    finally:
        if client.is_connected():
            await client.disconnect()
        print(f"Client status after disconnection for user {user_id}: {client.is_connected()}")


