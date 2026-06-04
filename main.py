# ============================================================
# VIDEO MONETIZATION TELEGRAM BOT
# ============================================================
# Single file - Ready for Render / Any Web Service
# ============================================================

import os
import sys
import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta

# --- Pyrogram ---
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    CallbackQuery,
    Message
)
from pyrogram.errors import UserNotParticipant, FloodWait

# ============================================================
# CONFIGURATION - Environment Variables
# ============================================================

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

OWNER_ID = 6501901607  # Your Telegram User ID

# Channel 1
CHANNEL_1_LINK = "https://t.me/+awB_9F3KdV82ZWZl"
CHANNEL_1_ID = -1004295662200
CHANNEL_1_NAME = "𝐇𝐢𝐧𝐨𝐯𝐢𝐱𝐚"

# Channel 2
CHANNEL_2_LINK = "https://t.me/+EDVjhWCNhTk0MDBl"
CHANNEL_2_ID = -1004297747395
CHANNEL_2_NAME = "𝐇𝐢𝐧𝐨𝐯𝐢𝐱𝐚 𝐛𝐚𝐜𝐤𝐮𝐩"

# Settings
DELETE_AFTER_MINUTES = 30

# ============================================================
# VALIDATE CONFIGURATION
# ============================================================

if not API_ID or not API_HASH or not BOT_TOKEN:
    print("ERROR: API_ID, API_HASH, and BOT_TOKEN must be set as environment variables!")
    sys.exit(1)

# ============================================================
# SETUP LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ============================================================
# DATA STORAGE (Simple JSON - works on Render)
# ============================================================

DATA_FILE = "bot_data.json"

def load_data():
    """Load bot data from JSON file"""
    default_data = {
        "users": {},        # Stores all user info
        "videos": {},       # Stores all uploaded videos
        "stats": {          # Running statistics
            "total_users": 0,
            "total_videos_sent": 0,
            "total_verified": 0,
            "total_rejected": 0
        }
    }
    
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Ensure all keys exist
                for key in default_data:
                    if key not in data:
                        data[key] = default_data[key]
                return data
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            return default_data
    return default_data

def save_data():
    """Save bot data to JSON file"""
    global bot_data
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(bot_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving data: {e}")

bot_data = load_data()

# ============================================================
# INITIALIZE BOT
# ============================================================

app = Client(
    "video_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ============================================================
# HELPER FUNCTIONS
# ============================================================

async def is_member_of_channel(user_id: int, channel_id: int) -> bool:
    """
    Check if user is a member of a specific channel.
    Bot must be admin in the channel for this to work.
    """
    try:
        member = await app.get_chat_member(chat_id=channel_id, user_id=user_id)
        # Valid member statuses
        return member.status in ["member", "administrator", "creator"]
    except UserNotParticipant:
        return False
    except Exception as e:
        logger.error(f"Error checking membership for user {user_id} in channel {channel_id}: {e}")
        return False

async def check_both_channels(user_id: int):
    """Check if user has joined BOTH channels"""
    ch1 = await is_member_of_channel(user_id, CHANNEL_1_ID)
    ch2 = await is_member_of_channel(user_id, CHANNEL_2_ID)
    return (ch1 and ch2), ch1, ch2

def get_join_buttons():
    """
    Create inline keyboard with:
    - Row 1: [Channel 1 Button] [Channel 2 Button]
    - Row 2: [I Have Joined Both Channels]
    """
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(CHANNEL_1_NAME, url=CHANNEL_1_LINK),
            InlineKeyboardButton(CHANNEL_2_NAME, url=CHANNEL_2_LINK)
        ],
        [
            InlineKeyboardButton("✅ I Have Joined Both Channels", callback_data="verify_join")
        ]
    ])
    return buttons

def format_join_message(ch1_ok: bool, ch2_ok: bool) -> str:
    """Format the join channels message"""
    msg = (
        "**You need to join the following channels first:**\n\n"
        f"{'✅' if ch1_ok else '❌'} {CHANNEL_1_NAME}\n"
        f"{'✅' if ch2_ok else '❌'} {CHANNEL_2_NAME}\n\n"
        "**Click the buttons below to join, then click verify.**"
    )
    return msg

