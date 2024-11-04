
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
            if "authorized_users" not in config:
                config["authorized_users"] = {}  
            return config
    except FileNotFoundError:
        return {"authorized_users": {}}
    except json.JSONDecodeError:
        return {"authorized_users": {}}

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
# Logging setup
logging.basicConfig(
    level=logging.INFO,  # Logging level
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
                    data["users"][user_id]["forwarding_on"] = False #just disables forwarding if on
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

    # Load the user data from config.json
    data = load_user_data()

    if user_id in data["users"]:
        expiry_date = data["users"][user_id]["expiry_date"]
        try:
            # Parse the expiry date
            expiry_datetime = datetime.strptime(expiry_date, '%Y-%m-%d %H:%M:%S')
            time_left = (expiry_datetime - datetime.now()).days
            formatted_expiry = expiry_datetime.strftime('%Y-%m-%d %H:%M:%S')  
            logger.info(f"User {user_id} subscription expires on {formatted_expiry}")
        except ValueError as e:
            logger.error(f"Date parsing error: {e}")
            await update.message.reply_text("There was an error processing your subscription. Please contact admin.")
            return
        
        if time_left >= 0:
            # If subscription is still active
            keyboard = [
                [InlineKeyboardButton("Help ❕", callback_data='help')],
                [InlineKeyboardButton("Video 🎥", url='https://youtu.be/8naENmP3rg4?si=K1e-Vf0mxQJL-SmD')],
                [InlineKeyboardButton("Login 🔑", callback_data='login')],
                [InlineKeyboardButton("Settings ⚙️", callback_data='settings')],
                [InlineKeyboardButton("Auto Reply ⚙️", callback_data='auto_reply')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f'Welcome to <b>DEVSCOTT AUTO F Bot</B>\nYour subscription ends on <b>{formatted_expiry}</b>.',
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        else:
            # If subscription has ended, disable forwarding
            await update.message.reply_text(
                "<b>Your Subscription Has Ended, Please contact</b> <a href=\"tg://resolve?domain=devscottreal\">Admin</a>",
                parse_mode="HTML"
            )
            # Set forwarding to false for this specific user
            data["users"][user_id]["forwarding_on"] = False
            save_user_data(data)
    else:
        # If the user is not found in the data
        logger.info(f"User {user_id} is not authorized or subscription has expired.")
        await update.message.reply_text(
            "<b>No Active Subscription, Please contact</b> <a href=\"tg://resolve?domain=devscottreal\">Admin</a>",
            parse_mode="HTML"
        )
        # Ensure forwarding is off for users without a subscription
        if user_id in data["users"]:
            data["users"][user_id]["forwarding_on"] = False
        save_user_data(data)

        



# User: /post command handler
async def post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)  

    if await is_authorized(user_id):
        if context.args:
            post_message = ' '.join(context.args)  # Join all arguments into a single message
            
            # Load user data from config.json
            data = load_user_data()

            if user_id in data["users"]:
                try:
                    # Save the post message for the user
                    data["users"][user_id]["post_message"] = post_message
                    save_user_data(data)  # Save the updated data back to config.json
                    
                    await update.message.reply_text("*Message saved for forwarding ✅*", parse_mode="Markdown")
                except Exception as e:
                    await update.message.reply_text(f"Failed to save the message due to an error: {e}")
            else:
                await update.message.reply_text("User not found in the system.")
        else:
            await update.message.reply_text("Usage: `/post <message / text link>`", parse_mode="Markdown")
    else:
        await update.message.reply_text("<b>No Active Subscription, Please contact</b> <a href=\"tg://resolve?domain=devscottreal\">Admin</a>", parse_mode="HTML")

from datetime import datetime, timedelta  # Ensure correct imports

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id_from_message = str(update.message.from_user.id)  # Get the user ID of the message sender

    if user_id_from_message in ADMIN_IDS:  # Check if the sender is an admin
        data = load_user_data()  # Load user data from JSON
        try:
            user_id = str(context.args[0])
            days = int(context.args[1])

            # Calculate expiry date
            expiry_date = datetime.now() + timedelta(days=days)

            # Ensure "users" key exists
            if "users" not in data:
                data["users"] = {}

            # Default user structure template for new users
            default_user_data = {
                "expiry_date": expiry_date.strftime('%Y-%m-%d %H:%M:%S'),
                "api_id": "",
                "api_hash": "",
                "post_message": "",
                "interval": "",
                "groups": [],
                "keywords": {},
                "match_option": "exact", 
                "auto_reply_status": False,
                "forwarding_on": False
            }

            # Check if the user already exists in the data
            if user_id in data["users"]:
                data["users"][user_id]["expiry_date"] = expiry_date.strftime('%Y-%m-%d %H:%M:%S')
            else:
                data["users"][user_id] = default_user_data

            # Save the updated user data back to the JSON file
            save_user_data(data)

            await update.message.reply_text(f"User `{user_id}` added with expiry date: {expiry_date.strftime('%Y-%m-%d %H:%M:%S')}", parse_mode="Markdown")
        
        except IndexError:
            await update.message.reply_text("*Please provide both user ID and number of days.*\n Usage: `/add <user_id> <days>`", parse_mode="Markdown")
        
        except ValueError:
            await update.message.reply_text("Invalid input. Please make sure you're entering a valid number of days.")
        
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")
    else:
        # Reply with a message if the user is not an admin
        await update.message.reply_text("*You do not have permission to use this command ❌*", parse_mode="Markdown")



# /remove command to remove users
async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id_from_message = str(update.message.from_user.id)  # Get the user ID of the message sender

    if user_id_from_message in ADMIN_IDS:  # Check if the sender is an admin
        data = load_user_data()  # Load user data from JSON
        try:
            user_id = str(context.args[0])  # Convert user_id to string to match your data structure
            
            # Check if the user exists in the 'users' section
            if user_id in data["users"]:
                del data["users"][user_id]  # Remove the user from 'users'
                save_user_data(data)  # Save the updated data back to JSON
                
                await update.message.reply_text(f"User {user_id} removed.")
            else:
                await update.message.reply_text("User not found.")
        except IndexError:
            await update.message.reply_text("Please provide the user ID. Usage: /remove <user_id>")
        
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")
    else:
        # Reply with a message if the user is not an admin
        await update.message.reply_text("You do not have permission to use this command.")

async def api_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id) 
    if  await is_authorized(user_id):
        if len(context.args) == 1:
            api_id = context.args[0]

            # Load user data
            data = load_user_data()

            # Update API ID for the user
            if user_id not in data["users"]:
                data["users"][user_id] = {}  
            data["users"][user_id]["api_id"] = api_id

            # Save updated data
            save_user_data(data)
            await update.message.reply_text("*API ID saved✅*", parse_mode="Markdown")
        else:
            await update.message.reply_text("Usage: /api_id <API_ID>")
    else:
        await update.message.reply_text("<b>No Active Subscription, Please contact</b> <a href=\"tg://resolve?domain=devscottreal\">Admin</a>", parse_mode="HTML")

# /hash command handler
async def api_hash(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id) 
    if await is_authorized(user_id):
        if len(context.args) == 1:
            api_hash = context.args[0]

            # Load user data
            data = load_user_data()

            # Update API Hash for the user
            if user_id not in data["users"]:
                data["users"][user_id] = {}  
            data["users"][user_id]["api_hash"] = api_hash

            # Save updated data
            save_user_data(data)
            await update.message.reply_text("*API Hash saved ✅*", parse_mode="Markdown")
        else:
            await update.message.reply_text("Usage:\n `/hash <API_HASH>`", parse_mode="Markdown")
    else:
        await update.message.reply_text("<b>No Active Subscription, Please contact</b> <a href=\"tg://resolve?domain=devscottreal\">Admin</a>", parse_mode="HTML")


async def login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id) 
    if await is_authorized(user_id):
        # Load user data from JSON
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
        await update.message.reply_text("<b>No Active Subscription, Please contact</b> <a href=\"tg://resolve?domain=devscottreal\">Admin</a>", parse_mode="HTML")

