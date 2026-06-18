#!/usr/bin/env python3
"""
Ultimate Multi-Bot Telegram Bot – ALL BOTS TOGETHER, MAX SPEED
Default reaction: 😂  |  NC emojis: ❤️🧡💛💚🩵💙💜🤎🖤🩶🤍🩷
"""

import asyncio
import json
import logging
import random
import io
from datetime import datetime, timedelta
from telegram import Update, ChatPermissions, ReactionTypeEmoji
from telegram.ext import (
    Application,
    MessageHandler,
    filters,
    ContextTypes,
    ChatMemberHandler,
)
from telegram.error import RetryAfter, TelegramError

# ========== CONFIG ==========
MAIN_TOKEN = "8922807950:AAGe7LbhOg8LYsIxz5epZ7Uma6W_xvpL2f8"      # Replace with your main bot token
OWNER_ID   = 8581502899                # Replace with your Telegram user ID
# ===========================

DATA_FILE = "bot_data.json"
LOG_MAX   = 200

# ---- Custom logging ----
log_buffer = []

class BufferHandler(logging.Handler):
    def emit(self, record):
        msg = self.format(record)
        log_buffer.append(msg)
        if len(log_buffer) > LOG_MAX:
            log_buffer.pop(0)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger()
logger.handlers = []
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
logger.addHandler(handler)
buffer_handler = BufferHandler()
buffer_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(buffer_handler)

# ---------- DATA ----------
DEFAULT_DATA = {
    "owner_id": OWNER_ID,
    "admins": [],
    "prefixes": ["/", "!", ".", "?"],
    "default_reaction_emoji": "😂",
    "local_reactions": {},
    "target_replies": {},
    "dmuted_users": {},
    "global_reactions": {},
    "rr_entries": {},
    "active_tokens": [MAIN_TOKEN],
    "warns": {},
    "all_chats": [],
}

data_lock = asyncio.Lock()

def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = DEFAULT_DATA.copy()
        save_data(data)
    for k, v in DEFAULT_DATA.items():
        if k not in data:
            data[k] = v
    if MAIN_TOKEN not in data["active_tokens"]:
        data["active_tokens"].append(MAIN_TOKEN)
    if not isinstance(data.get("all_chats"), list):
        data["all_chats"] = []
    if "rr_entries" not in data:
        data["rr_entries"] = {}
    return data

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

data = load_data()
start_time = datetime.utcnow()

running_bots = {}  # token -> Application

# ---------- UTILS ----------
def is_admin(user_id: int) -> bool:
    return user_id == data["owner_id"] or user_id in data["admins"]

async def reply_not_allowed(update: Update):
    await update.message.reply_text("❌ You are not allowed to do this. Contact @Divkylu for permission.")

def parse_command(text: str):
    for prefix in data["prefixes"]:
        if text.startswith(prefix):
            cmd = text[len(prefix):].strip()
            parts = cmd.split()
            command = parts[0].lower() if parts else ""
            args = parts[1:] if len(parts) > 1 else []
            return command, args
    return None, None

def get_all_bots():
    """Return list of bot instances from all running apps."""
    return [app.bot for app in running_bots.values()]

# ---------- ACTIVE LOOP TASKS (NO SLEEP, MAX SPEED) ----------
active_tasks = {}
tasks_lock = asyncio.Lock()

async def stop_loop_in_chat(chat_id, loop_type=None):
    async with tasks_lock:
        if chat_id in active_tasks:
            if loop_type:
                task = active_tasks[chat_id].get(loop_type)
                if task:
                    task.cancel()
                    active_tasks[chat_id][loop_type] = None
                    return True
            else:
                for t in active_tasks[chat_id].values():
                    if t: t.cancel()
                active_tasks[chat_id] = {"spam": None, "nc": None, "reply": None, "status": None}
                return True
    return False

async def stop_loop(update: Update, context: ContextTypes.DEFAULT_TYPE, loop_type: str = None):
    chat_id = update.effective_chat.id
    success = await stop_loop_in_chat(chat_id, loop_type)
    if success:
        await update.message.reply_text(f"✅ `{loop_type or 'all'}` loop stopped.")
    else:
        await update.message.reply_text("No active loop found.")

# ---------- SPAM LOOP (ALL BOTS) ----------
async def start_spam(chat_id, text):
    async with tasks_lock:
        if chat_id not in active_tasks:
            active_tasks[chat_id] = {"spam": None, "nc": None, "reply": None, "status": None}
        if active_tasks[chat_id]["spam"]:
            active_tasks[chat_id]["spam"].cancel()
    async def spam_loop():
        while True:
            bots = get_all_bots()
            if not bots:
                await asyncio.sleep(0.1)
                continue
            tasks = [bot.send_message(chat_id, text) for bot in bots]
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Spam gather error: {e}")
    async with tasks_lock:
        active_tasks[chat_id]["spam"] = asyncio.create_task(spam_loop())
    return True

async def cmd_spam(update, context, args):
    chat_id = update.effective_chat.id
    if not args:
        await update.message.reply_text("⚠️ Usage: /spam <text>")
        return
    spam_text = " ".join(args)
    await start_spam(chat_id, spam_text)
    await update.message.reply_text("🔥 Spam started on ALL bots (max speed). /stopspam to stop.")

# ---------- NC LOOP (ALL BOTS) ----------
NC_EMOJIS = ["❤️","🧡","💛","💚","🩵","💙","💜","🤎","🖤","🩶","🤍","🩷"]