async def register_user(user_id: int, username: str, first_name: str):
    """Register or update user in database"""
    uid = str(user_id)
    now = datetime.now().isoformat()
    
    if uid not in bot_data["users"]:
        bot_data["users"][uid] = {
            "username": username or "",
            "first_name": first_name or "",
            "joined_date": now,
            "last_active": now,
            "videos_watched": []
        }
        bot_data["stats"]["total_users"] = len(bot_data["users"])
        save_data()
        logger.info(f"New user registered: {user_id} ({first_name})")
    else:
        bot_data["users"][uid]["last_active"] = now
        bot_data["users"][uid]["username"] = username or bot_data["users"][uid]["username"]
        save_data()

async def send_video_with_note(chat_id: int, file_id: str, caption: str, video_id: str):
    """
    Send video and a separate note message.
    The note says: "Save/forward this video. It will be deleted in 30 minutes due to copyright."
    """
    # 1. Send the video WITHOUT any caption
    video_msg = await app.send_video(
        chat_id=chat_id,
        video=file_id,
        caption="",  # No caption on video
        protect_content=True  # Prevents forwarding (but user can still save)
    )
    
    # 2. Send a SEPARATE note message (not attached to video)
    note_text = (
        "**⚠️ IMPORTANT NOTE ⚠️**\n\n"
        "**Please save or forward this video now.**\n"
        f"**This video will be deleted in {DELETE_AFTER_MINUTES} minutes due to copyright.**\n\n"
        "**Instructions:**\n"
        "• Tap and hold the video above\n"
        "• Select 'Save to Gallery' or 'Forward'\n"
        f"• Video will be automatically deleted in {DELETE_AFTER_MINUTES} minutes"
    )
    
    note_msg = await app.send_message(
        chat_id=chat_id,
        text=note_text,
        reply_to_message_id=video_msg.id,
        disable_web_page_preview=True
    )
    
    # 3. Schedule auto-deletion after 30 minutes
    asyncio.create_task(
        auto_delete_messages(
            chat_id=chat_id,
            message_ids=[video_msg.id, note_msg.id],
            delay_minutes=DELETE_AFTER_MINUTES
        )
    )
    
    return video_msg, note_msg

async def auto_delete_messages(chat_id: int, message_ids: list, delay_minutes: int):
    """Delete messages after specified delay"""
    await asyncio.sleep(delay_minutes * 60)  # Convert minutes to seconds
    
    deleted_any = False
    for msg_id in message_ids:
        try:
            await app.delete_messages(chat_id=chat_id, message_ids=msg_id)
            deleted_any = True
            logger.info(f"Deleted message {msg_id} in chat {chat_id}")
        except Exception as e:
            logger.error(f"Failed to delete message {msg_id}: {e}")
    
    # Notify user that video was deleted
    if deleted_any:
        try:
            await app.send_message(
                chat_id=chat_id,
                text="**♻️ The video has been automatically deleted as per copyright policy.**"
            )
        except:
            pass

async def send_video_to_user(user_id: int, video_id: str):
    """Send a stored video to user and track it"""
    video_data = bot_data["videos"].get(video_id)
    if not video_data:
        await app.send_message(
            chat_id=user_id,
            text="**❌ This video is no longer available or has expired.**"
        )
        return False
    
    # Send video + note
    await send_video_with_note(
        chat_id=user_id,
        file_id=video_data["file_id"],
        caption=video_data.get("caption", ""),
        video_id=video_id
    )
    
    # Track video view
    uid = str(user_id)
    if uid in bot_data["users"]:
        if video_id not in bot_data["users"][uid]["videos_watched"]:
            bot_data["users"][uid]["videos_watched"].append(video_id)
            bot_data["stats"]["total_videos_sent"] += 1
            save_data()
    
    return True

# ============================================================
# COMMAND: /start
# ============================================================

