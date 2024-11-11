import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telethon.sync import TelegramClient
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from dotenv import load_dotenv
from telethon import functions, events
from telethon.errors import SessionPasswordNeededError
import os
import json
from datetime import datetime, timedelta
import datetime
import time
import asyncio
import http.server
import socketserver
import threading
import json
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from autoreply import set_word, reply_with_telethon, keyword_response, keyword_settings, start_telethon_client, stop_telethon_client

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
scheduler = AsyncIOScheduler()
ADMIN_IDS = os.getenv("ADMIN_IDS").split(',') 
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "devscottreal")

def load_config():
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            if "users" not in config:
                config["users"] = {}  
            return config
    except FileNotFoundError:
        # Default config structure
        config = {"users": {}}
        save_config(config)  
        return config
    except json.JSONDecodeError:
        return {"users": {}}

def save_config(config):
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=4)

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

logging.basicConfig(
    level=logging.INFO,  
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

async def is_authorized(user_id: str) -> bool:
    data = load_user_data()
    if user_id in data["users"]:
        expiry_date = data["users"][user_id].get("expiry_date")

        if expiry_date:
            try:

                expiry_datetime = datetime.strptime(expiry_date, '%Y-%m-%d %H:%M:%S')
                logger.info(f"Parsed expiry date for user {user_id}: {expiry_datetime}")

                if expiry_datetime > datetime.now():
                    return True
                else:
                    logger.info(f"Subscription for user {user_id} has expired.")
                    data["users"][user_id]["forwarding_on"] = False 
                    data["users"].pop(user_id, None) 
                    save_user_data(data)
            except ValueError as e:
                logger.error(f"Date parsing error for user {user_id}: {e}")
        else:
            logger.info(f"No expiry date found for user {user_id}.")
    else:
        logger.info(f"User {user_id} not found in the database.")

    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id).strip() 
    logger.info(f"Checking subscription for user: {user_id}")

    data = load_user_data()

    if user_id in data["users"]:
        expiry_date = data["users"][user_id]["expiry_date"]
        try:

            expiry_datetime = datetime.strptime(expiry_date, '%Y-%m-%d %H:%M:%S')
            time_left = (expiry_datetime - datetime.now()).days
            formatted_expiry = expiry_datetime.strftime('%Y-%m-%d %H:%M:%S')  
            logger.info(f"User {user_id} subscription expires on {formatted_expiry}")
        except ValueError as e:
            logger.error(f"Date parsing error: {e}")
            await update.message.reply_text("There was an error processing your subscription. Please contact admin.")
            return

        if time_left >= 0:

            keyboard = [
                [InlineKeyboardButton("HELP GUIDE ❕", callback_data='help')],
                [InlineKeyboardButton("AUTO RESPONDER GUIDE❕", url='https://telegra.ph/AUTO-RESPONDER-GUIDE-11-11')],
                [InlineKeyboardButton("API AND HASH ID 🎥", url='https://youtu.be/s7Ys5reuxHc?si=e3724tW8NhpzbvJR')],
                [InlineKeyboardButton("LOGIN WITH TELEGRAM 🔑", callback_data='login')],
                [InlineKeyboardButton("Settings ⚙️", callback_data='settings')],
                [InlineKeyboardButton("Auto Reply ⚙️", callback_data='auto_reply')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f'Welcome to <b>DEVSCOTT AUTO F Bot</B>\nYour subscription ends on\n <b>{formatted_expiry}</b>.',
                reply_markup=reply_markup,
                parse_mode="HTML"
            )   
        else:

            await update.message.reply_text(
                f"<b>Your Subscription Has Ended, Please contact</b> <a href=\"tg://resolve?domain={ADMIN_USERNAME}\">Admin</a>",
                parse_mode="HTML"
            )

            data["users"][user_id]["forwarding_on"] = False
            save_user_data(data)
    else:

        logger.info(f"User {user_id} is not authorized or subscription has expired.")
        await update.message.reply_text(
            f"<b>No Active Subscription, Please contact</b> <a href=\"tg://resolve?domain={ADMIN_USERNAME}\">Admin</a>",
            parse_mode="HTML"
        )

        if user_id in data["users"]:
            data["users"][user_id]["forwarding_on"] = False
        save_user_data(data)

async def post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)  

    if await is_authorized(user_id):
        if context.args:
            post_message = ' '.join(context.args)  

            data = load_user_data()

            if user_id in data["users"]:
                try:

                    if "post_messages" not in data["users"][user_id]:
                        data["users"][user_id]["post_messages"] = []

                    data["users"][user_id]["post_messages"].append(post_message)
                    save_user_data(data)  

                    # Get the index of the new post message
                    post_index = len(data["users"][user_id]["post_messages"])  # Index starts from 1
                    await update.message.reply_text(f"*Message saved for forwarding with index number {post_index} ✅*\n\n*Add more messages with*\n`/post message here`", parse_mode="Markdown")
                except Exception as e:
                    await update.message.reply_text(f"Failed to save the message due to an error: {e}")
            else:
                await update.message.reply_text("User not found in the system.")
        else:
            await update.message.reply_text("Usage: `/post <message / text link>`", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"<b>No Active Subscription, Please contact</b> <a href=\"tg://resolve?domain={ADMIN_USERNAME}\">Admin</a>", parse_mode="HTML")


