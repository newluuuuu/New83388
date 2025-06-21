from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telethon.sync import TelegramClient
from telethon import TelegramClient, events
from telethon.tl.types import User, Chat, MessageMediaPhoto, MessageMediaDocument
from telethon.errors.rpcerrorlist import AuthKeyUnregisteredError
from telethon.errors import FloodWaitError
from telethon.tl.types import MessageEntityMentionName
import re
import os
import json
from datetime import datetime, timedelta
import datetime
import asyncio
import json
import logging
from dotenv import load_dotenv
import time

load_dotenv()
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "devscottreal")

FURL = f"https://t.me/{ADMIN_USERNAME}" 
active_clients = {}
last_reply_time = {}

# Anti-deleted message functionality
message_cache = {}
CACHE_EXPIRY = 86400
last_cache_clean = datetime.datetime.now()

def clean_expired_cache():
    current_time = time.time()
    for chat_id, messages in list(message_cache.items()):
        for msg_id, message_data in list(messages.items()):
            if (current_time - message_data["date"].timestamp()) > CACHE_EXPIRY:
                del message_cache[chat_id][msg_id]
        if not message_cache[chat_id]:
            del message_cache[chat_id]

def check_and_clean_cache():
    global last_cache_clean
    current_time = datetime.datetime.now()
    if (current_time - last_cache_clean).total_seconds() >= 86400:
        clean_expired_cache()
        last_cache_clean = current_time

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

async def log_deleted_message(client, sender_id, sender_name, group_name, time_str, content, media=None, deleted_group=None):
    sender_link = f"[{sender_name}](tg://user?id={sender_id})"  
    
    if deleted_group:
        if media:
            caption = (
                "🚫 **DELETED MESSAGE DETECTED**\n\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 **From:** {sender_link}\n"
                f"👥 **Group:** {group_name}\n"
                f"🕒 **Time:** {time_str}\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "📎 **Media Content Attached**"
            )
            try:
                await client.send_file(deleted_group, media, caption=caption, parse_mode="markdown")
                print(f"✅ Deleted media message sent to group: {deleted_group}")
            except Exception as e:
                print(f"❌ Failed to send media to group: {e}")
        else:
            message = (
                "🚫 **DELETED MESSAGE DETECTED**\n\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 **From:** {sender_link}\n"
                f"👥 **Group:** {group_name}\n"
                f"🕒 **Time:** {time_str}\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "📝 **Message Content:**\n"
                f"\n{content if content else 'No text content'}\n\n"
                "━━━━━━━━━━━━━━━━━━━━━"
            )
            try:
                await client.send_message(deleted_group, message, parse_mode="markdown")
                print(f"✅ Deleted message sent to group: {deleted_group}")
            except Exception as e:
                print(f"❌ Failed to send message to group: {e}")

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
    auto_reply_status = "𝙴𝚗𝚊𝚋𝚕𝚎𝚍 ✅" if user_data.get("auto_reply_status", False) else "𝙳𝚒𝚜𝚊𝚋𝚕𝚎𝚍 ❌"
    auto_reply_text = "𝙳𝚒𝚜𝚊𝚋𝚕𝚎 🔴" if user_data.get("auto_reply_status", False) else "𝙴𝚗𝚊𝚋𝚕𝚎 🟢"
    responder_option = user_data.get("responder_option", "𝙿𝙼") 
    save_location = user_data.get("save_location", "chat")
    
    # Anti-deleted messages settings
    anti_deleted_enabled = user_data.get("anti_deleted_enabled", False)
    anti_deleted_text = "Turn Off 🔴" if anti_deleted_enabled else "Turn On 🟢"
    anti_deleted_status = "𝙴𝚗𝚊𝚋𝚕𝚎𝚍 ✅" if anti_deleted_enabled else "𝙳𝚒𝚜𝚊𝚋𝚕𝚎𝚍 ❌"
    deleted_group = user_data.get("deleted_group", "Not Set")
    deleted_monitor_mode = user_data.get("deleted_monitor_mode", "All")  

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
    respond_display = {
        'PM': '𝙿𝚛𝚒𝚟𝚊𝚝𝚎 𝙲𝚑𝚊𝚝',
        'GC': '𝙶𝚛𝚘𝚞𝚙𝚜',
        'All': '𝙳𝙼𝚜 & 𝙶𝚛𝚘𝚞𝚙𝚜'
    }.get(responder_option, responder_option)

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
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