# /otp command handler
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
        # Load user data from JSON
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
                # Ensure the client is disconnected
                await client.disconnect()
        else:
            await update.message.reply_text("API ID and Hash not found. Set them with /api_id and /hash.")
    else:
        await update.message.reply_text("Usage: /2fa <password>")

# /logout command handler
async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Determine if the update is a callback query or a command
    if update.callback_query:
        message = update.callback_query.message
    else:
        message = update.message

    if not message:
        await update.message.reply_text("Unable to process the request.")
        return

    user_id = str(message.from_user.id)  # Convert user ID to string for JSON key compatibility

    # Load user data from JSON
    data = load_user_data()
    user_data = data["users"].get(user_id, {})

    api_id = user_data.get("api_id")
    api_hash = user_data.get("api_hash")

    if api_id and api_hash:
        try:
            # Log out and remove session file
            client = TelegramClient(f'{user_id}.session', api_id, api_hash)
            
            try:
                await client.connect()
            except Exception as e:
                await message.reply_text(f"Failed to connect: {e}")
                return  # Exit if connection fails

            try:
                await client.log_out()
            except Exception as e:
                await message.reply_text(f"Failed to log out: {e}")
                return  # Exit if logout fails

            # Remove session file
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


# /add_group command handler
async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)  # Store user ID as string in JSON

    if await is_authorized(user_id):
        message_text = update.message.text
        group_links = message_text.split("\n")[1:] 

        if len(group_links) > 50:
            await update.message.reply_text("You can add a maximum of 50 group links at a time.")
            return

        # Load the config from config.json
        with open("config.json", "r") as f:
            config_data = json.load(f)

        user_data = config_data["users"].get(user_id, {})
        user_groups = user_data.get("groups", [])  # Get user's groups or empty list

        added_groups = []
        already_in_list = []

        # Loop through each group link and add it if it starts with https://t.me/ and is not already in the user's list
        for group_link in group_links:
            group_link = group_link.strip()  # Remove extra spaces
            if group_link.startswith("https://t.me/"):
                if group_link and group_link not in user_groups:
                    user_groups.append(group_link)
                    added_groups.append(group_link)
                elif group_link in user_groups:
                    already_in_list.append(group_link)
            else:
                # Optionally, you can notify the user if the link does not start with https://t.me/
                await update.message.reply_text(f"Link '{group_link}' is not a valid Telegram link.")

        user_data["groups"] = user_groups  # Update the user's groups
        config_data["users"][user_id] = user_data  # Update the user's data

        # Save the updated config back to config.json
        with open("config.json", "w") as f:
            json.dump(config_data, f, indent=4)

        # Prepare the response
        if added_groups:
            added_groups_message = "\n".join(added_groups)
            await update.message.reply_text(f"The following groups have been added for message forwarding:\n{added_groups_message}")
        if already_in_list:
            already_in_list_message = "\n".join(already_in_list)
            await update.message.reply_text(f"The following groups were already in your forwarding list:\n{already_in_list}")

        if not added_groups and not already_in_list:
            await update.message.reply_text("Invalid Format❗\nUsage:\n`/add_group\n<link1>\n<link2>`", parse_mode="Markdown")
        
    else:
        await update.message.reply_text(
            "<b>No Active Subscription, Please contact</b> <a href=\"tg://resolve?domain=devscottreal\">Admin</a>", 
            parse_mode="HTML"
        )