async def delpost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)

    if await is_authorized(user_id):
        if context.args:

            if context.args[0].lower() == 'all':

                data = load_user_data()

                if user_id in data["users"] and "post_messages" in data["users"][user_id]:
                    try:
                        deleted_posts = data["users"][user_id]["post_messages"]
                        data["users"][user_id]["post_messages"] = []  
                        save_user_data(data)

                        await update.message.reply_text(f"All posts have been deleted. {len(deleted_posts)} posts removed.", parse_mode="Markdown")
                    except Exception as e:
                        await update.message.reply_text(f"Failed to delete posts due to an error:\n<pre> {e}</pre>", parse_mode="HTML")
                else:
                    await update.message.reply_text("No posts found for this user.")

            else:

                post_message = ' '.join(context.args)

                data = load_user_data()

                if user_id in data["users"] and "post_messages" in data["users"][user_id]:
                    try:
                        post_messages = data["users"][user_id]["post_messages"]

                        if post_message in post_messages:

                            post_messages.remove(post_message)
                            save_user_data(data)
                            await update.message.reply_text(f"Deleted post:\n `{post_message}`", parse_mode="Markdown")
                        else:

                            try:
                                post_index = int(post_message) - 1
                                if 0 <= post_index < len(post_messages):
                                    deleted_post = post_messages.pop(post_index)
                                    save_user_data(data)
                                    await update.message.reply_text(f"Deleted post:\n `{deleted_post}`", parse_mode="Markdown")
                                else:
                                    await update.message.reply_text("Invalid post index.")
                            except ValueError:
                                await update.message.reply_text("Invalid input. Use the index or the exact message text to delete a post.")
                    except Exception as e:
                        await update.message.reply_text(f"Failed to delete the post due to an error: {e}")
                else:
                    await update.message.reply_text("No posts found for this user.")
        else:
            await update.message.reply_text("Usage: `/delpost <post index or message>`", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"<b>No Active Subscription, Please contact</b> <a href=\"tg://resolve?domain={ADMIN_USERNAME}\">Admin</a>", parse_mode="HTML")

from datetime import datetime, timedelta  

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id_from_message = str(update.message.from_user.id)  

    if user_id_from_message in ADMIN_IDS:  
        data = load_user_data()  
        try:
            user_id = str(context.args[0])
            days = int(context.args[1])

            expiry_date = datetime.now() + timedelta(days=days)

            if "users" not in data:
                data["users"] = {}

            default_user_data = {
                "expiry_date": expiry_date.strftime('%Y-%m-%d %H:%M:%S'),
                "api_id": "",
                "api_hash": "",
                "post_messages": [],
                "interval": "",
                "groups": [],
                "keywords": {},
                "match_option": "exact", 
                "auto_reply_status": False,
                "forwarding_on": False
            }

            if user_id in data["users"]:
                data["users"][user_id]["expiry_date"] = expiry_date.strftime('%Y-%m-%d %H:%M:%S')
            else:
                data["users"][user_id] = default_user_data

            save_user_data(data)

            await update.message.reply_text(f"User `{user_id}` added with expiry date: {expiry_date.strftime('%Y-%m-%d %H:%M:%S')}", parse_mode="Markdown")

        except IndexError:
            await update.message.reply_text("*Please provide both user ID and number of days.*\n Usage: `/add <user_id> <days>`", parse_mode="Markdown")

        except ValueError:
            await update.message.reply_text("Invalid input. Please make sure you're entering a valid number of days.")

        except Exception as e:
            await update.message.reply_text(f"Error: {e}")
    else:

        await update.message.reply_text("*You do not have permission to use this command ❌*", parse_mode="Markdown")

async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id_from_message = str(update.message.from_user.id)  

    if user_id_from_message in ADMIN_IDS:  
        data = load_user_data()  
        try:
            user_id = str(context.args[0])  

            if user_id in data["users"]:
                # Stop the Telethon client for this user
                await stop_telethon_client(user_id)

                # Delete the user's session file if it exists
                session_file = f'{user_id}.session'
                if os.path.exists(session_file):
                    os.remove(session_file)
                    print(f"Deleted session file: {session_file}")
                
                # Remove user data and save changes
                del data["users"][user_id]
                save_user_data(data)  

                await update.message.reply_text(f"User {user_id} removed, Telethon client stopped, and Session file deleted.")
            else:
                await update.message.reply_text("User not found.")
        except IndexError:
            await update.message.reply_text("Please provide the user ID. Usage: /remove <user_id>")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")
    else:
        await update.message.reply_text("You do not have permission to use this command.")

async def api_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id) 
    if  await is_authorized(user_id):
        if len(context.args) == 1:
            api_id = context.args[0]

            data = load_user_data()

            if user_id not in data["users"]:
                data["users"][user_id] = {}  
            data["users"][user_id]["api_id"] = api_id

            save_user_data(data)
            await update.message.reply_text("*API ID saved✅*", parse_mode="Markdown")
        else:
            await update.message.reply_text("Usage: /api_id <API_ID>")
    else:
        await update.message.reply_text(f"<b>No Active Subscription, Please contact</b> <a href=\"tg://resolve?domain={ADMIN_USERNAME}\">Admin</a>", parse_mode="HTML")

