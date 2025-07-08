import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telethon.sync import TelegramClient
from telethon import TelegramClient, events, functions
from telethon.sessions import StringSession
from dotenv import load_dotenv
from telethon.errors import SessionPasswordNeededError, PeerFloodError, UserPrivacyRestrictedError, UserIsBlockedError
from scraper import *
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty, Chat, Channel
import math


import os
import json
from datetime import datetime, timedelta
import datetime
import time
import time as time_module
import asyncio
import requests
import http.server
import socketserver
import threading
import json
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from autoreply import set_word, keyword_settings, start_telethon_client, stop_telethon_client
from stats import *
from payment import *

from fastapi import FastAPI, Request, Form, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import re
import shutil

from starlette.middleware.sessions import SessionMiddleware

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
scheduler = AsyncIOScheduler()
ADMIN_IDS = os.getenv("ADMIN_IDS").split(',') 
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "spidertisesup")
WEBAPP = os.getenv("WEBAPP")
session_lock = asyncio.Lock()
############ FAST API SECTION ############

spider_app =  FastAPI()

spider_app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv('SECRET_KEY', os.urandom(24))
)



# Mount static files and templates
spider_app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@spider_app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_bot())

@spider_app.get("/")
async def ping():
    return {"message": "pong"}

@spider_app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user_id: str = "", first_name: str = ""):
    # Store in session for later use
    request.session['user_id'] = user_id
    request.session['first_name'] = first_name
    
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "user_id": user_id, 
        "first_name": first_name
    })

@spider_app.post("/submit-phone")
async def submit_phone(request: Request, phone: str = Form(...), user_id: str = Form(...)):
    """Handle phone number submission"""
    
    logger.info(f"Received phone: {phone}")
    logger.info(f"Received user_id: {user_id}")

    if not phone:
        logger.error("Error: Phone number is missing")
        return JSONResponse({'success': False, 'message': 'Phone number is required'})
    
    if not re.match(r'^\+[1-9]\d{1,14}$', phone):
        return JSONResponse({'success': False, 'message': 'Phone number must be in international format (e.g., +1234567890)'})
    
    # Load user data to get API credentials
    try:
        with open("config.json", "r") as f:
            data = json.load(f)
        
        logger.info(f"Config loaded successfully")

        user_data = data["users"].get(user_id, {})
        api_id = user_data.get("api_id")
        api_hash = user_data.get("api_hash")
        
        forwarding_on = user_data.get("forwarding_on", False)
        auto_reply_status = user_data.get("auto_reply_status", False)
        
        # Define message variable with a default value
        message = "You are already logged in"
        
        if forwarding_on and auto_reply_status:
            message = "You are already logged in with forwarding and auto-reply enabled"
        elif forwarding_on:
            message = "You are already logged in with forwarding enabled"
        elif auto_reply_status:
            message = "You are already logged in with auto-reply enabled"
                
        # Check if session exists
        session_file = f'{user_id}.session'
        if os.path.exists(session_file):
            # Verify if the session is valid
            async def check_session():
                client = TelegramClient(session_file, api_id, api_hash)
                await client.connect()
                
                if await client.is_user_authorized():
                    await client.disconnect()
                    return True
                
                await client.disconnect()
                return False
            
            is_authorized = await check_session()
            if is_authorized:
                # User already has a valid session
                return JSONResponse({
                    'success': True, 
                    'already_logged_in': True, 
                    'message': message,
                    'forwarding_on': forwarding_on,
                    'auto_reply_status': auto_reply_status
                })
        
        if not api_id or not api_hash:
            return JSONResponse({'success': False, 'message': 'API credentials not found. Please set them first.'})
        
        # Store in session for later use
        request.session['user_id'] = user_id
        request.session['phone'] = phone
        request.session['api_id'] = api_id
        request.session['api_hash'] = api_hash
        
        # Create a new Telethon client and send code request
        async def send_code():
            # Create sessions directory if it doesn't exist
            os.makedirs('sessions', exist_ok=True)
            
            client = TelegramClient(f'sessions/{user_id}.session', api_id, api_hash)
            await client.connect()
            
            # Send the code request
            sent_code = await client.send_code_request(phone)
            request.session['phone_code_hash'] = sent_code.phone_code_hash
            
            await client.disconnect()
            return True
        
        success = await send_code()
        if success:
            return JSONResponse({'success': True, 'phone': phone})
        else:
            return JSONResponse({'success': False, 'message': 'Failed to send verification code'})
        
    except Exception as e:
        logger.error(f"Error in submit-phone: {e}")
        return JSONResponse({'success': False, 'message': f'Error: {str(e)}'})

@spider_app.post("/submit-otp")
async def submit_otp(request: Request, otp: str = Form(...), phone: str = Form(...)):
    """Handle OTP submission"""
    
    if not otp or not phone:
        return JSONResponse({'success': False, 'message': 'OTP and phone are required'})
    
    user_id = request.session.get('user_id')
    api_id = request.session.get('api_id')
    api_hash = request.session.get('api_hash')
    phone_code_hash = request.session.get('phone_code_hash')
    
    if not all([user_id, api_id, api_hash, phone_code_hash]):
        return JSONResponse({'success': False, 'message': 'Session data missing. Please start over.'})
    
    async def verify_code():
        try:
            # Create a new Telethon client
            client = TelegramClient(f'sessions/{user_id}.session', api_id, api_hash)
            await client.connect()
            
            try:
                # Try to sign in with the code
                await client.sign_in(phone=phone, code=otp, phone_code_hash=phone_code_hash)
                await client.disconnect()
                
                # Copy the session file to the main directory
                import shutil
                source_path = f'sessions/{user_id}.session'
                target_path = f'{user_id}.session'
                shutil.copy2(source_path, target_path)
                
                return {'success': True, 'needs_2fa': False}
                
            except SessionPasswordNeededError:
                await client.disconnect()
                return {'success': True, 'needs_2fa': True}
                
        except Exception as e:
            logger.error(f"Error in verify_code: {e}")
            return {'success': False, 'message': str(e)}
    
    result = await verify_code()
    return JSONResponse(result)

@spider_app.post("/submit-2fa")
async def submit_2fa(request: Request, password: str = Form(...)):
    """Handle 2FA password submission"""
    
    if not password:
        return JSONResponse({'success': False, 'message': 'Password is required'})
    
    user_id = request.session.get('user_id')
    api_id = request.session.get('api_id')
    api_hash = request.session.get('api_hash')
    
    if not all([user_id, api_id, api_hash]):
        return JSONResponse({'success': False, 'message': 'Session data missing. Please start over.'})
    
    async def verify_2fa():
        try:
            # Create a new Telethon client
            client = TelegramClient(f'sessions/{user_id}.session', api_id, api_hash)
            await client.connect()
            
            # Sign in with 2FA password
            await client.sign_in(password=password)
            await client.disconnect()
            
            # Copy the session file to the main directory
            import shutil
            source_path = f'sessions/{user_id}.session'
            target_path = f'{user_id}.session'
            shutil.copy2(source_path, target_path)
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error in verify_2fa: {e}")
            return {'success': False, 'message': str(e)}
    
    result = await verify_2fa()
    return JSONResponse(result)

@spider_app.post("/save-api-credentials")
async def save_api_credentials(request: Request):
    """Handle API credentials submission"""
    try:
        data = await request.json()
        api_id = data.get('api_id')
        api_hash = data.get('api_hash')
        user_id = data.get('user_id')
        
        if not all([api_id, api_hash, user_id]):
            return JSONResponse({'success': False, 'message': 'API ID, API Hash, and User ID are required'})
        
        # Load config file
        try:
            with open("config.json", "r") as f:
                config_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            config_data = {"users": {}}
        
        # Ensure users dict exists
        if "users" not in config_data:
            config_data["users"] = {}
        
        # Ensure user exists in config
        if user_id not in config_data["users"]:
            config_data["users"][user_id] = {}
        
        # Update API credentials
        config_data["users"][user_id]["api_id"] = api_id
        config_data["users"][user_id]["api_hash"] = api_hash
        
        # Save updated config
        with open("config.json", "w") as f:
            json.dump(config_data, f, indent=4)
        
        return JSONResponse({'success': True, 'message': 'API credentials saved successfully'})
        
    except Exception as e:
        logger.error(f"Error in save-api-credentials: {e}")
        return JSONResponse({'success': False, 'message': f'Error: {str(e)}'})

@spider_app.get("/success", response_class=HTMLResponse)
async def success(request: Request):
    """Show success page after login"""
    return templates.TemplateResponse("success.html", {"request": request})


def start_fastapi_app():
    """Start FastAPI app with Uvicorn"""
    try:
        port = int(os.environ.get('PORT', 8000))
        host = os.environ.get('HOST', '0.0.0.0')
        
        # SSL configuration for HTTPS
        ssl_keyfile = os.environ.get('SSL_KEYFILE')
        ssl_certfile = os.environ.get('SSL_CERTFILE')
        
        if ssl_keyfile and ssl_certfile:
            # HTTPS mode
            uvicorn.run(
                spider_app,
                host=host,
                port=port,
                ssl_keyfile=ssl_keyfile,
                ssl_certfile=ssl_certfile,
                reload=False,
                workers=1
            )
        else:
            # HTTP mode (for development or behind reverse proxy)
            uvicorn.run(
                spider_app,
                host=host,
                port=port,
                reload=False,
                workers=1
            )
    except Exception as e:
        logger.error(f"Error starting FastAPI app: {e}")





















###############
def load_config():
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            if "users" not in config:
                config["users"] = {}  
            return config
    except FileNotFoundError:

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
    if user_id in ADMIN_IDS:
        return True
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
    if user_id in ADMIN_IDS and user_id not in data["users"]:
        
        expiry = datetime.now() + timedelta(days=365)
        data["users"][user_id] = {
            "expiry_date": expiry.strftime('%Y-%m-%d %H:%M:%S'),
            "forwarding_on": False,
            "post_messages": [],
            "message_source": "mypost",
            "interval": "",
            "groups": [],
            "keywords": {},
            "match_option": "exact",
            "auto_reply_status": False,
            "responder_option": "PM"
        }
        save_user_data(data)
        logger.info(f"Added automatic subscription for admin {user_id}")
    if user_id in data["users"]:
        expiry_date = data["users"][user_id]["expiry_date"]
        try:

            expiry_datetime = datetime.strptime(expiry_date, '%Y-%m-%d %H:%M:%S')
            time_left = (expiry_datetime - datetime.now()).days
            formatted_expiry = expiry_datetime.strftime('%Y-%m-%d %H:%M:%S')  
            logger.info(f"User {user_id} subscription expires on {formatted_expiry}")
        except ValueError as e:
            logger.error(f"Date parsing error: {e}")
            await update.message.reply_text("Oops! 😅 Something went wrong with your subscription. Please reach out to our admin for help! 🙏")
            return

        if time_left >= 0:
            keyboard = [
                [InlineKeyboardButton("𝗛𝗘𝗟𝗣 𝗚𝗨𝗜𝗗𝗘 ❕", callback_data='help')],
                [InlineKeyboardButton("𝗔𝗨𝗧𝗢 𝗥𝗘𝗦𝗣𝗢𝗡𝗗𝗘𝗥 𝗚𝗨𝗜𝗗𝗘❕", url='https://telegra.ph/AUTO-RESPONDER-GUIDE-11-11')],
                [InlineKeyboardButton("𝗔𝗣𝗜 𝗔𝗡𝗗 𝗛𝗔𝗦𝗛 𝗜𝗗 🎥", url='https://youtu.be/8naENmP3rg4?si=LVxsTXSSI864t6Kv')],
                [InlineKeyboardButton("𝗟𝗢𝗚𝗜𝗡 𝗪𝗜𝗧𝗛 𝗧𝗘𝗟𝗘𝗚𝗥𝗔𝗠 🔑", callback_data='login')],
                [InlineKeyboardButton("𝗦𝗲𝘁𝘁𝗶𝗻𝗴𝘀 ⚙️", callback_data='settings')],
                [InlineKeyboardButton("𝗔𝘂𝘁𝗼 𝗥𝗲𝗽𝗹𝘆 + 𝙰𝙽𝚃𝙸 𝚅𝙸𝙴𝚆 𝙾𝙽𝙲𝙴 ⚙️⚙️", callback_data='auto_reply')],
                [InlineKeyboardButton("𝗦𝘁𝒂𝘁𝘀 📈", callback_data='refresh_stats')],
            ]          
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(  
                "===================================\n"  
                "       👋 𝐖𝐞𝐥𝐜𝐨𝐦𝐞 𝐭𝐨\n"  
                "     <b>Spidertise 𝔸𝕌𝕋𝕆 𝔽𝕆ℝ𝕎𝔸ℝ𝔻𝔼ℝ 𝔹𝕠𝕥</b>\n"  
                "---------------------------------------------\n"  
                " 𝒀𝒐𝒖𝒓 𝒔𝒖𝒃𝒔𝒄𝒓𝒊𝒑𝒕𝒊𝒐𝒏 𝒊𝒔 𝒂𝒄𝒕𝒊𝒗𝒆 𝒖𝒏𝒕𝒊𝒍:\n"  
                f"       <b>{formatted_expiry}</b> 📅\n"  
                "===================================",  
                reply_markup=reply_markup,  
                parse_mode="HTML"              )  
        else:

            await update.message.reply_text(
                f"Uh oh! 😕 Your subscription has ended. Please contact our <a href=\"tg://resolve?domain={ADMIN_USERNAME}\">friendly admin</a> to renew! ✨",
                parse_mode="HTML"
            )

            data["users"][user_id]["forwarding_on"] = False
            save_user_data(data)
    else:

        logger.info(f"User {user_id} is not authorized or subscription has expired.")
        await update.message.reply_text(
            f"Hey! 👋 Looks like you don't have an active subscription yet. Reach out to our <a href=\"tg://resolve?domain={ADMIN_USERNAME}\">awesome admin</a> to get started! ✨",
            parse_mode="HTML"
        )

        if user_id in data["users"]:
            data["users"][user_id]["forwarding_on"] = False
        save_user_data(data)