async def start_nc(chat_id, base_name=None):
    async with tasks_lock:
        if chat_id not in active_tasks:
            active_tasks[chat_id] = {"spam": None, "nc": None, "reply": None, "status": None}
        if active_tasks[chat_id]["nc"]:
            active_tasks[chat_id]["nc"].cancel()
    async def nc_loop():
        while True:
            bots = get_all_bots()
            if not bots:
                await asyncio.sleep(0.1)
                continue
            try:
                chat = await bots[0].get_chat(chat_id)
                title = chat.title or "Group"
                name_part = base_name or title.split(" ")[0]
                new_name = f"{name_part} {random.choice(NC_EMOJIS)}"
            except Exception as e:
                logging.error(f"NC get_chat error: {e}")
                new_name = f"Bot {random.choice(NC_EMOJIS)}"
            tasks = [bot.set_chat_title(chat_id, new_name) for bot in bots]
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"NC gather error: {e}")
    async with tasks_lock:
        active_tasks[chat_id]["nc"] = asyncio.create_task(nc_loop())
    return True

async def cmd_nc(update, context, args):
    chat_id = update.effective_chat.id
    base_name = " ".join(args) if args else None
    await start_nc(chat_id, base_name)
    await update.message.reply_text("🔄 Name change loop started on ALL bots (max speed). /stopnc to stop.")

# ---------- REPLY LOOP (ALL BOTS) ----------
async def start_reply(chat_id, target_msg_id, reply_text):
    async with tasks_lock:
        if chat_id not in active_tasks:
            active_tasks[chat_id] = {"spam": None, "nc": None, "reply": None, "status": None}
        if active_tasks[chat_id]["reply"]:
            active_tasks[chat_id]["reply"].cancel()
    async def reply_loop():
        while True:
            bots = get_all_bots()
            if not bots:
                await asyncio.sleep(0.1)
                continue
            tasks = [bot.send_message(chat_id, reply_text, reply_to_message_id=target_msg_id) for bot in bots]
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Reply gather error: {e}")
    async with tasks_lock:
        active_tasks[chat_id]["reply"] = asyncio.create_task(reply_loop())
    return True

async def cmd_reply(update, context, args):
    chat_id = update.effective_chat.id
    msg = update.message
    if not msg.reply_to_message:
        await msg.reply_text("⚠️ Reply to a message and use /reply <text>")
        return
    target_id = msg.reply_to_message.message_id
    reply_text = " ".join(args) if args else "💀"
    await start_reply(chat_id, target_id, reply_text)
    await msg.reply_text("💬 Reply loop started on ALL bots (max speed). /stopreply to stop.")

# ---------- GLOBAL LOOPS ----------
async def get_all_chats():
    async with data_lock:
        return list(data["all_chats"])

async def cmd_allgcspam(update, context, args):
    if not args:
        await update.message.reply_text("⚠️ /allgcspam <text>"); return
    spam_text = " ".join(args)
    chat_ids = await get_all_chats()
    if not chat_ids:
        await update.message.reply_text("No groups recorded yet."); return
    count = 0
    for cid in chat_ids:
        try:
            await start_spam(cid, spam_text)
            count += 1
        except Exception as e:
            logging.warning(f"Failed to start spam in {cid}: {e}")
    await update.message.reply_text(
        f"🌐 Global spam started in {count}/{len(chat_ids)} groups. /stopallgcspam to stop."
    )

async def cmd_allgcnc(update, context, args):
    base_name = " ".join(args) if args else None
    chat_ids = await get_all_chats()
    if not chat_ids:
        await update.message.reply_text("No groups recorded yet."); return
    count = 0
    for cid in chat_ids:
        try:
            await start_nc(cid, base_name)
            count += 1
        except Exception as e:
            logging.warning(f"Failed to start NC in {cid}: {e}")
    await update.message.reply_text(
        f"🌐 Global name change started in {count}/{len(chat_ids)} groups. /stopallgcnc to stop."
    )

async def cmd_stopallgcspam(update, context):
    chat_ids = await get_all_chats()
    stopped = 0
    for cid in chat_ids:
        if await stop_loop_in_chat(cid, "spam"):
            stopped += 1
    await update.message.reply_text(f"🛑 Stopped spam in {stopped} groups.")

async def cmd_stopallgcnc(update, context):
    chat_ids = await get_all_chats()
    stopped = 0
    for cid in chat_ids:
        if await stop_loop_in_chat(cid, "nc"):
            stopped += 1
    await update.message.reply_text(f"🛑 Stopped name change in {stopped} groups.")

# ---------- REACTION / TARGET ----------
async def resolve_user(update, context, args):
    msg = update.message
    if msg.reply_to_message:
        return msg.reply_to_message.from_user
    if args and args[0].startswith("@"):
        username = args[0].lstrip("@")
        try:
            return await context.bot.get_chat(f"@{username}")
        except:
            return None
    if args and args[0].isdigit():
        try:
            return await context.bot.get_chat(int(args[0]))
        except:
            return None
    return None

async def cmd_react(update, context, args):
    msg = update.message
    chat_id = update.effective_chat.id
    target_id = None
    emoji = data["default_reaction_emoji"]
    if msg.reply_to_message:
        target_id = msg.reply_to_message.from_user.id
        if args:
            emoji = args[0] if len(args) == 1 else " ".join(args)
    elif args and args[0].startswith("@"):
        username = args[0].lstrip("@")
        try:
            user = await context.bot.get_chat(f"@{username}")
            target_id = user.id
        except TelegramError:
            await msg.reply_text("❌ User not found."); return
        if len(args) > 1:
            emoji = args[1]
    else:
        await msg.reply_text("⚠️ Reply to a user or mention @username."); return
    key = f"{chat_id}:{target_id}"
    async with data_lock:
        data["local_reactions"][key] = emoji
        save_data(data)
    await msg.reply_text(
        f"✅ Reacting to {target_id} with {emoji} in this chat. /stopreact @username to stop."
    )