async def api_hash(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id) 
    if await is_authorized(user_id):
        if len(context.args) == 1:
            api_hash = context.args[0]

            data = load_user_data()

            if user_id not in data["users"]:
                data["users"][user_id] = {}  
            data["users"][user_id]["api_hash"] = api_hash

            save_user_data(data)
            await update.message.reply_text("*API Hash saved ✅*", parse_mode="Markdown")
        else:
            await update.message.reply_text("Usage:\n `/hash <API_HASH>`", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"<b>No Active Subscription, Please contact</b> <a href=\"tg://resolve?domain={ADMIN_USERNAME}\">Admin</a>", parse_mode="HTML")

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id) 
    if await is_authorized(user_id):

        data = load_user_data()
        user_data = data["users"].get(user_id, {})

        api_id = user_data.get("api_id")
        api_hash = user_data.get("api_hash")

        if api_id and api_hash:
            if context.args:
                phone_number = context.args[0]  
                client = TelegramClient(f'{user_id}.session', api_id, api_hash)
                await client.connect()

                if not await client.is_user_authorized():
                    try:
                        sent_code = await client.send_code_request(phone_number)
                        context.user_data['phone_number'] = phone_number
                        context.user_data['phone_code_hash'] = sent_code.phone_code_hash  
                        await update.message.reply_text(
                            "*OTP sent to your phone ✅*.\n Use `/otp <code>` to continue.\n\n"
                            "Please space out your OTP Code when sending it to the bot\n"
                            "`/otp 2 3 4 5 6`"
                        ,parse_mode="Markdown")
                    except Exception as e:
                        await update.message.reply_text(f"Failed to send OTP: {e}")
                else:
                    await update.message.reply_text("You are already logged in.")
            else:
                await update.message.reply_text("Usage: /login <phone_number>")
        else:
            await update.message.reply_text("*API ID and Hash not found ❌*. Set them with `/api_id` and `/hash`", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"<b>No Active Subscription, Please contact</b> <a href=\"tg://resolve?domain={ADMIN_USERNAME}\">Admin</a>", parse_mode="HTML")

async def otp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)  
    otp_parts = context.args  

    if otp_parts:
        otp_code = ''.join(otp_parts) 
        phone_number = context.user_data.get('phone_number')
        phone_code_hash = context.user_data.get('phone_code_hash')  

        if phone_number and phone_code_hash:
            data = load_user_data()
            user_data = data["users"].get(user_id, {})

            api_id = user_data.get("api_id")
            api_hash = user_data.get("api_hash")

            if api_id and api_hash:
                client = TelegramClient(f'{user_id}.session', api_id, api_hash)
                await client.connect()

                try:
                    if not await client.is_user_authorized():
                        try:
                            await client.sign_in(phone=phone_number, code=otp_code, phone_code_hash=phone_code_hash)
                            await update.message.reply_text("OTP accepted! You're now logged in.")
                        except SessionPasswordNeededError:
                            await update.message.reply_text("*2FA is required ❕*\n Please enter your 2FA password with\n `/2fa <password>`", parse_mode="Markdown")
                        except Exception as e:
                            await update.message.reply_text(f"Login failed: {e}")
                    else:
                        await update.message.reply_text("You are already logged in.")
                finally:
                    await client.disconnect()
            else:
                await update.message.reply_text("API ID and Hash not found. Set them with\n\n /api_id and /hash.")
        else:
            await update.message.reply_text("Phone number or phone_code_hash not found. Start the login process with\n\n /login <phone_number>.")
    else:
        await update.message.reply_text("Usage: `/otp 1 2 3 4 5`", parse_mode="Markdown")

async def two_fa(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id) 
    password = context.args[0] if context.args else None

    if password:

        data = load_user_data()
        user_data = data["users"].get(user_id, {})

        api_id = user_data.get("api_id")
        api_hash = user_data.get("api_hash")

        if api_id and api_hash:
            client = TelegramClient(f'{user_id}.session', api_id, api_hash)
            await client.connect()

            try:
                await client.sign_in(password=password)
                await update.message.reply_text("*2FA password accepted! You're now logged in ✅*", parse_mode="Markdown")
            except Exception as e:
                await update.message.reply_text(f"*Login failed: {e} ❌*", parse_mode="Markdown")
            finally:

                await client.disconnect()
        else:
            await update.message.reply_text("API ID and Hash not found. Set them with /api_id and /hash.")
    else:
        await update.message.reply_text("Usage: /2fa <password>")

async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    if update.callback_query:
        message = update.callback_query.message
    else:
        message = update.message

    if not message:
        await update.message.reply_text("Unable to process the request.")
        return

    user_id = str(message.from_user.id)  

    data = load_user_data()
    user_data = data["users"].get(user_id, {})

    api_id = user_data.get("api_id")
    api_hash = user_data.get("api_hash")

    if api_id and api_hash:
        try:

            client = TelegramClient(f'{user_id}.session', api_id, api_hash)

            try:
                await client.connect()
            except Exception as e:
                await message.reply_text(f"Failed to connect: {e}")
                return  

            try:
                await client.log_out()
            except Exception as e:
                await message.reply_text(f"Failed to log out: {e}")
                return  

            session_file = f'{user_id}.session'
            try:
                if os.path.exists(session_file):
                    os.remove(session_file)
                    await message.reply_text("You have been logged out and session file has been deleted.")
                else:
                    await message.reply_text("Logout successful ✔")
            except Exception as e:
                await message.reply_text(f"Failed to delete session file: {e}")

        except Exception as e:
            await message.reply_text(f"An unexpected error occurred: {e}")
    else:
        await message.reply_text("API credentials not found. Please log in first.")

async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)  

    if await is_authorized(user_id):
        message_text = update.message.text
        group_links = message_text.split("\n")[1:] 

        if len(group_links) > 50:
            await update.message.reply_text("You can add a maximum of 50 group links at a time.")
            return

        with open("config.json", "r") as f:
            config_data = json.load(f)

        user_data = config_data["users"].get(user_id, {})
        user_groups = user_data.get("groups", [])  

        added_groups = []
        already_in_list = []

        for group_link in group_links:
            group_link = group_link.strip()  
            if group_link.startswith("https://t.me/"):
                if group_link and group_link not in user_groups:
                    user_groups.append(group_link)
                    added_groups.append(group_link)
                elif group_link in user_groups:
                    already_in_list.append(group_link)
            else:

                await update.message.reply_text(f"Link '{group_link}' is not a valid Telegram link.")

        user_data["groups"] = user_groups  
        config_data["users"][user_id] = user_data  

        with open("config.json", "w") as f:
            json.dump(config_data, f, indent=4)

        if added_groups:
            added_groups_message = "\n".join(added_groups)
            await update.message.reply_text(f"The following groups have been added for message forwarding:\n`{added_groups_message}`",parse_mode="Markdown")
        if already_in_list:
            already_in_list_message = "\n".join(already_in_list)
            await update.message.reply_text(f"The following groups were already in your forwarding list:\n`{already_in_list}`", parse_mode="Markdown")

        if not added_groups and not already_in_list:
            await update.message.reply_text("Invalid Format❗\nUsage:\n`/addgroup\n<link1>\n<link2>`", parse_mode="Markdown")

    else:
        await update.message.reply_text(
            "<b>No Active Subscription, Please contact</b> <a href=\"tg://resolve?domain=devscottreal\">Admin</a>", 
            parse_mode="HTML"
        )

