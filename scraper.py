from telethon import TelegramClient, functions
from telethon.tl.types import ChannelParticipantsAdmins
import json
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
async def scrape_members(client, group_id):
    """Scrape members from a group"""
    try:
        me = await client.get_me()
        participants = await client.get_participants(group_id)
        return [str(user.id) for user in participants if not user.bot and user.id != me.id]
    except Exception as e:
        print(f"Error scraping members: {e}")
        return None

def save_scraped_members(user_id, group_id, members, group_title):
    """Save scraped members to user's data"""
    with open("config.json", "r") as f:
        data = json.load(f)
    
    if "scraped_groups" not in data["users"][user_id]:
        data["users"][user_id]["scraped_groups"] = {}
    
    data["users"][user_id]["scraped_groups"][group_id] = {
        "members": members,
        "title": group_title
    }
    data["users"][user_id]["message_target"] = "groups" 
    
    with open("config.json", "w") as f:
        json.dump(data, f, indent=4)

async def handle_scrape(update, context):
    """Handle /scrape command with enhanced group identification"""
    user_id = str(update.message.from_user.id)
    
    if not context.args:
        await update.message.reply_text(
            "*Usage:*\n"
            "• `/scrape <group_link>`\n"
            "• `/scrape <group_id>`\n\n"
            "*Supported formats:*\n"
            "• https://t.me/groupname\n"
            "• https://t.me/+privatehash\n"
            "• -100123456789\n",
            parse_mode="Markdown"
        )
        return

    group_identifier = context.args[0]
    
    with open("config.json", "r") as f:
        data = json.load(f)
    
    user_data = data["users"].get(user_id)
    session_file = f'{user_id}.session'

    if not os.path.exists(session_file):
        await update.message.reply_text("*You need to log in first!*\nUse `/login` command", parse_mode="Markdown")
        return

    client = TelegramClient(session_file, user_data["api_id"], user_data["api_hash"])
    
    try:
        if client.is_connected():
            await client.disconnect()
            
        await client.connect()
        
        if not await client.is_user_authorized():
            await update.message.reply_text("*Session expired!*\nPlease log in again using `/login`", parse_mode="Markdown")
            return

        progress_msg = await update.message.reply_text("*🔄 Processing group/channel...*", parse_mode="Markdown")
        
        print(f"Attempting to scrape group: {group_identifier}")
        
        group_id = await extract_group_id(client, group_identifier)
        if not group_id:
            print(f"Failed to extract group ID from: {group_identifier}")
            await progress_msg.edit_text("❌ *Invalid group/channel identifier*", parse_mode="Markdown")
            return

        try:
            entity = await client.get_entity(group_id)
            print(f"Successfully got entity: {entity.id} | Type: {type(entity).__name__}")
            
            try:
                members = await scrape_members(client, group_id)
                if members:
                    save_scraped_members(user_id, str(group_id), members, entity.title)
                    await progress_msg.edit_text(
                        f"✅ *Successfully scraped {len(members)} members from* `{entity.title}`",
                        parse_mode="Markdown"
                    )
                    return
            except Exception as e:
                print(f"Failed to get members directly: {e}")
                await progress_msg.edit_text("❌ *You don't have permission to view members*", parse_mode="Markdown")
                return
                
        except Exception as e:
            print(f"Error accessing group: {str(e)}")
            await progress_msg.edit_text(f"❌ *Access failed:* `{str(e)}`", parse_mode="Markdown")
            return


        await progress_msg.edit_text("*🔄 Scraping members...*", parse_mode="Markdown")
        members = await scrape_members(client, group_id)
        
        if members:
            save_scraped_members(user_id, str(group_id), members, entity.title)
            await progress_msg.edit_text(
                        f"✅ *Successfully scraped {len(members)} members from* `{entity.title}`",
                        parse_mode="Markdown"
                    )
        else:
            await progress_msg.edit_text("❌ *Failed to scrape members*", parse_mode="Markdown")
            
    except Exception as e:
        await update.message.reply_text(f"❌ *Error:* `{str(e)}`", parse_mode="Markdown")
    finally:
        if client.is_connected():
            await client.disconnect()