async def cmd_stopreact(update, context, args):
    chat_id = update.effective_chat.id
    target_id = None
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
    elif args and args[0].startswith("@"):
        username = args[0].lstrip("@")
        try:
            user = await context.bot.get_chat(f"@{username}")
            target_id = user.id
        except:
            await update.message.reply_text("❌ User not found."); return
    else:
        await update.message.reply_text("⚠️ Reply or mention @username."); return
    key = f"{chat_id}:{target_id}"
    async with data_lock:
        if key in data["local_reactions"]:
            del data["local_reactions"][key]; save_data(data)
            await update.message.reply_text("🛑 Local reaction stopped.")
        else:
            await update.message.reply_text("No local reaction for that user.")

async def cmd_globalreact(update, context, args):
    if not args or not args[0].startswith("@"):
        await update.message.reply_text("⚠️ /globalreact @username [emoji]"); return
    username = args[0].lstrip("@")
    try:
        user = await context.bot.get_chat(f"@{username}")
        target_id = user.id
    except:
        await update.message.reply_text("❌ User not found."); return
    emoji = data["default_reaction_emoji"]
    if len(args) > 1:
        emoji = args[1]
    async with data_lock:
        data["global_reactions"][str(target_id)] = emoji
        save_data(data)
    await update.message.reply_text(f"🌍 Global reaction for @{username} set to {emoji}")

async def cmd_stopglobalreact(update, context, args):
    if not args or not args[0].startswith("@"):
        await update.message.reply_text("⚠️ /stopglobalreact @username"); return
    username = args[0].lstrip("@")
    try:
        user = await context.bot.get_chat(f"@{username}")
        target_id = str(user.id)
    except:
        await update.message.reply_text("❌ User not found."); return
    async with data_lock:
        if target_id in data["global_reactions"]:
            del data["global_reactions"][target_id]; save_data(data)
            await update.message.reply_text("🛑 Global reaction removed.")
        else:
            await update.message.reply_text("No global reaction for that user.")

async def cmd_target(update, context, args):
    msg = update.message
    chat_id = update.effective_chat.id
    target_id = None
    reply_text = " ".join(args) if args else None
    if msg.reply_to_message:
        target_id = msg.reply_to_message.from_user.id
        if not reply_text:
            await msg.reply_text("⚠️ Please provide reply text. Example: `/target Hello`"); return
    elif args and args[0].startswith("@"):
        username = args[0].lstrip("@")
        try:
            user = await context.bot.get_chat(f"@{username}")
            target_id = user.id
        except:
            await msg.reply_text("❌ User not found."); return
        if len(args) > 1:
            reply_text = " ".join(args[1:])
        else:
            await msg.reply_text("⚠️ Provide reply text."); return
    else:
        await msg.reply_text("⚠️ Reply to a user or mention @username with text."); return
    key = f"{chat_id}:{target_id}"
    async with data_lock:
        data["target_replies"][key] = reply_text
        save_data(data)
    await msg.reply_text(f"🎯 Now replying to {target_id} with \"{reply_text}\". /stoptarget @username to stop.")

async def cmd_stoptarget(update, context, args):
    chat_id = update.effective_chat.id
    target_id = None
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
    elif args and args[0].startswith("@"):
        username = args[0].lstrip("@")
        try:
            user = await context.bot.get_chat(f"@{username}")
            target_id = user.id
        except:
            await update.message.reply_text("❌ User not found."); return
    else:
        await update.message.reply_text("⚠️ Reply or mention @username."); return
    key = f"{chat_id}:{target_id}"
    async with data_lock:
        if key in data["target_replies"]:
            del data["target_replies"][key]; save_data(data)
            await update.message.reply_text("🛑 Target reply removed.")
        else:
            await update.message.reply_text("No target reply set for that user.")

async def cmd_changereactionemoji(update, context, args):
    if not args:
        await update.message.reply_text(f"Current default emoji: {data['default_reaction_emoji']}"); return
    async with data_lock:
        data["default_reaction_emoji"] = args[0]; save_data(data)
    await update.message.reply_text(f"✅ Default reaction emoji changed to {args[0]}")

async def cmd_setprefix(update, context, args):
    if not args:
        await update.message.reply_text(f"Current prefixes: {' '.join(data['prefixes'])}"); return
    new_prefs = [p for p in args if p in ["/", "!", ".", "?"]]
    async with data_lock:
        data["prefixes"] = new_prefs; save_data(data)
    await update.message.reply_text(f"✅ Prefixes set to: {' '.join(new_prefs)}")

# ---------- GROUP MANAGEMENT ----------
async def cmd_dmute(update, context, args):
    chat_id = update.effective_chat.id
    user = await resolve_user(update, context, args)
    if not user:
        await update.message.reply_text("⚠️ Reply or mention @username to dmute."); return
    async with data_lock:
        data["dmuted_users"][f"{chat_id}:{user.id}"] = True; save_data(data)
    await update.message.reply_text(
        f"🔇 Messages from {user.mention_html()} will be deleted.", parse_mode="HTML"
    )

async def cmd_dunmute(update, context, args):
    chat_id = update.effective_chat.id
    user = await resolve_user(update, context, args)
    if not user:
        await update.message.reply_text("⚠️ Reply or mention to dunmute."); return
    key = f"{chat_id}:{user.id}"
    async with data_lock:
        if key in data["dmuted_users"]:
            del data["dmuted_users"][key]; save_data(data)
            await update.message.reply_text("🔊 User unmuted (messages will no longer be deleted).")
        else:
            await update.message.reply_text("User is not dmuted.")