async def set_delay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    
    if not await is_authorized(user_id):
        await update.message.reply_text(
            f"🔒 <b>Access Restricted</b>\n\n❌ No active subscription found\n✨ Please contact <a href=\"tg://resolve?domain={ADMIN_USERNAME}\">Admin</a> for access", 
            parse_mode="HTML"
        )
        return
    
    if not context.args:
        data = load_user_data()
        user_data = data["users"].get(user_id, {})
        current_delay = user_data.get("group_delay", 0)
        
        await update.message.reply_text(
            f"⏱️ *Current Group Delay Settings*\n\n"
            f"📊 *Current Delay:* `{current_delay} seconds`\n\n"
            f"📝 *Usage:* `/delay <seconds>`\n"
            f"💡 *Example:* `/delay 10`\n\n"
            f"ℹ️ *Note:* This sets the delay between forwarding to each group",
            parse_mode="Markdown"
        )
        return
    
    try:
        delay_seconds = int(context.args[0])
        if delay_seconds < 0:
            await update.message.reply_text("❌ Delay cannot be negative. Please enter a positive number.")
            return
        
        data = load_user_data()
        if user_id not in data["users"]:
            data["users"][user_id] = {}
        
        data["users"][user_id]["group_delay"] = delay_seconds
        save_user_data(data)
        
        await update.message.reply_text(
            f"✅ *Group Delay Updated Successfully*\n\n"
            f"⏱️ *New Delay:* `{delay_seconds} seconds`\n"
            f"📤 *Effect:* {delay_seconds} second delay between each group when forwarding\n\n"
            f"💡 *Tip:* Use `/delay 0` to disable delay",
            parse_mode="Markdown"
        )
        
    except ValueError:
        await update.message.reply_text(
            "❌ *Invalid Input*\n\n"
            "Please enter a valid number of seconds.\n"
            "Example: `/delay 10`",
            parse_mode="Markdown"
        )

async def list_groups_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    
    if not await is_authorized(user_id):
        await update.message.reply_text(
            f"🔒 <b>Access Restricted</b>\n\n❌ No active subscription found\n✨ Please contact <a href=\"tg://resolve?domain={ADMIN_USERNAME}\">Admin</a> for access", 
            parse_mode="HTML"
        )
        return
    
    # Check if forwarding or auto-reply is enabled
    data = load_user_data()
    user_data = data["users"].get(user_id, {})
    
    if user_data.get("forwarding_on", False):
        await update.message.reply_text(
            "⚠️ *Cannot List Groups*\n\n"
            "❌ Forwarding is currently enabled\n"
            "🔄 Please disable forwarding first using `/off`",
            parse_mode="Markdown"
        )
        return
    
    if user_data.get("auto_reply_status", False):
        await update.message.reply_text(
            "⚠️ *Cannot List Groups*\n\n"
            "❌ Auto-reply is currently enabled\n"
            "🔄 Please disable auto-reply first from settings",
            parse_mode="Markdown"
        )
        return
    
    # Check if user is logged in
    session_file = f'{user_id}.session'
    if not os.path.exists(session_file):
        await update.message.reply_text(
            "🔐 *Not Logged In*\n\n"
            "❌ Please log in first using `/login +1234567890`",
            parse_mode="Markdown"
        )
        return
    
    api_id = user_data.get("api_id")
    api_hash = user_data.get("api_hash")
    
    if not api_id or not api_hash:
        await update.message.reply_text(
            "⚠️ *API Credentials Missing*\n\n"
            "❌ Please set your API credentials first\n"
            "🔑 Use `/api_id` and `/hash` commands",
            parse_mode="Markdown"
        )
        return
    
    try:
        processing_msg = await update.message.reply_text(
            "🔄 *Fetching Your Groups...*\n\n"
            "⏳ Please wait while we retrieve your group list",
            parse_mode="Markdown"
        )
        
        async with TelegramClient(session_file, api_id, api_hash) as client:
            if not await client.is_user_authorized():
                await processing_msg.edit_text(
                    "❌ *Session Expired*\n\n"
                    "🔐 Please log in again using `/login +1234567890`",
                    parse_mode="Markdown"
                )
                return
            
            # Get all dialogs (chats)
            dialogs = await client.get_dialogs()
            
            # Filter only groups and channels
            groups = []
            for dialog in dialogs:
                entity = dialog.entity
                if isinstance(entity, (Chat, Channel)):
                    if hasattr(entity, 'megagroup') and entity.megagroup:
                        # Supergroup
                        groups.append({
                            'id': entity.id,
                            'title': entity.title,
                            'type': 'Supergroup',
                            'entity': entity
                        })
                    elif isinstance(entity, Channel):
                        # Channel
                        groups.append({
                            'id': entity.id,
                            'title': entity.title,
                            'type': 'Channel',
                            'entity': entity
                        })
                    elif isinstance(entity, Chat):
                        # Regular group
                        groups.append({
                            'id': entity.id,
                            'title': entity.title,
                            'type': 'Group',
                            'entity': entity
                        })
            
            if not groups:
                await processing_msg.edit_text(
                    "📭 *No Groups Found*\n\n"
                    "❌ You're not a member of any groups or channels",
                    parse_mode="Markdown"
                )
                return
            
            # Store groups in user data for pagination
            context.user_data['user_groups_list'] = groups
            context.user_data['current_page'] = 0
            
            await show_groups_page(processing_msg, context, 0)
            
    except Exception as e:
        await update.message.reply_text(
            f"❌ *Error Fetching Groups*\n\n"
            f"🔴 Error: `{str(e)}`",
            parse_mode="Markdown"
        )

async def show_groups_page(message, context, page):
    groups = context.user_data.get('user_groups_list', [])
    groups_per_page = 20
    total_pages = math.ceil(len(groups) / groups_per_page)
    
    start_idx = page * groups_per_page
    end_idx = start_idx + groups_per_page
    page_groups = groups[start_idx:end_idx]
    
    keyboard = []
    
    # Add group buttons (2 per row)
    for i in range(0, len(page_groups), 2):
        row = []
        for j in range(2):
            if i + j < len(page_groups):
                group = page_groups[i + j]
                # Truncate title if too long
                title = group['title'][:25] + "..." if len(group['title']) > 25 else group['title']
                row.append(InlineKeyboardButton(
                    f"{group['type'][:1]} {title}", 
                    callback_data=f"group_info_{start_idx + i + j}"
                ))
        keyboard.append(row)
    
    # Add navigation buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"groups_page_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"groups_page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("🔗 List All Links", callback_data="list_all_links")])
    # Add back button
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"👥 *Your Groups & Channels*\n\n"
        f"📊 *Total:* {len(groups)} groups/channels\n"
        f"📄 *Page:* {page + 1}/{total_pages}\n"
        f"📋 *Showing:* {start_idx + 1}-{min(end_idx, len(groups))}\n\n"
        f"💡 *Click on any group to view details*"
    )
    
    try:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    except:
        await message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

    
async def list_all_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    data = load_user_data()
    user_data = data["users"].get(user_id, {})
    
    if user_data.get("forwarding_on", False):
        await query.edit_message_text(
            "⚠️ *Cannot List Links*\n\n"
            "❌ Forwarding is currently enabled\n"
            "🔄 Please disable forwarding first using `/off`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_groups")]
            ])
        )
        return
    
    if user_data.get("auto_reply_status", False):
        await query.edit_message_text(
            "⚠️ *Cannot List Links*\n\n"
            "❌ Auto-reply is currently enabled\n"
            "🔄 Please disable auto-reply first from settings",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_groups")]
            ])
        )
        return

    try:
        await query.edit_message_text(
            "🔄 *Fetching All Group Links...*\n\n"
            "⏳ Please wait while we retrieve all links",
            parse_mode="Markdown"
        )
        
        groups = context.user_data.get('user_groups_list', [])
        session_file = f'{user_id}.session'
        
        async with TelegramClient(session_file, user_data["api_id"], user_data["api_hash"]) as client:
            group_links = []
            
            for group in groups:
                entity = group['entity']
                
                try:
                    # Get full entity info
                    full_entity = await client.get_entity(entity.id)
                    
                    # Check if user is admin for private groups
                    is_admin = False
                    try:
                        permissions = await client.get_permissions(entity.id, query.from_user.id)
                        is_admin = permissions.is_admin or permissions.is_creator
                    except:
                        is_admin = False
                    
                    # Format the correct group ID
                    if isinstance(full_entity, Channel):
                        if hasattr(full_entity, 'megagroup') and full_entity.megagroup:
                            # Supergroup - add -100 prefix
                            formatted_id = f"-100{full_entity.id}"
                        else:
                            # Channel - add -100 prefix
                            formatted_id = f"-100{full_entity.id}"
                    else:
                        # Regular group - use negative ID
                        formatted_id = f"-{full_entity.id}"

                    group_link = formatted_id  # Default to ID
                    link_type = "ID"

                    # Check if public group/channel
                    if hasattr(full_entity, 'username') and full_entity.username:
                        group_link = f"https://t.me/{full_entity.username}"
                        link_type = "Public"
                    else:
                        # Try to get invite link if admin
                        if is_admin:
                            try:
                                from telethon.tl.functions.messages import ExportChatInviteRequest
                                invite_result = await client(ExportChatInviteRequest(full_entity.id))
                                if hasattr(invite_result, 'link'):
                                    group_link = invite_result.link
                                    link_type = "Invite"
                            except:
                                pass  # Keep the ID as fallback
                    
                    group_links.append({
                        'title': entity.title,
                        'link': group_link,
                        'type': group['type'],
                        'link_type': link_type
                    })
                    
                except Exception as e:
                    # If error, just add the ID
                    if isinstance(entity, Channel):
                        formatted_id = f"-100{entity.id}"
                    else:
                        formatted_id = f"-{entity.id}"
                    
                    group_links.append({
                        'title': entity.title,
                        'link': formatted_id,
                        'type': group['type'],
                        'link_type': "ID"
                    })
            
            # Store links for pagination
            context.user_data['group_links'] = group_links
            context.user_data['links_page'] = 0
            
            await show_links_page(query, context, 0)
            
    except Exception as e:
        await query.edit_message_text(
            f"❌ *Error Fetching Links*\n\n"
            f"🔴 Error: `{str(e)}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_groups")]
            ])
        )

async def show_links_page(query, context, page):
    group_links = context.user_data.get('group_links', [])
    links_per_page = 50  # Increased to 50 per page
    total_pages = math.ceil(len(group_links) / links_per_page)
    
    start_idx = page * links_per_page
    end_idx = start_idx + links_per_page
    page_links = group_links[start_idx:end_idx]
    
    # Build the text
    text = (
        f"🔗 *All Group Links*\n\n"
        f"📊 *Total:* {len(group_links)} groups/channels\n"
        f"📄 *Page:* {page + 1}/{total_pages}\n"
        f"📋 *Showing:* {start_idx + 1}-{min(end_idx, len(group_links))}\n\n"
    )
    
    # Add all links in a code block
    links_text = ""
    for link_info in page_links:
        links_text += f"{link_info['link']}\n"
    
    # Remove the last newline and add to text
    if links_text:
        text += f"```\n{links_text.rstrip()}\n```"
    
    # Navigation buttons
    keyboard = []
    nav_buttons = []
    
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"links_page_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"links_page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Back button
    keyboard.append([InlineKeyboardButton("🔙 Back to Groups", callback_data="back_to_groups")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    except:
        await query.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")


async def show_group_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    data = load_user_data()
    user_data = data["users"].get(user_id, {})
    
    if user_data.get("forwarding_on", False):
        await query.edit_message_text(
            "⚠️ *Cannot View Group Info*\n\n"
            "❌ Forwarding is currently enabled\n"
            "🔄 Please disable forwarding first using `/off`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_groups")]
            ])
        )
        return
    
    if user_data.get("auto_reply_status", False):
        await query.edit_message_text(
            "⚠️ *Cannot View Group Info*\n\n"
            "❌ Auto-reply is currently enabled\n"
            "🔄 Please disable auto-reply first from settings",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_groups")]
            ])
        )
        return

    try:
        group_idx = int(query.data.split("_")[-1])
        groups = context.user_data.get('user_groups_list', [])
        
        if group_idx >= len(groups):
            await query.edit_message_text("❌ Group not found")
            return
        
        group = groups[group_idx]
        entity = group['entity']
        
        # Get additional info
        session_file = f'{user_id}.session'
        
        async with TelegramClient(session_file, user_data["api_id"], user_data["api_hash"]) as client:
            try:
                # Get full entity info
                full_entity = await client.get_entity(entity.id)
                
                # Check if user is admin
                is_admin = False
                try:
                    permissions = await client.get_permissions(entity.id, query.from_user.id)
                    is_admin = permissions.is_admin or permissions.is_creator
                except:
                    is_admin = False
                
                # Get member count
                try:
                    if hasattr(full_entity, 'participants_count'):
                        member_count = full_entity.participants_count
                    else:
                        member_count = "Unknown"
                except:
                    member_count = "Unknown"
                
                # Format the correct group ID (with -100 prefix for supergroups/channels)
                if isinstance(full_entity, Channel):
                    if hasattr(full_entity, 'megagroup') and full_entity.megagroup:
                        # Supergroup - add -100 prefix
                        formatted_id = f"-100{full_entity.id}"
                    else:
                        # Channel - add -100 prefix
                        formatted_id = f"-100{full_entity.id}"
                else:
                    # Regular group - use negative ID
                    formatted_id = f"-{full_entity.id}"

                group_link = "Not Available"
                privacy = "Private"

                # Determine if public or private
                if hasattr(full_entity, 'username') and full_entity.username:
                    privacy = "Public"
                    group_link = f"https://t.me/{full_entity.username}"
                else:
                    if is_admin:
                        try:
                            from telethon.tl.functions.messages import ExportChatInviteRequest
                            invite_result = await client(ExportChatInviteRequest(full_entity.id))
                            if hasattr(invite_result, 'link'):
                                group_link = invite_result.link
                                privacy = "Private (Invite Link)"
                            else:
                                group_link = "Private Group (Admin access required)"
                        except Exception as e:
                            print(f"Error getting invite link: {e}")
                            group_link = "Private Group (Cannot generate invite link)"
                    else:
                        group_link = "Private Group (Admin access required)"
                
                # Format group info
                info_text = (
                    f"📋 *Group Information*\n\n"
                    f"🏷️ *Name:* `{entity.title}`\n"
                    f"🆔 *ID:* `{formatted_id}`\n"
                    f"📊 *Type:* {group['type']}\n"
                    f"👥 *Members:* {member_count}\n"
                    f"🔒 *Privacy:* {privacy}\n"
                    f"👑 *You are Admin:* {'Yes ✅' if is_admin else 'No ❌'}\n\n"
                    f"🔗 *Link:*\n`{group_link}`"
                )
                
                keyboard = [
                    [InlineKeyboardButton("🔙 Back to List", callback_data="back_to_groups")],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="back")]
                ]
                
                await query.edit_message_text(
                    info_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
                
            except Exception as e:
                await query.edit_message_text(
                    f"❌ *Error Getting Group Info*\n\n"
                    f"🔴 Error: `{str(e)}`",
                    parse_mode="Markdown"
                )
                
    except Exception as e:
        await query.edit_message_text(
            f"❌ Error: {str(e)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_groups")]
            ])
        )