async def toggle_target(update, context):
    """Toggle between sending to groups or scraped users"""
    user_id = str(update.message.from_user.id)
    
    with open("config.json", "r") as f:
        data = json.load(f)
        
    current_target = data["users"][user_id].get("message_target", "groups")
    new_target = "scraped" if current_target == "groups" else "groups"
    
    data["users"][user_id]["message_target"] = new_target
    
    with open("config.json", "w") as f:
        json.dump(data, f, indent=4)
        
    await update.message.reply_text(f"Message target switched to: {new_target}")

async def view_scraped(update, context):
    """View scraped users callback handler"""
    query = update.callback_query
    user_id = str(query.from_user.id)
    
    with open("config.json", "r") as f:
        data = json.load(f)
    
    user_data = data["users"].get(user_id, {})
    scraped_groups = user_data.get("scraped_groups", {})
    
    if not scraped_groups:
        await query.edit_message_text(
            "*📊 Scraped Users Overview*\n\n"
            "No scraped users found.\n"
            "*Usage:*\n"
            "• `/scrape <group_link>`\n"
            "• `/scrape <group_id>`\n\n",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data="settings")
            ]])
        )
        return
        
    message = "*📊 Scraped Users Overview*\n\n"
    total_users = 0
    
    for group_id, group_data in scraped_groups.items():
        members = group_data["members"]
        user_count = len(members)
        group_title = group_data.get("title", f"Group with {user_count} users")
        total_users += user_count
        message += f"*Group:* `{group_title} || `{group_id}``\n"
        message += f"*Users:* `{user_count}`\n\n"
    
    message += f"*Total Scraped Users:* `{total_users}`"
    
    await query.edit_message_text(
        message,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Back", callback_data="settings")
        ]])
    )

async def extract_group_id(client, group_link):
    """Extract group/channel ID from link or ID string"""
    try:
        if group_link.startswith('https://t.me/'):
            if '/+' in group_link:  # Private group
                hash_id = group_link.split('+')[1]
                group = await client(functions.messages.CheckChatInviteRequest(hash=hash_id))
                return group.chat.id
            else:  # Public group/channel
                username = group_link.split('/')[-1]
                entity = await client.get_entity(username)
                return entity.id
        elif group_link.startswith('-100') and group_link[4:].isdigit():
            return int(group_link)
        elif group_link.lstrip('-').isdigit():
            return int(group_link)
        return None
    except Exception as e:
        print(f"Error extracting group ID: {e}")
        return None
    

async def remove_scraped(update, context):
    """Remove scraped data for specific group or all groups"""
    user_id = str(update.message.from_user.id)
    
    if not context.args:
        await update.message.reply_text(
            "*Usage:*\n"
            "• `/rmvscraped 123456789` - Remove specific group\n"
            "• `/rmvscraped all` - Remove all scraped data\n",
            parse_mode="Markdown"
        )
        return

    target = context.args[0].lower()
    
    with open("config.json", "r") as f:
        data = json.load(f)
    
    user_data = data["users"].get(user_id, {})
    scraped_groups = user_data.get("scraped_groups", {})
    
    if not scraped_groups:
        await update.message.reply_text("*No scraped data found*", parse_mode="Markdown")
        return
        
    if target == 'all':
        user_data["scraped_groups"] = {}
        removed_msg = "✅ *All scraped data has been removed*"
    else:
        if target in scraped_groups:
            group_title = scraped_groups[target].get("title", target)
            del scraped_groups[target]
            removed_msg = f"✅ *Removed scraped data from:*\n`{group_title}`"
        else:
            await update.message.reply_text("❌ *Group ID not found in scraped data*", parse_mode="Markdown")
            return
    
    data["users"][user_id] = user_data
    with open("config.json", "w") as f:
        json.dump(data, f, indent=4)
        
    await update.message.reply_text(removed_msg, parse_mode="Markdown")