@app.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    """
    When user clicks /start or a video link (https://t.me/bot?start=VIDEO_ID):
    - If it's just /start: Show welcome message
    - If it's a video link: Check channel membership, then send video
    """
    user = message.from_user
    user_id = user.id
    username = user.username or ""
    first_name = user.first_name or ""
    
    # Always register the user
    await register_user(user_id, username, first_name)
    
    # Parse command arguments
    command_parts = message.text.split()
    
    # Case 1: User clicked a video link (e.g., /start VIDEO_ID)
    if len(command_parts) > 1:
        video_id = command_parts[1]
        
        # Check if user has joined both channels
        is_ok, ch1, ch2 = await check_both_channels(user_id)
        
        if not is_ok:
            # Show channel join message with buttons
            join_msg = format_join_message(ch1, ch2)
            
            await message.reply_text(
                text=join_msg,
                reply_markup=get_join_buttons(),
                disable_web_page_preview=True
            )
            
            # Store the video_id so we can send it after verification
            if "pending" not in bot_data:
                bot_data["pending"] = {}
            bot_data["pending"][str(user_id)] = video_id
            save_data()
            return
        
        # User has joined both channels - send video directly
        success = await send_video_to_user(user_id, video_id)
        
        if not success:
            await message.reply_text("**❌ Video not found. Please try again with a valid link.**")
        
        return
    
    # Case 2: Just /start command (no video link)
    welcome_msg = (
        "**🎬 Welcome to the Premium Video System!**\n\n"
        "**How it works:**\n"
        "• Click on a video link shared in our channel\n"
        "• Join both required channels\n"
        "• Get your video instantly\n\n"
        f"**⚠️ Note:** All videos are automatically deleted after {DELETE_AFTER_MINUTES} minutes due to copyright protection.\n\n"
        "**Please save or forward videos immediately after receiving them.**"
    )
    
    await message.reply_text(welcome_msg)

# ============================================================
# CALLBACK: Verify Channel Join
# ============================================================