async def post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)  

    if await is_authorized(user_id):
        if context.args:
            post_message = ' '.join(context.args)  
            
            
            post_message = post_message.replace('\\n', '\n')

            data = load_user_data()

            if user_id in data["users"]:
                try:

                    if "post_messages" not in data["users"][user_id]:
                        data["users"][user_id]["post_messages"] = []

                    data["users"][user_id]["post_messages"].append(post_message)
                    save_user_data(data)  

                    post_index = len(data["users"][user_id]["post_messages"])  
                    await update.message.reply_text(f"Awesome! 🎉 Your message has been saved with index number {post_index} ✅\n\nWant to add more? Just use\n`/post your message here` 📝\n\nPreview of your message:\n`{post_message}`", parse_mode="Markdown")
                except Exception as e:
                    await update.message.reply_text(f"Oops! 😅 Couldn't save your message: {e}", parse_mode=None)
            else:
                await update.message.reply_text("Hmm... 🤔 I can't find you in the system.")
        else:
            await update.message.reply_text("Here's how to use it: `/post your message or text link here` 📝\n\nYou can use:\n- \\n for new lines\n- *text* for bold\n- `text` for code format", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"Hey! 👋 You'll need an active subscription first. Contact our <a href=\"tg://resolve?domain={ADMIN_USERNAME}\">friendly admin</a> to get started! ✨", parse_mode="HTML")
        
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

                        await update.message.reply_text(f"All done! 🧹 I've cleared all {len(deleted_posts)} posts for you ✨", parse_mode="Markdown")
                    except Exception as e:
                        await update.message.reply_text(f"Oops! 😅 Something went wrong:\n<pre> {e}</pre>", parse_mode="HTML")
                else:
                    await update.message.reply_text("Hmm... 🤔 I couldn't find any posts to delete.")

            else:

                post_message = ' '.join(context.args)

                data = load_user_data()

                if user_id in data["users"] and "post_messages" in data["users"][user_id]:
                    try:
                        post_messages = data["users"][user_id]["post_messages"]

                        if post_message in post_messages:

                            post_messages.remove(post_message)
                            save_user_data(data)
                            await update.message.reply_text(f"Got it! 🗑️ I've deleted this post:\n `{post_message}`", parse_mode="Markdown")
                        else:

                            try:
                                post_index = int(post_message) - 1
                                if 0 <= post_index < len(post_messages):
                                    deleted_post = post_messages.pop(post_index)
                                    save_user_data(data)
                                    await update.message.reply_text(f"Done! 🗑️ I've deleted this post:\n `{deleted_post}`", parse_mode="Markdown")
                                else:
                                    await update.message.reply_text("Oops! 🤔 That post index doesn't exist.")
                            except ValueError:
                                await update.message.reply_text("Hey! 👋 Please use either the post number or the exact message text to delete a post.")
                    except Exception as e:
                        await update.message.reply_text(f"Uh oh! 😅 Something went wrong: {e}")
                else:
                    await update.message.reply_text("Hmm... 🤔 I couldn't find any posts to delete.")
        else:
            await update.message.reply_text("Here's how to use it: `/delpost post number or message` 📝", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"Hey! 👋 You'll need an active subscription first. Contact our <a href=\"tg://resolve?domain={ADMIN_USERNAME}\">friendly admin</a> to get started! ✨", parse_mode="HTML")

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
                "message_source": "mypost",
                "interval": "",
                "groups": [],
                "keywords": {},
                "match_option": "exact", 
                "auto_reply_status": False,
                "forwarding_on": False,
                "responder_option": "PM"
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

                await stop_telethon_client(user_id)

                session_file = f'{user_id}.session'
                if os.path.exists(session_file):
                    os.remove(session_file)
                    print(f"Deleted session file: {session_file}")

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
            await update.message.reply_text("🔑 *API ID successfully saved!* ✅\n\n_Your API ID has been securely stored in our system._", parse_mode="Markdown")
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
            await update.message.reply_text("🔑 *API HASH successfully saved!* ✅\n\n_Your API HASH has been securely stored in our system._", parse_mode="Markdown")
        else:
            await update.message.reply_text("Usage:\n `/hash <API_HASH>`", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"<b>No Active Subscription, Please contact</b> <a href=\"tg://resolve?domain={ADMIN_USERNAME}\">Admin</a>", parse_mode="HTML")

def get_otp_keyboard() -> InlineKeyboardMarkup:
    keys = [
        [InlineKeyboardButton(str(i), callback_data=f"otp_{i}") for i in range(1, 4)],
        [InlineKeyboardButton(str(i), callback_data=f"otp_{i}") for i in range(4, 7)],
        [InlineKeyboardButton(str(i), callback_data=f"otp_{i}") for i in range(7, 10)],
        [InlineKeyboardButton("0", callback_data="otp_0"),
         InlineKeyboardButton("↵ Enter", callback_data="otp_submit"),
         InlineKeyboardButton("⌫", callback_data="otp_delete")]
    ]
    return InlineKeyboardMarkup(keys)

async def otp_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    otp_input = context.user_data.get('otp_input', "")

    if query.data.startswith("otp_"):
        action = query.data.split("_")[1]

        if action == "submit":
            if otp_input:
                await query.edit_message_text(
                    f"🔄 *Processing OTP Code:* `{otp_input}`\n\n🚀 *Please wait...*",
                    parse_mode="Markdown"
                )
                await asyncio.sleep(1) 
                await query.message.delete()
                await otp(update, context)
            else:
                await query.message.reply_text("⚠️ *Error:* No OTP code entered!\n\n_Please try again._", parse_mode="Markdown")
        elif action == "delete":
            otp_input = otp_input[:-1]
        else:
            otp_input += action

        context.user_data['otp_input'] = otp_input
        new_message_text = (
            "🔐 *Secure Login Verification*\n\n"
            "📱 OTP has been sent to your phone!\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "🔹 Use the keyboard below\n"
            "🔸 Or type `/otp 1 2 3 4 5`\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"📟 *Input OTP:* `{otp_input or '⌛ Waiting for input...'}`\n"
            "━━━━━━━━━━━━━━━━━━━"
        )
        if query.message.text != new_message_text:
            try:
                otp_message = await query.edit_message_text(
                    new_message_text,
                    parse_mode="Markdown",
                    reply_markup=get_otp_keyboard()
                )
                context.user_data['keyboard_message_id'] = otp_message.message_id

            except Exception as e:
                print(f"Error updating message: {e}")

def get_number_keyboard():
    """Generate inline keyboard for entering phone number."""
    buttons = [
        [InlineKeyboardButton(str(i), callback_data=f"num_{i}") for i in range(1, 4)],
        [InlineKeyboardButton(str(i), callback_data=f"num_{i}") for i in range(4, 7)],
        [InlineKeyboardButton(str(i), callback_data=f"num_{i}") for i in range(7, 10)],
        [
            
            InlineKeyboardButton("✅ Submit", callback_data="num_submit"),
            InlineKeyboardButton("0", callback_data="num_0"),
            InlineKeyboardButton("⌫", callback_data="num_delete")
        ],
        [
            InlineKeyboardButton("Clear 🗑", callback_data="num_clear"),
            InlineKeyboardButton("Back 🔙", callback_data="back")
        ]
    ]
    return InlineKeyboardMarkup(buttons)