async def del_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)

    if await is_authorized(user_id):
        if context.args:
            group_ids = context.args  
            removed_groups = []
            not_found_groups = []

            with open("config.json", "r") as f:
                config_data = json.load(f)

            user_data = config_data["users"].get(user_id, {})
            user_groups = user_data.get("groups", [])

            for group_id in group_ids:
                if group_id in user_groups:
                    user_groups.remove(group_id)
                    removed_groups.append(group_id)
                else:
                    not_found_groups.append(group_id)

            user_data["groups"] = user_groups
            config_data["users"][user_id] = user_data

            with open("config.json", "w") as f:
                json.dump(config_data, f, indent=4)

            response = ""
            if removed_groups:
                response += f"Removed groups:\n`{' '.join(removed_groups)}`\n"
            if not_found_groups:
                response += f"Groups not found:\n`{' '.join(not_found_groups)}`."

            await update.message.reply_text(response, parse_mode="Markdown")
        else:
            await update.message.reply_text("Usage:\n /delgroup <group1> <group2> ...")
    else:
        await update.message.reply_text(
            "<b>No Active Subscription, Please contact</b> <a href=\"tg://resolve?domain=devscottreal\">Admin</a>", 
            parse_mode="HTML"
        )

import json

async def time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    interval = int(context.args[0]) if context.args else None
    user_id = str(update.message.from_user.id)  

    if await is_authorized(user_id):  
        if interval and interval > 0:

            with open("config.json", "r") as f:
                config_data = json.load(f)

            user_data = config_data["users"].get(user_id, {})
            user_data["interval"] = interval  
            config_data["users"][user_id] = user_data  

            with open("config.json", "w") as f:
                json.dump(config_data, f, indent=4)

            await update.message.reply_text(f"*Message forwarding interval set to {interval} seconds ✅*", parse_mode="Markdown")
        else:
            await update.message.reply_text("Usage: /time <interval_in_seconds>")
    else:
        await update.message.reply_text(f"<b>No Active Subscription, Please contact</b> <a href=\"tg://resolve?domain={ADMIN_USERNAME}\">Admin</a>", parse_mode="HTML")

async def offf(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, reason: str = "") -> None:
    with open("config.json", "r") as f:
        config_data = json.load(f)

    user_data = config_data["users"].get(user_id, {})
    if "forwarding_on" in user_data and user_data["forwarding_on"]:
        user_data["forwarding_on"] = False

        with open("config.json", "w") as f:
            json.dump(config_data, f, indent=4)

        for job in scheduler.get_jobs():
            if job.args[2] == user_id:
                scheduler.remove_job(job.id)
                break

        await update.message.reply_text(
            f"*Message forwarding has been disabled ❌*\n`{reason}`",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "*Message forwarding is already disabled or not set up for you ❗*",
            parse_mode="Markdown"
        )


async def off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)

    with open("config.json", "r") as f:
        config_data = json.load(f)

    user_data = config_data["users"].get(user_id, {})
    if "forwarding_on" in user_data and user_data["forwarding_on"]:

        user_data["forwarding_on"] = False

        with open("config.json", "w") as f:
            json.dump(config_data, f, indent=4)

        job_removed = False
        for job in scheduler.get_jobs():
            if job.args[2] == user_id:  
                scheduler.remove_job(job.id)
                job_removed = True
                break

        if job_removed:
            await update.message.reply_text("*Message forwarding has been disabled ❌*", parse_mode="Markdown")
        else:
            await update.message.reply_text("*No active forwarding job was found for you ❗*", parse_mode="Markdown")

        if not scheduler.get_jobs():
            scheduler.shutdown()
            print("Scheduler stopped as there are no remaining jobs.")

    else:
        await update.message.reply_text("*Message forwarding is already disabled or not set up for you ❗*", parse_mode="Markdown")

def extract_chat_and_message_id(post_message: str):
    """
    Extracts chat username and message ID from a Telegram message link.
    Example: https://t.me/chatusername/12345
    """
    if post_message.startswith("https://t.me/"):
        parts = post_message.replace("https://t.me/", "").split("/")
        if len(parts) == 2 and parts[1].isdigit():
            chat_username = parts[0]    
            message_id = parts[1]  
            return chat_username, int(message_id)  
    return None, None

def extract_group_and_topic_id(group_link: str):
    """
    Extracts the group username and optional topic ID from a group link.
    Example: https://t.me/groupusername/12345 (for topic links).
    """
    if group_link.startswith("https://t.me/"):
        parts = group_link.replace("https://t.me/", "").split("/")
        group_username = parts[0]  

        topic_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None

        return group_username, topic_id
    return None, None

