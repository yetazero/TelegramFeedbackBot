import tkinter as tk
from tkinter import messagebox
import threading
import configparser
import logging
import os
import asyncio
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BANNED_FILE = "banned.txt"
CONFIG_FILE = "config.ini"
USERS_FILE = "users.txt"  

def load_banned():
    try:
        with open(BANNED_FILE, "r") as f:
            return {line.strip() for line in f if line.strip()}
    except FileNotFoundError:
        with open(BANNED_FILE, "w") as f:
            pass
        return set()

def save_banned(banned_users):
    try:
        with open(BANNED_FILE, "w") as f:
            f.write("\n".join(banned_users))
    except Exception as e:
        logging.error(f"Ban save error: {e}")

def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            return {line.strip() for line in f if line.strip().isdigit()}
    except FileNotFoundError:
        with open(USERS_FILE, "w") as f:
            pass
        return set()

def save_users(users):
    try:
        with open(USERS_FILE, "w") as f:
            f.write("\n".join(users))
    except Exception as e:
        logging.error(f"Users save error: {e}")

class TelegramBotApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Telegram Bot Manager")
        self.root.geometry("400x300")
        
        self.config = configparser.ConfigParser()
        
        if not os.path.exists(CONFIG_FILE):
            self.config['DEFAULT'] = {'admin_id': '', 'token': '', 'cooldown': '0'}
            with open(CONFIG_FILE, 'w') as configfile:
                self.config.write(configfile)
        
        self.config.read(CONFIG_FILE)
        self.admin_id = self.config.get('DEFAULT', 'admin_id', fallback='')
        self.token = self.config.get('DEFAULT', 'token', fallback='')
        
        self.frame = tk.Frame(root)
        self.frame.pack(padx=10, pady=10)
        
        tk.Label(self.frame, text="Admin ID:").grid(row=0, column=0, sticky=tk.W)
        self.admin_entry = tk.Entry(self.frame, width=30)
        self.admin_entry.grid(row=0, column=1, padx=5, pady=5)
        self.admin_entry.insert(0, self.admin_id)
        
        tk.Label(self.frame, text="Bot Token:").grid(row=1, column=0, sticky=tk.W)
        self.token_entry = tk.Entry(self.frame, width=30)
        self.token_entry.grid(row=1, column=1, padx=5, pady=5)
        self.token_entry.insert(0, self.token)
        
        self.status_label = tk.Label(root, text="Not running", fg="red")
        self.status_label.pack(pady=10)
        
        self.button_frame = tk.Frame(root)
        self.button_frame.pack(pady=5)
        
        self.start_btn = tk.Button(self.button_frame, text="Start Bot", command=self.start_bot, width=15)
        self.start_btn.grid(row=0, column=0, padx=5)
        
        self.stop_btn = tk.Button(self.button_frame, text="Stop Bot", command=self.stop_bot, width=15, state=tk.DISABLED)
        self.stop_btn.grid(row=0, column=1, padx=5)
        
        self.tray_btn = tk.Button(root, text="Minimize to Tray", command=self.add_to_tray)
        self.tray_btn.pack(pady=5)
        
        self.bot_thread = None
        self.bot_running = False
        self.tray_icon = None
        self.application = None
        self.stop_event = threading.Event()

    def save_config(self):
        self.config['DEFAULT'] = {
            'admin_id': self.admin_entry.get(),
            'token': self.token_entry.get(),
            'cooldown': self.config.get('DEFAULT', 'cooldown', fallback='0')
        }
        with open(CONFIG_FILE, 'w') as configfile:
            self.config.write(configfile)

    def start_bot(self):
        admin_id = self.admin_entry.get().strip()
        token = self.token_entry.get().strip()
        
        if not admin_id or not token:
            messagebox.showerror("Error", "Please fill in all fields")
            return
            
        try:
            admin_id = int(admin_id)
        except ValueError:
            messagebox.showerror("Error", "Invalid Admin ID format")
            return
            
        self.save_config()
        
        self.stop_event.clear()
        
        self.bot_thread = threading.Thread(target=self.run_bot, args=(token, admin_id))
        self.bot_thread.daemon = True
        self.bot_thread.start()
        
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_label.config(text="Running...", fg="green")

    def stop_bot(self):
        if self.bot_thread and self.bot_thread.is_alive():
            self.stop_event.set()
            
            self.bot_thread.join(timeout=2)
            
            self.status_label.config(text="Stopped", fg="red")
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)

    def add_to_tray(self):
        try:
            import pystray
            from PIL import Image, ImageDraw
            
            def on_restore(icon, item):
                icon.stop()
                self.root.after(0, self.root.deiconify)

            def on_exit(icon, item):
                icon.stop()
                self.root.after(0, self.root.quit)

            image = Image.new('RGB', (64, 64), color='blue')
            dc = ImageDraw.Draw(image)
            dc.rectangle((16, 16, 48, 48), fill='white')
            
            menu = pystray.Menu(
                pystray.MenuItem("Restore", on_restore),
                pystray.MenuItem("Exit", on_exit)
            )
            
            self.tray_icon = pystray.Icon("Telegram Bot Manager", image, "Telegram Bot Manager", menu)
            
            self.root.withdraw()
            
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
            
        except ImportError as e:
            logging.error(f"Failed to import tray dependencies: {e}")
            messagebox.showerror("Error", "Failed to initialize tray. Make sure pystray and Pillow are installed.")

    def run_bot(self, token, admin_id):
        try:
            from telegram import Update
            from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
            
            banned = load_banned()
            users = load_users()
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            send_states = {}
            publish_state = {"active": False, "content": None}
            
            user_last_message = {}
            
            cooldown_seconds = int(self.config.get('DEFAULT', 'cooldown', fallback='0'))
            
            async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
                user_id = str(update.effective_user.id)
                
                if user_id not in users:
                    users.add(user_id)
                    save_users(users)
                
                if update.effective_user.id == admin_id:
                    help_message = (
                        "Welcome, Admin!\n\n"
                        "Available commands:\n"
                        "/ban user-id (/b) - Ban a user\n"
                        "/unban user-id (/u) - Unban a user\n"
                        "/cancel (/c) - Cancel message sending\n"
                        "/publish (/p) - Send message to all users\n"
                        "/cooldown seconds - Set anti-spam timer (0 to disable)\n"
                        "/help (/h) - Show this help"
                    )
                    await update.message.reply_text(help_message)
                else:
                    await update.message.reply_text("Write your message here:")
            
            async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
                if update.effective_user.id != admin_id:
                    return
                
                try:
                    user_id = str(context.args[0])
                    if user_id in banned:
                        await update.message.reply_text("User is already banned")
                        return
                    banned.add(user_id)
                    save_banned(banned)
                    await update.message.reply_text(f"User {user_id} has been banned")
                except (IndexError, ValueError):
                    await update.message.reply_text("Usage: /ban user-id or /b user-id")
            
            async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
                if update.effective_user.id != admin_id:
                    return
                
                try:
                    user_id = str(context.args[0])
                    if user_id not in banned:
                        await update.message.reply_text("User is not banned")
                        return
                    banned.remove(user_id)
                    save_banned(banned)
                    await update.message.reply_text(f"User {user_id} has been unbanned")
                except (IndexError, ValueError):
                    await update.message.reply_text("Usage: /unban user-id or /u user-id")
            
            async def set_cooldown(update: Update, context: ContextTypes.DEFAULT_TYPE):
                if update.effective_user.id != admin_id:
                    return
                
                try:
                    new_cooldown = int(context.args[0])
                    if new_cooldown < 0:
                        await update.message.reply_text("Cooldown must be 0 or positive number")
                        return
                        
                    nonlocal cooldown_seconds
                    cooldown_seconds = new_cooldown
                    
                    self.config['DEFAULT']['cooldown'] = str(new_cooldown)
                    with open(CONFIG_FILE, 'w') as configfile:
                        self.config.write(configfile)
                    
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
                await update.message.reply_text("Please send the content you want to publish to all users.")
            
            async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
                if update.effective_user.id == admin_id:
                    help_message = (
                        "Available commands:\n"
                        "/ban user-id (/b) - Ban a user\n"
                        "/unban user-id (/u) - Unban a user\n"
                        "/cancel (/c) - Cancel message sending\n"
                        "/publish (/p) - Send message to all users\n"
                        "/cooldown seconds - Set anti-spam timer (0 to disable)\n"
                        "/help (/h) - Show this help"
                    )
                    await update.message.reply_text(help_message)
                else:
                    await update.message.reply_text("Send your message to the administrator here. I'll forward it.")
            
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
                            f"Ready to publish to {len(users)} users. Please reply with `/confirm` to proceed or `/cancel` to abort."
                        )
                    else:
                        await message.reply_text("No content detected. Please send something to publish.")
                    return
                
                if message.text and message.text.lower().strip() == "confirm" and publish_state["content"]:
                    await process_publishing(message, context.bot, publish_state["content"], users, banned)
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
            
            async def process_publishing(message, bot, content, users, banned):
                sent_count = 0
                failed_count = 0
                
                status_msg = await message.reply_text(f"Publishing to {len(users)} users...")
                
                for user_id_str in users:
                    if user_id_str in banned:
                        continue
                        
                    try:
                        target_user_id = int(user_id_str)
                        await send_content_to_user(bot, target_user_id, content)
                        sent_count += 1
                        
                        if sent_count % 10 == 0:
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
                if user_id_str not in users:
                    users.add(user_id_str)
                    save_users(users)
                
                if user_id_str in banned:
                    return
                    
                if cooldown_seconds > 0:
                    current_time = time.time()
                    if user_id_str in user_last_message:
                        time_diff = current_time - user_last_message[user_id_str]
                        if time_diff < cooldown_seconds:
                            remaining = round(cooldown_seconds - time_diff)
                            await update.message.reply_text(f"Please wait {remaining} seconds before sending another message.")
                            return
                
                message = update.message
                username = update.effective_user.username or "N/A"
                
                user_last_message[user_id_str] = time.time()
                
                user_info = (
                    f"Message from user:\n"
                    f"User ID: `{user_id}`\n"
                    f"Username: @{username}"
                )
                
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
                
                # Forward location
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
                
                # Forward contact
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
                
                # Forward poll
                if message.poll:
                    # Get poll options
                    options = [option.text for option in message.poll.options]
                    
                    # Forward poll to admin
                    await context.bot.send_poll(
                        chat_id=admin_id,
                        question=message.poll.question,
                        options=options,
                        is_anonymous=message.poll.is_anonymous,
                        type=message.poll.type,
                        allows_multiple_answers=message.poll.allows_multiple_answers,
                        explanation=message.poll.explanation
                    )
                    
                    # Send user info separately
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
                    await process_publishing(update.message, context.bot, publish_state["content"], users, banned)
                else:
                    await update.message.reply_text("Nothing to confirm.")

            async def run_async_bot():
                app = Application.builder().token(token).build()
                
                app.add_handler(CommandHandler("start", start))
                app.add_handler(CommandHandler(["ban", "b"], ban_user))
                app.add_handler(CommandHandler(["unban", "u"], unban_user))
                app.add_handler(CommandHandler(["cancel", "c"], cancel_sending))
                app.add_handler(CommandHandler(["publish", "p"], start_publish))
                app.add_handler(CommandHandler("cooldown", set_cooldown))
                app.add_handler(CommandHandler(["help", "h"], show_help))
                app.add_handler(CommandHandler("confirm", confirm_command))
                
                admin_filter = filters.User(admin_id) & ~filters.COMMAND
                app.add_handler(MessageHandler(admin_filter, handle_admin_message))
                
                user_filter = ~filters.User(admin_id) & ~filters.COMMAND
                app.add_handler(MessageHandler(user_filter, forward_to_admin))
                
                await app.initialize()
                await app.start()
                await app.updater.start_polling()
                
                logging.info("Bot started successfully")
                
                try:
                    while not self.stop_event.is_set():
                        await asyncio.sleep(1)
                finally:
                    logging.info("Stopping bot...")
                    await app.updater.stop()
                    await app.stop()
                    await app.shutdown()
                    logging.info("Bot stopped")

            try:
                loop.run_until_complete(run_async_bot())
            except Exception as e:
                logging.error(f"Bot runtime error: {e}")
                self.status_label.config(text="Error: " + str(e), fg="red")
                self.start_btn.config(state=tk.NORMAL)
                self.stop_btn.config(state=tk.DISABLED)
        except ImportError as e:
            logging.error(f"Failed to import Telegram libraries: {e}")
            messagebox.showerror("Error", "Failed to start bot. Make sure python-telegram-bot is installed.")
            self.status_label.config(text="Error: Missing dependencies", fg="red")
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)


if __name__ == "__main__":
    root = tk.Tk()
    app = TelegramBotApp(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.stop_bot(), root.destroy()))
    root.mainloop()