# /del_group command handler
async def del_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    group_id = context.args[0] if context.args else None
    user_id = str(update.message.from_user.id)  # Store user ID as string in JSON

    if await is_authorized(user_id):  # Check if user is authorized
        if group_id:
            # Load the config from config.json
            with open("config.json", "r") as f:
                config_data = json.load(f)

            user_data = config_data["users"].get(user_id, {})
            user_groups = user_data.get("groups", [])  # Get user's groups or empty list

            if group_id in user_groups:
                user_groups.remove(group_id)
                user_data["groups"] = user_groups  # Update the user's groups
                config_data["users"][user_id] = user_data  # Update the user's data

                # Save back to config.json
                with open("config.json", "w") as f:
                    json.dump(config_data, f, indent=4)
                
                await update.message.reply_text(f"Group {group_id} removed from message forwarding.")
            else:
                await update.message.reply_text("Group not found in your list.")
        else:
            await update.message.reply_text("Usage: /del_group <group_link>")
    else:
        await update.message.reply_text("<b>No Active Subscription, Please contact</b> <a href=\"tg://resolve?domain=devscottreal\">Admin</a>", parse_mode="HTML")


# User: /time command handler to set interval
import json

# /time command handler
async def time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    interval = int(context.args[0]) if context.args else None
    user_id = str(update.message.from_user.id)  # Store user ID as string in JSON

    if await is_authorized(user_id):  # Check if user is authorized
        if interval and interval > 0:
            # Load the config from config.json
            with open("config.json", "r") as f:
                config_data = json.load(f)

            user_data = config_data["users"].get(user_id, {})
            user_data["interval"] = interval  # Update the user's interval setting
            config_data["users"][user_id] = user_data  # Update the user's data

            # Save back to config.json
            with open("config.json", "w") as f:
                json.dump(config_data, f, indent=4)
            
            await update.message.reply_text(f"*Message forwarding interval set to {interval} seconds ✅*", parse_mode="Markdown")
        else:
            await update.message.reply_text("Usage: /time <interval_in_seconds>")
    else:
        await update.message.reply_text("<b>No Active Subscription, Please contact</b> <a href=\"tg://resolve?domain=devscottreal\">Admin</a>", parse_mode="HTML")