# Add this function to autoreply.py
async def mark_all_messages_read(user_id):
    """Mark all messages as read for the specified user"""
    try:
        client = active_clients.get(user_id)
        
        if not client or not client.is_connected():
            print(f"No active client found for user {user_id}")
            raise Exception("No active client connection found")
        
        # Get all dialogs (chats)
        dialogs = await client.get_dialogs()
        
        marked_count = 0
        failed_count = 0
        skipped_count = 0
        total_dialogs = len(dialogs)
        
        # Filter dialogs to only process those with unread messages
        unread_dialogs = [dialog for dialog in dialogs if dialog.unread_count > 0]
        unread_count = len(unread_dialogs)
        skipped_count = total_dialogs - unread_count
        
        print(f"📊 Found {unread_count} chats with unread messages out of {total_dialogs} total chats")
        print(f"⏭️ Skipping {skipped_count} already read chats")
        
        if unread_count == 0:
            print("✅ All chats are already marked as read!")
            return True
        
        for i, dialog in enumerate(unread_dialogs, 1):
            try:
                # Mark dialog as read
                await client.send_read_acknowledge(dialog.entity)
                marked_count += 1
                print(f"✅ Marked chat '{dialog.name}' as read ({i}/{unread_count}) - {dialog.unread_count} unread messages")
                
                # Small delay to avoid rate limiting
                await asyncio.sleep(0.1)
                
            except Exception as e:
                failed_count += 1
                print(f"❌ Failed to mark chat '{dialog.name}' as read: {e}")
                continue
        
        print(f"📊 Mark as read completed:")
        print(f"   ✅ {marked_count} chats marked as read")
        print(f"   ❌ {failed_count} failed")
        print(f"   ⏭️ {skipped_count} already read (skipped)")
        print(f"   📊 Total processed: {unread_count}/{total_dialogs}")
        
        # Return True if at least some chats were marked successfully or if all were already read
        return marked_count > 0 or unread_count == 0
        
    except Exception as e:
        print(f"Error in mark_all_messages_read: {e}")
        raise e

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

    async def handle_vv_command(event):
        """Handles the /vv command to download a specific self-destructing media."""
        try:
            user_id = str(event.sender_id)
            data = load_user_data()
            if user_id not in data["users"]:
                data["users"][user_id] = {}
            if "save_location" not in data["users"][user_id]:
                data["users"][user_id]["save_location"] = "chat"  
                save_user_data(data)

            save_location = data["users"][user_id]["save_location"]

            reply = await event.message.get_reply_message()
            if not reply or not reply.media:
                await event.reply("Reply to a message containing self-destructing media to use the /vv command.")
                return

            media = reply.media
            is_self_destruct = (
                isinstance(media, (MessageMediaPhoto, MessageMediaDocument)) and
                getattr(media, "ttl_seconds", None) is not None
            )

            if not is_self_destruct:
                await event.reply("The replied-to message does not contain self-destructing media.")
                return

            logger.info("Downloading self-destructing media targeted by /vv command.")

            try:
                download_path = await reply.download_media()
                logger.info(f"Downloaded self-destructing media to {download_path}")

                caption = f"""
                  🎯 *DOWNLOADED*
                  Self-destruct media saved
                  
                  [Made with ❤️ by Spidertise]({FURL})
                  """               
                try:
                    if save_location == "saved":
                        await event.client.send_file("me", download_path, caption=caption, parse_mode='Markdown')
                        await event.reply("✅ Media saved to your Saved Messages")
                    else:
                        await event.client.send_file(event.chat_id, download_path, caption=caption, parse_mode='Markdown')

                except FloodWaitError as e:
                    logger.warning(f"FloodWaitError: Waiting for {e.seconds} seconds")
                    await asyncio.sleep(e.seconds)
                    await event.client.send_file(event.chat_id, download_path, caption=caption, parse_mode='Markdown')
                
                os.remove(download_path)
                logger.info(f"Removed downloaded file from {download_path}")
            except Exception as e:
                logger.error(f"Failed to download media: {e}")
                await event.reply("Failed to download the media.")
        except Exception as e:
            logger.exception(f"Error handling /vv command: {e}")
            await event.reply("An error occurred while processing the /vv command.")

    @client.on(events.NewMessage(pattern='/tag (.+)'))
    async def handle_tag_command(event):
        try:
            sender = await event.get_sender()
            chat = await event.get_input_chat()
            message_text = event.pattern_match.group(1)
            
            try:
                from telethon.tl.functions.messages import SendReactionRequest
                from telethon.tl.types import ReactionEmoji
                
                reaction = ReactionEmoji(emoticon='👍')
                await client(SendReactionRequest(
                    peer=chat,
                    msg_id=event.message.id,
                    reaction=[reaction]
                ))
            except Exception as react_error:
                print(f"Couldn't add reaction: {react_error}")
            
            await client.send_message(sender, "Starting to tag all members at once.")
            
            all_participants = []
            async for participant in client.iter_participants(chat):
                if not participant.bot and participant.id != sender.id:
                    all_participants.append(participant)
            
            if not all_participants:
                await client.send_message(sender, "No participants found to tag.")
                return
            
            total_members = len(all_participants)
            await client.send_message(sender, f"Found {total_members} members to tag.")
            
            mentions = ""
            successful_tags = 0
            skipped_tags = 0
            
            for user in all_participants:
                try:
                    mentions += f"[​](tg://user?id={user.id})"
                    successful_tags += 1
                except Exception as e:
                    print(f"Couldn't tag user {user.id}: {e}")
                    skipped_tags += 1
                    continue
            
            try:
                sent_message = await client.send_message(
                    chat,
                    mentions + message_text,
                    parse_mode='md'
                )
                
                if sent_message:
                    await client.send_message(
                        sender,
                        f"Tagging complete!\n"
                        f"Total members: {total_members}\n"
                        f"Successfully tagged: {successful_tags}\n"
                        f"Skipped: {skipped_tags}"
                    )
                else:
                    await client.send_message(
                        sender,
                        f"Failed to send the tag message."
                    )
            
            except Exception as e:
                print(f"Error sending tag message: {e}")
                await client.send_message(
                    sender,
                    f"Error sending tag message: {e}"
                )
            
            await asyncio.sleep(4)
            await event.delete()
            
        except Exception as e:
            print(f"Error in tag command: {e}")
            sender = await event.get_sender()
            await client.send_message(sender, f"Failed to tag members: {str(e)}")

    @client.on(events.NewMessage)
    async def cache_message_handler(event):
        """Cache messages for anti-deleted functionality"""
        check_and_clean_cache()
        
        # Check if anti-deleted is enabled for this user
        data = load_user_data()
        user_data = data["users"].get(user_id, {})
        if not user_data.get("anti_deleted_enabled", False):
            return

        monitor_mode = user_data.get("deleted_monitor_mode", "All")
        is_group = event.is_group

        if (monitor_mode == "Groups" and not is_group) or (monitor_mode == "Private" and is_group):
            return
            
        message_data = {
            "sender_id": event.sender_id,  
            "sender": await event.get_sender(),
            "text": event.message.message,
            "date": event.message.date,
            "media": event.message.media,  
        }

        if event.chat_id:
            if event.chat_id not in message_cache:
                message_cache[event.chat_id] = {}
            message_cache[event.chat_id][event.id] = message_data
            
        else:
            sender_id = event.sender_id
            if sender_id not in message_cache:
                message_cache[sender_id] = {}
            message_cache[sender_id][event.id] = message_data
            

    @client.on(events.MessageDeleted)
    async def on_message_deleted(event):
        """Handle deleted messages"""
        check_and_clean_cache()
        
        # Check if anti-deleted is enabled for this user
        data = load_user_data()
        user_data = data["users"].get(user_id, {})
        if not user_data.get("anti_deleted_enabled", False):
            return
            
        deleted_group = user_data.get("deleted_group")
        if not deleted_group:
            return
            
        print(f"Deleted event detected: Chat {event.chat_id}, Message IDs {event.deleted_ids}")

        for msg_id in event.deleted_ids:
            if event.chat_id:
                try:
                    entity = await client.get_entity(event.chat_id)
                    
                    if event.chat_id in message_cache and msg_id in message_cache[event.chat_id]:
                        message_data = message_cache[event.chat_id].pop(msg_id, None)
                        if message_data:
                            sender_id = message_data["sender_id"]
                            sender_name = message_data["sender"].first_name if message_data["sender"] else "Unknown"
                            time_str = message_data["date"].strftime("%Y-%m-%d %H:%M:%S")
                            content = message_data["text"] or "Media/Non-text content"
                            media = message_data["media"]
                            group_name = ""
                            try:
                                entity = await client.get_entity(event.chat_id)
                                group_name = entity.title if hasattr(entity, 'title') else 'Unknown Group'
                            except Exception as e:
                                group_name = "Unknown Group"
                                print(f"Failed to fetch group name: {e}")

                            await log_deleted_message(client, sender_id, sender_name, group_name, time_str, content, media, deleted_group)
                            print(f"Deleted group message logged from {sender_name} in group {group_name}: {content}")
                            
                except Exception as e:
                    print(f"Failed to process group message: {e}")
            else:
                # Handle private message deletions
                for sender_id_cache in message_cache:
                    if msg_id in message_cache[sender_id_cache]:
                        message_data = message_cache[sender_id_cache].pop(msg_id, None)
                        if message_data:
                            sender_name = message_data["sender"].first_name if message_data["sender"] else "Unknown"
                            content = message_data["text"] or "Media/Non-text content"
                            time_str = message_data["date"].strftime("%Y-%m-%d %H:%M:%S")
                            media = message_data["media"]

                            await log_deleted_message(client, sender_id_cache, sender_name, "Private Chat", time_str, content, media, deleted_group)
                            print(f"Deleted DM message logged from {sender_name}: {content}")
                        break

    @client.on(events.NewMessage)
    async def handler(event):
        try:
            chat = await event.get_chat()
            chat_id = chat.id
            chat_name = chat.title if hasattr(chat, 'title') else chat.username or chat_id
            message_text = event.message.message

            if message_text.startswith('/vv') and event.message.is_reply:
                await handle_vv_command(event)
                return
            

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

                    elif responder_option == "All":
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