async def login_kbd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles phone number input via inline keyboard."""
    query = update.callback_query
    await query.answer()

    number_input = context.user_data.get("number_input", "")

    if query.data.startswith("num_"):
        action = query.data.split("_")[1]

        if action == "submit":

            full_number = f"+{number_input}"  
            if full_number.startswith("+") and full_number[1:].isdigit():

                context.args = [full_number]
                await query.edit_message_text("🔄 *Processing your login...*", parse_mode="Markdown")
                await asyncio.sleep(1) 
                await login(update, context)  
            else:
                await query.edit_message_text(
                    "❌ *Invalid phone number format.*\n\n"
                    "Make sure it starts with `+` and only contains digits.",
                    parse_mode="Markdown",
                    reply_markup=get_number_keyboard()
                )
            return
        elif action == "delete":
            number_input = number_input[:-1] 
        elif action == "clear":
            number_input = "" 
        else:
            number_input += action  
    context.user_data["number_input"] = number_input

    display_number = f"+{number_input}" if number_input else "+[waiting for input]"
    await query.edit_message_text(
        f"🌟 *SECURE LOGIN PORTAL*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📱 Please enter your phone number:\n"
        f"🔹 International format included (+)\n"
        f"🔸 Include country code\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📟 *Current Input:*\n"
        f"`{display_number}`\n"
        f"━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
        reply_markup=get_number_keyboard()
    )
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    user_id = str(update.message.from_user.id) if update.message else str(update.callback_query.from_user.id)

    reply = update.message.reply_text if update.message else update.callback_query.edit_message_text

    phone_number = context.args[0] if context.args else f"+{context.user_data.get('number_input', '')}"
    if not phone_number or not phone_number.startswith("+") or not phone_number[1:].isdigit():
        await reply(
            "ℹ️ Please provide a valid phone number in international format.\n\n"
            "_Example: /login +1234567890_",
            parse_mode="Markdown"
        )
        return 

    if await is_authorized(user_id):
        data = load_user_data()
        user_data = data["users"].get(user_id, {})

        api_id = user_data.get("api_id")
        api_hash = user_data.get("api_hash")

        if api_id and api_hash:
            client = TelegramClient(f'{user_id}.session', api_id, api_hash)
            await client.connect()

            if not await client.is_user_authorized():
                try:
                    sent_code = await client.send_code_request(phone_number)
                    context.user_data['phone_number'] = phone_number
                    context.user_data['phone_code_hash'] = sent_code.phone_code_hash  
                    context.user_data['otp_input'] = "" 
                    otp_message = await reply(
                        "🔐 *Secure Login Verification*\n\n"
                        "📱 OTP has been sent to your phone!\n"
                        "━━━━━━━━━━━━━━━━━━━\n"
                        "🔹 Use the keyboard below\n"
                        "🔸 Or type `/otp 1 2 3 4 5`\n"
                        "━━━━━━━━━━━━━━━━━━━\n"
                        "📟 *Input OTP:* `⌛ Waiting for input...`\n"
                        "━━━━━━━━━━━━━━━━━━━",
                        parse_mode="Markdown",
                        reply_markup=get_otp_keyboard()
                    )
                    context.user_data['keyboard_message_id'] = otp_message.message_id
                except Exception as e:
                    await reply(f"❌ *Error:* Failed to send OTP!\n\n_Details: {e}_", parse_mode="Markdown")
            else:
                await reply("✅ *You are already logged in!*", parse_mode="Markdown")
                await client.disconnect()
        else:
            await reply(
                "⚠️ *Configuration Missing*\n\n"
                "API credentials not found!\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "🔸 Set API ID with `/api_id`\n"
                "🔹 Set Hash with `/hash`\n"
                "━━━━━━━━━━━━━━━━━━━",
                parse_mode="Markdown"
            )
    else:
        await reply(
            "⛔️ *Access Restricted*\n\n"
            f"📞 Please contact @{ADMIN_USERNAME}\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "❗️ No active subscription found\n"
            "━━━━━━━━━━━━━━━━━━━",
            parse_mode="Markdown"
        )
async def otp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:  
        user_id = str(update.message.from_user.id)
        otp_parts = context.args
        message = update.message
        try:
            await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
        except Exception as e:
            print(f"Error deleting user message: {e}")
    elif update.callback_query:  
        user_id = str(update.callback_query.from_user.id)
        otp_parts = context.user_data.get('otp_input', "")  
        message = update.callback_query.message
    else:
        return

    if 'keyboard_message_id' in context.user_data:
        try:
            await context.bot.delete_message(
                chat_id=message.chat_id,
                message_id=context.user_data['keyboard_message_id']
            )
            del context.user_data['keyboard_message_id']  
        except Exception as e:
            print(f"Error deleting keyboard message: {e}")

    if otp_parts:
        otp_code = ''.join(otp_parts) if isinstance(otp_parts, list) else otp_parts
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
                            await message.reply_text(
                                "🎉 *Success! Login Complete* ✅\n\n"
                                "📱 Your account has been successfully authenticated\n"
                                "━━━━━━━━━━━━━━━━━━━\n"
                                "🔐 You can now use all available features\n"
                                "━━━━━━━━━━━━━━━━━━━",
                                parse_mode="Markdown",
                                reply_markup=InlineKeyboardMarkup([
                                    [InlineKeyboardButton("🏠 Home", callback_data="back")]
                                ])
                            )
                        except SessionPasswordNeededError:
                            await message.reply_text(
                                "🔐 *Two-Factor Authentication Required*\n\n"
                                "📋 Please enter your 2FA password using:\n"
                                "━━━━━━━━━━━━━━━━━━━\n"
                                "🔑 `/2fa input password`\n"
                                "━━━━━━━━━━━━━━━━━━━",
                                parse_mode="Markdown",
                                reply_markup=InlineKeyboardMarkup([
                                    [InlineKeyboardButton("❌", callback_data="back")]
                                ])
                            )
                        except Exception as e:
                            await message.reply_text(
                                "❌ *Login Failed*\n\n"
                                f"⚠️ Error: `{str(e)}`\n"
                                "━━━━━━━━━━━━━━━━━━━\n"
                                "🔄 Please try again\n"
                                "━━━━━━━━━━━━━━━━━━━",
                                parse_mode="Markdown"
                            )
                    else:
                        await message.reply_text(
                            "✨ *Already Logged In*\n\n"
                            "📱 Your session is active and ready\n"
                            "━━━━━━━━━━━━━━━━━━━\n"
                            "✅ No additional authentication needed\n"
                            "━━━━━━━━━━━━━━━━━━━",
                            parse_mode="Markdown"
                        )                        
                        await client.disconnect()
                finally:
                    await client.disconnect()
            else:
                await message.reply_text("API ID and Hash not found. Set them with\n\n /api_id and /hash.")
        else:
            await message.reply_text("Phone number or phone_code_hash not found. Start the login process with\n\n /login <phone_number>.")
    else:
        await message.reply_text("Usage: `/otp 1 2 3 4 5`", parse_mode="Markdown")

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
                await update.message.reply_text(
                    "✨ *2FA Authentication Successful*\n\n"
                    "🔐 Password verified correctly\n"
                    "━━━━━━━━━━━━━━━━━━━\n"
                    "✅ You're now securely logged in\n"
                    "━━━━━━━━━━━━━━━━━━━",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Home", callback_data="back")]])
                )
            except Exception as e:
                await update.message.reply_text(
                    "❌ *2FA Authentication Failed*\n\n"
                    f"⚠️ Error: `{str(e)}`\n"
                    "━━━━━━━━━━━━━━━━━━━\n"
                    "🔄 Please try again with correct password\n"
                    "━━━━━━━━━━━━━━━━━━━",
                    parse_mode="Markdown"
                )            
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

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:  

    data = load_user_data()  
    users = data.get("users", {})  
    user_id = str(update.message.from_user.id)  

    if user_id not in ADMIN_IDS:  
        await update.message.reply_text("❌ *Unauthorized access!* You do not have permission to use this command.")  
        return  

    if not users:  
        await update.message.reply_text("❌ No users found in the database.")  
        return  

    message = "*🌟 User List with Expiry Dates 🌟*\n"  
    message += "════════════════════════════════\n"  

    for user_id, user_info in users.items():  
        try:  
            user_chat = await context.bot.get_chat(user_id)  
            first_name = user_chat.first_name  
        except Exception as e:  
            first_name = "Unknown"  
            print(f"Error fetching user {user_id}: {e}")  

        expiry_date = user_info.get("expiry_date", "Not Set")  

        message += (  
            "╭───────────────────╮\n"  
            f"│ 👤 *User*: {first_name:<30} \n"     
            f"│ 🆔 *ID*: `{user_id}`        \n"   
            f"│ 📅 *Expiry Date*: `{expiry_date}`\n"  
            "╰───────────────────╯\n"  
        )  

    message += "════════════════════════════════\n"  
    message += "*✨ Thank you for using our service! ✨*"  

    await update.message.reply_text(message, parse_mode="Markdown")

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
            # Check if the group link is a valid Telegram link or a chat ID  
            if group_link.startswith("https://t.me/") or (group_link.startswith('-') and group_link[1:].isdigit()):  
                if group_link and group_link not in user_groups:  
                    user_groups.append(group_link)  
                    added_groups.append(group_link)  
                elif group_link in user_groups:  
                    already_in_list.append(group_link)  
            else:  
                await update.message.reply_text(f"Link '{group_link}' is not a valid Telegram link or chat ID.")  

        user_data["groups"] = user_groups  
        config_data["users"][user_id] = user_data  

        with open("config.json", "w") as f:  
            json.dump(config_data, f, indent=4)  

        if added_groups:  
            added_groups_response = "*🎉 Groups Added for Forwarding:*\n"  
            added_groups_response += "╭───────┬───────────────╮\n"  
            added_groups_response += "│ *No*  │ *Group Link*   \n"  
            added_groups_response += "├───────┼───────────────┤\n"  

            for index, group in enumerate(added_groups, start=1):  
                added_groups_response += f"│ `{index}` │ `{group}`\n"  

            added_groups_response += "╰───────┴───────────────╯\n"  
            added_groups_response += "*✨ Thank you for participating! ✨*"  

            await update.message.reply_text(added_groups_response, parse_mode="Markdown")  

        if already_in_list:  
            already_in_list_response = "*⚠️ Groups Already in Your Forwarding List:*\n"  
            already_in_list_response += "╭───────┬───────────────────────╮\n"  
            already_in_list_response += "│ *No*  │ *Group Link*         │\n"  
            already_in_list_response += "├───────┼───────────────────────┤\n"  

            for index, group in enumerate(already_in_list, start=1):  
                already_in_list_response += f"│ `{index}` │ `{group}`\n"  

            already_in_list_response += "╰───────┴───────────────────────╯\n"  
            already_in_list_response += "*💡 No changes were made to these groups.*"  

            await update.message.reply_text(already_in_list_response, parse_mode="Markdown")  

        if not added_groups and not already_in_list:  
            await update.message.reply_text("Invalid Format❗\nUsage:\n`/addgroup\n<link1>\n<link2>`", parse_mode="Markdown")  

    else:  
        await update.message.reply_text(  
            f"<b>No Active Subscription, Please contact</b> <a href=\"tg://resolve?domain={ADMIN_USERNAME}\">Admin</a>",   
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
            if removed_groups or not_found_groups:  
                response += "*📋 Group Removal Summary:*\n"  
                response += "╭───────┬───────────────────╮\n"
                response += "│ *Status* │ *Group ID*     │\n"
                response += "├───────┼───────────────────┤\n"

                if removed_groups:
                    for group_id in removed_groups:
                        response += f"│ *Removed* │ `{group_id}`  │\n" 

                if not_found_groups:
                    for group_id in not_found_groups:
                        response += f"│ *Not Found* │ `{group_id}`│\n"

                response += "╰───────┴───────────────────╯\n"  
            else:  
                response = "*✅ No groups were removed.*"  

            await update.message.reply_text(response, parse_mode="Markdown")  
        else:  
            await update.message.reply_text("Usage:\n /delgroup <group1> <group2> ...")  
    else:  
        await update.message.reply_text(  
            f"<b>No Active Subscription, Please contact</b> <a href=\"tg://resolve?domain={ADMIN_USERNAME}\">Admin</a>",   
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

        if update and update.message:
            await update.message.reply_text(
                f"*Message forwarding has been disabled ❌*\n`{reason}`",
                parse_mode="Markdown"
            )
    else:
        if update and update.message:
            await update.message.reply_text(
                "*Message forwarding is already disabled or not set up for you ❗*",
                parse_mode="Markdown"
            )
async def off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query:
        user_id = str(update.callback_query.from_user.id)
        message = update.callback_query.message
        await update.callback_query.answer()
    else:
        user_id = str(update.message.from_user.id)
        message = update.message

    with open("config.json", "r") as f:
        config_data = json.load(f)

    user_data = config_data["users"].get(user_id, {})
    if "forwarding_on" in user_data and user_data["forwarding_on"]:
        user_data["forwarding_on"] = False
        with open("config.json", "w") as f:
            json.dump(config_data, f, indent=4)

        job_removed = False
        if scheduler.running:
            for job in scheduler.get_jobs():
                if job.args[2] == user_id:  
                    scheduler.remove_job(job.id)
                    job_removed = True
                    break

        response_text = "✅ *Message Forwarding Status*\n\n❌ *Forwarding has been disabled*\n└ _Your automated message forwarding service is now turned off_" if job_removed else "ℹ️ *Forwarding Status*\n\n❗ *No Active Service Found*\n└ _There are no running forwarding tasks for your account_"

        if update.callback_query:
            await message.edit_text(response_text, parse_mode="Markdown")
        else:
            await message.reply_text(response_text, parse_mode="Markdown")

        if not scheduler.get_jobs():
            scheduler.shutdown(wait=False)
            print("Scheduler stopped as there are no remaining jobs.")

    else:
        response_text = "*ℹ️ Message forwarding is already disabled or not set up for you ❗*"
        if update.callback_query:
            await message.edit_text(response_text, parse_mode="Markdown")
        else:
            await message.reply_text(response_text, parse_mode="Markdown")


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
    Extracts the group username/ID and optional topic ID from a group link.
    Handles both public and private group links.
    """
    if group_link.startswith("https://t.me/c/"):
        parts = group_link.replace("https://t.me/c/", "").split("/")
        if len(parts) >= 1:
            group_id = f"-100{parts[0]}"  # Convert to full chat ID
            topic_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
            return int(group_id), topic_id  # Return as integer for private groups
    elif group_link.startswith("https://t.me/"):
        # Public group link: https://t.me/groupname/123
        parts = group_link.replace("https://t.me/", "").split("/")
        group_username = parts[0]
        topic_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        return group_username, topic_id
    elif group_link.startswith('-') and group_link[1:].isdigit():
        # Direct group ID: -1001234567890
        return int(group_link), None
    
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
        session_file = f'{user_id}.session'
        message_target = user_data.get('message_target', 'groups')
        group_delay = user_data.get('group_delay', 0)


        async with session_lock:
            client = TelegramClient(session_file, api_id, api_hash)
            await client.connect()

            if not await client.is_user_authorized():
                await client.disconnect()
                if os.path.exists(session_file):
                    os.remove(session_file)
                await offf(update, context, user_id, reason="Your session was terminated. Please log in again ❌")
                print(f"Session was terminated for user {user_id}")
                return
            print(f"User {user_id} is authorized")
            await client.disconnect()
            await asyncio.sleep(0.8)
        if message_target == 'groups':
            destinations = user_data.get('groups', [])
        else:  # scraped users
            scraped_groups = user_data.get('scraped_groups', {})
            destinations = []
            for group_members in scraped_groups.values():
                destinations.extend(group_members)
        if not forwarding_on:
            print("Forwarding is disabled for this user.")
            await offf(update, context, user_id, reason="Forwarding is disabled")
            return  

        if not destinations:
            await offf(update, context, user_id, reason=f"No {message_target} found for forwarding.")
            return
        if not post_message:
            print("No post messages available for forwarding ❌")
            await offf(update, context, user_id, reason="No post messages available for forwarding ❌")
            return

        post_index = user_data.get("post_index", 0)
        if post_index >= len(post_message):  
            post_index = 0
            
        if message_target == 'scraped':
            async with TelegramClient(session_file, api_id, api_hash) as client:
                post_messages = user_data.get('post_messages', [])
                if not post_messages:
                    return
                current_post = post_messages[post_index]
                
                scraped_groups = user_data.get('scraped_groups', {})
                destinations = []
                for group_data in scraped_groups.values():
                    destinations.extend(group_data['members'])
                    
                print(f"Starting to forward messages to {len(destinations)} users")
                
                for user_to_message in destinations:
                    try:
                        if current_post.startswith("https://t.me/"):
                            from_peer, message_id = extract_chat_and_message_id(current_post)
                            if from_peer and message_id:
                                message = await client.get_messages(from_peer, ids=message_id)
                                await client.send_message(int(user_to_message), message)
                            else:
                                await client.send_message(int(user_to_message), current_post)
                        else:
                            await client.send_message(int(user_to_message), current_post, parse_mode='html')
                        
                        print(f"✅ Successfully sent message to user {user_to_message}")
                        await track_forward(user_id, True, user_to_message)
                        await asyncio.sleep(2)

                    except ValueError as ve:
                        print(f"Invalid user ID format: {user_to_message}")
                        await track_forward(user_id, False, user_to_message)
                    except PeerFloodError:
                        print(f"Too many requests to message users. Cooling down...")
                        await asyncio.sleep(60)
                    except UserPrivacyRestrictedError:
                        print(f"User {user_to_message} has privacy restrictions")
                        await track_forward(user_id, False, user_to_message)
                    except UserIsBlockedError:
                        print(f"User {user_to_message} has blocked the bot")
                        await track_forward(user_id, False, user_to_message)
                    except Exception as e:
                        print(f"Error messaging user {user_to_message}: {str(e)}")
                        await track_forward(user_id, False, user_to_message)
                
                print("✅ Completed sending messages to all scraped users")
                await offf(update, context, user_id, reason="Message forwarding to all scraped users completed ✅")

        else:
            async with TelegramClient(f'{user_id}.session', api_id, api_hash) as client:  
                current_post = post_message[post_index]  
                for i, group_link in enumerate(user_groups):  
                    while True:  
                        try:  
                            if group_link.startswith("https://t.me/"):  
                                to_peer, topic_id = extract_group_and_topic_id(group_link)  
                            elif group_link.startswith('-') and group_link[1:].isdigit():  
                                to_peer = int(group_link)
                                topic_id = None   
                            else:  
                                print(f"Invalid group link: {group_link}")  
                                break  

                            if current_post.startswith("https://t.me/"):  
                                from_peer, message_id = extract_chat_and_message_id(current_post)  

                                if "t.me/+" in group_link:   
                                    target_group = await client(functions.messages.CheckChatInviteRequest(  
                                        hash=group_link.split('+')[1]  
                                    ))  
                                    target_group = target_group.chat  
                                else:  
                                    if to_peer:  
                                        target_group = await client.get_entity(to_peer)  
                                    else:  
                                        print(f"Invalid group link: {group_link}")  
                                        break  

                                if from_peer and message_id:  
                                    if topic_id:  
                                        await client(functions.messages.ForwardMessagesRequest(  
                                            from_peer=from_peer,  
                                            id=[message_id],  
                                            to_peer=target_group,  
                                            top_msg_id=int(topic_id)
                                        
                                        ))  
                                    else:  
                                        await client(functions.messages.ForwardMessagesRequest(  
                                            from_peer=from_peer,  
                                            id=[message_id],  
                                            to_peer=target_group  
                                        ))  

                                    print(f"Message forwarded to group {group_link}.")  
                                else:  
                                    print(f"Invalid Telegram message link: {current_post}")  

                            else:  
                                if "t.me/+" in group_link:  
                                    target_group = await client(functions.messages.CheckChatInviteRequest(  
                                        hash=group_link.split('+')[1]  
                                    ))  
                                    target_group = target_group.chat  
                                else:  
                                    target_group = await client.get_entity(to_peer)  

                                if topic_id is not None:  
                                    await client.send_message(target_group, current_post, reply_to=int(topic_id), parse_mode="HTML")  
                                else:  
                                    await client.send_message(target_group, current_post, parse_mode="HTML")  

                                print(f"Message sent to group {group_link}.")  

                            await track_forward(user_id, True, group_link)
                            if group_delay > 0 and i < len(user_groups) - 1:  
                                print(f"Waiting {group_delay} seconds before next group...")
                                await asyncio.sleep(group_delay)
                            break  
                        except Exception as e:
                            error = f"⚠️ Error forwarding message to {group_link}\n\n🔴 Error: {e}"
                            error_message = f"⚠️ Error forwarding message:\n\n📎 Group: `{group_link}`\n\n🔴 Error: `{e}`"
                            print(error)
                            if update and update.message:
                                await update.message.reply_text(error_message, parse_mode="Markdown")
                            await asyncio.sleep(0.5) 
                            await track_forward(user_id, False, group_link) 
                            break
                print(f"All messages sent. Disconnecting client.")

        post_index = (post_index + 1) % len(post_message)
        user_data["post_index"] = post_index
        config_data["users"][user_id] = user_data  
        with open("config.json", "w") as f:
            json.dump(config_data, f, indent=4)
        await asyncio.sleep(interval)  
    except asyncio.CancelledError:
        print(f"Message forwarding for user {user_id} was canceled.")
        return 
    except Exception as e:
        print(f"An error occurred in forward_messages: {e}")
        await offf(update, context, user_id, reason=f"An error occurred in forward_messages: {e}")

