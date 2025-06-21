from telethon import TelegramClient, functions
from telethon.tl.types import ChannelParticipantsAdmins
import json
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import asyncio
import random
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import InviteToChannelRequest
import json
import os
from telethon.tl.functions.messages import GetWebPagePreviewRequest
import re
import aiohttp
import io
from telegram import InputMediaPhoto

async def scrape_members(client, group_id):
    """Scrape members from a group"""
    try:
        me = await client.get_me()
        participants = await client.get_participants(group_id)
        members = []
        usernames = []
        for user in participants:
            if not user.bot and user.id != me.id:
                members.append(str(user.id))
                if user.username:
                    usernames.append(user.username)
        return members, usernames
    except Exception as e:
        print(f"Error scraping members: {e}")
        return None, None

def save_scraped_members(user_id, group_id, members, group_title, usernames):
    """Save scraped members to user's data"""
    with open("config.json", "r") as f:
        data = json.load(f)
    
    if "scraped_groups" not in data["users"][user_id]:
        data["users"][user_id]["scraped_groups"] = {}
    
    data["users"][user_id]["scraped_groups"][group_id] = {
        "members": members,
        "title": group_title,
        "usernames": usernames
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
                members,usernames = await scrape_members(client, group_id)
                if members:
                    save_scraped_members(user_id, str(group_id), members, entity.title, usernames)
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
        members, usernames = await scrape_members(client, group_id)
        
        if members:
            save_scraped_members(user_id, str(group_id), members, entity.title, usernames)
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


async def add_to_group(update, context):
    """Add scraped users to target group"""
    user_id = str(update.message.from_user.id)
    
    if len(context.args) != 2:
        await update.message.reply_text(
            "*Usage:*\n"
            "• `/addtogc <scraped_group_id> <target_group_link>`\n\n"
            "*Example:*\n"
            "• `/addtogc -100123456789 https://t.me/targetgroup`",
            parse_mode="Markdown"
        )
        return

    progress_msg = await update.message.reply_text("*🔄 Processing...*", parse_mode="Markdown")
    
    try:
        scraped_group_id = context.args[0]
        target_group = context.args[1]
        
        with open("config.json", "r") as f:
            data = json.load(f)
        
        user_data = data["users"].get(user_id)
        scraped_groups = user_data.get("scraped_groups", {})
        
        if scraped_group_id not in scraped_groups:
            await progress_msg.edit_text("❌ *Scraped group ID not found*", parse_mode="Markdown")
            return
            
        session_file = f'{user_id}.session'
        if not os.path.exists(session_file):
            await progress_msg.edit_text("*You need to log in first!*\nUse `/login` command", parse_mode="Markdown")
            return

        client = TelegramClient(session_file, user_data["api_id"], user_data["api_hash"])
        
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            await progress_msg.edit_text("*Session expired!*\nPlease log in again using `/login`", parse_mode="Markdown")
            return

        target_entity = await get_target_entity(client, target_group)
        if not target_entity:
            await progress_msg.edit_text("❌ *Invalid target group*", parse_mode="Markdown")
            return
        
        usernames = scraped_groups[scraped_group_id]["usernames"]
        total_users = len(usernames)
        successful_adds = 0
        failed_adds = 0
        
        await progress_msg.edit_text("*🔄 Adding users in batches...*", parse_mode="Markdown")
        
        batch_size = 15
        for i in range(0, len(usernames), batch_size):
            batch = usernames[i:i + batch_size]
            try:
                await client(InviteToChannelRequest(
                    channel=target_entity,
                    users=batch
                ))
                successful_adds += len(batch)
                
                await update_progress(progress_msg, total_users, successful_adds, failed_adds)
                await asyncio.sleep(random.uniform(15, 30))
                
            except errors.FloodWaitError as e:
                wait_time = e.seconds
                await progress_msg.edit_text(
                    f"*⏳ Flood wait: {wait_time} seconds*\n"
                    f"Current progress:\n"
                    f"Added: `{successful_adds}`\n"
                    f"Failed: `{failed_adds}`",
                    parse_mode="Markdown"
                )
                await asyncio.sleep(wait_time)
                i -= batch_size
                continue
            except Exception as e:
                print(f"Batch add failed: {str(e)}")
                failed_adds += len(batch)
        
        await update_progress(progress_msg, total_users, successful_adds, failed_adds, final=True)
        
    except Exception as e:
        await progress_msg.edit_text(f"❌ *Error:* `{str(e)}`", parse_mode="Markdown")
    finally:
        if 'client' in locals():
            await client.disconnect()


async def get_target_entity(client, target_group):
    try:
        if target_group.startswith('https://t.me/'):
            if '/+' in target_group:
                invite_hash = target_group.split('+')[1]
                return await client.get_entity(invite_hash)
            else:
                username = target_group.split('/')[-1]
                return await client.get_entity(username)
        elif target_group.startswith('-100') and target_group[4:].isdigit():
            return await client.get_entity(int(target_group))
        elif target_group.lstrip('-').isdigit():
            return await client.get_entity(int(target_group))
        return None
    except Exception as e:
        print(f"Error getting target entity: {e}")
        return None

async def add_user_to_group(client, target_entity, username):
    try:
        await client(InviteToChannelRequest(
            channel=target_entity,
            users=[username]
        ))
    
    except errors.UserPrivacyRestrictedError:
        print(f"User {username} has privacy restrictions")
        raise
    except errors.UserNotMutualContactError:
        print(f"User {username} is not a mutual contact")
        raise
    except errors.UserChannelsTooMuchError:
        print(f"User {username} is in too many channels")
        raise
    except Exception as e:
        print(f"Unexpected error adding {username}: {e}")
        raise

async def update_progress(progress_msg, total_users, successful_adds, failed_adds, final=False):
    status = "Complete" if final else "In Progress"
    stats_message = (
        f"📊 *Addition {status}*\n\n"
        f"Total Users: `{total_users}`\n"
        f"Successfully Added: `{successful_adds}`\n"
        f"Failed Additions: `{failed_adds}`"
    )
    await progress_msg.edit_text(stats_message, parse_mode="Markdown")


# async def fetch_collectible(update, context):
#     """Fetch details of a Telegram NFT collectible"""
#     user_id = str(update.message.from_user.id)
    
#     if not context.args:
#         await update.message.reply_text(
#             "*Usage:*\n"
#             "• `/fetch <collectible_link>`\n\n"
#             "*Example:*\n"
#             "• `/fetch https://t.me/nft/durovscap-276`\n",
#             parse_mode="Markdown"
#         )
#         return

#     collectible_link = context.args[0]
    
#     # Validate the link format
#     if not re.match(r'https://t\.me/nft/[\w-]+', collectible_link):
#         await update.message.reply_text(
#             "❌ *Invalid collectible link format*\n"
#             "Link should be like: `https://t.me/nft/durovscap-276`",
#             parse_mode="Markdown"
#         )
#         return
    
#     progress_msg = await update.message.reply_text("*🔄 Fetching collectible details...*", parse_mode="Markdown")
    
#     with open("config.json", "r") as f:
#         data = json.load(f)
    
#     user_data = data["users"].get(user_id)
#     session_file = f'{user_id}.session'

#     if not os.path.exists(session_file):
#         await progress_msg.edit_text("*You need to log in first!*\nUse `/login` command", parse_mode="Markdown")
#         return

#     client = TelegramClient(session_file, user_data["api_id"], user_data["api_hash"])
    
#     try:
#         await client.connect()
        
#         if not await client.is_user_authorized():
#             await progress_msg.edit_text("*Session expired!*\nPlease log in again using `/login`", parse_mode="Markdown")
#             return
        
#         # Get webpage preview to extract collectible details
#         webpage_result = await client(GetWebPagePreviewRequest(collectible_link))
#         print(f"Webpage result type: {type(webpage_result)}")
#         print(f"Webpage result attributes: {dir(webpage_result)}")

        
#         if not webpage_result:
#             await progress_msg.edit_text("❌ *Failed to fetch collectible details*", parse_mode="Markdown")
#             return
        
#         webpage = webpage_result
        
#         # Extract collectible details
#         title = getattr(webpage, 'title', 'Unknown Collectible')
#         description = getattr(webpage, 'description', 'No description available')
        
#         # Extract attributes from description
#         attributes = {}
#         for line in description.split('\n'):
#             if ':' in line:
#                 key, value = line.split(':', 1)
#                 attributes[key.strip()] = value.strip()
        
#         model = attributes.get('Model', 'Unknown')
#         backdrop = attributes.get('Backdrop', 'Unknown')
#         symbol = attributes.get('Symbol', 'Unknown')
        
#         # Extract image if available
#         image_url = None
#         if hasattr(webpage, 'photo'):
#             # Download the image
#             image_data = await client.download_media(webpage.photo, bytes)
#             image_url = True
        
#         # Prepare response message with a different font style
#         details_message = (
#             f"✨ *{title}* ✨\n\n"
#             f"🔹 𝗠𝗼𝗱𝗲𝗹: `{model}`\n"
#             f"🔹 𝗕𝗮𝗰𝗸𝗱𝗿𝗼𝗽: `{backdrop}`\n"
#             f"🔹 𝗦𝘆𝗺𝗯𝗼𝗹: `{symbol}`\n\n"
#             f"🔗 [𝗩𝗶𝗲𝘄 𝗢𝗻 𝗧𝗲𝗹𝗲𝗴𝗿𝗮𝗺]({collectible_link})"
#         )
        
#         # Send the image with caption if available, otherwise just the text
#         if image_url:
#             await progress_msg.delete()
#             with io.BytesIO(image_data) as photo_file:
#                 photo_file.name = f"{title.replace(' ', '_')}.jpg"
#                 await update.message.reply_photo(
#                     photo=photo_file,
#                     caption=details_message,
#                     parse_mode="Markdown"
#                 )
#         else:
#             await progress_msg.edit_text(details_message, parse_mode="Markdown")
            
#     except Exception as e:
#         print(f"❌ *Error fetching collectible:* `{str(e)}`")
#     finally:
#         if client.is_connected():
#             await client.disconnect()


async def fetch_collectible(update, context):
    """Fetch details of a Telegram NFT collectible"""
    user_id = str(update.message.from_user.id)
    
    if not context.args:
        await update.message.reply_text(
            "*Usage:*\n"
            "• `/fetch <collectible_link>`\n\n"
            "*Example:*\n"
            "• `/fetch https://t.me/nft/durovscap-276`\n",
            parse_mode="Markdown"
        )
        return

    collectible_link = context.args[0]
    
    # Validate the link format
    if not re.match(r'https://t\.me/nft/[\w-]+', collectible_link):
        await update.message.reply_text(
            "❌ *Invalid collectible link format*\n"
            "Link should be like: `https://t.me/nft/durovscap-276`",
            parse_mode="Markdown"
        )
        return
    
    progress_msg = await update.message.reply_text("*🔄 Fetching collectible details...*", parse_mode="Markdown")
    
    with open("config.json", "r") as f:
        data = json.load(f)
    
    user_data = data["users"].get(user_id)
    session_file = f'{user_id}.session'

    if not os.path.exists(session_file):
        await progress_msg.edit_text("*You need to log in first!*\nUse `/login` command", parse_mode="Markdown")
        return

    client = TelegramClient(session_file, user_data["api_id"], user_data["api_hash"])
    
    try:
        await client.connect()
        
        if not await client.is_user_authorized():
            await progress_msg.edit_text("*Session expired!*\nPlease log in again using `/login`", parse_mode="Markdown")
            return
        
        # Get webpage preview to extract collectible details
        response = await client(GetWebPagePreviewRequest(collectible_link))
        
        # Debug the response structure
        print(f"Response type: {type(response)}")
        print(f"Response attributes: {dir(response)}")
        
        # The correct attribute is 'webpage' directly on the response
        if not response or not hasattr(response, 'webpage'):
            await progress_msg.edit_text("❌ *Failed to fetch collectible details*", parse_mode="Markdown")
            return
        
        webpage = response.webpage
        
        # Extract collectible details
        title = getattr(webpage, 'title', 'Unknown Collectible')
        description = getattr(webpage, 'description', 'No description available')
        
        # Extract attributes from description
        attributes = {}
        for line in description.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                attributes[key.strip()] = value.strip()
        
        model = attributes.get('Model', 'Unknown')
        backdrop = attributes.get('Backdrop', 'Unknown')
        symbol = attributes.get('Symbol', 'Unknown')
        
        # Prepare response message
        details_message = (
            f"✨ *{title}* ✨\n\n"
            f"🔹 𝗠𝗼𝗱𝗲𝗹: `{model}`\n"
            f"🔹 𝗕𝗮𝗰𝗸𝗱𝗿𝗼𝗽: `{backdrop}`\n"
            f"🔹 𝗦𝘆𝗺𝗯𝗼𝗹: `{symbol}`\n\n"
            f"🔗 [𝗩𝗶𝗲𝘄 𝗢𝗻 𝗧𝗲𝗹𝗲𝗴𝗿𝗮𝗺]({collectible_link})"
        )
        
        # Try to get image but don't fail if we can't
        image_data = None
        try:
            if hasattr(webpage, 'photo'):
                # Set a timeout for the download operation
                image_data = await asyncio.wait_for(
                    client.download_media(webpage.photo, bytes),
                    timeout=10  # 10 seconds timeout
                )
        except (asyncio.TimeoutError, Exception) as img_err:
            print(f"Image download failed: {img_err}")
            # Continue without the image
        
        # Send the response
        if image_data:
            await progress_msg.delete()
            with io.BytesIO(image_data) as photo_file:
                photo_file.name = f"{title.replace(' ', '_')}.jpg"
                await update.message.reply_photo(
                    photo=photo_file,
                    caption=details_message,
                    parse_mode="Markdown"
                )
        else:
            # Just send the text if we couldn't get the image
            await progress_msg.edit_text(details_message, parse_mode="Markdown")
            
    except Exception as e:
        print(f"Error fetching collectible: {str(e)}")
        await progress_msg.edit_text(f"❌ *Error fetching collectible:* `{str(e)}`", parse_mode="Markdown")
    finally:
        if client.is_connected():
            await client.disconnect()