# /off command handler
async def off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    
    # Load configuration from config.json
    with open("config.json", "r") as f:
        config_data = json.load(f)
    
    # Retrieve user data
    user_data = config_data["users"].get(user_id, {})
    if "forwarding_on" in user_data and user_data["forwarding_on"]:
        # Disable forwarding for this user
        user_data["forwarding_on"] = False
        
        # Save the updated configuration
        with open("config.json", "w") as f:
            json.dump(config_data, f, indent=4)
        
        # Remove the job from the scheduler
        for job in scheduler.get_jobs():
            if job.args[0] == user_id:
                scheduler.remove_job(job.id)
                break
        
        await update.message.reply_text("*Message forwarding has been disabled ❌*", parse_mode="Markdown")
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
            chat_username = parts[0]  # 'chatusername'
            message_id = parts[1]  # '12345'
            return chat_username, int(message_id)  # Ensure message_id is an integer
    return None, None

def extract_group_and_topic_id(group_link: str):
    """
    Extracts the group username and optional topic ID from a group link.
    Example: https://t.me/groupusername/12345 (for topic links).
    """
    if group_link.startswith("https://t.me/"):
        parts = group_link.replace("https://t.me/", "").split("/")
        group_username = parts[0]  # Group username

        # Extract topic ID if available
        topic_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None

        return group_username, topic_id
    return None, None




async def forward_messages(user_id: str) -> None:
    try:
        # Load configuration from config.json
        with open("config.json", "r") as f:
            config_data = json.load(f)

        # Retrieve user data
        user_data = config_data["users"].get(user_id, {})
        api_id = user_data.get('api_id', '')
        api_hash = user_data.get('api_hash', '')
        post_message = user_data.get('post_message', '')
        interval = user_data.get('interval', 60)  # Interval in seconds
        user_groups = user_data.get('groups', [])
        forwarding_on = user_data.get('forwarding_on', False)

        if not forwarding_on:
            print("Forwarding is disabled for this user.")
            return  # Stop if forwarding is disabled
        
        if not user_groups:
            print("No groups found for this user.")
            return

        async with TelegramClient(f'{user_id}.session', api_id, api_hash) as client:
            # Check if user is authorized
            if not await client.is_user_authorized():
                print("User is not authorized.")
                return

            # Iterate over all user groups and try sending messages
            for group_link in user_groups:
                retry_count = 2
                while retry_count > 0:
                    try:
                        # Extract group and topic IDs from group link
                        to_peer, topic_id = extract_group_and_topic_id(group_link)
                        if not to_peer:
                            print(f"Invalid group link: {group_link}")
                            break

                        if post_message.startswith("https://t.me/"):
                            # Handle Telegram message link
                            from_peer, message_id = extract_chat_and_message_id(post_message)
                            group_parts = group_link.replace("https://t.me/", "").split("/")
                            to_peer = group_parts[0]  # Group username
                            topic_ids = group_parts[1] if len(group_parts) > 1 and group_parts[1].isdigit() else None

                            if from_peer and message_id:
                                # Resolve the chat entity
                                target_group = await client.get_entity(to_peer)

                                if topic_ids:
                                    # Forward message to the specific topic discussion
                                    await client(functions.messages.ForwardMessagesRequest(
                                        from_peer=from_peer,
                                        id=[message_id],
                                        to_peer=target_group,
                                        top_msg_id=int(topic_ids)  # Use the topic ID in the forwarding request
                                    ))
                                else:
                                    # Forward message to the group without a topic
                                    await client(functions.messages.forwardMessagesRequest(
                                        from_peer=from_peer,
                                        id=[message_id],
                                        to_peer=target_group
                                    ))

                                print(f"Message forwarded to group {group_link}.")
                            else:
                                print(f"Invalid Telegram message link: {post_message}")

                        else:
                            # Send a custom post message to the group (with or without topic)
                            target_group = await client.get_entity(to_peer)

                            if topic_id is not None:
                                # Send message to a specific topic using 'reply_to'
                                await client.send_message(target_group, post_message, reply_to=int(topic_id))
                            else:
                                # Send message to the general group
                                await client.send_message(target_group, post_message)

                            print(f"Message sent to group {group_link}.")

                        break  # Break the retry loop on success
                    except Exception as e:
                        print(f"Error forwarding message to group {group_link}: {e}")
                        retry_count -= 1
                        await asyncio.sleep(1)  # Wait before retrying

            print(f"All messages sent. Disconnecting client.")
        
        # Wait for the next interval before reconnecting and sending again
        await asyncio.sleep(interval)  # Delay the next round of messages

    except Exception as e:
        print(f"An error occurred in forward_messages: {e}")



        