async def forward_messages(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str) -> None:
    try:

        with open("config.json", "r") as f:
            config_data = json.load(f)

        user_data = config_data["users"].get(user_id, {})
        api_id = user_data.get('api_id', '')
        api_hash = user_data.get('api_hash', '')
        post_message = user_data.get('post_messages', [])
        interval = int(user_data.get('interval', 60))  
        user_groups = user_data.get('groups', [])
        forwarding_on = user_data.get('forwarding_on', False)

        if not forwarding_on:
            print("Forwarding is disabled for this user.")
            await offf(update, context, user_id, reason="Forwarding is disabled")
            return  

        if not user_groups:
            print("No groups found for this user.")
            await offf(update, context, user_id, reason="No groups found for forwarding.")
            return
        
        if not post_message:
            print("No post messages available for forwarding ❌")
            await offf(update, context, user_id, reason="No post messages available for forwarding ❌")
            return
        
        post_index = user_data.get("post_index", 0) 
        if post_index >= len(post_message):  
            post_index = 0 
        async with TelegramClient(f'{user_id}.session', api_id, api_hash) as client:
        
            if not await client.is_user_authorized():
                print("User is not authorized.")
                return
            current_post = post_message[post_index]
            for group_link in user_groups:
                retry_count = 2
                while retry_count > 0:
                    try:

                        to_peer, topic_id = extract_group_and_topic_id(group_link)
                        if not to_peer:
                            print(f"Invalid group link: {group_link}")
                            break

                        if current_post.startswith("https://t.me/"):

                            from_peer, message_id = extract_chat_and_message_id(current_post)
                            group_parts = group_link.replace("https://t.me/", "").split("/")
                            to_peer = group_parts[0]  
                            topic_ids = group_parts[1] if len(group_parts) > 1 and group_parts[1].isdigit() else None

                            if from_peer and message_id:

                                target_group = await client.get_entity(to_peer)

                                if topic_ids:

                                    await client(functions.messages.ForwardMessagesRequest(
                                        from_peer=from_peer,
                                        id=[message_id],
                                        to_peer=target_group,
                                        top_msg_id=int(topic_ids)  
                                    ))
                                else:

                                    await client(functions.messages.ForwardMessagesRequest(
                                        from_peer=from_peer,
                                        id=[message_id],
                                        to_peer=target_group
                                    ))

                                print(f"Message forwarded to group {group_link}.")
                            else:
                                print(f"Invalid Telegram message link: {post_message}")

                        else:

                            target_group = await client.get_entity(to_peer)

                            if topic_id is not None:

                                await client.send_message(target_group, current_post, reply_to=int(topic_id))
                            else:

                                await client.send_message(target_group, current_post)

                            print(f"Message sent to group {group_link}.")

                        break  
                    except Exception as e:
                        print(f"Error forwarding message to group {group_link}: {e}")
                        retry_count -= 1
                        await asyncio.sleep(1)  

            print(f"All messages sent. Disconnecting client.")
        post_index = (post_index + 1) % len(post_message)
        user_data["post_index"] = post_index
        config_data["users"][user_id] = user_data  # Update user data in config
        with open("config.json", "w") as f:
            json.dump(config_data, f, indent=4)
        await asyncio.sleep(interval)  

    except Exception as e:
        print(f"An error occurred in forward_messages: {e}")