async def forward_saved(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str) -> None:
    try:
        with open("config.json", "r") as f:
            config_data = json.load(f)

        user_data = config_data["users"].get(user_id, {})
        api_id = user_data.get('api_id', '')
        api_hash = user_data.get('api_hash', '')
        interval = int(user_data.get('interval', 60))
        user_groups = user_data.get('groups', [])
        forwarding_on = user_data.get('forwarding_on', False)
        session_file = f'{user_id}.session'
        message_target = user_data.get('message_target', 'groups')
        group_delay = user_data.get('group_delay', 0) 

        async with session_lock:
            client = TelegramClient(session_file, api_id, api_hash)
            await client.connect()

            if not await client.is_user_authorized():
                await client.disconnect()
                if os.path.exists(session_file):
                    os.remove(session_file)
                await offf(update, context, user_id, reason="Your session was terminated. Please log in again ❌")
                print(f"Session was terminated for user {user_id}")
                return
            print(f"User {user_id} is authorized")
            await client.disconnect()
            await asyncio.sleep(0.8)

        if not forwarding_on:
            print(f"Forwarding is disabled for {user_id}")
            await offf(update, context, user_id, reason="Forwarding is disabled ❌")
            return  

        if message_target == 'groups':
            destinations = user_groups
        else:  
            scraped_groups = user_data.get('scraped_groups', {})
            destinations = []
            for group_data in scraped_groups.values():
                destinations.extend(group_data.get('members', []))

        if not destinations:
            print(f"No {message_target} found for this user.")
            await offf(update, context, user_id, reason=f"No {message_target} found for forwarding ❌")
            return

        async with TelegramClient(f'{user_id}.session', api_id, api_hash) as client:
            if not await client.is_user_authorized():
                print("User is not authorized.")
                return

            saved_messages = await client.get_entity('me')
            messages = await client.get_messages(saved_messages, limit=1)  
            if not messages:
                print("No messages found in Saved Messages.")
                await offf(update, context, user_id, reason="No messages found in Saved Messages ❌")
                return

            current_post = messages[0]  

            success_count = 0
            failed_count = 0
            errors = []
            removed_groups = []  # Track removed groups

            if message_target == 'scraped':
                for user_to_message in destinations:
                    try:
                        if current_post.text:
                            await client.send_message(int(user_to_message), current_post.text, parse_mode='html')
                        elif current_post.media:
                            await client.send_file(int(user_to_message), current_post.media)
                        
                        print(f"✅ Successfully sent message to user {user_to_message}")
                        await track_forward(user_id, True, user_to_message)
                        success_count += 1
                        await asyncio.sleep(1)

                    except ValueError as ve:
                        print(f"Invalid user ID format: {user_to_message}\n\nError ❌:\n{ve}")
                        await track_forward(user_id, False, user_to_message)
                        failed_count += 1
                        errors.append(f"Invalid user ID: {user_to_message}")
                    except PeerFloodError:
                        print(f"Too many requests to message users. Cooling down...")
                        failed_count += 1
                        errors.append("PeerFloodError")
                    except UserPrivacyRestrictedError:
                        print(f"User {user_to_message} has privacy restrictions")
                        await track_forward(user_id, False, user_to_message)
                        failed_count += 1
                        errors.append(f"Privacy restrictions: {user_to_message}")
                    except UserIsBlockedError:
                        print(f"User {user_to_message} has blocked the bot")
                        await track_forward(user_id, False, user_to_message)
                        failed_count += 1
                        errors.append(f"User blocked: {user_to_message}")
                    except Exception as e:
                        print(f"Error messaging user {user_to_message}: {str(e)}")
                        await track_forward(user_id, False, user_to_message)
                        failed_count += 1
                        errors.append(f"Error for {user_to_message}: {str(e)}")
                
                print("✅ Completed sending messages to all scraped users")
                reason = f"Message forwarding to all scraped users completed ✅\n\nSuccess: {success_count}\n Failed: {failed_count}\n Errors ❌:\n {errors[:5] if errors else 'None'}"
                await offf(update, context, user_id, reason=reason)
            else:
                # Create a copy of user_groups to iterate over
                groups_to_process = user_groups.copy()
                
                for i, group_link in enumerate(groups_to_process):  
                    try:
                        if group_link.startswith('-') and group_link[1:].isdigit():  
                            to_peer = int(group_link)  
                            target_group = await client.get_entity(to_peer)
                            topic_id = None  
                        else:
                            to_peer, topic_id = extract_group_and_topic_id(group_link)
                            if "t.me/+" in group_link:  
                                target_group = await client(functions.messages.CheckChatInviteRequest(
                                    hash=group_link.split('+')[1]
                                ))
                                target_group = target_group.chat
                            else:
                                target_group = await client.get_entity(to_peer)

                        if current_post.text or current_post.media:
                            if topic_id is not None:
                                await client(functions.messages.ForwardMessagesRequest(
                                    from_peer=saved_messages,
                                    id=[current_post.id],
                                    to_peer=target_group,
                                    top_msg_id=int(topic_id)
                                ))
                            else:
                                await client(functions.messages.ForwardMessagesRequest(
                                    from_peer=saved_messages,
                                    id=[current_post.id],
                                    to_peer=target_group
                                ))
                            print(f"Message forwarded to group {group_link}.")
                            await track_forward(user_id, True, group_link)
                            success_count += 1
                        else:
                            print(f"Message does not contain text or media, skipping: {current_post.id}")
                        
                        if group_delay > 0 and i < len(groups_to_process) - 1:  
                            print(f"Waiting {group_delay} seconds before next group...")
                            await asyncio.sleep(group_delay)
                           
                    except Exception as e:
                        error = f"⚠️ Error forwarding message to {group_link}\n\n🔴 Error: {e}"
                        error_message = f"⚠️ Error forwarding message:\n\n📎 Group: `{group_link}`\n\n🔴 Error: `{e}`"
                        print(error)
                        
                        # Remove the problematic group from user's groups
                        try:
                            # Reload config to get latest data
                            with open("config.json", "r") as f:
                                current_config = json.load(f)
                            
                            if user_id in current_config["users"] and "groups" in current_config["users"][user_id]:
                                if group_link in current_config["users"][user_id]["groups"]:
                                    current_config["users"][user_id]["groups"].remove(group_link)
                                    removed_groups.append(group_link)
                                    
                                    # Save updated config
                                    with open("config.json", "w") as f:
                                        json.dump(current_config, f, indent=4)
                                    
                                    print(f"🗑️ Automatically removed problematic group: {group_link}")
                                    
                                    # Inform user about the removal
                                    removal_message = f"🗑️ *Group Automatically Removed*\n\n📎 Group: `{group_link}`\n\n🔴 Reason: `{str(e)}`\n\n✅ The group has been removed from your forwarding list to prevent future errors."
                                    if update and update.message:
                                        await update.message.reply_text(removal_message, parse_mode="Markdown")
                                        
                        except Exception as removal_error:
                            print(f"Error removing group {group_link}: {removal_error}")
                        
                        await asyncio.sleep(0.5)  
                        await track_forward(user_id, False, group_link)
                        failed_count += 1
                        errors.append(f"Removed group {group_link}: {str(e)}")
                            
            print(f"All messages sent. Disconnecting client.")
            
            # Final summary including removed groups
            if removed_groups:
                removal_summary = f"\n\n🗑️ *Automatically Removed Groups:*\n" + "\n".join([f"• `{group}`" for group in removed_groups])
                final_reason = f"Message forwarding completed ✅\n\nSuccess: {success_count}\nFailed: {failed_count}{removal_summary}"
                if update and update.message:
                    await update.message.reply_text(final_reason, parse_mode="Markdown")
        
        await asyncio.sleep(interval)
    except asyncio.CancelledError:
        print(f"Message forwarding for user {user_id} was canceled.")
        return 
    except Exception as e:
        print(f"An error occurred in forward_saved: {e}")
        await offf(update, context, user_id, reason=f"An error occurred in forward_saved: {e}")