@app.on_callback_query(filters.regex("^verify_join$"))
async def verify_join_callback(client: Client, callback_query: CallbackQuery):
    """
    When user clicks "I Have Joined Both Channels":
    - Check membership again
    - If joined: Send video
    - If not joined: Show error message, increase rejection count
    """
    user = callback_query.from_user
    user_id = user.id
    
    await callback_query.answer()
    
    # Re-check channel membership
    is_ok, ch1, ch2 = await check_both_channels(user_id)
    
    if not is_ok:
        # REJECTED - User hasn't actually joined
        bot_data["stats"]["total_rejected"] += 1
        save_data()
        
        reject_msg = (
            "**❌ ACCESS DENIED ❌**\n\n"
            "**You have not joined both channels yet!**\n\n"
            f"{'✅' if ch1 else '❌'} {CHANNEL_1_NAME}\n"
            f"{'✅' if ch2 else '❌'} {CHANNEL_2_NAME}\n\n"
            "**Please join BOTH channels first, then click the verify button again.**"
        )
        
        try:
            await callback_query.edit_message_text(
                text=reject_msg,
                reply_markup=get_join_buttons(),
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Edit message error: {e}")
            await app.send_message(
                chat_id=user_id,
                text=reject_msg,
                reply_markup=get_join_buttons(),
                disable_web_page_preview=True
            )
        return
    
    # VERIFIED - User has joined both channels
    bot_data["stats"]["total_verified"] += 1
    save_data()
    
    success_msg = (
        "**✅ VERIFICATION SUCCESSFUL ✅**\n\n"
        "**You have successfully joined both channels!**\n\n"
        f"✅ {CHANNEL_1_NAME}\n"
        f"✅ {CHANNEL_2_NAME}\n\n"
        "**Access granted! Please wait for your video...**"
    )
    
    try:
        await callback_query.edit_message_text(
            text=success_msg,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Edit message error: {e}")
        await app.send_message(
            chat_id=user_id,
            text=success_msg
        )
    
    # Check if there's a pending video request
    uid = str(user_id)
    video_id = None
    if "pending" in bot_data and uid in bot_data["pending"]:
        video_id = bot_data["pending"].pop(uid)
        save_data()
    
    if video_id:
        await send_video_to_user(user_id, video_id)
    else:
        await app.send_message(
            chat_id=user_id,
            text="**✅ You now have full access!**\n\n"
                 "Click any video link from our channel to receive content."
        )

# ============================================================
# COMMAND: /video - Add a new video (OWNER ONLY)
# ============================================================

@app.on_message(filters.command("video") & filters.private)
async def video_command(client: Client, message: Message):
    """
    Owner command to add a new monetized video.
    Usage: Reply to a video with: /video Caption here
    """
    user_id = message.from_user.id
    
    # Only owner can use this
    if user_id != OWNER_ID:
        await message.reply_text("**❌ You are not authorized to use this command.**")
        return
    
    # Check if replying to a video
    if not message.reply_to_message or not message.reply_to_message.video:
        await message.reply_text(
            "**📤 How to add a video:**\n\n"
            "1. Send me the video file\n"
            "2. Reply to that video with:\n"
            "   `/video Your Caption Here`\n\n"
            "The bot will generate a shareable link.\n"
            "Users must join both channels to access it."
        )
        return
    
    video = message.reply_to_message.video
    caption = message.text.replace("/video", "", 1).strip()
    if not caption:
        caption = "🎬 Premium Video Content"
    
    # Generate unique video ID
    video_id = str(uuid.uuid4())[:8]
    
    # Store video info
    bot_data["videos"][video_id] = {
        "file_id": video.file_id,
        "caption": caption,
        "duration": video.duration,
        "file_size": video.file_size,
        "file_name": video.file_name or "video.mp4",
        "added_date": datetime.now().isoformat()
    }
    save_data()
    
    # Generate shareable link
    bot_username = (await app.get_me()).username
    video_link = f"https://t.me/{bot_username}?start={video_id}"
    
    await message.reply_text(
        f"**✅ VIDEO ADDED SUCCESSFULLY ✅**\n\n"
        f"**Video ID:** `{video_id}`\n"
        f"**Caption:** {caption}\n"
        f"**Duration:** {video.duration} seconds\n"
        f"**Size:** {video.file_size / (1024 * 1024):.1f} MB\n\n"
        f"**🔗 Share this link with users:**\n"
        f"`{video_link}`\n\n"
        f"**⏰ Auto-delete:** {DELETE_AFTER_MINUTES} minutes\n"
        f"**🔒 Protection:** Channel join required\n\n"
        f"**📊 Use /stats to see analytics**"
    )

# ============================================================
# COMMAND: /stats - View analytics (OWNER ONLY)
# ============================================================

@app.on_message(filters.command("stats") & filters.private)
async def stats_command(client: Client, message: Message):
    """
    Owner command to view real-time bot analytics.
    Shows: user count, video views, verification stats, etc.
    """
    user_id = message.from_user.id
    
    if user_id != OWNER_ID:
        await message.reply_text("**❌ Unauthorized. This command is for the bot owner only.**")
        return
    
    users = bot_data.get("users", {})
    videos = bot_data.get("videos", {})
    stats = bot_data.get("stats", {})
    
    # Calculate active users (last 24 hours)
    now = datetime.now()
    active_24h = 0
    today_users = 0
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    for uid, uinfo in users.items():
        last_active = uinfo.get("last_active", "")
        try:
            last_dt = datetime.fromisoformat(last_active)
            if (now - last_dt).total_seconds() < 86400:  # 24 hours
                active_24h += 1
            if last_dt >= today_start:
                today_users += 1
        except:
            pass
    
    # Find most watched video
    video_watch_count = {}
    for uid, uinfo in users.items():
        for vid in uinfo.get("videos_watched", []):
            video_watch_count[vid] = video_watch_count.get(vid, 0) + 1
    
    most_watched_id = max(video_watch_count, key=video_watch_count.get) if video_watch_count else None
    most_watched_count = video_watch_count.get(most_watched_id, 0) if most_watched_id else 0
    
    # Get info about most watched video
    most_watched_caption = "N/A"
    if most_watched_id and most_watched_id in videos:
        most_watched_caption = videos[most_watched_id].get("caption", "N/A")[:30]
    
    stats_msg = (
        "**📊 BOT ANALYTICS DASHBOARD 📊**\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "**👥 USER STATISTICS**\n"
        f"• **Total Users:** `{len(users)}`\n"
        f"• **Active (24h):** `{active_24h}`\n"
        f"• **New Today:** `{today_users}`\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "**🎬 VIDEO STATISTICS**\n"
        f"• **Total Videos:** `{len(videos)}`\n"
        f"• **Total Views:** `{stats.get('total_videos_sent', 0)}`\n"
        f"• **Avg Views/Video:** `{stats.get('total_videos_sent', 0) / max(len(videos), 1):.1f}`\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "**🏆 MOST WATCHED VIDEO**\n"
        f"• **ID:** `{most_watched_id or 'N/A'}`\n"
        f"• **Caption:** {most_watched_caption}\n"
        f"• **Views:** `{most_watched_count}`\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "**✅ VERIFICATION STATS**\n"
        f"• **Successful:** `{stats.get('total_verified', 0)}`\n"
        f"• **Rejected:** `{stats.get('total_rejected', 0)}`\n"
        f"• **Rate:** `{stats.get('total_verified', 0) / max(stats.get('total_verified', 0) + stats.get('total_rejected', 0), 1) * 100:.0f}%`\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "**⚙️ SYSTEM**\n"
        f"• **Auto-Delete:** {DELETE_AFTER_MINUTES} minutes\n"
        f"• **Channels:** 2 (Force Join)\n"
        f"• **Data File:** `{DATA_FILE}`\n\n"
        f"🕒 Last Updated: {now.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    await message.reply_text(stats_msg)

# ============================================================
# COMMAND: /users - List all users (OWNER ONLY)
# ============================================================

@app.on_message(filters.command("users") & filters.private)
async def users_command(client: Client, message: Message):
    """Owner command to see list of all registered users"""
    user_id = message.from_user.id
    
    if user_id != OWNER_ID:
        await message.reply_text("**❌ Unauthorized. This command is for the bot owner only.**")
        return
    
    users = bot_data.get("users", {})
    
    if not users:
        await message.reply_text("**📭 No users registered yet.**")
        return
    
    # Pagination
    page = 1
    args = message.text.split()
    if len(args) > 1:
        try:
            page = int(args[1])
        except:
            pass
    
    per_page = 15
    total_pages = (len(users) + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = min(start + per_page, len(users))
    
    user_items = sorted(users.items(), key=lambda x: x[1].get("last_active", ""), reverse=True)
    user_items = user_items[start:end]
    
    text = f"**📋 USER LIST (Page {page}/{total_pages})**\n\n"
    text += f"**Total Users:** {len(users)}\n"
    text += "━━━━━━━━━━━━━━━━━━━\n\n"
    
    for i, (uid, uinfo) in enumerate(user_items, start=start + 1):
        name = uinfo.get("first_name", "Unknown")[:20]
        videos = len(uinfo.get("videos_watched", []))
        last_active = uinfo.get("last_active", "")
        try:
            last_dt = datetime.fromisoformat(last_active)
            last_str = last_dt.strftime("%b %d %H:%M")
        except:
            last_str = "N/A"
        
        text += f"**{i}.** {name}\n"
        text += f"   🆔 `{uid}` | 👁 {videos} videos\n"
        text += f"   🕒 {last_str}\n\n"
    
    if page < total_pages:
        text += f"━━━━━━━━━━━━━━━━━━━\n"
        text += f"Use `/users {page + 1}` for next page"
    
    await message.reply_text(text)

# ============================================================
# COMMAND: /videos - List all videos (OWNER ONLY)
# ============================================================

@app.on_message(filters.command("videos") & filters.private)
async def videos_command(client: Client, message: Message):
    """Owner command to see all uploaded videos with view counts"""
    user_id = message.from_user.id
    
    if user_id != OWNER_ID:
        await message.reply_text("**❌ Unauthorized. This command is for the bot owner only.**")
        return
    
    videos = bot_data.get("videos", {})
    
    if not videos:
        await message.reply_text(
            "**📭 No videos uploaded yet.**\n\n"
            "To add a video:\n"
            "1. Send a video file\n"
            "2. Reply with: `/video Your Caption`"
        )
        return
    
    text = "**🎬 VIDEO LIST**\n\n"
    text += f"**Total Videos:** {len(videos)}\n"
    text += "━━━━━━━━━━━━━━━━━━━\n\n"
    
    for vid, vinfo in videos.items():
        # Count how many users watched this video
        watch_count = 0
        for uinfo in bot_data.get("users", {}).values():
            if vid in uinfo.get("videos_watched", []):
                watch_count += 1
        
        size_mb = vinfo.get("file_size", 0) / (1024 * 1024)
        added = vinfo.get("added_date", "")[:19]
        
        text += f"**ID:** `{vid}`\n"
        text += f"**Caption:** {vinfo.get('caption', 'N/A')[:40]}\n"
        text += f"**Views:** {watch_count} | **Size:** {size_mb:.1f}MB\n"
        text += f"**Added:** {added}\n\n"
    
    # Generate shareable link for latest video
    bot_username = (await app.get_me()).username
    latest_vid = list(videos.keys())[-1] if videos else None
    if latest_vid:
        link = f"https://t.me/{bot_username}?start={latest_vid}"
        text += "━━━━━━━━━━━━━━━━━━━\n"
        text += f"**🔗 Latest Video Link:**\n`{link}`"
    
    await message.reply_text(text)

# ============================================================
# COMMAND: /deletevideo <video_id> - Delete a video (OWNER ONLY)
# ============================================================

@app.on_message(filters.command("deletevideo") & filters.private)
async def deletevideo_command(client: Client, message: Message):
    """Owner command to delete a video from the system"""
    user_id = message.from_user.id
    
    if user_id != OWNER_ID:
        await message.reply_text("**❌ Unauthorized. This command is for the bot owner only.**")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.reply_text(
            "**📋 Usage:** `/deletevideo VIDEO_ID`\n\n"
            "Example: `/deletevideo abc12345`\n\n"
            "Use `/videos` to see all video IDs."
        )
        return
    
    video_id = args[1]
    
    if video_id not in bot_data["videos"]:
        await message.reply_text(f"**❌ Video `{video_id}` not found.**")
        return
    
    # Delete video
    deleted = bot_data["videos"].pop(video_id)
    save_data()
    
    await message.reply_text(
        f"**✅ VIDEO DELETED**\n\n"
        f"**ID:** `{video_id}`\n"
        f"**Caption:** {deleted.get('caption', 'N/A')}\n"
        f"**Removed from system.**"
    )

# ============================================================
# COMMAND: /userinfo <user_id> - Get user details (OWNER ONLY)
# ============================================================

@app.on_message(filters.command("userinfo") & filters.private)
async def userinfo_command(client: Client, message: Message):
    """Owner command to get detailed info about a specific user"""
    user_id = message.from_user.id
    
    if user_id != OWNER_ID:
        await message.reply_text("**❌ Unauthorized. This command is for the bot owner only.**")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.reply_text(
            "**📋 Usage:** `/userinfo USER_ID`\n\n"
            "Example: `/userinfo 123456789`"
        )
        return
    
    target_id = args[1]
    users = bot_data.get("users", {})
    
    if target_id not in users:
        await message.reply_text(f"**❌ User `{target_id}` not found in database.**")
        return
    
    uinfo = users[target_id]
    videos_watched = uinfo.get("videos_watched", [])
    
    text = (
        f"**🔍 USER DETAILS**\n\n"
        f"**Name:** {uinfo.get('first_name', 'N/A')}\n"
        f"**User ID:** `{target_id}`\n"
        f"**Username:** @{uinfo.get('username', 'N/A')}\n"
        f"**Joined:** {uinfo.get('joined_date', 'N/A')[:19]}\n"
        f"**Last Active:** {uinfo.get('last_active', 'N/A')[:19]}\n"
        f"**Videos Watched:** {len(videos_watched)}\n\n"
        f"**Video History:**\n"
    )
    
    if videos_watched:
        for vid in videos_watched[-10:]:
            vid_info = bot_data.get("videos", {}).get(vid, {})
            cap = vid_info.get("caption", "Unknown")[:25]
            text += f"• `{vid}` - {cap}\n"
    else:
        text += "• No videos watched yet\n"
    
    # Check current channel membership
    ch1 = await is_member_of_channel(int(target_id), CHANNEL_1_ID)
    ch2 = await is_member_of_channel(int(target_id), CHANNEL_2_ID)
    
    text += f"\n**Current Channel Status:**\n"
    text += f"{'✅' if ch1 else '❌'} {CHANNEL_1_NAME}\n"
    text += f"{'✅' if ch2 else '❌'} {CHANNEL_2_NAME}"
    
    await message.reply_text(text)

# ============================================================
# COMMAND: /broadcast - Send message to all users (OWNER ONLY)
# ============================================================

@app.on_message(filters.command("broadcast") & filters.private)
async def broadcast_command(client: Client, message: Message):
    """Owner command to send a message to all registered users"""
    user_id = message.from_user.id
    
    if user_id != OWNER_ID:
        await message.reply_text("**❌ Unauthorized. This command is for the bot owner only.**")
        return
    
    if not message.reply_to_message:
        await message.reply_text(
            "**📢 How to broadcast:**\n\n"
            "1. Send the message you want to broadcast\n"
            "2. Reply to it with: `/broadcast`\n\n"
            "The message will be sent to all registered users."
        )
        return
    
    broadcast_msg = message.reply_to_message
    users = bot_data.get("users", {})
    
    if not users:
        await message.reply_text("**📭 No users to broadcast to.**")
        return
    
    sent = 0
    failed = 0
    
    status_msg = await message.reply_text(f"**📢 Broadcasting to {len(users)} users...**")
    
    for uid in users.keys():
        try:
            if broadcast_msg.text:
                await app.send_message(int(uid), broadcast_msg.text)
            elif broadcast_msg.photo:
                await app.send_photo(int(uid), broadcast_msg.photo.file_id, caption=broadcast_msg.caption or "")
            elif broadcast_msg.video:
                await app.send_video(int(uid), broadcast_msg.video.file_id, caption=broadcast_msg.caption or "")
            sent += 1
            await asyncio.sleep(0.05)  # Anti-flood
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
            try:
                if broadcast_msg.text:
                    await app.send_message(int(uid), broadcast_msg.text)
                sent += 1
            except:
                failed += 1
        except:
            failed += 1
    
    await status_msg.edit_text(
        f"**✅ BROADCAST COMPLETE**\n\n"
        f"**Sent:** {sent}\n"
        f"**Failed:** {failed}\n"
        f"**Total Users:** {len(users)}"
    )

# ============================================================
# COMMAND: /help
# ============================================================

@app.on_message(filters.command("help") & filters.private)
async def help_command(client: Client, message: Message):
    """Show help menu"""
    user_id = message.from_user.id
    
    if user_id == OWNER_ID:
        help_text = (
            "**📚 BOT COMMANDS - OWNER PANEL**\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "**📹 VIDEO MANAGEMENT**\n"
            "• `/video caption` - Add video (reply to video)\n"
            "• `/videos` - List all videos\n"
            "• `/deletevideo id` - Delete a video\n\n"
            "**👥 USER MANAGEMENT**\n"
            "• `/stats` - View analytics dashboard\n"
            "• `/users` - List all users\n"
            "• `/userinfo id` - User details\n\n"
            "**📢 COMMUNICATION**\n"
            "• `/broadcast` - Message all users\n\n"
            "**ℹ️ GENERAL**\n"
            "• `/start` - Start / Access video\n"
            "• `/help` - Show this menu\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"**Users:** {len(bot_data.get('users', {}))}\n"
            f"**Videos:** {len(bot_data.get('videos', {}))}\n"
            f"**Delete Timer:** {DELETE_AFTER_MINUTES} min"
        )
    else:
        help_text = (
            "**📚 HELP**\n\n"
            "1. Click on a video link shared in our channel\n"
            "2. Join both required channels\n"
            "3. Click verify to confirm\n"
            "4. Receive your video\n\n"
            f"**⚠️ Videos auto-delete after {DELETE_AFTER_MINUTES} minutes.**\n"
            "**💾 Always save or forward videos immediately!**"
        )
    
    await message.reply_text(help_text)

# ============================================================
# HANDLE: Direct video uploads from owner
# ============================================================

@app.on_message(filters.video & filters.private)
async def handle_video_upload(client: Client, message: Message):
    """When owner sends a video directly, guide them to use /video command"""
    user_id = message.from_user.id
    
    if user_id != OWNER_ID:
        await message.reply_text("**❌ This bot does not accept direct uploads from users.**")
        return
    
    video = message.video
    await message.reply_text(
        f"**📹 Video received!**\n\n"
        f"**Size:** {video.file_size / (1024 * 1024):.1f} MB\n"
        f"**Duration:** {video.duration} seconds\n\n"
        "**To add to system, reply with:**\n"
        "`/video Your Caption Here`"
    )

# ============================================================
# HANDLE: Unknown messages
# ============================================================

@app.on_message(filters.private & ~filters.command([
    "start", "video", "stats", "users", "videos",
    "deletevideo", "userinfo", "broadcast", "help"
]))
async def unknown_handler(client: Client, message: Message):
    """Handle unknown messages - ignore videos (handled above)"""
    if message.video or message.photo or message.document:
        return
    
    if message.text and ("t.me" in message.text or "http" in message.text):
        await message.reply_text(
            "**🔗 Link detected!**\n\n"
            "If you received a video link from our channel:\n"
            "• Click the link directly\n"
            "• The bot will guide you\n\n"
            "Need help? Use /help"
        )
        return
    
    await message.reply_text(
        "**🤖 I don't understand that.**\n\n"
        "• Click a video link from our channel\n"
        "• Use /start to begin\n"
        "• Use /help for assistance"
    )

# ============================================================
# MAIN FUNCTION
# ============================================================

async def main():
    """Start the bot"""
    logger.info("=" * 50)
    logger.info("VIDEO MONETIZATION BOT STARTING")
    logger.info("=" * 50)
    
    # Get bot info
    bot_info = await app.get_me()
    logger.info(f"Bot: @{bot_info.username} (ID: {bot_info.id})")
    logger.info(f"Owner ID: {OWNER_ID}")
    logger.info(f"Channel 1: {CHANNEL_1_NAME} ({CHANNEL_1_ID})")
    logger.info(f"Channel 2: {CHANNEL_2_NAME} ({CHANNEL_2_ID})")
    logger.info(f"Auto-Delete: {DELETE_AFTER_MINUTES} minutes")
    logger.info(f"Data File: {DATA_FILE}")
    logger.info(f"Total Users: {len(bot_data.get('users', {}))}")
    logger.info(f"Total Videos: {len(bot_data.get('videos', {}))}")
    
    # Verify bot is admin in channels
    try:
        bot_ch1 = await app.get_chat_member(CHANNEL_1_ID, bot_info.id)
        logger.info(f"Channel 1 admin status: {bot_ch1.status}")
    except Exception as e:
        logger.warning(f"Channel 1 - Bot may not be admin: {e}")
    
    try:
        bot_ch2 = await app.get_chat_member(CHANNEL_2_ID, bot_info.id)
        logger.info(f"Channel 2 admin status: {bot_ch2.status}")
    except Exception as e:
        logger.warning(f"Channel 2 - Bot may not be admin: {e}")
    
    logger.info("Bot is running...")

if __name__ == "__main__":
    app.run()