async def on(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    if not await is_authorized(user_id):
        # Notify the user that they are not authorized (expired subscription, etc.)
        await update.message.reply_text(
            "⚠️ *Your subscription has expired or you are not authorized to enable forwarding.*\n"
            "*Please contact the* [Admin](tg://resolve?domain=devscottreal) *for assistance ❕*",
            parse_mode="Markdown"
        )
        return
    
    # Load user data
    data = load_user_data()
    user_data = data["users"].get(user_id, {})

    required_keys = ["api_id", "api_hash", "post_message", "groups", "interval"]
    missing_keys = [key for key in required_keys if not user_data.get(key)]

    if user_data.get("auto_reply_status", False):
        await update.message.reply_text("*Forwarding cannot be toggled when Auto-reply is active ❌*", parse_mode="Markdown")
        return

    # Check for missing keys or interval less than 15 seconds
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

        # Enable forwarding for this user
        data["users"][user_id]["forwarding_on"] = True
        save_user_data(data)

        for group_link in user_data.get('groups', []):
            try:
                # Extract group and topic IDs from group link
                to_peer, topic_id = extract_group_and_topic_id(group_link)
                if not to_peer:
                    print("Invalid group link.")
                    continue

                post_message = user_data['post_message']
                if post_message.startswith("https://t.me/"):
                    # Handle Telegram message link
                    from_peer, message_id = extract_chat_and_message_id(post_message)
                    group_parts = group_link.replace("https://t.me/", "").split("/")
                    to_peer = group_parts[0]  # Group username
                    topic_ids = group_parts[1] if len(group_parts) > 1 and group_parts[1].isdigit() else None
                              
                    if from_peer and message_id:
                                    # Resolve the chat entity
                        target_group = await client.get_entity(to_peer)

                        if topic_ids:
                            await client(functions.messages.ForwardMessagesRequest(
                                            from_peer=from_peer,
                                            id=[message_id],
                                            to_peer=target_group,
                                            top_msg_id=int(topic_ids)  # Use the topic ID in the forwarding request
                                        ))
                                    
                            
                        else:
                             
                            await client(functions.messages.ForwardMessagesRequest(
                                    from_peer=from_peer,
                                    id=[message_id],
                                    to_peer=target_group
                                        ))

                        print(f"Message forwarded to group {group_link}.")

                else:
                                # Send the custom post message to the group (with or without topic)
                                target_group = await client.get_entity(to_peer)

                                if topic_id is not None:
                                    # Send message to a specific topic using 'reply_to'
                                    await client.send_message(target_group, post_message, reply_to=int(topic_id))
                                else:
                                    # Send message to the general group
                                    await client.send_message(target_group, post_message)

                                print(f"Message sent to group {group_link}.")
                                      
                           
            except Exception as e:
                print(f"Error sending initial message to group {group_link}: {e}")
       
        # Check if the scheduler is running before starting it
        if not scheduler.running:
            scheduler.start()

        # Start forwarding messages using scheduler
        job_exists = any(job.args[0] == user_id for job in scheduler.get_jobs())
        if not job_exists:
            scheduler.add_job(forward_messages, 'interval', seconds=user_data["interval"], args=[user_id], max_instances=5)

        await update.message.reply_text("*Message forwarding is now enabled ✅*", parse_mode="Markdown")
        

    except Exception as e:
        print(f"An error occurred while checking your session: {e}")
        await update.message.reply_text("*An error occurred while checking your session. Forwarding may still be active ❗*", parse_mode="Markdown")
    finally:
        if client.is_connected():
            await client.disconnect()



async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Determine if the update is a callback query or a command
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

        
        # Format the settings message
        settings_text = (f"*Your Settings*\n\n"
                        f"*- Groups Added: {group_count}*\n"
                        f"*- Interval: {interval} seconds*")
        
        # Create the keyboard
        keyboard = [
            [InlineKeyboardButton("My Post 📝", callback_data='my_post'), InlineKeyboardButton("My Groups 👥 ", callback_data='my_groups')],
            [InlineKeyboardButton("Add Group ➕ ", callback_data='add_group'), InlineKeyboardButton("Remove Group ❌", callback_data='remove_group')],
            [InlineKeyboardButton("Set Time ⏲", callback_data='set_time'), InlineKeyboardButton("Toggle Forwarding ⏩", callback_data='on_off')],
            [InlineKeyboardButton("Logout 🚪", callback_data='logout'), InlineKeyboardButton("Back 🔙", callback_data='back')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
    else:
        await update.message.reply_text("<b>No Active Subscription, Please contact</b> <a href=\"tg://resolve?domain=devscottreal\">Admin</a>", parse_mode="HTML")

    # Edit the existing message if it's a callback query, otherwise send a new message
    if is_callback:
        await message.edit_text(settings_text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await message.reply_text(settings_text, reply_markup=reply_markup, parse_mode="Markdown")

async def my_posts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Determine whether the update is from a command or a callback query
    if update.callback_query:
        # Called via a button (callback query)
        user_id = str(update.callback_query.from_user.id)
        message = update.callback_query.message
        is_callback = True
    else:
        # Called via a command (normal message)
        user_id = str(update.message.from_user.id)
        message = update.message
        is_callback = False
    
    # Load user settings from config.json
    with open("config.json", "r") as f:
        config_data = json.load(f)

    # Retrieve the user's post_message
    user_data = config_data["users"].get(user_id, {})
    post_message = user_data.get('post_message', '')

    # Check if the user has set a post_message
    if post_message:
        message_text = f"*Your Post Message:*\n\n`{post_message}`\n\n *You can use* `/postset` *to check your post*"
    else:
        message_text = "*No post message found*"

    # Create the keyboard with a back button
    keyboard = [
        [InlineKeyboardButton("Back 🔙", callback_data='settings')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Respond based on whether it's a command or a callback query
    if is_callback:
        # Edit the message for a callback query
        await message.edit_text(message_text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        # Send a new message for a command
        await message.reply_text(message_text, reply_markup=reply_markup, parse_mode="Markdown")

async def my_groups(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Determine whether the update is from a command or a callback query
    if update.callback_query:
        # Called via a button (callback query)
        user_id = str(update.callback_query.from_user.id)
        message = update.callback_query.message
        is_callback = True
    else:
        # Called via a command (normal message)
        user_id = str(update.message.from_user.id)
        message = update.message
        is_callback = False
    
    # Load user settings from config.json
    with open("config.json", "r") as f:
        config_data = json.load(f)

    # Retrieve the user's groups
    user_data = config_data["users"].get(user_id, {})
    user_groups = user_data.get('groups', [])

    # Check if the user has added any groups
    if user_groups:
        group_count = len(user_groups)
        group_list = "\n".join([f"{idx+1}. `{group}`" for idx, group in enumerate(user_groups)])
        message_text = f"*Groups Added: {group_count}*\n\n{group_list}"
    else:
        message_text = "*No groups added*"

    # Create the keyboard with a back button
    keyboard = [
        [InlineKeyboardButton("Back 🔙", callback_data='settings')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Respond based on whether it's a command or a callback query
    if is_callback:
        # Edit the message for a callback query
        await message.edit_text(message_text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        # Send a new message for a command
        await message.reply_text(message_text, reply_markup=reply_markup, parse_mode="Markdown")


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("Help ❕", callback_data='help')],
        [InlineKeyboardButton("Tutorial 💡", url='https://youtu.be/8naENmP3rg4?si=K1e-Vf0mxQJL-SmD')],
        [InlineKeyboardButton("Login 🔑", callback_data='login')],
        [InlineKeyboardButton("Settings ⚙️", callback_data='settings')],
        [InlineKeyboardButton("Auto Reply ⚙️", callback_data='auto_reply')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        # If it's triggered by a command (like /start), use message.reply_text
        await update.message.reply_text("DEVSCOTT Main Menu", reply_markup=reply_markup)
    elif update.callback_query:
        # If it's triggered by a callback query (like the "back" button), use query.edit_message_text
        query = update.callback_query
        await query.edit_message_text("DEVSCOTT Main Menu", reply_markup=reply_markup)



# Back to Menu Button Handler
async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()  # Acknowledge the button press

    # Call the main menu function to display the menu again
    await main_menu(update, context)

def get_user_keywords(user_data):
    keywords = user_data.get("keywords", {})
    match_option = user_data.get("match_option", "exact")

    if not keywords:
        return "You haven't set any keywords yet."

    # Create a formatted string to display keywords and their responses
    response_text = "<b>Here are your keywords and responses:</b>\n\n"
    response_text += f"<b>Matching Option:</b> {match_option.capitalize()}\n\n"
    response_text += "<b>Keyword</b> ➡️ <b>Response</b>\n"
    response_text += "=====================\n"

    for keyword, response in keywords.items():
        response_text += f"<code>{keyword}</code> ➡️ {response}\n"

    return response_text

async def keywords_command(update, context):
    """
    Command handler for /keywords command or callback query. Displays the user's keywords and responses.
    """
    # Check if this was triggered by a callback query
    if update.callback_query:
        query = update.callback_query
        user_id = str(query.from_user.id)  # user_id from callback query
        await query.answer()  # Acknowledge the callback query
    else:
        user_id = str(update.message.from_user.id)  # user_id from message

    # Load user data
    data = load_user_data()
    user_data = data["users"].get(user_id, {})

    # Prepare the response text
    response_text = get_user_keywords(user_data)

    # Create buttons to interact (e.g., go back, add more keywords, etc.)
    keyboard = [
        [InlineKeyboardButton("Add Keyword", callback_data="add_keyword")],
        [InlineKeyboardButton("Del Keyword", callback_data="del_keyword")],
        [InlineKeyboardButton("Back 🔙", callback_data="auto_reply")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send or edit the message with inline buttons
    if update.callback_query:
        await query.edit_message_text(response_text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        await update.message.reply_text(response_text, reply_markup=reply_markup, parse_mode="HTML")

async def stopword_command(update, context):
    """
    Command handler for /stopword <keyword>. Deletes a specific keyword for the user, including multi-word keywords.
    """
    user_id = str(update.message.from_user.id)  # user_id as string
    # Load user data
    data = load_user_data()
    user_data = data["users"].get(user_id, {})

    # Get the keyword from the command arguments, allowing multi-word keywords
    try:
        keyword_to_remove = ' '.join(context.args)  # Join all arguments to handle multi-word keywords
    except IndexError:
        await update.message.reply_text("Please specify the keyword you want to remove. Example: /stopword Good Morning")
        return

    # Check if the keyword exists in the user's data
    keywords = user_data.get("keywords", {})
    if keyword_to_remove in keywords:
        # Display animated deleting message
        message = await update.message.reply_text("<b>Deleting ▪▪</b>", parse_mode="HTML")
        await asyncio.sleep(0.2)
        await message.edit_text("<b>Deleting ▪▪▪▪</b>", parse_mode="HTML")
        await asyncio.sleep(0.2)
        await message.edit_text("<b>Deleting ▪▪▪▪▪▪</b>", parse_mode="HTML")
        await asyncio.sleep(0.4)

        # Remove the keyword
        del keywords[keyword_to_remove]

        # Save the updated user data
        save_user_data(data)

        # Send the final confirmation message
        await message.edit_text(f"<b>Deleted '{keyword_to_remove}' successfully ✅</b>", parse_mode="HTML")
    else:
        await update.message.reply_text(f"<b>Keyword '{keyword_to_remove}' not found in your list ❌</b>", parse_mode="HTML")


async def autoreply_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = str(query.from_user.id).strip()
    
    # Load user data
    data = load_user_data()
    user_data = data["users"].get(user_id, {})
    
    # Authorization check
    if not await is_authorized(user_id):
        await query.edit_message_text("*You are not allowed to use this feature ❌*", parse_mode="Markdown")
        return

    # Handle different callback data for match options and auto-reply toggle
    if query.data == "set_exact":
        user_data["match_option"] = "exact"
    elif query.data == "set_partial":
        user_data["match_option"] = "partial"
    elif query.data == "set_case_insensitive":
        user_data["match_option"] = "case_insensitive"
    elif query.data == "toggle_auto_reply":
        user_data = data["users"].get(user_id)  # Ensure you fetch the user data correctly

        keywords = user_data.get("keywords", {})
        if not keywords:
            await query.answer("No keywords have been set for you ❌\n Please add at least one word\n (/setword Message | Response)", show_alert=True)
            return
        # Check if "forwarding_on" is false
        if user_data.get("forwarding_on", False):
            await query.answer("Auto-reply cannot be toggled while forwarding is active ❌", show_alert=True)
        else:
            # Toggle auto-reply status
            user_data["auto_reply_status"] = not user_data.get("auto_reply_status", False)
          
            # Save the updated user data back to the JSON file
            save_user_data(data)

            # Send a message to the user indicating the new auto-reply status
            await query.answer(f"Auto-reply is now {'enabled' if user_data['auto_reply_status'] else 'disabled'} ✅", show_alert=True)

            # If auto-reply is enabled, start the Telethon client
            if user_data["auto_reply_status"]:
                await start_telethon_client(user_id, context)  
            else:
                await stop_telethon_client(user_id)

        
    else:
        await all_callback(update, context)
        return

    # Save updated user data after all changes
    save_user_data(data)

    # Get the updated settings to display
    match_option = user_data["match_option"]
    auto_reply_status = "On" if user_data.get("auto_reply_status", False) else "Off"
    auto_reply_text = "Off" if user_data.get("auto_reply_status", False) else "On"

    # Update the keyboard and message text
    keyboard = [
        [InlineKeyboardButton(f"Exact Match {'✅' if match_option == 'exact' else ''}", callback_data='set_exact')],
        [InlineKeyboardButton(f"Partial Match {'✅' if match_option == 'partial' else ''}", callback_data='set_partial')],
        [InlineKeyboardButton(f"Case Insensitive {'✅' if match_option == 'case_insensitive' else ''}", callback_data='set_case_insensitive')],
        [InlineKeyboardButton(f"Turn {auto_reply_text}", callback_data='toggle_auto_reply')],
        [InlineKeyboardButton("My Keywords", callback_data='words')],
        [InlineKeyboardButton("🔙", callback_data='back')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Edit the original message with the new settings
    await query.edit_message_text(
        f"Your Auto-reply settings\n\n*Match Option: {match_option}✅*\n*Mode: {auto_reply_status}✅*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )



# Inline callback handler for settings
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
        await query.edit_message_text("*Please Use:* \n`/add_group\n<group_link>\n<group_link2>`\n\n *to add a group or groups*", reply_markup=back_button(), parse_mode="Markdown")
    elif query.data == 'remove_group':
        await query.edit_message_text("Please use /del_group <group_link> to remove a group.", reply_markup=back_button())
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
        "   - Use <code>/mypost</code> to check the post you have added\n\n"
        
        "3. <code>/add_group &lt;group_link&gt;</code> - Adds a group to your forwarding list.\n"
        "   - Example: <code>/add_group https://t.me/mygroupusername</code> adds the group with link <code> https://t.me/mygroupusername</code> to your list for message forwarding.\n\n"
        
        "4. <code>/del_group &lt;group_id&gt https://t.me/mygroupusername;</code> - Removes a group from your forwarding list.\n"
        "   - Example: <code>/del_group  https://t.me/mygroupusername</code> removes the group with link <code>https://t.me/mygroupusernam</code>.\n\n"
        
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
        
        "💡 <b>Need more help?</b> Contact the <a href=\"tg://resolve?domain=devscottreal\">Admin</a> or refer to the tutorial"
    )

        await query.edit_message_text(text=help_text, parse_mode='HTML', reply_markup=back_button())

  
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
    application.add_handler(CommandHandler("add_group", add_group))
    application.add_handler(CommandHandler("del_group", del_group))
    application.add_handler(CommandHandler("setword", set_word))
    application.add_handler(CommandHandler("keywords", keywords_command))
    application.add_handler(CommandHandler("stopword", stopword_command))
    application.add_handler(CommandHandler("time", time))
    application.add_handler(CommandHandler('post', post)) 
    application.add_handler(CommandHandler('mypost', my_posts)) 
    application.add_handler(CommandHandler("settings", settings))
    application.add_handler(CallbackQueryHandler(autoreply_callback))
    application.add_handler(CallbackQueryHandler(all_callback))
    
    # Start the bot
    application.run_polling()  

class CustomHandler(http.server.SimpleHTTPRequestHandler):  
    def do_GET(self):  
        self.send_response(200)  
        self.send_header("Content-type", "text/html")  
        self.end_headers()  

        # Write the custom message to the response body  
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

