import tkinter as tk
from tkinter import messagebox
import threading
import configparser
import logging
import os
import asyncio
import sys

# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Configuration
BANNED_FILE = "banned.txt"
CONFIG_FILE = "config.ini"
USERS_FILE = "users.txt"  # Файл для хранения ID пользователей

# Banned list functions
def load_banned():
    try:
        with open(BANNED_FILE, "r") as f:
            return {line.strip() for line in f if line.strip()}
    except FileNotFoundError:
        # Create empty file if not exists
        with open(BANNED_FILE, "w") as f:
            pass
        return set()

def save_banned(banned_users):
    try:
        with open(BANNED_FILE, "w") as f:
            f.write("\n".join(banned_users))
    except Exception as e:
        logging.error(f"Ban save error: {e}")

# User list functions
def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            return {line.strip() for line in f if line.strip().isdigit()}
    except FileNotFoundError:
        # Create empty file if not exists
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
        
        # Loading configuration
        self.config = configparser.ConfigParser()
        
        # Create default config if it doesn't exist
        if not os.path.exists(CONFIG_FILE):
            self.config['DEFAULT'] = {'admin_id': '', 'token': ''}
            with open(CONFIG_FILE, 'w') as configfile:
                self.config.write(configfile)
        
        self.config.read(CONFIG_FILE)
        self.admin_id = self.config.get('DEFAULT', 'admin_id', fallback='')
        self.token = self.config.get('DEFAULT', 'token', fallback='')
        
        # Interface
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
            'token': self.token_entry.get()
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
        
        # Reset stop event
        self.stop_event.clear()
        
        # Start bot in a separate thread
        self.bot_thread = threading.Thread(target=self.run_bot, args=(token, admin_id))
        self.bot_thread.daemon = True
        self.bot_thread.start()
        
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_label.config(text="Running...", fg="green")

    def stop_bot(self):
        if self.bot_thread and self.bot_thread.is_alive():
            # Signal the thread to stop
            self.stop_event.set()
            
            # Wait for thread to finish (with timeout)
            self.bot_thread.join(timeout=2)
            
            # Update UI
            self.status_label.config(text="Stopped", fg="red")
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)

    def add_to_tray(self):
        try:
            # Try to import only when function is called
            import pystray
            from PIL import Image, ImageDraw
            
            def on_restore(icon, item):
                icon.stop()
                self.root.after(0, self.root.deiconify)

            def on_exit(icon, item):
                icon.stop()
                self.root.after(0, self.root.quit)

            # Create a simple icon 
            image = Image.new('RGB', (64, 64), color='blue')
            dc = ImageDraw.Draw(image)
            dc.rectangle((16, 16, 48, 48), fill='white')
            
            menu = pystray.Menu(
                pystray.MenuItem("Restore", on_restore),
                pystray.MenuItem("Exit", on_exit)
            )
            
            self.tray_icon = pystray.Icon("Telegram Bot Manager", image, "Telegram Bot Manager", menu)
            
            # Hide main window
            self.root.withdraw()
            
            # Start tray icon in separate thread
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
            
        except ImportError as e:
            logging.error(f"Failed to import tray dependencies: {e}")
            messagebox.showerror("Error", "Failed to initialize tray. Make sure pystray and Pillow are installed.")

    def run_bot(self, token, admin_id):
        try:
            # Import python-telegram-bot
            from telegram import Update
            from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
            
            banned = load_banned()
            users = load_users()
            
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Dictionary to store message sending states
            send_states = {}
            publish_state = {"active": False, "content": None}
            
            # Command handlers
            async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
                user_id = str(update.effective_user.id)
                
                # Add user to users list
                if user_id not in users:
                    users.add(user_id)
                    save_users(users)
                
                if update.effective_user.id == admin_id:
                    help_message = (
                        "Welcome, Admin!\n\n"
                        "Available commands:\n"
                        "/ban user-id (`/b`) - Ban a user\n"
                        "/unban user-id (`/u`) - Unban a user\n"
                        "/cancel (`/c`) - Cancel message sending\n"
                        "/publish (`/p`) - Send message to all users\n"
                        "/help (`/h`) - Show this help\n\n"
                        "To send a message to a user, enter the message and then the user ID.\n\n"
                        "Author: [yetazero](https://t.me/yetazero)"
                    )
                    await update.message.reply_text(help_message, parse_mode="Markdown")
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
                        "/ban user-id (`/b`) - Ban a user\n"
                        "/unban user-id (`/u`) - Unban a user\n"
                        "/cancel (`/c`) - Cancel message sending\n"
                        "/publish (`/p`) - Send message to all users\n"
                        "/help (`/h`) - Show this help\n\n"
                        "To send a message to a user, enter the message and then the user ID.\n\n"
                        "Author: [yetazero](https://t.me/yetazero)"
                    )
                    await update.message.reply_text(help_message, parse_mode="Markdown")
                else:
                    await update.message.reply_text("Send your message to the administrator here. I'll forward it.")
            
            async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
                if update.effective_user.id != admin_id:
                    return
                
                user_id = update.effective_user.id
                message = update.message
                
                # Handle publish mode
                if publish_state["active"]:
                    # Capture the message for publishing
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
                        "dice": {"emoji": message.dice.emoji, "value": message.dice.value} if message.dice else None
                    }
                    
                    # Check if any content was captured
                    if any(value for key, value in publish_content.items() if key != "caption"):
                        publish_state["content"] = publish_content
                        
                        # Only text prompt, no button
                        await message.reply_text(
                            f"Ready to publish to {len(users)} users. Please reply with `/confirm` to proceed or `/cancel` to abort.",
                            parse_mode="Markdown"
                        )
                    else:
                        await message.reply_text("No content detected. Please send something to publish.")
                    return
                
                # Process confirmation for publishing
                if message.text and message.text.lower().strip() == "confirm" and publish_state["content"]:
                    await process_publishing(message, context.bot, publish_state["content"], users, banned)
                    return
                
                # If admin sends any content (file, photo, video, etc.)
                if any([message.document, message.photo, message.video, message.audio, 
                       message.voice, message.video_note, message.sticker, message.dice]):
                    # Save content data
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
                            "dice": {"emoji": message.dice.emoji, "value": message.dice.value} if message.dice else None
                        },
                        "step": "choose_user"
                    }
                    await message.reply_text("Now enter the user ID:")
                
                # If admin sends text only
                elif message.text and user_id not in send_states:
                    # Save text
                    send_states[user_id] = {
                        "content": {
                            "text": message.text
                        },
                        "step": "choose_user"
                    }
                    await message.reply_text("Now enter the user ID:")
                
                # If admin enters user ID
                elif message.text and user_id in send_states and send_states[user_id]["step"] == "choose_user":
                    target_user_id = message.text.strip()
                    
                    # Check if it's a number
                    if not target_user_id.isdigit():
                        await message.reply_text("Invalid user ID. Please enter a valid numeric ID.")
                        return
                    
                    target_user_id = int(target_user_id)
                    content = send_states[user_id]["content"]
                    
                    try:
                        # Send content to user
                        await send_content_to_user(context.bot, target_user_id, content)
                        await message.reply_text(f"Content sent to user {target_user_id}.")
                    except Exception as e:
                        logging.error(f"Failed to send content: {e}")
                        await message.reply_text(f"Failed to send content: {e}")
                    
                    # Clear state
                    del send_states[user_id]
            
            # Function to process publishing
            async def process_publishing(message, bot, content, users, banned):
                sent_count = 0
                failed_count = 0
                
                # Status message
                status_msg = await message.reply_text(f"Publishing to {len(users)} users...")
                
                # Send to all users
                for user_id_str in users:
                    if user_id_str in banned:
                        continue
                        
                    try:
                        target_user_id = int(user_id_str)
                        await send_content_to_user(bot, target_user_id, content)
                        sent_count += 1
                        
                        # Update status occasionally
                        if sent_count % 10 == 0:
                            await status_msg.edit_text(
                                f"Publishing: {sent_count}/{len(users)} done, {failed_count} failed..."
                            )
                            
                    except Exception as e:
                        logging.error(f"Failed to publish to user {user_id_str}: {e}")
                        failed_count += 1
                
                # Final status update
                await status_msg.edit_text(
                    f"Publishing complete: {sent_count} succeeded, {failed_count} failed."
                )
                
                # Reset publish state
                publish_state["active"] = False
                publish_state["content"] = None
            
            async def send_content_to_user(bot, target_user_id, content):
                # Helper function to send any content type to a user
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
                elif content.get("text"):
                    await bot.send_message(
                        chat_id=target_user_id, 
                        text=content["text"]
                    )
            
            async def forward_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
                user_id = update.effective_user.id
                
                # Store user ID if not already present
                user_id_str = str(user_id)
                if user_id_str not in users:
                    users.add(user_id_str)
                    save_users(users)
                
                # Check for ban
                if user_id_str in banned:
                    return
                
                message = update.message
                username = update.effective_user.username or "N/A"
                
                # Format user information with copyable ID
                user_info = (
                    f"Message from user:\n"
                    f"User ID: `{user_id}`\n"
                    f"Username: @{username}"
                )
                
                # Forward text message
                if message.text:
                    await context.bot.send_message(admin_id, f"{user_info}\nText: {message.text}", parse_mode="Markdown")
                
                # Get caption if available
                caption = message.caption or ""
                caption_info = f"\nCaption: {caption}" if caption else ""
                
                # Forward dice message (interactive emoji)
                if message.dice:
                    # Get dice info
                    dice_emoji = message.dice.emoji
                    dice_value = message.dice.value
                    
                    # Send the dice to admin
                    await context.bot.send_dice(
                        chat_id=admin_id,
                        emoji=dice_emoji
                    )
                    
                    # Send additional info about the dice
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"{user_info}\nDice sent with emoji: {dice_emoji}, value: {dice_value}",
                        parse_mode="Markdown"
                    )
                
                # Forward document
                if message.document:
                    await context.bot.send_document(
                        chat_id=admin_id,
                        document=message.document.file_id,
                        caption=f"{user_info}{caption_info}\nDocument from user",
                        parse_mode="Markdown"
                    )
                
                # Forward photo
                if message.photo:
                    await context.bot.send_photo(
                        chat_id=admin_id,
                        photo=message.photo[-1].file_id,
                        caption=f"{user_info}{caption_info}\nPhoto from user",
                        parse_mode="Markdown"
                    )
                
                # Forward video
                if message.video:
                    await context.bot.send_video(
                        chat_id=admin_id,
                        video=message.video.file_id,
                        caption=f"{user_info}{caption_info}\nVideo from user",
                        parse_mode="Markdown"
                    )
                
                # Forward audio
                if message.audio:
                    await context.bot.send_audio(
                        chat_id=admin_id,
                        audio=message.audio.file_id,
                        caption=f"{user_info}{caption_info}\nAudio from user",
                        parse_mode="Markdown"
                    )
                
                # Forward voice message
                if message.voice:
                    await context.bot.send_voice(
                        chat_id=admin_id,
                        voice=message.voice.file_id,
                        caption=f"{user_info}{caption_info}\nVoice message from user",
                        parse_mode="Markdown"
                    )
                
                # Forward video note
                if message.video_note:
                    # First send the video note
                    await context.bot.send_video_note(
                        chat_id=admin_id,
                        video_note=message.video_note.file_id
                    )
                    # Then send user information
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"{user_info}\nVideo note from user",
                        parse_mode="Markdown"
                    )
                
                # Forward sticker 
                if message.sticker:
                    # First send the sticker
                    await context.bot.send_sticker(
                        chat_id=admin_id,
                        sticker=message.sticker.file_id
                    )
                    # Then send user information
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"{user_info}\nSticker from user",
                        parse_mode="Markdown"
                    )
                
                # Confirmation for user
                await message.reply_text("Your message has been sent to the administrator!")

            # Text-based confirm command handler
            async def confirm_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
                if update.effective_user.id != admin_id:
                    return
                    
                if publish_state["content"]:
                    await process_publishing(update.message, context.bot, publish_state["content"], users, banned)
                else:
                    await update.message.reply_text("Nothing to confirm.")

            async def run_async_bot():
                # Create application and pass token
                app = Application.builder().token(token).build()
                
                # Register command handlers
                app.add_handler(CommandHandler("start", start))
                app.add_handler(CommandHandler(["ban", "b"], ban_user))
                app.add_handler(CommandHandler(["unban", "u"], unban_user))
                app.add_handler(CommandHandler(["cancel", "c"], cancel_sending))
                app.add_handler(CommandHandler(["publish", "p"], start_publish))
                app.add_handler(CommandHandler(["help", "h"], show_help))
                app.add_handler(CommandHandler("confirm", confirm_command))
                
                # Filter for admin messages (not commands)
                admin_filter = filters.User(admin_id) & ~filters.COMMAND
                app.add_handler(MessageHandler(admin_filter, handle_admin_message))
                
                # Filter for user messages (not commands and not banned)
                user_filter = ~filters.User(admin_id) & ~filters.COMMAND
                app.add_handler(MessageHandler(user_filter, forward_to_admin))
                
                # Start the bot
                await app.initialize()
                await app.start()
                await app.updater.start_polling()
                
                logging.info("Bot started successfully")
                
                # Loop while bot is active
                try:
                    while not self.stop_event.is_set():
                        await asyncio.sleep(1)
                finally:
                    logging.info("Stopping bot...")
                    await app.updater.stop()
                    await app.stop()
                    await app.shutdown()
                    logging.info("Bot stopped")

            # Run the bot in the event loop
            try:
                loop.run_until_complete(run_async_bot())
            except Exception as e:
                logging.error(f"Bot runtime error: {e}")
                # Update UI from this thread
                self.root.after(0, lambda: self.status_label.config(text="Error", fg="red"))
                self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))
            finally:
                loop.close()
                
        except ImportError as e:
            logging.error(f"Failed to import python-telegram-bot: {e}")
            self.root.after(0, lambda: messagebox.showerror("Error", 
                f"Error importing python-telegram-bot modules: {e}\n\nПожалуйста, установите библиотеку командой:\npip install python-telegram-bot"))
            self.root.after(0, lambda: self.status_label.config(text="Error", fg="red"))
            self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))
        except Exception as e:
            logging.error(f"General error: {e}")
            self.root.after(0, lambda: messagebox.showerror("Error", f"Произошла ошибка: {e}"))
            self.root.after(0, lambda: self.status_label.config(text="Error", fg="red"))
            self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))

if __name__ == "__main__":
    # Check for required dependencies
    missing_deps = []
    try:
        import telegram
    except ImportError:
        missing_deps.append("python-telegram-bot")
    
    try:
        from PIL import Image
    except ImportError:
        missing_deps.append("pillow")
    
    try:
        import pystray
    except ImportError:
        missing_deps.append("pystray")
    
    # If dependencies are missing, show a message
    if missing_deps:
        root = tk.Tk()
        root.withdraw()
        deps_str = ", ".join(missing_deps)
        install_cmd = "pip install " + " ".join(missing_deps)
        messagebox.showwarning("Missing Dependencies", 
            f"Следующие библиотеки не установлены: {deps_str}\n\n"
            f"Установите их, используя команду:\n{install_cmd}")
    
    # Start the application
    root = tk.Tk()
    app = TelegramBotApp(root)
    root.mainloop()