async def on(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query:
        message = update.callback_query.message
        user_id = str(update.callback_query.from_user.id)
        is_callback = True
    else:
        message = update.message
        user_id = str(update.message.from_user.id)
        is_callback = False

    

    if not await is_authorized(user_id):
        await (message.edit_text if is_callback else message.reply_text)(
            "⚠️ *Your subscription has expired or you are not authorized to enable forwarding.*\n"
            f"*Please contact the* [Admin](tg://resolve?domain={ADMIN_USERNAME}) *for assistance ❕*",
            parse_mode="Markdown"
        )
        return

    data = load_user_data()
    user_data = data["users"].get(user_id, {})
    message_source = user_data.get("message_source", "mypost")
    message_target = user_data.get('message_target', 'groups')

    required_keys = ["api_id", "api_hash", "groups", "interval"]
    missing_keys = [key for key in required_keys if not user_data.get(key)]
    if message_target == 'groups':
            destinations = user_data.get('groups', [])
    else:  
            scraped_groups = user_data.get('scraped_groups', {})
            destinations = []
            for group_members in scraped_groups.values():
                destinations.extend(group_members)

    if user_data.get("forwarding_on", False):
        await (message.edit_text if is_callback else message.reply_text)("*Forwarding cannot be toggled twice ❌*", parse_mode="Markdown")
        return
    if user_data.get("auto_reply_status", False):
        await (message.edit_text if is_callback else message.reply_text)("*Forwarding cannot be toggled when Auto-reply is active ❌*", parse_mode="Markdown")
        return
    if message_source == "saved_messages":
        pass  
    else:
        if "post_messages" not in user_data or not user_data["post_messages"]:
            await (message.edit_text if is_callback else message.reply_text)("*⚠️ Please set at least one* `post_messages` *to proceed or switch your Message Source*", parse_mode="Markdown")
            return
        
    if not destinations:
        await (message.edit_text if is_callback else message.reply_text)(f"No {message_target} found for forwarding ❌\n\nTry Switching Your Message Target ✅")
        return
    if missing_keys:
        await (message.edit_text if is_callback else message.reply_text)(
            f"*Please ensure the following keys are set before enabling forwarding:* {', '.join(missing_keys)}",
            parse_mode="Markdown"
        )
        return

    if int(user_data.get("interval", 0)) < 60:
        await (message.edit_text if is_callback else message.reply_text)(
            "The interval must be at least 60 seconds. Please update it using the `/time` command.",
            parse_mode="Markdown"
        )
        return

    session_file = f'{user_id}.session'
    if not os.path.exists(session_file):
        await (message.edit_text if is_callback else message.reply_text)("*Sorry, you are logged out. Please log in again with* `/login +1234567890`", parse_mode="Markdown")
        return

    try:
        client = TelegramClient(session_file, user_data["api_id"], user_data["api_hash"])
        await client.connect()  

        if not await client.is_user_authorized():
            await client.disconnect()
            os.remove(session_file)
            await (message.edit_text if is_callback else message.reply_text)("*Your session was terminated. Please log in again ❌*", parse_mode="Markdown")
            return

        data["users"][user_id]["forwarding_on"] = True
        save_user_data(data)

        if not scheduler.running:
            scheduler.start()

        job_exists = any(job.args[0] == user_id for job in scheduler.get_jobs())
        if not job_exists:
            if message_source == "saved_messages":
                scheduler.add_job(forward_saved, 'interval', seconds=int(user_data["interval"]), args=[update, context, user_id], max_instances=10)
            else:
                scheduler.add_job(forward_messages, 'interval', seconds=int(user_data["interval"]), args=[update, context, user_id], max_instances=10)

        await (message.edit_text if is_callback else message.reply_text)("*Message forwarding is now enabled ✅*", parse_mode="Markdown")

    except Exception as e:
        print(f"An error occurred while checking your session: {e}")
        await (message.edit_text if is_callback else message.reply_text)(f"*An error occurred while checking your session.\n{e}❗*", parse_mode="Markdown")
    finally:
        if client.is_connected():
            await client.disconnect()

    await asyncio.sleep(1)
    if message_source == "saved_messages":
        asyncio.create_task(forward_saved(update, context, user_id))  
    else:
        asyncio.create_task(forward_messages(update, context, user_id))

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
        forwarding_status = user_data.get('forwarding_on', False)
        group_count = len(user_groups)
        if user_groups:
            formatted_groups = "\n".join([f"`{group}`" for group in user_groups])
        if group_count > 0:
            group_info = f"Groups Added: {group_count}"
        else:
            group_info = "No Group has been added"

        session_exists = os.path.exists(f"{user_id}.session")
        settings_text = (
            "*📱 Settings Dashboard*\n\n"
            "*📊 Status Overview:*\n"
            "─────────────────────────────\n"
            f"*└ 👥 Groups: {group_count}*\n"
            f"*└ ⏱️ Interval: {interval} seconds*\n"
            f"*└ 📤 Forwarding: {'Active ✅' if forwarding_status else 'Inactive ❌'}*\n"
            f"*└ 🔐 Logged in: {'YES ✅' if session_exists else 'NO ❌'}*\n"
            "─────────────────────────────"
        )

        keyboard = [
            [InlineKeyboardButton("My Posts 📝", callback_data='my_post'), InlineKeyboardButton("My Groups 👥", callback_data='my_groups')],
            [InlineKeyboardButton("Add Group ➕", callback_data='add_group'), InlineKeyboardButton("Remove Group ➖", callback_data='remove_group')],
            [InlineKeyboardButton("Set Interval ⏱️", callback_data='set_time'), InlineKeyboardButton("Toggle Forward ▶️", callback_data='on_off')],
            [InlineKeyboardButton("Logout 🔓", callback_data='logout'), InlineKeyboardButton("Message Source 📨", callback_data='msg_source')],
            [InlineKeyboardButton(f"Target: Groups 👥 {' ✅' if user_data.get('message_target', 'groups') == 'groups' else ''}", callback_data='target_groups'),
            InlineKeyboardButton(f"Target: Scraped 👤 {' ✅' if user_data.get('message_target', 'groups') == 'scraped' else ''}", callback_data='target_scraped')],
            [InlineKeyboardButton("View Scraped Users 📊", callback_data='view_scraped'), InlineKeyboardButton("Remove Scraped 🗑️", callback_data='rmvscraped')],
            [InlineKeyboardButton("Add Users to Group 👥", callback_data='add_to_gc')],

            [InlineKeyboardButton("Back ◀️", callback_data='back')]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)    
    else:
        await update.message.reply_text(f"<b>No Active Subscription, Please contact</b> <a href=\"tg://resolve?domain={ADMIN_USERNAME}\">Admin</a>", parse_mode="HTML")

    if is_callback:
        await message.edit_text(settings_text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await message.reply_text(settings_text, reply_markup=reply_markup, parse_mode="Markdown")

async def message_source(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query:
        user_id = str(update.callback_query.from_user.id)
        message = update.callback_query.message
        is_callback = True
    else:
        user_id = str(update.message.from_user.id)
        message = update.message
        is_callback = False

    data = load_user_data()
    user_data = data["users"].get(user_id, {})

    current_source = user_data.get("message_source", "mypost")

    keyboard = [  
    [InlineKeyboardButton(f"📄 My Post 📝 {'🟢' if current_source == 'mypost' else ''}", callback_data='mypost')],  
    [InlineKeyboardButton(f"📥 Saved Messages {'🟢' if current_source == 'saved_messages' else ''}", callback_data='saved_messages')],  
    [InlineKeyboardButton("🔙 Back", callback_data='settings')]  
    ]  

    display_source = "MY POST" if current_source == "mypost" else "SAVED MESSAGES"  

    if is_callback:  
        await message.edit_text(  
            "╔═══════════════╗\n"  
            "  🔧 Current Source Settings\n"  
            "╚═══════════════╝\n"  
            f" *Current Source:* {display_source} ✅\n"  
            "─────────────────\n"  
            "Choose an option below:\n",  
            reply_markup=InlineKeyboardMarkup(keyboard),  
            parse_mode="Markdown"  
        )  
    else:  
        await message.reply_text(  
            "╔═══════════════╗\n"  
            "        🔧 Current Source Settings\n"  
            "╚═══════════════╝\n"  
            f"  *Current Source:* {display_source} ✅\n"  
            "─────────────────\n"  
            "Choose an option below:\n",  
            reply_markup=InlineKeyboardMarkup(keyboard),  
            parse_mode="Markdown"  
        )

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
        message_text = "📝 *Here are your saved posts:*\n\n"
        for i, post in enumerate(post_messages, start=1):
            message_text += f"*{i}.* 💬 `{post}`\n\n"
        message_text += "\n✨ *Want to update your posts? Just use* `/post message` *to add new ones!* ✨"
    else:
        message_text = "📭 *Oops! Looks like you haven't added any posts yet.*"

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

    if not await is_authorized(user_id):
        await (message.edit_text if is_callback else message.reply_text)(
            f"🔒 <b>Access Restricted</b>\n\n❌ No active subscription found\n✨ Please contact <a href=\"tg://resolve?domain={ADMIN_USERNAME}\">Admin</a> for access", 
            parse_mode="HTML"
        )
        return

    with open("config.json", "r") as f:
        config_data = json.load(f)

    user_data = config_data["users"].get(user_id, {})
    user_groups = user_data.get('groups', [])
    group_delay = user_data.get('group_delay', 0)

    if not user_groups:
        message_text = (
            "📭 *No Forwarding Groups Set*\n\n"
            "❌ You haven't added any groups for forwarding yet\n\n"
            "🚀 *Get Started:*\n"
            "• Use `/addgroup <group_link>` to add groups\n"
            "• Use `/listgc` to see all your groups\n"
            "• Use `/delay <seconds>` to set forwarding delay\n\n"
            "💡 *Example:*\n"
            "`/addgroup https://t.me/mygroup`"
        )
        
        keyboard = [
            [InlineKeyboardButton("➕ Add Groups", callback_data='add_group')],
            [InlineKeyboardButton("📋 List All Groups", callback_data='list_all_groups')],
            [InlineKeyboardButton("🔙 Back", callback_data='settings')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if is_callback:
            await message.edit_text(message_text, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await message.reply_text(message_text, reply_markup=reply_markup, parse_mode="Markdown")
        return

    # Store groups in context for pagination
    context.user_data['my_groups_list'] = user_groups
    context.user_data['my_groups_page'] = 0
    
    await show_my_groups_page(message, context, 0, group_delay, is_callback)

async def show_my_groups_page(message, context, page, group_delay, is_callback=True):
    user_groups = context.user_data.get('my_groups_list', [])
    groups_per_page = 15  # Reduced to ensure message doesn't exceed limit
    total_pages = math.ceil(len(user_groups) / groups_per_page)
    
    start_idx = page * groups_per_page
    end_idx = start_idx + groups_per_page
    page_groups = user_groups[start_idx:end_idx]
    
    group_count = len(user_groups)
    
    # Create header
    message_text = (
        f"👥 *Your Forwarding Groups*\n\n"
        f"📊 *Total Groups:* {group_count}\n"
        f"⏱️ *Group Delay:* {group_delay} seconds\n"
        f"📄 *Page:* {page + 1}/{total_pages}\n"
        f"📋 *Showing:* {start_idx + 1}-{min(end_idx, group_count)}\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
    )
    
    # Add groups for current page
    for idx, group in enumerate(page_groups, start=start_idx + 1):
        # Determine group type based on link format
        if group.startswith("https://t.me/"):
            if "/+" in group:
                group_type = "🔒"
            else:
                group_type = "🌐"
        elif group.startswith('-') and group[1:].isdigit():
            group_type = "🆔"
        else:
            group_type = "❓"
        
        # Truncate long links for display (more aggressive truncation)
        display_link = group[:35] + "..." if len(group) > 35 else group
        message_text += f"{idx}. {group_type} `{display_link}`\n"
    
    # Add footer
    message_text += (
        f"\n💡 *Legend:*\n"
        f"🌐 Public • 🔒 Private • 🆔 ID • ❓ Unknown"
    )
    
    # Create keyboard
    keyboard = []
    
    # Navigation buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"my_groups_page_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"my_groups_page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Action buttons
    keyboard.extend([
        [InlineKeyboardButton("➕ Add Groups", callback_data='add_group'),
         InlineKeyboardButton("➖ Remove Groups", callback_data='remove_group')],
        [InlineKeyboardButton("📋 List All Groups", callback_data='list_all_groups'),
         InlineKeyboardButton("⏱️ Set Delay", callback_data='set_delay')],
        [InlineKeyboardButton("🔙 Back", callback_data='settings')]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        if is_callback:
            await message.edit_text(message_text, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await message.reply_text(message_text, reply_markup=reply_markup, parse_mode="Markdown")
    except Exception as e:
        # If message is still too long, further truncate
        if "message is too long" in str(e).lower():
            # Emergency truncation - show fewer groups
            groups_per_page = 10
            total_pages = math.ceil(len(user_groups) / groups_per_page)
            start_idx = page * groups_per_page
            end_idx = start_idx + groups_per_page
            page_groups = user_groups[start_idx:end_idx]
            
            message_text = (
                f"👥 *Your Forwarding Groups*\n\n"
                f"📊 *Total:* {group_count} | ⏱️ *Delay:* {group_delay}s\n"
                f"📄 *Page:* {page + 1}/{total_pages}\n"
                f"━━━━━━━━━━━━━━━━━━━\n\n"
            )
            
            for idx, group in enumerate(page_groups, start=start_idx + 1):
                group_type = "🌐" if group.startswith("https://t.me/") and "/+" not in group else "🔒" if "/+" in group else "🆔" if group.startswith('-') else "❓"
                display_link = group[:25] + "..." if len(group) > 25 else group
                message_text += f"{idx}. {group_type} `{display_link}`\n"
            
            # Update navigation for new page size
            nav_buttons = []
            if page > 0:
                nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"my_groups_page_{page-1}"))
            if page < total_pages - 1:
                nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"my_groups_page_{page+1}"))
            
            keyboard = []
            if nav_buttons:
                keyboard.append(nav_buttons)
            keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='settings')])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if is_callback:
                await message.edit_text(message_text, reply_markup=reply_markup, parse_mode="Markdown")
            else:
                await message.reply_text(message_text, reply_markup=reply_markup, parse_mode="Markdown")


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
                [InlineKeyboardButton("𝗛𝗘𝗟𝗣 𝗚𝗨𝗜𝗗𝗘 ❕", callback_data='help')],
                [InlineKeyboardButton("𝗔𝗨𝗧𝗢 𝗥𝗘𝗦𝗣𝗢𝗡𝗗𝗘𝗥 𝗚𝗨𝗜𝗗𝗘❕", url='https://telegra.ph/AUTO-RESPONDER-GUIDE-11-11')],
                [InlineKeyboardButton("𝗔𝗣𝗜 𝗔𝗡𝗗 𝗛𝗔𝗦𝗛 𝗜𝗗 🎥", url='https://youtu.be/8naENmP3rg4?si=LVxsTXSSI864t6Kv')],
                [InlineKeyboardButton("𝗟𝗢𝗚𝗜𝗡 𝗪𝗜𝗧𝗛 𝗧𝗘𝗟𝗘𝗚𝗥𝗔𝗠 🔑", callback_data='login')],
                [InlineKeyboardButton("𝗦𝗲𝘁𝘁𝗶𝗻𝗴𝘀 ⚙️", callback_data='settings')],
                [InlineKeyboardButton("𝗔𝘂𝘁𝗼 𝗥𝗲𝗽𝗹𝘆 ⚙️", callback_data='auto_reply')],
                [InlineKeyboardButton("𝗦𝘁𝒂𝘁𝘀 📈", callback_data='refresh_stats')],
            ]    
    
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:

        await update.message.reply_text("Spidertise Main Menu", reply_markup=reply_markup)
    elif update.callback_query:

        query = update.callback_query
        await query.edit_message_text("Spidertise Main Menu", reply_markup=reply_markup)

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()  

    await main_menu(update, context)

def get_user_keywords(user_data):
    keywords = user_data.get("keywords", {})
    match_option = user_data.get("match_option", "exact")

    if not keywords:
        return "📝 Looks like you haven't set any keywords yet! Let's add some to get started 🚀"

    response_text = "<b>Here are your keywords and responses:</b>\n\n"
    response_text += f"<b>Matching Option:</b> {match_option.capitalize()}\n\n"
    response_text += "<b>Keyword</b> ➡️ <b>Response</b>\n"
    response_text += "=====================\n"

    for keyword, response in keywords.items():
        response_text += f"🔹 <code>{keyword}</code> ➡️ <code>{response}</code>\n"

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
        [InlineKeyboardButton("➕ Add New Keyword", callback_data="add_keyword")],
        [InlineKeyboardButton("🗑️ Remove Keyword", callback_data="del_keyword")],
        [InlineKeyboardButton("↩️ Back", callback_data="auto_reply")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await query.edit_message_text(response_text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        await update.message.reply_text(response_text, reply_markup=reply_markup, parse_mode="HTML")
async def get_ip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get the public IP address of the server running the bot."""
    user_id = str(update.message.from_user.id)
    
    # Only allow admins to check IP
    if user_id in ADMIN_IDS:
        try:
            # Use ipify API to get public IP
            response = requests.get('https://api.ipify.org?format=json')
            if response.status_code == 200:
                ip_data = response.json()
                ip_address = ip_data.get('ip', 'Unknown')
                
                await update.message.reply_text(
                    f"🌐 *Server IP Address*\n\n"
                    f"`{ip_address}`\n\n"
                    f"✅ Successfully retrieved IP information",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    "❌ *Failed to retrieve IP address*\n\n"
                    f"Status code: {response.status_code}",
                    parse_mode="Markdown"
                )
        except Exception as e:
            await update.message.reply_text(
                "❌ *Error retrieving IP address*\n\n"
                f"Error details: `{str(e)}`",
                parse_mode="Markdown"
            )
    else:
        await update.message.reply_text(
            "🔒 *Access Denied*\n\n"
            "This command is restricted to administrators only.",
            parse_mode="Markdown"
        )

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
        await update.message.reply_text("🤔 Oops! Please tell me which keyword you want to remove.\n\n💡 Example: /stopword Good Morning")
        return

    keywords = user_data.get("keywords", {})
    if keyword_to_remove in keywords:

        message = await update.message.reply_text("🔄 <b>Processing</b>", parse_mode="HTML")
        await asyncio.sleep(0.2)
        await message.edit_text("🔄 <b>Almost there...</b>", parse_mode="HTML")
        await asyncio.sleep(0.2)
        await message.edit_text("🔄 <b>Just a moment...</b>", parse_mode="HTML")
        await asyncio.sleep(0.4)

        del keywords[keyword_to_remove]

        save_user_data(data)

        await message.edit_text(f"✨ <b>Success! '{keyword_to_remove}' has been removed from your keywords!</b> 🎉", parse_mode="HTML")
    else:
        await update.message.reply_text(f"🔍 <b>Hmm... I couldn't find '{keyword_to_remove}' in your keywords list</b> 🤔", parse_mode="HTML")
async def autoreply_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        print("No callback query received.")
        return

    user_id = str(query.from_user.id).strip()
    data = load_user_data()
    user_data = data["users"].get(user_id, {})

    if not await is_authorized(user_id):
        await query.edit_message_text("*You are not allowed to use this feature ❌*", parse_mode="Markdown")
        return
   
    elif query.data == "mark_all_read":
        if not user_data.get("auto_reply_status", False):
            await query.answer("⚠️ Auto-reply must be enabled to use this feature", show_alert=True)
            return
        
        # Edit the message to show processing status
        try:
            await query.edit_message_text(
                "📖 **Marking all messages as read** ✅\n\n"
                "⏳ Please wait while we process all your chats...\n"
                "🤖 This might take a while but you can use the bot\n"
                "━━━━━━━━━━━━━━━━━━━━━",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Error editing message: {e}")
        
        # Import the function from autoreply.py
        from autoreply import mark_all_messages_read
        
        async def background_mark_read():
            try:
                result = await mark_all_messages_read(user_id)
                
                if result:
                    # Edit message to show success
                    await query.edit_message_text(
                        "✅ **All messages marked as read successfully!**\n\n"
                        "🎉 All your chats have been marked as read\n"
                        "━━━━━━━━━━━━━━━━━━━━━\n\n"
                        "Click the button below to return to settings.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Back to Settings", callback_data='auto_reply')
                        ]]),
                        parse_mode="Markdown"
                    )
                else:
                    # Edit message to show failure
                    await query.edit_message_text(
                        "❌ **Failed to mark messages as read**\n\n"
                        "⚠️ Please try again later or check your connection\n"
                        "━━━━━━━━━━━━━━━━━━━━━\n\n"
                        "Click the button below to return to settings.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Back to Settings", callback_data='autoreply')
                        ]]),
                        parse_mode="Markdown"
                    )
                    
            except Exception as e:
                print(f"Error marking messages as read: {e}")
                # Edit message to show error
                try:
                    await query.edit_message_text(
                        f"❌ **Error occurred**\n\n"
                        f"⚠️ {str(e)}\n"
                        "━━━━━━━━━━━━━━━━━━━━━\n\n"
                        "Click the button below to return to settings.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Back to Settings", callback_data='autoreply')
                        ]]),
                        parse_mode="Markdown"
                    )
                except Exception as edit_error:
                    print(f"Error editing message after failure: {edit_error}")
        
        # Create background task
        asyncio.create_task(background_mark_read())
        
        return 

    elif query.data == "set_exact":
        user_data["match_option"] = "exact"
    elif query.data == "set_pm":
        user_data["responder_option"] = "PM"
    elif query.data == "set_gc":
        user_data["responder_option"] = "GC"
    elif query.data == "set_all":
        user_data["responder_option"] = "All"
    elif query.data == "set_partial":
        user_data["match_option"] = "partial"
    elif query.data == "set_case_insensitive":
        user_data["match_option"] = "case_insensitive"
    elif query.data == "set_saved":
        user_data["save_location"] = "saved"
    elif query.data == "set_chat":
        user_data["save_location"] = "chat"
    elif query.data == "set_deleted_groups":
        user_data["deleted_monitor_mode"] = "Groups"
        save_user_data(data)
        await query.answer("Monitoring deleted messages in groups only", show_alert=True)
        
    elif query.data == "set_deleted_private":
        user_data["deleted_monitor_mode"] = "Private"
        save_user_data(data)
        await query.answer("Monitoring deleted messages in private chats only", show_alert=True)
        
    elif query.data == "set_deleted_all":
        user_data["deleted_monitor_mode"] = "All"
        save_user_data(data)
        await query.answer("Monitoring deleted messages in all chats", show_alert=True)
    elif query.data == "toggle_anti_deleted":
        # Check if deleted_group is set
        deleted_group = user_data.get("deleted_group")
        
        if not deleted_group and not user_data.get("anti_deleted_enabled", False):
            # User is trying to enable without setting a group
            await query.answer(
                "⚠️ You need to set a deleted messages group first using /deletedgc command",
                show_alert=True
            )
        else:
            # Toggle the setting
            user_data["anti_deleted_enabled"] = not user_data.get("anti_deleted_enabled", False)
            save_user_data(data)
            
            # If they're disabling, we allow it regardless of deleted_group
            # If they're enabling, we already checked for deleted_group above
            await query.answer(
                f"Anti-deleted monitoring is now {'enabled' if user_data['anti_deleted_enabled'] else 'disabled'} ✅",
                show_alert=True
            )
    elif query.data == "toggle_auto_reply":
        if user_data.get("forwarding_on", False):
            await query.answer("Cannot enable auto-reply while forwarding is active", show_alert=True)
            return
        user_data["auto_reply_status"] = not user_data.get("auto_reply_status", False)
        save_user_data(data)
        try:
            if user_data["auto_reply_status"]:
                await start_telethon_client(user_id, context)
            else:
                await stop_telethon_client(user_id)
            await query.answer(
                f"Auto-reply is now {'enabled' if user_data['auto_reply_status'] else 'disabled'} ✅",
                show_alert=True
            )
        except Exception as e:
            print(f"Error while toggling auto-reply: {e}")
            await query.answer(
                f"Failed to toggle auto-reply: {str(e)} ❌",
                show_alert=True
            )   
    else:
        await all_callback(update, context)
        return

    save_user_data(data)

    match_option = user_data.get("match_option", "exact")
    auto_reply_status = "𝙴𝚗𝚊𝚋𝚕𝚎𝚍 ✅" if user_data.get("auto_reply_status", False) else "𝙳𝚒𝚜𝚊𝚋𝚕𝚎𝚍 ❌"
    auto_reply_text = "𝙳𝚒𝚜𝚊𝚋𝚕𝚎 🔴" if user_data.get("auto_reply_status", False) else "𝙴𝚗𝚊𝚋𝚕𝚎 🟢"
    responder_option = user_data.get("responder_option", "𝙿𝙼")
    save_location = user_data.get("save_location", "chat")

    anti_deleted_enabled = user_data.get("anti_deleted_enabled", False)
    anti_deleted_text = "Turn Off 🔴" if anti_deleted_enabled else "Turn On 🟢"
    anti_deleted_status = "𝙴𝚗𝚊𝚋𝚕𝚎𝚍 ✅" if anti_deleted_enabled else "𝙳𝚒𝚜𝚊𝚋𝚕𝚎𝚍 ❌"
    deleted_group = user_data.get("deleted_group", "Not Set")
    deleted_monitor_mode = user_data.get("deleted_monitor_mode", "All")  # Default

    keyboard = [
            [InlineKeyboardButton("Match Options", callback_data="pass")],
            [InlineKeyboardButton(f"Exact Match {'✅' if match_option == 'exact' else '❌'}", callback_data='set_exact'),
             InlineKeyboardButton(f"Partial {'✅' if match_option == 'partial' else '❌'}", callback_data='set_partial')],
            [InlineKeyboardButton(f"Case Insensitive {'✅' if match_option == 'case_insensitive' else '❌'}", callback_data='set_case_insensitive')],
            [InlineKeyboardButton("Response Settings", callback_data="pass")],
            [InlineKeyboardButton(f"PM {'✅' if responder_option == 'PM' else '❌'}", callback_data='set_pm'),
             InlineKeyboardButton(f"GC {'✅' if responder_option == 'GC' else '❌'}", callback_data='set_gc'),
             InlineKeyboardButton(f"All {'✅' if responder_option == 'All' else '❌'}", callback_data='set_all')],
            [InlineKeyboardButton("View Once Save Location", callback_data="pass")],
            [InlineKeyboardButton(f"Saved {'✅' if save_location == 'saved' else '❌'}", callback_data='set_saved'),
             InlineKeyboardButton(f"In-Chat {'✅' if save_location == 'chat' else '❌'}", callback_data='set_chat')],
            [InlineKeyboardButton("Anti Delete Settings", callback_data="pass")],
            [InlineKeyboardButton(f"{anti_deleted_text}", callback_data='toggle_anti_deleted')],
            [InlineKeyboardButton(f"Groups {'✅' if deleted_monitor_mode == 'Groups' else '❌'}", callback_data='set_deleted_groups'),
             InlineKeyboardButton(f"Private {'✅' if deleted_monitor_mode == 'Private' else '❌'}", callback_data='set_deleted_private'),
             InlineKeyboardButton(f"All {'✅' if deleted_monitor_mode == 'All' else '❌'}", callback_data='set_deleted_all')],
            [InlineKeyboardButton("Keywords", callback_data='words'),
             InlineKeyboardButton("Mark All Read", callback_data='mark_all_read')],
            [InlineKeyboardButton(f"{auto_reply_text}", callback_data='toggle_auto_reply'),
             InlineKeyboardButton("Back", callback_data='back')]
    ]    
    reply_markup = InlineKeyboardMarkup(keyboard)

    respond_display = {
        'PM': 'Private Chat',
        'GC': 'Groups',
        'All': 'DMs & Groups'
    }.get(responder_option, responder_option)

    try:
        await query.edit_message_text(
        "⚙️ <b>𝙰𝚄𝚃𝙾-𝚁𝙴𝙿𝙻𝚈 𝚂𝙴𝚃𝚃𝙸𝙽𝙶𝚂 + 𝙰𝙽𝚃𝙸 𝚅𝙸𝙴𝚆 𝙾𝙽𝙲𝙴 + 𝙰𝙽𝚃𝙸 𝙼𝚂𝙶 𝙳𝙴𝙻𝙴𝚃𝙴</b>\n\n"       
        "━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>𝙼𝚊𝚝𝚌𝚑 𝙼𝚘𝚍𝚎:</b> <code>{match_option}</code>\n"
        f"📊 <b>𝚂𝚝𝚊𝚝𝚞𝚜:</b> <code>{auto_reply_status}</code>\n"
        f"🌐 <b>𝚁𝚎𝚜𝚙𝚘𝚗𝚍 𝙸𝚗:</b> <code>{respond_display}</code>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "📸 <b>𝙰𝚗𝚝𝚒 𝚅𝚒𝚎𝚠 𝙾𝚗𝚌𝚎:</b>\n"
        "<code>𝚁𝚎𝚙𝚕𝚢 𝚝𝚘 𝚊𝚗𝚢 𝚟𝚒𝚎𝚠 𝚘𝚗𝚌𝚎 𝚖𝚎𝚍𝚒𝚊 𝚠𝚒𝚝𝚑 /𝚟𝚟</code>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"🗑️ <b>𝙰𝚗𝚝𝚒 𝙼𝚜𝚐 𝙳𝚎𝚕𝚎𝚝𝚎:</b> <code>{anti_deleted_status}</code>\n"       
        f"📍 <b>𝙳𝚎𝚕𝚎𝚝𝚎𝚍 𝙶𝚛𝚘𝚞𝚙:</b> <code>{deleted_group}</code>\n\n"
        "💡 <b>𝚃𝚒𝚙:</b> <code>𝚄𝚜𝚎 /𝚍𝚎𝚕𝚎𝚝𝚎𝚍𝚐𝚌 &lt;𝚕𝚒𝚗𝚔&gt; 𝚝𝚘 𝚜𝚎𝚝 𝚍𝚎𝚕𝚎𝚝𝚎𝚍 𝚖𝚎𝚜𝚜𝚊𝚐𝚎𝚜 𝚐𝚛𝚘𝚞𝚙</code>",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

    except Exception as e:
        print(f"Failed to update message: {e}")
    await query.answer()

async def handle_my_groups_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("my_groups_page_"):
        page = int(query.data.split("_")[-1])
        context.user_data['my_groups_page'] = page
        
        # Get group delay
        user_id = str(query.from_user.id)
        data = load_user_data()
        user_data = data["users"].get(user_id, {})
        group_delay = user_data.get('group_delay', 0)
        
        await show_my_groups_page(query.message, context, page, group_delay, True)

async def handle_groups_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("groups_page_"):
        page = int(query.data.split("_")[-1])
        context.user_data['current_page'] = page
        await show_groups_page(query.message, context, page)
    
    elif query.data.startswith("group_info_"):
        await show_group_info(update, context)
    
    elif query.data == "back_to_groups":
        current_page = context.user_data.get('current_page', 0)
        await show_groups_page(query.message, context, current_page)
    
    elif query.data == "list_all_groups":
        # Redirect to listgc command
        await list_groups_command(update, context)
    
    elif query.data == "set_delay":
        await query.edit_message_text(
            "⏱️ *Set Group Delay*\n\n"
            "Use `/delay <seconds>` to set delay between forwarding to each group\n\n"
            "💡 *Examples:*\n"
            "• `/delay 10` - 10 second delay\n"
            "• `/delay 0` - No delay\n\n"
            "ℹ️ *Current delay will be shown when you use `/delay` without parameters*",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data='my_groups')]
            ]),
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
    if query.data.startswith("my_groups_page_"):
        await handle_my_groups_callback(update, context)
        return
    elif query.data == "list_all_links":
        await list_all_links(update, context)
    elif query.data.startswith("links_page_"):
        page = int(query.data.split("_")[-1])
        await show_links_page(query, context, page)
        return
    elif query.data.startswith("groups_page_") or query.data.startswith("group_info_") or query.data == "back_to_groups" or query.data == "list_all_groups" or query.data == "set_delay":
        await handle_groups_callback(update, context)
        return
    elif query.data == 'add_group':
        await query.edit_message_text("*Please Use:* \n`/addgroup\n<group_link>\n<group_link2>`\n\n *to add a group or groups*", reply_markup=back_button(), parse_mode="Markdown")
    elif query.data == 'remove_group':
        await query.edit_message_text("Please use /delgroup <group_link> to remove a group.", reply_markup=back_button())
    elif query.data == 'set_time':
        await query.edit_message_text("Please use /time <interval> to set the message interval in seconds only.", reply_markup=back_button())
    elif query.data == 'on_off':
        data = load_user_data()
        user_id = str(query.from_user.id).strip()
        user_data = data["users"].get(user_id, {})
        forwarding_status = user_data.get("forwarding_on", False)
        
        button_text = "Disable ❌" if forwarding_status else "Enable 🟢"
        status_text = "ON" if forwarding_status else "OFF"
        
        await query.edit_message_text(
            "⚙️ <b>FORWARDING STATUS</b>\n\n"
            "━━━━━━━━━━━━━━━\n"
            f"📊 <b>Status:</b> <code>{status_text}</code>\n"
            "━━━━━━━━━━━━━━━",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(button_text, callback_data='toggle_forwarding')],
                [InlineKeyboardButton("🔙 Back", callback_data='settings')]
            ]),
            parse_mode="HTML"
        )    
    elif query.data == 'toggle_forwarding':
        data = load_user_data()
        user_id = str(query.from_user.id).strip()
        user_data = data["users"].get(user_id, {})
        current_status = user_data.get("forwarding_on", False)
        
        if current_status:
            await off(update, context)
        else:
            await on(update, context)
    elif query.data == 'back':
        await back_to_menu(update, context)
    elif query.data == "words": 
        await keywords_command(update, context)
    elif query.data == "msg_source":
        await message_source(update, context)
    elif query.data == "add_keyword":
        await query.edit_message_text(
            "*How to Add Auto-Reply Keywords:*\n\n"
            "Use the format: `/setword Trigger | Response`\n\n"
            "*Examples:*\n"
            "`/setword Hello | Hi there!`\n"
            "`/setword Price? | The price is $10`\n\n"
            "Note: The `|` symbol separates the trigger word from the response",
            parse_mode="Markdown",
            reply_markup=back_button()
        )
    elif query.data == "del_keyword":
        await query.edit_message_text("Use `/stopword <keyword>` to delete a set word", parse_mode="Markdown", reply_markup=back_button())

    elif query.data == 'add_to_gc':
        await query.edit_message_text(
            "*📥 Add Scraped Users to Group*\n\n"
            "*Usage:*\n"
            "`/addtogc <scraped_group_id> <target_group_link>`\n\n"
            "*Example:*\n"
            "`/addtogc -100123456789 https://t.me/targetgroup`\n\n"
            "*Note:*\n"
            "• Only users with usernames can be added\n"
            "• You must be admin in target group\n"
            "• View scraped group IDs using 'View Scraped Users' button",
            parse_mode="Markdown",
            reply_markup=back_button()
        )

    elif query.data == 'logout':
        await logout(update, context)
    elif query.data == "login_kbd":
        await login_kbd(update, context)
    elif query.data == 'login':
        first_name = query.from_user.first_name
        webapp_url = f"{WEBAPP}/login?user_id={user_id}&first_name={first_name}" 
        await query.edit_message_text(
            "*Telegram Login*\n\n"
            "Click the button below to open the secure login interface.\n\n"
            "📱 You'll be able to enter your phone number and verification code in a user-friendly interface.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔐 Login via Web", web_app={"url": webapp_url})],
                [InlineKeyboardButton("🔐 Login via Keyboard", callback_data='login_kbd')],
                [InlineKeyboardButton("🔙 Back", callback_data='back')]
            ])
        )

    elif query.data == "my_post":
        await my_posts(update, context)
    elif query.data == "my_groups":
        await my_groups(update, context)
    elif query.data == "auto_reply":
        await keyword_settings(update, context)

    elif query.data == 'help':
        help_text = (
        "🤖 <b>Spidertise AUTO FORWARDING Bot Help</b>\n\n"
        "Welcome to the Spidertise AUTO FORWARDING Bot! Here's a guide on how to use the available commands:\n\n"

        "1. <code>/start</code> - Initiates the bot and provides subscription information.\n"
        "   - Displays your current subscription status and expiration date, along with quick links to login and settings.\n\n"

        "2. <code>/post &lt;message&gt;</code> - Sets the message to be forwarded to your groups.\n"
        "   - Example: <code>/post Hello everyone!</code> sets the message <code>Hello everyone!</code> to be forwarded.\nSet telegram message link if you want the message to be forwarded\n"
        "   - Use <code>/mypost</code> to check the posts you have added\n"
        "   - Multiple Posts can be added, use <code>/delpost index \\ message</code> to delete a post\n<code>/delpost all</code> to delete all post set\n\n"
        "2ii. <code>Message Source</code>\n<pre>/msource</pre> - Sets the source of the messages to forward.\n"
        "   - You can choose between <b>My Post 📝</b> or <b>Saved Messages 📥</b>.\n"
        "   - <b>My Post 📝</b> will forward messages from your post messages <code>/post message</code> (default option for all users).\n"
        "   - <b>Saved Messages 📥</b> will forward messages from your saved messages in Telegram.\n"
        "   - You can toggle between the sources at any time through the settings menu.\n"
        "   - The currently selected message source will be displayed in the settings and can be changed anytime.\n\n"
        "3. <code>/addgroup &lt;group_link&gt;</code> - Adds a group to your forwarding list.\n"
        "   - Example: <code>/addgroup https://t.me/mygroupusername</code> adds the group with link <code> https://t.me/mygroupusername</code> to your list for message forwarding.\n\n"

        "4. <code>/delgroup &lt;group_id&gt https://t.me/mygroupusername;</code> - Removes a group from your forwarding list.\n"
        "   - Example: <code>/delgroup  https://t.me/mygroupusername</code> removes the group with link <code>https://t.me/mygroupusernam</code>.\n\n"

        "5. <code>/time &lt;seconds&gt;</code> - Sets the interval between message forwarding in seconds.\n"
        "   - Example: <code>/time 60</code> sets the message forwarding interval to 60 seconds.\n\n"

        "6. <code>/delay &lt;seconds&gt;</code> - Sets delay between forwarding to each group.\n"
        "   - Example: <code>/delay 10</code> sets 10 second delay between each group\n"
        "   - Use <code>/delay 0</code> to disable delay\n\n"

        "7. <code>/listgc</code> - Lists all groups you're a member of.\n"
        "   - Shows detailed information about each group\n"
        "   - Cannot be used while forwarding or auto-reply is active\n"
        "   - Includes pagination for large group lists\n\n"

        "8. <code>/on</code> - Enables automatic message forwarding.\n"
        "   - Before you use this command, make sure you've set the following:\n"
        "     - API ID and API Hash\n"
        "     - Groups to forward messages to\n"
        "     - The post message\n"
        "     - Interval for forwarding\n\n"

        "9. <code>/off</code> - Disables message forwarding.\n"
        "   - This will stop the bot from forwarding messages to any of your groups.\n\n"

        "🔑 <b>API Key and Login Instructions:</b>\n"
        "   1. <b>To log in:</b>\n"
        "      - Use the <code>/start</code> command to initiate the bot. If you're not logged in, use the <code>/login</code> (phone number) and complete the verification process.\n"
        "   2. <b>To add your API keys:</b>\n"
        "      - Ensure you have your Telegram API ID and API Hash.\n"
        "      - Use the <code>/api_id</code> and <code>/hash</code> commands to set them up for forwarding. Ensure your API ID and API Hash are correctly configured in your user settings.\n"
        "      - If you encounter issues with logging in or setting up API keys, check that your credentials are correct and ensure you've completed all required steps.\n\n"
        
        "10. <code>/scrape &lt;group_link&gt;</code> - Scrapes members from groups/channels.\n"
        "   - Example: <code>/scrape https://t.me/groupname</code>\n"
        "   - Supports public groups, private groups, and channels\n"
        "   - Use <code>/target</code> to switch between forwarding to groups or scraped users\n"
        "   - Use <code>/remove_scraped</code> to clear scraped data\n\n"

        "11. <code>/vv</code> - Anti View-Once Media Saver\n"
        "   - Reply to any view-once media with /vv\n"
        "   - Saves media to Saved Messages or current chat based on settings\n"
        "   - Works in both private chats and groups\n"
        "   - Configure save location in Auto Reply settings\n\n"
        
        "12. <code>/addtogc &lt;scraped_group_id&gt; &lt;target_group_link&gt;</code> - Add Scraped Users to Group\n"
        "   - Example: <code>/addtogc -100123456789 https://t.me/targetgroup</code>\n"
        "   - Adds users from scraped group to target group\n"
        "   - Shows success/failure statistics after completion\n"
        "   - Only users with usernames will be added\n\n"

        "13. <code>/deletedgc &lt;group_link&gt;</code> - Anti-Deleted Messages Monitor\n"
        "   - Example: <code>/deletedgc https://t.me/myloggroup</code>\n"
        "   - Sets a group where deleted messages will be forwarded\n"
        "   - Captures both text and media that gets deleted\n"
        "   - Must be enabled in Auto Reply settings after setting group\n"
        "   - Works in both private chats and groups you're in\n\n"

        "14. <code>/conv &lt;amount&gt; &lt;from&gt; &lt;to&gt;</code> - Currency Converter\n"
        "   - Example: <code>/conv 200 usdt btc</code> converts 200 USDT to BTC\n"
        "   - Example: <code>/conv 40 usd eur</code> converts 40 USD to EUR\n"
        "   - Supports various cryptocurrencies and fiat currencies\n"
        "   - Format: /conv [amount] [from_currency] [to_currency]\n"
        "   - Also works with <code>/convert</code> and <code>/c</code>\n\n"
        f"💡 <b>Need more help?</b> Contact the <a href=\"tg://resolve?domain={ADMIN_USERNAME}\">Admin</a> or refer to the tutorial"
    )

        await query.edit_message_text(text=help_text, parse_mode='HTML', reply_markup=back_button())
    elif query.data == 'settings':
        await settings(update, context) 

    elif query.data == 'rmvscraped':
        await query.edit_message_text(
            "*🗑️ Remove Scraped Groups*\n\n"
            "*Usage Options:*\n"
            "1️⃣ Remove Specific Group:\n"
            "`/rmvscraped group_id`\n\n"
            "2️⃣ Remove All Groups:\n"
            "`/rmvscraped all`\n\n"
            "*Examples:*\n"
            "• `/rmvscraped 1234567890`\n"
            "• `/rmvscraped all`\n\n"
            "💡 *Tip:* View your scraped groups and their IDs using the 'View Scraped Users' button in settings",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 View Scraped Users", callback_data='view_scraped')],
                [InlineKeyboardButton("🔙 Back", callback_data='back')]
            ])
        )

    elif query.data == 'mypost':  
        user_data["message_source"] = "mypost"  
        data["users"][user_id] = user_data  
        save_user_data(data)  

        current_source = "My Post"  
        keyboard = [  
            [InlineKeyboardButton(f"📄 My Post {'✅' if current_source == 'My Post' else ''}", callback_data='mypost')],  
            [InlineKeyboardButton(f"📥 Saved Messages {'✅' if current_source == 'Saved Messages' else ''}", callback_data='saved_messages')],  
            [InlineKeyboardButton("🔙 Back", callback_data='settings')]  
        ]  

        await update.callback_query.edit_message_text(  
            "╔═══════════════╗\n"  
            "  🔧 Current Source Settings\n"  
            "╚═══════════════╝\n"  
            "  📄 *My Post* ✅\n"  
            "  📥 *Saved Messages* \n"  
            "─────────────────\n"  
            "Choose an option below:\n",  
            reply_markup=InlineKeyboardMarkup(keyboard),  
            parse_mode="Markdown"  
        )  
    elif query.data == 'view_scraped':
        await view_scraped(update, context)
    elif query.data in ['target_groups', 'target_scraped']:
        new_target = 'groups' if query.data == 'target_groups' else 'scraped'
        data["users"][user_id]["message_target"] = new_target
        save_user_data(data)
        await settings(update, context)
    elif query.data == 'saved_messages':  
        user_data["message_source"] = "saved_messages"  
        data["users"][user_id] = user_data  
        save_user_data(data)  

        current_source = "Saved Messages"  
        keyboard = [  
            [InlineKeyboardButton(f"📄 My Post {'✅' if current_source == 'My Post' else ''}", callback_data='mypost')],  
            [InlineKeyboardButton(f"📥 Saved Messages {'✅' if current_source == 'Saved Messages' else ''}", callback_data='saved_messages')],  
            [InlineKeyboardButton("🔙 Back", callback_data='settings')]  
        ]  

        await update.callback_query.edit_message_text(  
            "╔═══════════════╗\n"  
            " 🔧 Current Source Settings\n"  
            "╚═══════════════╝\n"  
            "  📄 *My Post* \n"  
            "  📥 *Saved Messages* ✅\n"  
            "─────────────────\n"  
            "Choose an option below:\n",  
            reply_markup=InlineKeyboardMarkup(keyboard),  
            parse_mode="Markdown"  
        )

def back_button():
    keyboard = [[InlineKeyboardButton("Back 🔙", callback_data='settings')]]
    return InlineKeyboardMarkup(keyboard)

async def get_json(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    if user_id in ADMIN_IDS:
        try:
            with open('config.json', 'r', encoding='utf-8') as file:
                await update.message.reply_document(
                    document=file,
                    filename='config.json',
                    caption="✨ Here's your current configuration file"
                )
        except Exception as e:
            await update.message.reply_text(f"Error reading config file: {str(e)}")
    else:
        await update.message.reply_text("🔒 This command is restricted to administrators")

async def set_json(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    if user_id in ADMIN_IDS:
        if update.message.reply_to_message and update.message.reply_to_message.document:
            doc = update.message.reply_to_message.document
            if doc.file_name == 'config.json':
                file = await context.bot.get_file(doc.file_id)
                try:
                    await file.download_to_drive('config.json')
                    await update.message.reply_text("✅ Configuration file updated successfully!")
                except Exception as e:
                    await update.message.reply_text(f"❌ Error updating config file: {str(e)}")
            else:
                await update.message.reply_text("📄 Please upload a file named 'config.json'")
        else:
            await update.message.reply_text("↩️ Please reply to a config.json file")
    else:
        await update.message.reply_text("🔒 This command is restricted to administrators")

async def restart_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    if user_id in ADMIN_IDS:
        RENDER_API_KEY = os.getenv("RENDER_API_KEY")
        SERVICE_ID = os.getenv("RENDER_SERVICE_ID")
        
        if not RENDER_API_KEY or not SERVICE_ID:
            await update.message.reply_text(
                "⚠️ *Render API Configuration Missing*\n\n"
                "Please set the following environment variables:\n"
                "• `RENDER_API_KEY`\n"
                "• `RENDER_SERVICE_ID`",
                parse_mode="Markdown"
            )
            return
            
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {RENDER_API_KEY}"
        }
        
        url = f"https://api.render.com/v1/services/{SERVICE_ID}/deploys"
        
        try:
            response = requests.post(url, headers=headers)
            if response.status_code == 201:
                await update.message.reply_text("🔄 Service restart initiated! Allow a few minutes for the process to complete.")
            else:
                await update.message.reply_text(
                    "❌ *This command is for Render hosting users only*\n\n"
                    "If you're using Render, please check your API configuration.",
                    parse_mode="Markdown"
                )
        except Exception as e:
            await update.message.reply_text(
                "❌ *This command is for Render hosting users only*\n\n"
                "If you're using Render, verify your hosting setup and API access.",
                parse_mode="Markdown"
            )
    else:
        await update.message.reply_text("🔒 This command is restricted to administrators")

async def set_deleted_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    
    if not await is_authorized(user_id):
        await update.message.reply_text(f"🔒 <b>Access Restricted</b>\n\n❌ No active subscription found\n✨ Please contact <a href=\"tg://resolve?domain={ADMIN_USERNAME}\">Admin</a> for access", parse_mode="HTML")
        return
    
    if not context.args:
        await update.message.reply_text(
            "📝 *Usage:*\n"
            "`/deletedgc <group_link_or_id>`\n\n"
            "*Examples:*\n"
            "• `/deletedgc https://t.me/mygroup`\n"
            "• `/deletedgc -1001234567890`\n"
            "• `/deletedgc @groupusername`",
            parse_mode="Markdown"
        )
        return
    
    group_link = ' '.join(context.args).strip()
    
    data = load_user_data()
    if user_id not in data["users"]:
        data["users"][user_id] = {}
    
    data["users"][user_id]["deleted_group"] = group_link
    data["users"][user_id]["anti_deleted_enabled"] = True
    save_user_data(data)
    
    await update.message.reply_text(
        f"✅ *Anti-Deleted Messages Setup Complete*\n\n"
        f"📍 *Group Set:* `{group_link}`\n"
        f"🔔 *Status:* Enabled\n\n"
        f"💡 *Note:* Anti-deleted monitoring will activate when Auto-Reply is enabled",
        parse_mode="Markdown"
    )

async def run_bot():
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
    application.add_handler(CommandHandler("msource", message_source))
    application.add_handler(CommandHandler("keywords", keywords_command))
    application.add_handler(CommandHandler("stopword", stopword_command))
    application.add_handler(CommandHandler("scrape", handle_scrape))
    application.add_handler(CommandHandler("target", toggle_target))
    application.add_handler(CommandHandler("time", time))
    application.add_handler(CommandHandler('post', post)) 
    application.add_handler(CommandHandler("restart", restart_service))
    application.add_handler(CommandHandler('mypost', my_posts)) 
    application.add_handler(CommandHandler("delpost", delpost))
    application.add_handler(CommandHandler('list', list_users))
    application.add_handler(CommandHandler("settings", settings))
    application.add_handler(CommandHandler("getjson", get_json))
    application.add_handler(CommandHandler("setjson", set_json))
    application.add_handler(CommandHandler("gettrack", get_track))
    application.add_handler(CommandHandler("settrack", set_track))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("payment", show_payment_options))
    application.add_handler(CommandHandler("rmvscraped", remove_scraped))
    application.add_handler(CommandHandler("addtogc", add_to_group))
    application.add_handler(CommandHandler("ip", get_ip))
    application.add_handler(CommandHandler("fetch", fetch_collectible))
    application.add_handler(CommandHandler("deletedgc", set_deleted_group))
    application.add_handler(CommandHandler("delay", set_delay))
    application.add_handler(CommandHandler("listgc", list_groups_command))




    application.add_handler(CallbackQueryHandler(handle_payment_selection, pattern="^pay_"))
    application.add_handler(CallbackQueryHandler(handle_payment_sent, pattern="^payment_sent$"))
    application.add_handler(CallbackQueryHandler(handle_payment_cancel, pattern="^cancel_payment$"))
    application.add_handler(CallbackQueryHandler(stats, pattern="^refresh_stats$"))
    application.add_handler(CallbackQueryHandler(otp_callback, pattern="^otp_"))
    application.add_handler(CallbackQueryHandler(login_kbd, pattern="^num_"))
    application.add_handler(CallbackQueryHandler(autoreply_callback))
    application.add_handler(CallbackQueryHandler(all_callback))

    await application.initialize()
    await application.start()
    await application.updater.start_polling() 

  



if __name__ == '__main__':
   import uvicorn
   port = int(os.getenv("PORT", 8000))
   uvicorn.run(spider_app, host="0.0.0.0", port=port)
