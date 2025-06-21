import json
from collections import defaultdict
from telegram import Update
from telegram.ext import ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv
import os
load_dotenv()

ADMIN_IDS = os.getenv("ADMIN_IDS").split(',')


def load_tracking_stats():
    try:
        with open('track.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return defaultdict(lambda: {
            "total_forwards": 0,
            "successful": 0,
            "failed": 0,
            "groups": defaultdict(int)
        })
    except json.JSONDecodeError:
        return defaultdict(lambda: {
            "total_forwards": 0,
            "successful": 0,
            "failed": 0,
            "groups": defaultdict(int)
        })

def save_tracking_stats(stats):
    with open('track.json', 'w') as f:
        json.dump(stats, f, indent=4)

async def track_forward(user_id, success, group=None):
    stats = load_tracking_stats()
    
    if user_id not in stats:
        stats[user_id] = {
            "total_forwards": 0,
            "successful": 0,
            "failed": 0,
            "groups": {}
        }
    
    stats[user_id]["total_forwards"] += 1
    stats[user_id]["successful" if success else "failed"] += 1
    
    if group:
        if "groups" not in stats[user_id]:
            stats[user_id]["groups"] = {}
        if group not in stats[user_id]["groups"]:
            stats[user_id]["groups"][group] = 0
        stats[user_id]["groups"][group] += 1
    
    save_tracking_stats(stats)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Handle both direct commands and callback queries
    if update.callback_query:
        user_id = str(update.callback_query.from_user.id)
        message = update.callback_query.message
        await update.callback_query.answer()  # Acknowledge the button press
    else:
        user_id = str(update.message.from_user.id)
        message = update.message
    from main import is_authorized
    if await is_authorized(user_id):
        stats = load_tracking_stats()
        user_stats = stats.get(user_id, {
            "total_forwards": 0,
            "successful": 0,
            "failed": 0,
            "groups": {}
        })
        
        stats_text = (
            "📊 *Forwarding Statistics*\n\n"
            f"Total Messages: `{user_stats['total_forwards']}`\n"
            f"✅ Successful: `{user_stats['successful']}`\n" 
            f"❌ Failed: `{user_stats['failed']}`\n\n"
            "*Group Statistics:*\n"
        )
        
        for group, count in user_stats.get("groups", {}).items():
            stats_text += f"`{group}`: {count} messages\n"
            
        keyboard = [[InlineKeyboardButton("🔄 Refresh Stats", callback_data='refresh_stats')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.callback_query:
            await message.edit_text(stats_text, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await message.reply_text(stats_text, reply_markup=reply_markup, parse_mode="Markdown")

async def get_track(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    if user_id in ADMIN_IDS:
        try:
            with open('track.json', 'r', encoding='utf-8') as file:
                await update.message.reply_document(
                    document=file,
                    filename='track.json',
                    caption="✨ Here's your current tracking stats file"
                )
        except Exception as e:
            await update.message.reply_text(f"Error reading track file: {str(e)}")
    else:
        await update.message.reply_text("🔒 This command is restricted to administrators")

async def set_track(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    if user_id in ADMIN_IDS:
        if update.message.reply_to_message and update.message.reply_to_message.document:
            doc = update.message.reply_to_message.document
            if doc.file_name == 'track.json':
                file = await context.bot.get_file(doc.file_id)
                try:
                    await file.download_to_drive('track.json')
                    await update.message.reply_text("✅ Tracking stats file updated successfully!")
                except Exception as e:
                    await update.message.reply_text(f"❌ Error updating track file: {str(e)}")
            else:
                await update.message.reply_text("📄 Please upload a file named 'track.json'")
        else:
            await update.message.reply_text("↩️ Please reply to a track.json file")
    else:
        await update.message.reply_text("🔒 This command is restricted to administrators")
