import asyncio
import logging
import threading
import time

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ParseMode

from utils import load_banned, save_banned, load_users, save_users
from config_manager import ConfigManager

# Shared event for stopping the bot
stop_telegram_bot_event = threading.Event()

# Global state for send states and publish state
send_states = {}
publish_state = {"active": False, "content": None}

# Global dictionary for user last message time for cooldown
user_last_message = {}

# This will be loaded from config when the bot starts
current_cooldown_seconds = 0
admin_id = None # Admin ID will be set when run_telegram_bot is called

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    # Check if user is banned
    banned_users = load_banned()
    if user_id in banned_users:
        await update.message.reply_text("You are currently banned from using this bot.")
        return

    # User is automatically added to users.txt (subscribed) on /start
    # if they are not already there and not banned.
    users = load_users()
    if user_id not in users: # Only add if not already in the list
        users.add(user_id)
        save_users(users)
        # Optional: Inform the user about automatic subscription and how to unsubscribe.
        # await update.message.reply_text("You've been subscribed to updates! You can use /unsubscribe to opt-out.")
    
    if update.effective_user.id == admin_id:
        help_message = (
            "Welcome, Admin!\n\n"
            "Available commands:\n"
            "/ban user-id (/b) - Ban a user\n"
            "/unban user-id (/u) - Unban a user\n"
            "/cancel (/c) - Cancel message sending\n"
            "/publish (/p) - Send message to all subscribed users\n"
            "/cooldown seconds - Set anti-spam timer (0 to disable)\n"
            "/help (/h) - Show this help\n"
            "/subscribe (/sub) - Subscribe to mass publications\n"
            "/unsubscribe (/unsub) - Unsubscribe from mass publications\n\n"
            "Author - <a href='https://t.me/yetazero'>yetazero</a>"
        )
        await update.message.reply_text(help_message, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text("Write your message here:")

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != admin_id:
        return
    
    banned_users = load_banned()
    users = load_users() # Load users list to remove banned user from it
    try:
        user_id_to_ban = str(context.args[0])
        if user_id_to_ban in banned_users:
            await update.message.reply_text("User is already banned")
            return
        
        banned_users.add(user_id_to_ban)
        save_banned(banned_users)
        
        # Also remove from users list (subscription list) if they are there
        if user_id_to_ban in users:
            users.remove(user_id_to_ban)
            save_users(users)

        await update.message.reply_text(f"User {user_id_to_ban} has been banned and removed from subscriptions.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /ban user-id or /b user-id")

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != admin_id:
        return
    
    banned_users = load_banned()
    try:
        user_id_to_unban = str(context.args[0])
        if user_id_to_unban not in banned_users:
            await update.message.reply_text("User is not banned")
            return
        banned_users.remove(user_id_to_unban)
        save_banned(banned_users)
        
        # When unbanning, user is NOT automatically re-added to users.txt.
        # They would be re-added on their next /start if not already in users.txt,
        # or they can use /subscribe.
        await update.message.reply_text(f"User {user_id_to_unban} has been unbanned. They will be re-subscribed on next /start if not already, or can use /subscribe.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /unban user-id or /u user-id")

async def set_cooldown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != admin_id:
        return
    
    global current_cooldown_seconds
    try:
        new_cooldown = int(context.args[0])
        if new_cooldown < 0:
            await update.message.reply_text("Cooldown must be 0 or positive number")
            return
            
        current_cooldown_seconds = new_cooldown
        
        config_manager = ConfigManager("config.ini")
        config_manager.set_config('cooldown', str(new_cooldown))
        config_manager.save_config()
        
        if new_cooldown == 0:
            await update.message.reply_text("Anti-spam protection disabled")
        else:
            await update.message.reply_text(f"Anti-spam cooldown set to {new_cooldown} seconds")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /cooldown seconds (0 to disable)")

async def cancel_sending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != admin_id:
        return
    
    user_id = update.effective_user.id
    if user_id in send_states and send_states[user_id]["step"] == "choose_user":
        del send_states[user_id]
        await update.message.reply_text("Cancelled.")
    elif publish_state["active"]:
        publish_state["active"] = False
        publish_state["content"] = None
        await update.message.reply_text("Mass mailing cancelled.")
    else:
        await update.message.reply_text("Nothing to cancel.")

async def start_publish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != admin_id:
        return
    
    publish_state["active"] = True
    await update.message.reply_text("Please send the content you want to publish to all subscribed users.")

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == admin_id:
        help_message = (
            "Available commands:\n"
            "/ban user-id (/b) - Ban a user\n"
            "/unban user-id (/u) - Unban a user\n"
            "/cancel (/c) - Cancel message sending\n"
            "/publish (/p) - Send message to all subscribed users\n"
            "/cooldown seconds - Set anti-spam timer (0 to disable)\n"
            "/help (/h) - Show this help\n"
            "/subscribe (/sub) - Subscribe to mass publications\n"
            "/unsubscribe (/unsub) - Unsubscribe from mass publications\n\n"
            "Author - <a href='https://t.me/yetazero'>yetazero</a>"
        )
        await update.message.reply_text(help_message, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text("Send your message to the administrator here. I'll forward it.")

async def subscribe_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id_to_subscribe = str(update.effective_user.id)
    
    banned_users = load_banned()
    if user_id_to_subscribe in banned_users:
        await update.message.reply_text("You cannot subscribe because you are currently banned.")
        return

    all_users = load_users() # This is users.txt, i.e. the subscription list
    
    if user_id_to_subscribe not in all_users: # If not already in subscription list
        all_users.add(user_id_to_subscribe)   # Add to subscription list
        save_users(all_users)                 # Save subscription list
        await update.message.reply_text("You have successfully subscribed to mass publications from the administrator!")
    else:
        await update.message.reply_text("You are already subscribed to mass publications.")

async def unsubscribe_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id_to_unsubscribe = str(update.effective_user.id)
    
    all_users = load_users() # This is users.txt
    
    if user_id_to_unsubscribe in all_users: # If user is in the subscription list
        all_users.remove(user_id_to_unsubscribe) # Remove them
        save_users(all_users)                 # Save the updated list
        await update.message.reply_text("You have been unsubscribed from mass publications. You will no longer receive them from the administrator.")
    else:
        await update.message.reply_text("You are not currently subscribed to mass publications.")

async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != admin_id:
        return
    
    user_id = update.effective_user.id
    message = update.message
    
    if publish_state["active"]:
        publish_content = {
            "document": message.document.file_id if message.document else None,
            "photo": message.photo[-1].file_id if message.photo else None,
            "video": message.video.file_id if message.video else None,
            "audio": message.audio.file_id if message.audio else None,
            "voice": message.voice.file_id if message.voice else None,
            "video_note": message.video_note.file_id if message.video_note else None,
            "sticker": message.sticker.file_id if message.sticker else None,
            "text": message.text if message.text else None,
            "caption": message.caption if message.caption else None,
            "dice": {"emoji": message.dice.emoji, "value": message.dice.value} if message.dice else None,
            "location": {"latitude": message.location.latitude, "longitude": message.location.longitude} if message.location else None,
            "contact": {"phone_number": message.contact.phone_number, "first_name": message.contact.first_name} if message.contact else None,
            "poll": message.poll.to_dict() if message.poll else None
        }
        
        if any(value for key, value in publish_content.items() if key != "caption"):
            publish_state["content"] = publish_content
            
            await message.reply_text(
                f"Ready to publish to {len(load_users())} users. Please reply with `/confirm` to proceed or `/cancel` to abort."
            )
        else:
            await message.reply_text("No content detected. Please send something to publish.")
        return
    
    if message.text and message.text.lower().strip() == "/confirm" and publish_state["content"]:
        await process_publishing(message, context.bot, publish_state["content"])
        return
    
    if any([message.document, message.photo, message.video, message.audio, 
           message.voice, message.video_note, message.sticker, message.dice,
           message.location, message.contact, message.poll]):
        send_states[user_id] = {
            "content": {
                "document": message.document.file_id if message.document else None,
                "photo": message.photo[-1].file_id if message.photo else None,
                "video": message.video.file_id if message.video else None,
                "audio": message.audio.file_id if message.audio else None,
                "voice": message.voice.file_id if message.voice else None,
                "video_note": message.video_note.file_id if message.video_note else None,
                "sticker": message.sticker.file_id if message.sticker else None,
                "caption": message.caption,
                "dice": {"emoji": message.dice.emoji, "value": message.dice.value} if message.dice else None,
                "location": {"latitude": message.location.latitude, "longitude": message.location.longitude} if message.location else None,
                "contact": {"phone_number": message.contact.phone_number, "first_name": message.contact.first_name} if message.contact else None,
                "poll": message.poll.to_dict() if message.poll else None
            },
            "step": "choose_user"
        }
        await message.reply_text("Now enter the user ID:")
    
    elif message.text and user_id not in send_states:
        send_states[user_id] = {
            "content": {
                "text": message.text
            },
            "step": "choose_user"
        }
        await message.reply_text("Now enter the user ID:")
    
    elif message.text and user_id in send_states and send_states[user_id]["step"] == "choose_user":
        target_user_id = message.text.strip()
        
        if not target_user_id.isdigit():
            await message.reply_text("Invalid user ID. Please enter a valid numeric ID.")
            return
        
        target_user_id = int(target_user_id)
        content = send_states[user_id]["content"]
        
        try:
            await send_content_to_user(context.bot, target_user_id, content)
            await message.reply_text(f"Content sent to user {target_user_id}.")
        except Exception as e:
            logging.error(f"Failed to send content: {e}")
            await message.reply_text(f"Failed to send content: {e}")
        
        del send_states[user_id]

async def process_publishing(message, bot, content):
    sent_count = 0
    failed_count = 0
    
    users = load_users() # Only send to subscribed users (from users.txt)
    banned = load_banned()

    status_msg = await message.reply_text(f"Publishing to {len(users)} users...")
    
    for user_id_str in users:
        if user_id_str in banned: # Double-check to ensure no banned users receive
            continue
            
        try:
            target_user_id = int(user_id_str)
            await send_content_to_user(bot, target_user_id, content)
            sent_count += 1
            
            if sent_count % 10 == 0: # Update status every 10 users
                await status_msg.edit_text(
                    f"Publishing: {sent_count}/{len(users)} done, {failed_count} failed..."
                )
                
        except Exception as e:
            logging.error(f"Failed to publish to user {user_id_str}: {e}")
            failed_count += 1
    
    await status_msg.edit_text(
        f"Publishing complete: {sent_count} succeeded, {failed_count} failed."
    )
    
    publish_state["active"] = False
    publish_state["content"] = None

async def send_content_to_user(bot, target_user_id, content):
    if content.get("document"):
        await bot.send_document(
            chat_id=target_user_id, 
            document=content["document"], 
            caption=content.get("caption")
        )
    elif content.get("photo"):
        await bot.send_photo(
            chat_id=target_user_id, 
            photo=content["photo"], 
            caption=content.get("caption")
        )
    elif content.get("video"):
        await bot.send_video(
            chat_id=target_user_id, 
            video=content["video"], 
            caption=content.get("caption")
        )
    elif content.get("audio"):
        await bot.send_audio(
            chat_id=target_user_id, 
            audio=content["audio"], 
            caption=content.get("caption")
        )
    elif content.get("voice"):
        await bot.send_voice(
            chat_id=target_user_id, 
            voice=content["voice"], 
            caption=content.get("caption")
        )
    elif content.get("video_note"):
        await bot.send_video_note(
            chat_id=target_user_id, 
            video_note=content["video_note"]
        )
    elif content.get("sticker"):
        await bot.send_sticker(
            chat_id=target_user_id, 
            sticker=content["sticker"]
        )
    elif content.get("dice"):
        await bot.send_dice(
            chat_id=target_user_id, 
            emoji=content["dice"]["emoji"]
        )
    elif content.get("location"):
        await bot.send_location(
            chat_id=target_user_id,
            latitude=content["location"]["latitude"],
            longitude=content["location"]["longitude"]
        )
    elif content.get("contact"):
        await bot.send_contact(
            chat_id=target_user_id,
            phone_number=content["contact"]["phone_number"],
            first_name=content["contact"]["first_name"]
        )
    elif content.get("poll"):
        poll_data = content["poll"]
        await bot.send_poll(
            chat_id=target_user_id,
            question=poll_data["question"],
            options=[option["text"] for option in poll_data["options"]],
            is_anonymous=poll_data["is_anonymous"],
            type=poll_data["type"],
            allows_multiple_answers=poll_data["allows_multiple_answers"],
            explanation=poll_data.get("explanation")
        )
    elif content.get("text"):
        await bot.send_message(
            chat_id=target_user_id, 
            text=content["text"]
        )

async def forward_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_id_str = str(user_id)
    
    banned_users = load_banned()
    if user_id_str in banned_users:
        # If banned, just ignore the message and don't forward it.
        return
        
    # MODIFICATION: Sending a message does NOT automatically add user to users.txt (subscription list)
    # all_users = load_users()
    # if user_id_str not in all_users:
    #     all_users.add(user_id_str)
    #     save_users(all_users)
    
    global current_cooldown_seconds
    if current_cooldown_seconds > 0:
        current_time = time.time()
        if user_id_str in user_last_message:
            time_diff = current_time - user_last_message[user_id_str]
            if time_diff < current_cooldown_seconds:
                remaining = round(current_cooldown_seconds - time_diff)
                await update.message.reply_text(f"Please wait {remaining} seconds before sending another message.")
                return
    
    message = update.message
    first_name = update.effective_user.first_name or ""
    last_name = update.effective_user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()
    username = update.effective_user.username or "N/A"
    
    user_last_message[user_id_str] = time.time()
    
    user_info = (
        f"Message from user:\n"
        f"User ID: `{user_id}`\n"
        f"Username: @{username}"
    )
    if full_name:
        user_info += f"\nName: {full_name}"
    
    if message.text:
        await context.bot.send_message(admin_id, f"{user_info}\nText: {message.text}", parse_mode="Markdown")
    
    caption = message.caption or ""
    caption_info = f"\nCaption: {caption}" if caption else ""
    
    if message.dice:
        dice_emoji = message.dice.emoji
        dice_value = message.dice.value
        
        await context.bot.send_dice(
            chat_id=admin_id,
            emoji=dice_emoji
        )
        
        await context.bot.send_message(
            chat_id=admin_id,
            text=f"{user_info}\nDice sent with emoji: {dice_emoji}, value: {dice_value}",
            parse_mode="Markdown"
        )
    
    if message.document:
        await context.bot.send_document(
            chat_id=admin_id,
            document=message.document.file_id,
            caption=f"{user_info}{caption_info}",
            parse_mode="Markdown"
        )
    
    if message.photo:
        await context.bot.send_photo(
            chat_id=admin_id,
            photo=message.photo[-1].file_id,
            caption=f"{user_info}{caption_info}",
            parse_mode="Markdown"
        )
    
    if message.video:
        await context.bot.send_video(
            chat_id=admin_id,
            video=message.video.file_id,
            caption=f"{user_info}{caption_info}",
            parse_mode="Markdown"
        )
    
    if message.audio:
        await context.bot.send_audio(
            chat_id=admin_id,
            audio=message.audio.file_id,
            caption=f"{user_info}{caption_info}",
            parse_mode="Markdown"
        )
    
    if message.voice:
        await context.bot.send_voice(
            chat_id=admin_id,
            voice=message.voice.file_id,
            caption=f"{user_info}{caption_info}",
            parse_mode="Markdown"
        )
    
    if message.video_note:
        await context.bot.send_video_note(
            chat_id=admin_id,
            video_note=message.video_note.file_id
        )
        await context.bot.send_message(
            chat_id=admin_id,
            text=f"{user_info}",
            parse_mode="Markdown"
        )
    
    if message.sticker:
        await context.bot.send_sticker(
            chat_id=admin_id,
            sticker=message.sticker.file_id
        )
        await context.bot.send_message(
            chat_id=admin_id,
            text=f"{user_info}",
            parse_mode="Markdown"
        )
    
    if message.location:
        await context.bot.send_location(
            chat_id=admin_id,
            latitude=message.location.latitude,
            longitude=message.location.longitude
        )
        await context.bot.send_message(
            chat_id=admin_id,
            text=f"{user_info}\nLocation received",
            parse_mode="Markdown"
        )
    
    if message.contact:
        await context.bot.send_contact(
            chat_id=admin_id,
            phone_number=message.contact.phone_number,
            first_name=message.contact.first_name,
            last_name=message.contact.last_name
        )
        await context.bot.send_message(
            chat_id=admin_id,
            text=f"{user_info}\nContact received",
            parse_mode="Markdown"
        )
    
    if message.poll:
        options = [option.text for option in message.poll.options]
        
        await context.bot.send_poll(
            chat_id=admin_id,
            question=message.poll.question,
            options=options,
            is_anonymous=message.poll.is_anonymous,
            type=message.poll.type,
            allows_multiple_answers=message.poll.allows_multiple_answers,
            explanation=message.poll.explanation
        )
        
        await context.bot.send_message(
            chat_id=admin_id,
            text=f"{user_info}\nPoll received",
            parse_mode="Markdown"
        )
    
    await message.reply_text("Your message has been sent to the administrator!")

async def confirm_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != admin_id:
        return
        
    if publish_state["content"]:
        await process_publishing(update.message, context.bot, publish_state["content"])
    else:
        await update.message.reply_text("Nothing to confirm.")

async def run_telegram_bot(token: str, admin_id_param: int, initial_cooldown: int):
    global admin_id, current_cooldown_seconds
    admin_id = admin_id_param
    current_cooldown_seconds = initial_cooldown
    
    try:
        app = Application.builder().token(token).build()
        
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler(["ban", "b"], ban_user))
        app.add_handler(CommandHandler(["unban", "u"], unban_user))
        app.add_handler(CommandHandler(["cancel", "c"], cancel_sending))
        app.add_handler(CommandHandler(["publish", "p"], start_publish))
        app.add_handler(CommandHandler("cooldown", set_cooldown))
        app.add_handler(CommandHandler(["help", "h"], show_help))
        app.add_handler(CommandHandler("confirm", confirm_command))
        app.add_handler(CommandHandler(["subscribe", "sub"], subscribe_user))
        app.add_handler(CommandHandler(["unsubscribe", "unsub"], unsubscribe_user))
        
        admin_filter = filters.User(admin_id) & ~filters.COMMAND
        app.add_handler(MessageHandler(admin_filter, handle_admin_message))
        
        user_filter = ~filters.User(admin_id) & ~filters.COMMAND
        app.add_handler(MessageHandler(user_filter, forward_to_admin))
        
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        
        logging.info("Bot started successfully")
        
        while not stop_telegram_bot_event.is_set():
            await asyncio.sleep(1)
    finally:
        logging.info("Stopping bot...")
        if 'app' in locals() and app.running:
            await app.updater.stop()
            await app.stop()
            await app.shutdown()
        logging.info("Bot stopped")