async def on(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    if not await is_authorized(user_id):

        await update.message.reply_text(
            "⚠️ *Your subscription has expired or you are not authorized to enable forwarding.*\n"
            f"*Please contact the* [Admin](tg://resolve?domain={ADMIN_USERNAME}) *for assistance ❕*",
            parse_mode="Markdown"
        )
        return

    data = load_user_data()
    user_data = data["users"].get(user_id, {})

    required_keys = ["api_id", "api_hash", "post_messages", "groups", "interval"]
    missing_keys = [key for key in required_keys if not user_data.get(key)]

    if user_data.get("auto_reply_status", False):
        await update.message.reply_text("*Forwarding cannot be toggled when Auto-reply is active ❌*", parse_mode="Markdown")
        return

    if missing_keys:
        await update.message.reply_text(
            f"*Please ensure the following keys are set before enabling forwarding:* ```{', '.join(missing_keys)}```",
            parse_mode="Markdown"
        )
        return

    if int(user_data.get("interval", 0)) < 15:
        await update.message.reply_text(
            "The interval must be at least 15 seconds. Please update it using the `/time` command.",
            parse_mode="Markdown"
        )
        return

    session_file = f'{user_id}.session'
    if not os.path.exists(session_file):
        await update.message.reply_text("*Sorry, you are logged out. Please log in again with* `/login +1234567890`", parse_mode="Markdown")
        return

    try:
        client = TelegramClient(session_file, user_data["api_id"], user_data["api_hash"])
        await client.connect()  

        if not await client.is_user_authorized():
            await client.disconnect()
            os.remove(session_file)
            await update.message.reply_text("*Your session was terminated. Please log in again ❌*", parse_mode="Markdown")
            return

        data["users"][user_id]["forwarding_on"] = True
        save_user_data(data)

        for group_link in user_data.get('groups', []):
            try:

                to_peer, topic_id = extract_group_and_topic_id(group_link)
                if not to_peer:
                    print("Invalid group link.")
                    continue

                post_message = user_data["post_messages"][0]
                if post_message.startswith("https://t.me/"):

                    from_peer, message_id = extract_chat_and_message_id(post_message)
                    group_parts = group_link.replace("https://t.me/", "").split("/")
                    to_peer = group_parts[0]  
                    topic_ids = group_parts[1] if len(group_parts) > 1 and group_parts[1].isdigit() else None

                    if from_peer and message_id:

                        target_group = await client.get_entity(to_peer)

                        if topic_ids:
                            await client(functions.messages.ForwardMessagesRequest(
                                            from_peer=from_peer,
                                            id=[message_id],
                                            to_peer=target_group,
                                            top_msg_id=int(topic_ids)  
                                        ))

                        else:

                            await client(functions.messages.ForwardMessagesRequest(
                                    from_peer=from_peer,
                                    id=[message_id],
                                    to_peer=target_group
                                        ))

                        print(f"Message forwarded to group {group_link}.")

                else:

                                target_group = await client.get_entity(to_peer)

                                if topic_id is not None:

                                    await client.send_message(target_group, post_message, reply_to=int(topic_id))
                                else:

                                    await client.send_message(target_group, post_message)

                                print(f"Message sent to group {group_link}.")

            except Exception as e:
                print(f"Error sending initial message to group {group_link}: {e}")

        if not scheduler.running:
            scheduler.start()

        job_exists = any(job.args[0] == user_id for job in scheduler.get_jobs())
        if not job_exists:
            scheduler.add_job(forward_messages, 'interval', seconds=int(user_data["interval"]), args=[update, context, user_id], max_instances=5)



        await update.message.reply_text("*Message forwarding is now enabled ✅*", parse_mode="Markdown")

    except Exception as e:
        print(f"An error occurred while checking your session: {e}")
        await update.message.reply_text(f"*An error occurred while checking your session.\n{e}❗*", parse_mode="Markdown")
    finally:
        if client.is_connected():
            await client.disconnect()

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    if update.callback_query:
        message = update.callback_query.message
        user_id = str(update.callback_query.from_user.id)
        is_callback = True
    else:
        message = update.message
        user_id = str(update.message.from_user.id)
        is_callback = False

    with open("config.json", "r") as f:
        config_data = json.load(f)
    if await is_authorized(user_id):
        user_data = config_data["users"].get(user_id, {})
        user_groups = user_data.get('groups', [])
        interval = user_data.get('interval', "Not set")
        group_count = len(user_groups)
        if user_groups:
            formatted_groups = "\n".join([f"`{group}`" for group in user_groups])
        if group_count > 0:
            group_info = f"Groups Added: {group_count}"
        else:
            group_info = "No Group has been added"

        settings_text = (f"*Your Settings*\n\n"
                        f"*- Groups Added: {group_count}*\n"
                        f"*- Interval: {interval} seconds*")

        keyboard = [
            [InlineKeyboardButton("My Post 📝", callback_data='my_post'), InlineKeyboardButton("My Groups 👥 ", callback_data='my_groups')],
            [InlineKeyboardButton("Add Group ➕ ", callback_data='add_group'), InlineKeyboardButton("Remove Group ❌", callback_data='remove_group')],
            [InlineKeyboardButton("Set Time ⏲", callback_data='set_time'), InlineKeyboardButton("Toggle Forwarding ⏩", callback_data='on_off')],
            [InlineKeyboardButton("Logout 🚪", callback_data='logout'), InlineKeyboardButton("Back 🔙", callback_data='back')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
    else:
        await update.message.reply_text(f"<b>No Active Subscription, Please contact</b> <a href=\"tg://resolve?domain={ADMIN_USERNAME}\">Admin</a>", parse_mode="HTML")

    if is_callback:
        await message.edit_text(settings_text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await message.reply_text(settings_text, reply_markup=reply_markup, parse_mode="Markdown")

async def my_posts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    if update.callback_query:
        user_id = str(update.callback_query.from_user.id)
        message = update.callback_query.message
        is_callback = True
    else:
        user_id = str(update.message.from_user.id)
        message = update.message
        is_callback = False

    with open("config.json", "r") as f:
        config_data = json.load(f)

    user_data = config_data["users"].get(user_id, {})
    post_messages = user_data.get('post_messages', [])

    if post_messages:
        message_text = "*Your Post Messages:*\n\n"
        for i, post in enumerate(post_messages, start=1):
            message_text += f"*{i}.* `{post}`\n\n"
        message_text += "\n*Use* `/post message` *to update your posts.*"
    else:
        message_text = "*No post messages found.*"

    keyboard = [[InlineKeyboardButton("Back 🔙", callback_data='settings')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if is_callback:
        await message.edit_text(message_text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await message.reply_text(message_text, reply_markup=reply_markup, parse_mode="Markdown")

async def my_groups(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    if update.callback_query:

        user_id = str(update.callback_query.from_user.id)
        message = update.callback_query.message
        is_callback = True
    else:

        user_id = str(update.message.from_user.id)
        message = update.message
        is_callback = False

    with open("config.json", "r") as f:
        config_data = json.load(f)

    user_data = config_data["users"].get(user_id, {})
    user_groups = user_data.get('groups', [])

    if user_groups:
        group_count = len(user_groups)
        group_list = "\n".join([f"{idx+1}. `{group}`" for idx, group in enumerate(user_groups)])
        message_text = f"*Groups Added: {group_count}*\n\n{group_list}"
    else:
        message_text = "*No groups added*"

    keyboard = [
        [InlineKeyboardButton("Back 🔙", callback_data='settings')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if is_callback:

        await message.edit_text(message_text, reply_markup=reply_markup, parse_mode="Markdown")
    else:

        await message.reply_text(message_text, reply_markup=reply_markup, parse_mode="Markdown")

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("HELP GUIDE ❕", callback_data='help')],
        [InlineKeyboardButton("AUTO RESPONDER GUIDE❕", url='https://telegra.ph/AUTO-RESPONDER-GUIDE-11-11')],
        [InlineKeyboardButton("API AND HASH ID 🎥", url='https://youtu.be/s7Ys5reuxHc?si=e3724tW8NhpzbvJR')],
        [InlineKeyboardButton("LOGIN WITH TELEGRAM 🔑", callback_data='login')],
        [InlineKeyboardButton("Settings ⚙️", callback_data='settings')],
        [InlineKeyboardButton("Auto Reply ⚙️", callback_data='auto_reply')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:

        await update.message.reply_text("DEVSCOTT Main Menu", reply_markup=reply_markup)
    elif update.callback_query:

        query = update.callback_query
        await query.edit_message_text("DEVSCOTT Main Menu", reply_markup=reply_markup)

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()  

    await main_menu(update, context)

def get_user_keywords(user_data):
    keywords = user_data.get("keywords", {})
    match_option = user_data.get("match_option", "exact")

    if not keywords:
        return "You haven't set any keywords yet."

    response_text = "<b>Here are your keywords and responses:</b>\n\n"
    response_text += f"<b>Matching Option:</b> {match_option.capitalize()}\n\n"
    response_text += "<b>Keyword</b> ➡️ <b>Response</b>\n"
    response_text += "=====================\n"

    for keyword, response in keywords.items():
        response_text += f"<code>{keyword}</code> ➡️ <code>{response}</code>\n"

    return response_text

async def keywords_command(update, context):
    """
    Command handler for /keywords command or callback query. Displays the user's keywords and responses.
    """

    if update.callback_query:
        query = update.callback_query
        user_id = str(query.from_user.id)  
        await query.answer()  
    else:
        user_id = str(update.message.from_user.id)  

    data = load_user_data()
    user_data = data["users"].get(user_id, {})

    response_text = get_user_keywords(user_data)

    keyboard = [
        [InlineKeyboardButton("Add Keyword", callback_data="add_keyword")],
        [InlineKeyboardButton("Del Keyword", callback_data="del_keyword")],
        [InlineKeyboardButton("Back 🔙", callback_data="auto_reply")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await query.edit_message_text(response_text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        await update.message.reply_text(response_text, reply_markup=reply_markup, parse_mode="HTML")

async def stopword_command(update, context):
    """
    Command handler for /stopword <keyword>. Deletes a specific keyword for the user, including multi-word keywords.
    """
    user_id = str(update.message.from_user.id)  

    data = load_user_data()
    user_data = data["users"].get(user_id, {})

    try:
        keyword_to_remove = ' '.join(context.args)  
    except IndexError:
        await update.message.reply_text("Please specify the keyword you want to remove. Example: /stopword Good Morning")
        return

    keywords = user_data.get("keywords", {})
    if keyword_to_remove in keywords:

        message = await update.message.reply_text("<b>Deleting ▪▪</b>", parse_mode="HTML")
        await asyncio.sleep(0.2)
        await message.edit_text("<b>Deleting ▪▪▪▪</b>", parse_mode="HTML")
        await asyncio.sleep(0.2)
        await message.edit_text("<b>Deleting ▪▪▪▪▪▪</b>", parse_mode="HTML")
        await asyncio.sleep(0.4)

        del keywords[keyword_to_remove]

        save_user_data(data)

        await message.edit_text(f"<b>Deleted '{keyword_to_remove}' successfully ✅</b>", parse_mode="HTML")
    else:
        await update.message.reply_text(f"<b>Keyword '{keyword_to_remove}' not found in your list ❌</b>", parse_mode="HTML")

async def autoreply_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = str(query.from_user.id).strip()

    data = load_user_data()
    user_data = data["users"].get(user_id, {})

    if not await is_authorized(user_id):
        await query.edit_message_text("*You are not allowed to use this feature ❌*", parse_mode="Markdown")
        return

    if query.data == "set_exact":
        user_data["match_option"] = "exact"
    elif query.data == "set_partial":
        user_data["match_option"] = "partial"
    elif query.data == "set_case_insensitive":
        user_data["match_option"] = "case_insensitive"
    elif query.data == "toggle_auto_reply":
        user_data = data["users"].get(user_id)  

        keywords = user_data.get("keywords", {})
        if not keywords:
            await query.answer("No keywords have been set for you ❌\n Please add at least one word\n (/setword Message | Response)", show_alert=True)
            return

        if user_data.get("forwarding_on", False):
            await query.answer("Auto-reply cannot be toggled while forwarding is active ❌", show_alert=True)
        else:

            user_data["auto_reply_status"] = not user_data.get("auto_reply_status", False)

            save_user_data(data)

            await query.answer(f"Auto-reply is now {'enabled' if user_data['auto_reply_status'] else 'disabled'} ✅", show_alert=True)

            if user_data["auto_reply_status"]:
                await start_telethon_client(user_id, context)  
            else:
                await stop_telethon_client(user_id)

    else:
        await all_callback(update, context)
        return

    save_user_data(data)

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

    await query.edit_message_text(
        f"Your Auto-reply settings\n\n*Match Option: {match_option}✅*\n*Mode: {auto_reply_status}✅*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def all_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id).strip()
    data = load_user_data()
    user_data = data["users"].get(user_id, {})

    if not await is_authorized(user_id):
        await query.edit_message_text("*You are not allowed to use this feature ❌*", parse_mode="Markdown")
        return

    if query.data == 'add_group':
        await query.edit_message_text("*Please Use:* \n`/addgroup\n<group_link>\n<group_link2>`\n\n *to add a group or groups*", reply_markup=back_button(), parse_mode="Markdown")
    elif query.data == 'remove_group':
        await query.edit_message_text("Please use /delgroup <group_link> to remove a group.", reply_markup=back_button())
    elif query.data == 'set_time':
        await query.edit_message_text("Please use /time <interval> to set the message interval in seconds only.", reply_markup=back_button())
    elif query.data == 'on_off':
        await query.edit_message_text("Please use /on or /off to toggle forwarding.", reply_markup=back_button())
    elif query.data == 'back':
        await back_to_menu(update, context)
    elif query.data == "words": 
        await keywords_command(update, context)
    elif query.data == "add_keyword":
        await query.edit_message_text("Use `/setword Message | Response`", parse_mode="Markdown", reply_markup=back_button())
    elif query.data == "del_keyword":
        await query.edit_message_text("Use `/stopword <keyword>` to delete a set word", parse_mode="Markdown", reply_markup=back_button())
    elif query.data == 'logout':
        await logout(update, context)
    elif query.data == "my_post":
        await my_posts(update, context)
    elif query.data == "my_groups":
        await my_groups(update, context)
    elif query.data == "auto_reply":
        await keyword_settings(update, context)

    elif query.data == 'help':
        help_text = (
        "🤖 <b>DEVSCOTT AUTO FORWARDING Bot Help</b>\n\n"
        "Welcome to the DEVSCOTT AUTO FORWARDING Bot! Here's a guide on how to use the available commands:\n\n"

        "1. <code>/start</code> - Initiates the bot and provides subscription information.\n"
        "   - Displays your current subscription status and expiration date, along with quick links to login and settings.\n\n"

        "2. <code>/post &lt;message&gt;</code> - Sets the message to be forwarded to your groups.\n"
        "   - Example: <code>/post Hello everyone!</code> sets the message <code>Hello everyone!</code> to be forwarded.\nSet telegram message link if you want the message to be forwarded\n"
        "   - Use <code>/mypost</code> to check the posts you have added\n"
        "   - Multiple Posts can be added, use <code>/delpost index \ message</code> to delete a post\n<code>\delpost all</code> to delete all post set\n\n"

        "3. <code>/addgroup &lt;group_link&gt;</code> - Adds a group to your forwarding list.\n"
        "   - Example: <code>/addgroup https://t.me/mygroupusername</code> adds the group with link <code> https://t.me/mygroupusername</code> to your list for message forwarding.\n\n"

        "4. <code>/delgroup &lt;group_id&gt https://t.me/mygroupusername;</code> - Removes a group from your forwarding list.\n"
        "   - Example: <code>/delgroup  https://t.me/mygroupusername</code> removes the group with link <code>https://t.me/mygroupusernam</code>.\n\n"

        "5. <code>/time &lt;seconds&gt;</code> - Sets the interval between message forwarding in seconds.\n"
        "   - Example: <code>/time 60</code> sets the message forwarding interval to 60 seconds.\n\n"

        "6. <code>/on</code> - Enables automatic message forwarding.\n"
        "   - Before you use this command, make sure you've set the following:\n"
        "     - API ID and API Hash\n"
        "     - Groups to forward messages to\n"
        "     - The post message\n"
        "     - Interval for forwarding\n\n"

        "7. <code>/off</code> - Disables message forwarding.\n"
        "   - This will stop the bot from forwarding messages to any of your groups.\n\n"

        "🔑 <b>API Key and Login Instructions:</b>\n"
        "   1. <b>To log in:</b>\n"
        "      - Use the <code>/start</code> command to initiate the bot. If you're not logged in, use the <code>/login</code> (phone number) and complete the verification process.\n"
        "   2. <b>To add your API keys:</b>\n"
        "      - Ensure you have your Telegram API ID and API Hash.\n"
        "      - Use the <code>/api_id</code> and <code>/hash</code> commands to set them up for forwarding. Ensure your API ID and API Hash are correctly configured in your user settings.\n"
        "      - If you encounter issues with logging in or setting up API keys, check that your credentials are correct and ensure you've completed all required steps.\n\n"

        f"💡 <b>Need more help?</b> Contact the <a href=\"tg://resolve?domain={ADMIN_USERNAME}\">Admin</a> or refer to the tutorial"
    )

        await query.edit_message_text(text= help_text, parse_mode='HTML', reply_markup=back_button())

    elif query.data == 'login':
        await query.edit_message_text("Usage: /login <phone_number>", reply_markup=back_button())
    elif query.data == 'settings':
        await settings(update, context) 

def back_button():
    keyboard = [[InlineKeyboardButton("Back 🔙", callback_data='settings')]]
    return InlineKeyboardMarkup(keyboard)

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add))
    application.add_handler(CommandHandler("remove", remove))
    application.add_handler(CommandHandler("api_id", api_id))
    application.add_handler(CommandHandler("hash", api_hash))
    application.add_handler(CommandHandler("login", login))
    application.add_handler(CommandHandler("otp", otp))
    application.add_handler(CommandHandler("on", on))
    application.add_handler(CommandHandler("off", off))
    application.add_handler(CommandHandler("2fa", two_fa))
    application.add_handler(CommandHandler("logout", logout))
    application.add_handler(CommandHandler("groups", my_groups))
    application.add_handler(CommandHandler("addgroup", add_group))
    application.add_handler(CommandHandler("delgroup", del_group))
    application.add_handler(CommandHandler("setword", set_word))
    application.add_handler(CommandHandler("keywords", keywords_command))
    application.add_handler(CommandHandler("stopword", stopword_command))
    application.add_handler(CommandHandler("time", time))
    application.add_handler(CommandHandler('post', post)) 
    application.add_handler(CommandHandler('mypost', my_posts)) 
    application.add_handler(CommandHandler("delpost", delpost))
    application.add_handler(CommandHandler("settings", settings))
    application.add_handler(CallbackQueryHandler(autoreply_callback))
    application.add_handler(CallbackQueryHandler(all_callback))

    application.run_polling()  

class CustomHandler(http.server.SimpleHTTPRequestHandler):  
    def do_GET(self):  
        self.send_response(200)  
        self.send_header("Content-type", "text/html")  
        self.end_headers()  

        self.wfile.write(b"<!doctype html><html><head><title>Server Status</title></head>")  
        self.wfile.write(b"<body><h1>Bot is running...</h1></body></html>")  

def run_web_server():  
    port = int(os.environ.get('PORT', 5000))  
    handler = CustomHandler  
    with socketserver.TCPServer(("", port), handler) as httpd:  
        print(f"Forwarder is running >> Serving at port {port}")  
        httpd.serve_forever()  

if __name__ == '__main__':
    server_thread = threading.Thread(target=run_web_server)
    server_thread.start()
    main()