async def cmd_ban(update, context, args):
    chat_id = update.effective_chat.id
    user = await resolve_user(update, context, args)
    if not user:
        await update.message.reply_text("⚠️ Reply or mention @username to ban."); return
    try:
        await context.bot.ban_chat_member(chat_id, user.id)
        await update.message.reply_text(f"🚫 Banned {user.mention_html()}.", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to ban: {e}")

async def cmd_unban(update, context, args):
    chat_id = update.effective_chat.id
    user = await resolve_user(update, context, args)
    if not user:
        await update.message.reply_text("⚠️ Provide @username or ID to unban."); return
    try:
        await context.bot.unban_chat_member(chat_id, user.id)
        await update.message.reply_text(f"✅ Unbanned {user.mention_html()}.", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to unban: {e}")

async def cmd_kick(update, context, args):
    chat_id = update.effective_chat.id
    user = await resolve_user(update, context, args)
    if not user:
        await update.message.reply_text("⚠️ Reply or mention to kick."); return
    try:
        await context.bot.ban_chat_member(chat_id, user.id)
        await context.bot.unban_chat_member(chat_id, user.id)
        await update.message.reply_text(f"👢 Kicked {user.mention_html()}.", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to kick: {e}")

async def cmd_mute(update, context, args):
    chat_id = update.effective_chat.id
    user = await resolve_user(update, context, args)
    if not user:
        await update.message.reply_text("⚠️ Reply or mention to mute."); return
    duration_str = None
    if len(args) > 1:
        duration_str = args[1]
    until_date = None
    if duration_str:
        import re
        match = re.match(r"(\d+)([mhd])", duration_str)
        if match:
            num = int(match.group(1))
            unit = match.group(2)
            delta = {"m": timedelta(minutes=num), "h": timedelta(hours=num), "d": timedelta(days=num)}.get(unit)
            if delta:
                until_date = datetime.utcnow() + delta
    try:
        permissions = ChatPermissions(can_send_messages=False)
        await context.bot.restrict_chat_member(chat_id, user.id, permissions, until_date=until_date)
        dur = f" for {duration_str}" if duration_str else ""
        await update.message.reply_text(f"🔇 Muted {user.mention_html()}{dur}.", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to mute: {e}")

async def cmd_unmute(update, context, args):
    chat_id = update.effective_chat.id
    user = await resolve_user(update, context, args)
    if not user:
        await update.message.reply_text("⚠️ Reply or mention to unmute."); return
    try:
        permissions = ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True
        )
        await context.bot.restrict_chat_member(chat_id, user.id, permissions)
        await update.message.reply_text(f"🔊 Unmuted {user.mention_html()}.", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to unmute: {e}")

async def cmd_warn(update, context, args):
    user = await resolve_user(update, context, args)
    if not user:
        await update.message.reply_text("⚠️ Reply or mention to warn."); return
    reason = " ".join(args[1:]) if len(args) > 1 else "No reason"
    await update.message.reply_text(
        f"⚠️ Warning for {user.mention_html()}:\n{reason}", parse_mode="HTML"
    )

async def cmd_pin(update, context):
    msg = update.message
    if not msg.reply_to_message:
        await msg.reply_text("⚠️ Reply to a message to pin it."); return
    try:
        await msg.reply_to_message.pin()
        await msg.reply_text("📌 Pinned.")
    except Exception as e:
        await msg.reply_text(f"❌ Failed to pin: {e}")

async def cmd_unpin(update, context, args):
    msg = update.message
    chat_id = update.effective_chat.id
    try:
        if msg.reply_to_message:
            await msg.reply_to_message.unpin()
        else:
            await context.bot.unpin_all_chat_messages(chat_id)
        await msg.reply_text("📌 Unpinned.")
    except Exception as e:
        await msg.reply_text(f"❌ Failed to unpin: {e}")

async def cmd_purge(update, context):
    msg = update.message
    if not msg.reply_to_message:
        await msg.reply_text("⚠️ Reply to a message to purge from there."); return
    chat_id = update.effective_chat.id
    from_id = msg.reply_to_message.message_id
    to_id = msg.message_id
    deleted = 0
    while from_id <= to_id:
        batch_end = min(from_id + 99, to_id)
        try:
            await context.bot.delete_messages(chat_id, list(range(from_id, batch_end+1)))
            deleted += (batch_end - from_id + 1)
        except Exception as e:
            await msg.reply_text(f"⚠️ Some messages could not be deleted: {e}")
            break
        from_id = batch_end + 1
    await msg.reply_text(f"🗑️ Deleted {deleted} messages.")

# ---------- FULL DEMOTE ----------
async def cmd_fulldemote(update: Update, context: ContextTypes.DEFAULT_TYPE, args):
    chat_id = update.effective_chat.id
    user = await resolve_user(update, context, args)
    if not user:
        await update.message.reply_text("⚠️ Reply or mention @username to fully demote."); return
    async with data_lock:
        data["dmuted_users"][f"{chat_id}:{user.id}"] = True
        save_data(data)
    permissions = ChatPermissions(
        can_send_messages=False,
        can_send_media_messages=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False
    )
    try:
        await context.bot.restrict_chat_member(chat_id, user.id, permissions)
        await update.message.reply_text(
            f"🔇🔨 Fully demoted {user.mention_html()}: messages deleted + muted permanently.\n"
            "Use /fullundemote @user to undo.",
            parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to mute (dmute still applied): {e}")

async def cmd_fullundemote(update: Update, context: ContextTypes.DEFAULT_TYPE, args):
    chat_id = update.effective_chat.id
    user = await resolve_user(update, context, args)
    if not user:
        await update.message.reply_text("⚠️ Reply or mention @username to undo full demote."); return
    key = f"{chat_id}:{user.id}"
    async with data_lock:
        if key in data["dmuted_users"]:
            del data["dmuted_users"][key]
            save_data(data)
    permissions = ChatPermissions(
        can_send_messages=True,
        can_send_media_messages=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True
    )
    try:
        await context.bot.restrict_chat_member(chat_id, user.id, permissions)
        await update.message.reply_text(f"🔊 Fully unmuted {user.mention_html()}.", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to unmute (dmute removed): {e}")

# ---------- /rr (Reply+React) ----------
async def cmd_rr(update: Update, context: ContextTypes.DEFAULT_TYPE, args):
    """Set combined reply text + reaction emoji for a user."""
    msg = update.message
    chat_id = update.effective_chat.id
    target_id = None
    reply_text = None
    emoji = data["default_reaction_emoji"]

    if not args:
        await msg.reply_text("⚠️ Usage: /rr <reply_text> [emoji]   (reply to a user or mention)")
        return

    if len(args) >= 2:
        reply_text = " ".join(args[:-1])
        emoji = args[-1]
    else:
        reply_text = args[0]

    if msg.reply_to_message:
        target_id = msg.reply_to_message.from_user.id
    elif args and args[0].startswith("@"):
        username = args[0].lstrip("@")
        try:
            user = await context.bot.get_chat(f"@{username}")
            target_id = user.id
        except:
            await msg.reply_text("❌ User not found."); return
        if len(args) > 1:
            sub_args = args[1:]
            if len(sub_args) >= 2:
                reply_text = " ".join(sub_args[:-1])
                emoji = sub_args[-1]
            else:
                reply_text = sub_args[0]
        else:
            await msg.reply_text("⚠️ Provide reply text after mention."); return
    else:
        await msg.reply_text("⚠️ Reply to a user or mention @username to set /rr."); return

    if not reply_text:
        await msg.reply_text("⚠️ Reply text cannot be empty."); return

    key = f"{chat_id}:{target_id}"
    async with data_lock:
        data["rr_entries"][key] = {"reply": reply_text, "emoji": emoji}
        save_data(data)
    await msg.reply_text(
        f"🎯🔁 Now replying with \"{reply_text}\" and reacting with {emoji} to {target_id}'s messages.\n"
        "Use /stoprr @username to remove."
    )

async def cmd_stoprr(update: Update, context: ContextTypes.DEFAULT_TYPE, args):
    chat_id = update.effective_chat.id
    target_id = None
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
    elif args and args[0].startswith("@"):
        username = args[0].lstrip("@")
        try:
            user = await context.bot.get_chat(f"@{username}")
            target_id = user.id
        except:
            await update.message.reply_text("❌ User not found."); return
    else:
        await update.message.reply_text("⚠️ Reply or mention @username to stop /rr."); return
    key = f"{chat_id}:{target_id}"
    async with data_lock:
        if key in data["rr_entries"]:
            del data["rr_entries"][key]; save_data(data)
            await update.message.reply_text("🛑 Reply+React removed.")
        else:
            await update.message.reply_text("No /rr set for that user.")

# ---------- LIVE STATUS ----------
def get_status_text():
    uptime = datetime.utcnow() - start_time
    uptime_str = str(uptime).split('.')[0]
    num_groups = len(data.get("all_chats", []))
    spam_count = sum(1 for cid, t in active_tasks.items() if t.get("spam") and not t["spam"].done())
    nc_count = sum(1 for cid, t in active_tasks.items() if t.get("nc") and not t["nc"].done())
    reply_count = sum(1 for cid, t in active_tasks.items() if t.get("reply") and not t["reply"].done())
    log_tail = "\n".join(log_buffer[-5:]) if log_buffer else "No logs yet."
    return (
        f"🤖 **Bot Status**\n"
        f"🆙 Uptime: `{uptime_str}`\n"
        f"👥 Groups: `{num_groups}`\n"
        f"🔥 Active Spams: `{spam_count}`\n"
        f"🔄 Active NC: `{nc_count}`\n"
        f"💬 Active Replies: `{reply_count}`\n"
        f"📄 Recent logs:\n```\n{log_tail}\n```"
    )

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await stop_loop_in_chat(chat_id, "status")
    msg = await update.message.reply_text(get_status_text(), parse_mode="Markdown")
    async with tasks_lock:
        if chat_id not in active_tasks:
            active_tasks[chat_id] = {"spam": None, "nc": None, "reply": None, "status": None}
    async def status_loop():
        while True:
            await asyncio.sleep(5)
            try:
                await msg.edit_text(get_status_text(), parse_mode="Markdown")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Status update error: {e}")
                break
    task = asyncio.create_task(status_loop())
    async with tasks_lock:
        active_tasks[chat_id]["status"] = task
    await update.message.reply_text("📊 Live status started. Use /stopstatus to stop.")

async def cmd_stopstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if await stop_loop_in_chat(chat_id, "status"):
        await update.message.reply_text("🛑 Live status stopped.")
    else:
        await update.message.reply_text("No active status loop.")

# ---------- OTHER UTILITY ----------
async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start = datetime.utcnow()
    msg = await update.message.reply_text("🏓 Pong!")
    end = datetime.utcnow()
    latency = (end - start).total_seconds() * 1000
    await msg.edit_text(f"🏓 Pong! `{latency:.2f} ms`", parse_mode="Markdown")

async def cmd_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not log_buffer:
        await update.message.reply_text("No logs captured yet.")
        return
    log_text = "\n".join(log_buffer[-50:])
    bio = io.BytesIO(log_text.encode("utf-8"))
    bio.name = "recent_logs.txt"
    await update.message.reply_document(document=bio, caption="📄 Recent logs (last 50 lines)")

async def cmd_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await resolve_user(update, context, context.args)
    if not user:
        await update.message.reply_text("⚠️ Reply to a user or mention @username.")
        return
    try:
        chat = await context.bot.get_chat(user.id)
    except:
        chat = user
    info = (
        f"👤 **User Info**\n"
        f"• ID: `{chat.id}`\n"
        f"• First Name: {chat.first_name or 'N/A'}\n"
        f"• Last Name: {chat.last_name or 'N/A'}\n"
        f"• Username: @{chat.username or 'N/A'}\n"
        f"• Language: {chat.language_code or 'N/A'}\n"
        f"• Is Bot: {'Yes' if chat.is_bot else 'No'}\n"
        f"• Bio: {chat.bio or 'N/A'}"
    )
    await update.message.reply_text(info, parse_mode="Markdown")

async def cmd_getalldp(update: Update, context: ContextTypes.DEFAULT_TYPE, args):
    user = await resolve_user(update, context, args)
    if not user:
        await update.message.reply_text("⚠️ Reply to a user or mention @username."); return
    try:
        photos = await context.bot.get_user_profile_photos(user.id, limit=100)
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to get photos: {e}"); return
    if not photos.photos:
        await update.message.reply_text("No profile photos found."); return
    total = len(photos.photos)
    sent = 0
    for i, photo_set in enumerate(photos.photos):
        largest = photo_set[-1]
        caption = f"Profile picture {i+1}/{total}"
        try:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=largest.file_id, caption=caption)
            sent += 1
            await asyncio.sleep(0.1)
        except Exception as e:
            logging.error(f"Error sending photo {i+1}: {e}")
    await update.message.reply_text(f"✅ Sent {sent}/{total} profile photos of {user.mention_html()}.", parse_mode="HTML")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
**📋 All Commands**

**🚀 Spam / NC / Reply**
- `/spam <text>` – Start spam loop
- `/nc [name]` – Auto change group name with emojis
- `/reply <text>` – Auto reply to a specific message
- `/stop`, `/stopspam`, `/stopnc`, `/stopreply`

**🌐 Global Loops**
- `/allgcspam <text>` – Spam in all groups
- `/allgcnc [name]` – Name change in all groups
- `/stopallgcspam`, `/stopallgcnc`

**❤️ Reactions**
- `/react @user [emoji]` – Auto react to user's messages
- `/globalreact @user [emoji]` – Global react
- `/stopreact`, `/stopglobalreact`
- `/changereactionemoji <emoji>`

**🎯 Target Reply**
- `/target @user <text>` – Auto reply to user's messages
- `/stoptarget`

**🔁 Reply+React (NEW)**
- `/rr <reply_text> [emoji]` – Auto reply + react to user's messages
- `/stoprr @user`

**🛡️ Group Management**
- `!dmute @user` – Delete all messages of user
- `!dunmute`, `!ban`, `!unban`, `!kick`, `!mute`, `!unmute`, `!warn`, `!pin`, `!unpin`, `!purge`
- `/fulldemote @user` – dmute + permanent mute
- `/fullundemote @user`

**👑 Owner / Admin**
- `/addadmin`, `/removeadmin`, `/addbot`, `/listbots`, `/setprefix`
- `/bots` – Show currently running bots
- `/restartbots` – Try to start all saved bots that aren't running

**🔧 Utility**
- `/ping` – Check bot latency
- `/logs` – Recent logs
- `/info @user` – User info
- `/getalldp @user` – Download all profile pics of a user
- `/status` – Live-updating bot status
- `/stopstatus` – Stop live status
- `/help` – This message

Prefixes: {", ".join(data["prefixes"])}
    """
    await update.message.reply_text(help_text, parse_mode="Markdown")

# ---------- BOTS COMMANDS ----------
async def cmd_bots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await reply_not_allowed(update); return
    count = len(running_bots)
    tokens = list(running_bots.keys())
    msg = f"**🤖 Running Bots: {count}**\n"
    for t in tokens:
        msg += f"• `...{t[-6:]}`\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_restartbots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await reply_not_allowed(update); return
    tokens = data["active_tokens"]
    started = 0
    for token in tokens:
        if token not in running_bots:
            app = await build_and_start_bot(token)
            if app:
                started += 1
    await update.message.reply_text(f"✅ Attempted to restart bots. Started {started} new bot(s). Now running {len(running_bots)} total.")

# ---------- OWNER / ADMIN / MULTI-BOT ----------
async def cmd_addadmin(update, context, args):
    if update.effective_user.id != data["owner_id"]:
        await reply_not_allowed(update); return
    if not args: await update.message.reply_text("⚠️ /addadmin <user_id>"); return
    try: uid = int(args[0])
    except: await update.message.reply_text("Invalid user ID."); return
    async with data_lock:
        if uid not in data["admins"]:
            data["admins"].append(uid); save_data(data)
            await update.message.reply_text(f"✅ Admin {uid} added.")
        else:
            await update.message.reply_text("Already an admin.")

async def cmd_removeadmin(update, context, args):
    if update.effective_user.id != data["owner_id"]:
        await reply_not_allowed(update); return
    if not args: await update.message.reply_text("⚠️ /removeadmin <user_id>"); return
    try: uid = int(args[0])
    except: await update.message.reply_text("Invalid user ID."); return
    async with data_lock:
        if uid in data["admins"]:
            data["admins"].remove(uid); save_data(data)
            await update.message.reply_text(f"✅ Admin {uid} removed.")
        else:
            await update.message.reply_text("Not an admin.")

async def cmd_addbot(update, context, args):
    if update.effective_user.id != data["owner_id"]:
        await reply_not_allowed(update); return
    if not args: await update.message.reply_text("⚠️ /addbot <new_bot_token>"); return
    new_token = args[0]
    # Check if token already in data
    async with data_lock:
        if new_token in data["active_tokens"]:
            # If token is in data but not running, try to start it
            if new_token in running_bots:
                await update.message.reply_text("❌ This bot is already running.")
                return
            else:
                # Token in data but not running – try to start it
                await update.message.reply_text("🔄 Token found in saved list but not running. Attempting to start...")
                app = await build_and_start_bot(new_token)
                if app:
                    await update.message.reply_text(f"✅ Bot started successfully! Token ends with ...{new_token[-5:]}")
                else:
                    await update.message.reply_text("❌ Failed to start the bot. Check token and logs.")
                return
        else:
            # New token – add and start
            data["active_tokens"].append(new_token)
            save_data(data)
    # Try to start the bot
    app = await build_and_start_bot(new_token)
    if app:
        await update.message.reply_text(f"✅ New bot started! Token ends with ...{new_token[-5:]}")
    else:
        await update.message.reply_text("❌ Failed to start new bot.")
        async with data_lock:
            data["active_tokens"].remove(new_token)
            save_data(data)

async def cmd_listbots(update, context):
    if not is_admin(update.effective_user.id):
        await reply_not_allowed(update); return
    tokens = data["active_tokens"]
    running = list(running_bots.keys())
    msg = "**Saved Bot Tokens:**\n" + "\n".join(f"• `...{t[-6:]}`" for t in tokens)
    msg += f"\n\n**Actually Running: {len(running)}**"
    await update.message.reply_text(msg, parse_mode="Markdown")

# ---------- COMMAND DISPATCHER ----------
async def command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    text = update.message.text
    command, args = parse_command(text)
    if not command: return

    user_id = update.effective_user.id
    no_auth = ["setowner", "addbot", "listbots", "ping", "help", "logs", "info", "getalldp", "bots", "restartbots"]
    if command not in no_auth and not is_admin(user_id):
        await reply_not_allowed(update)
        return

    chat = update.effective_chat
    if chat.type in ["group", "supergroup"]:
        async with data_lock:
            if chat.id not in data["all_chats"]:
                data["all_chats"].append(chat.id)
                save_data(data)

    # Route
    if command == "spam": await cmd_spam(update, context, args)
    elif command == "nc": await cmd_nc(update, context, args)
    elif command == "reply": await cmd_reply(update, context, args)
    elif command == "stop": await stop_loop(update, context)
    elif command == "stopspam": await stop_loop(update, context, "spam")
    elif command == "stopnc": await stop_loop(update, context, "nc")
    elif command == "stopreply": await stop_loop(update, context, "reply")
    elif command == "react": await cmd_react(update, context, args)
    elif command == "stopreact": await cmd_stopreact(update, context, args)
    elif command == "globalreact": await cmd_globalreact(update, context, args)
    elif command == "stopglobalreact": await cmd_stopglobalreact(update, context, args)
    elif command in ["changereactionemoji", "changereacremoji"]: await cmd_changereactionemoji(update, context, args)
    elif command == "target": await cmd_target(update, context, args)
    elif command == "stoptarget": await cmd_stoptarget(update, context, args)
    elif command == "rr": await cmd_rr(update, context, args)
    elif command == "stoprr": await cmd_stoprr(update, context, args)
    elif command == "dmute": await cmd_dmute(update, context, args)
    elif command == "dunmute": await cmd_dunmute(update, context, args)
    elif command == "ban": await cmd_ban(update, context, args)
    elif command == "unban": await cmd_unban(update, context, args)
    elif command == "kick": await cmd_kick(update, context, args)
    elif command == "mute": await cmd_mute(update, context, args)
    elif command == "unmute": await cmd_unmute(update, context, args)
    elif command == "warn": await cmd_warn(update, context, args)
    elif command == "pin": await cmd_pin(update, context)
    elif command == "unpin": await cmd_unpin(update, context, args)
    elif command == "purge": await cmd_purge(update, context)
    elif command == "allgcspam": await cmd_allgcspam(update, context, args)
    elif command == "allgcnc": await cmd_allgcnc(update, context, args)
    elif command == "stopallgcspam": await cmd_stopallgcspam(update, context)
    elif command == "stopallgcnc": await cmd_stopallgcnc(update, context)
    elif command == "fulldemote": await cmd_fulldemote(update, context, args)
    elif command == "fullundemote": await cmd_fullundemote(update, context, args)
    elif command == "status": await cmd_status(update, context)
    elif command == "stopstatus": await cmd_stopstatus(update, context)
    elif command == "setprefix": await cmd_setprefix(update, context, args)
    elif command == "addadmin": await cmd_addadmin(update, context, args)
    elif command == "removeadmin": await cmd_removeadmin(update, context, args)
    elif command == "addbot": await cmd_addbot(update, context, args)
    elif command == "listbots": await cmd_listbots(update, context)
    elif command == "bots": await cmd_bots(update, context)
    elif command == "restartbots": await cmd_restartbots(update, context)
    elif command == "setowner" and data["owner_id"] == 0:
        async with data_lock:
            data["owner_id"] = user_id; save_data(data)
        await update.message.reply_text("✅ You are now the owner.")
    elif command == "ping": await cmd_ping(update, context)
    elif command == "logs": await cmd_logs(update, context)
    elif command == "info": await cmd_info(update, context)
    elif command == "getalldp": await cmd_getalldp(update, context, args)
    elif command == "help": await cmd_help(update, context)
    else:
        await update.message.reply_text("Unknown command. Use /help.")

# ---------- AUTO HANDLER (ALL BOTS TOGETHER) ----------
async def auto_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user:
        return
    if update.message.from_user.id == context.bot.id:
        return

    user_id = update.message.from_user.id
    chat_id = update.effective_chat.id
    message_id = update.message.message_id

    chat = update.effective_chat
    if chat.type in ["group", "supergroup"]:
        async with data_lock:
            if chat_id not in data["all_chats"]:
                data["all_chats"].append(chat_id)
                save_data(data)

    # Dmute deletion (only receiving bot)
    async with data_lock:
        if f"{chat_id}:{user_id}" in data["dmuted_users"]:
            try:
                await context.bot.delete_message(chat_id, message_id)
                return
            except: pass

    local_key = f"{chat_id}:{user_id}"

    # Get all bots – if none, use current bot
    bots = get_all_bots()
    if not bots:
        bots = [context.bot]
    logging.info(f"[AUTO] Using {len(bots)} bots for message {message_id} in {chat_id}")

    # RR combined (reply + react)
    async with data_lock:
        rr = data["rr_entries"].get(local_key)
    if rr:
        reply_tasks = [bot.send_message(chat_id, rr["reply"], reply_to_message_id=message_id) for bot in bots]
        react_tasks = [bot.set_message_reaction(chat_id, message_id, reaction=[ReactionTypeEmoji(emoji=rr["emoji"])]) for bot in bots]
        try:
            await asyncio.gather(*reply_tasks, *react_tasks, return_exceptions=True)
        except Exception as e:
            logging.error(f"RR gather error: {e}")
        return

    # Normal reactions
    emoji = None
    async with data_lock:
        if local_key in data["local_reactions"]:
            emoji = data["local_reactions"][local_key]
        elif str(user_id) in data["global_reactions"]:
            emoji = data["global_reactions"][str(user_id)]
    if emoji:
        tasks = [bot.set_message_reaction(chat_id, message_id, reaction=[ReactionTypeEmoji(emoji=emoji)]) for bot in bots]
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logging.error(f"React gather error: {e}")

    # Normal target reply
    async with data_lock:
        reply_text = data["target_replies"].get(local_key)
    if reply_text:
        tasks = [bot.send_message(chat_id, reply_text, reply_to_message_id=message_id) for bot in bots]
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logging.error(f"Target reply gather error: {e}")

# ---------- WELCOME NEW MEMBER ----------
async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.new_chat_members: return
    chat = update.effective_chat
    group_name = chat.title or "this group"
    for new_member in update.message.new_chat_members:
        if new_member.id == context.bot.id: continue
        photo = None
        try:
            photos = await context.bot.get_user_profile_photos(new_member.id, limit=1)
            if photos.photos:
                photo = photos.photos[0][-1].file_id
        except: pass
        welcome_text = f"🎉 Welcome to **{group_name}**, {new_member.mention_html()}! 🎊"
        try:
            if photo:
                await context.bot.send_photo(chat_id=chat.id, photo=photo, caption=welcome_text, parse_mode="HTML")
            else:
                await context.bot.send_message(chat_id=chat.id, text=welcome_text, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Welcome message failed: {e}")

# ---------- BOT ADDED TO GROUP TRACKING ----------
async def chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    my_chat_member = update.my_chat_member
    if not my_chat_member: return
    if chat.type in ["group", "supergroup"]:
        new_status = my_chat_member.new_chat_member.status
        if new_status in ["member", "administrator"]:
            async with data_lock:
                if chat.id not in data["all_chats"]:
                    data["all_chats"].append(chat.id)
                    save_data(data)
        elif new_status in ["left", "kicked"]:
            async with data_lock:
                if chat.id in data["all_chats"]:
                    data["all_chats"].remove(chat.id)
                    save_data(data)

# ---------- BUILD & START BOT ----------
async def build_and_start_bot(token: str) -> Application:
    if token in running_bots:
        return running_bots[token]
    app = Application.builder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT, command_handler), group=1)
    app.add_handler(MessageHandler(filters.ALL, auto_handler), group=2)
    app.add_handler(ChatMemberHandler(chat_member_update, ChatMemberHandler.MY_CHAT_MEMBER), group=3)
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member), group=4)
    app.add_error_handler(lambda u, c: logging.error(c.error))
    try:
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        running_bots[token] = app
        logging.info(f"✅ Bot with token ...{token[-5:]} started successfully. Total running: {len(running_bots)}")
        return app
    except Exception as e:
        logging.error(f"Failed to start bot ...{token[-5:]}: {e}")
        return None

async def stop_all_bots():
    for token, app in running_bots.items():
        try:
            await app.updater.stop()
            await app.stop()
            await app.shutdown()
        except: pass
    running_bots.clear()

async def main():
    global start_time
    start_time = datetime.utcnow()
    try:
        primary_app = await build_and_start_bot(MAIN_TOKEN)
        if not primary_app:
            logging.critical("Main bot failed to start.")
            return
    except Exception as e:
        logging.critical(f"Failed to start main bot: {e}")
        return
    try:
        await primary_app.bot.send_message(OWNER_ID, "✅ Bot fully ready – MAX SPEED MODE! Use /restartbots to start all saved bots.")
    except:
        pass
    stop_event = asyncio.Event()
    try:
        await stop_event.wait()
    except KeyboardInterrupt:
        logging.info("Shutting down...")
    finally:
        await stop_all_bots()

if __name__ == "__main__":
    asyncio.run(main())
