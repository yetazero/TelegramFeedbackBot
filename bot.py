import tkinter as tk
from tkinter import messagebox
import threading
import configparser
import logging
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Configuration
BANNED_FILE = "banned.txt"
CONFIG_FILE = "config.ini"

# Banned list functions
def load_banned():
    try:
        with open(BANNED_FILE, "r") as f:
            return {line.strip() for line in f}
    except FileNotFoundError:
        return set()

def save_banned(banned_users):
    try:
        with open(BANNED_FILE, "w") as f:
            f.write("\n".join(banned_users))
    except Exception as e:
        logging.error(f"Ban save error: {e}")

class TelegramBotApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Telegram Bot Manager")
        self.root.geometry("400x300")
        
        # Loading configuration
        self.config = configparser.ConfigParser()
        self.config.read(CONFIG_FILE)
        self.admin_id = self.config.get('DEFAULT', 'admin_id', fallback='')
        self.token = self.config.get('DEFAULT', 'token', fallback='')
        
        # Interface
        self.frame = tk.Frame(root)
        self.frame.pack(padx=10, pady=10)
        
        tk.Label(self.frame, text="Admin ID:").grid(row=0, column=0)
        self.admin_entry = tk.Entry(self.frame, width=30)
        self.admin_entry.grid(row=0, column=1)
        self.admin_entry.insert(0, self.admin_id)
        
        tk.Label(self.frame, text="Bot Token:").grid(row=1, column=0)
        self.token_entry = tk.Entry(self.frame, width=30)
        self.token_entry.grid(row=1, column=1)
        self.token_entry.insert(0, self.token)
        
        self.status_label = tk.Label(root, text="Not running", fg="red")
        self.status_label.pack(pady=10)
        
        self.start_btn = tk.Button(root, text="Start Bot", command=self.start_bot)
        self.start_btn.pack(pady=5)
        
        self.stop_btn = tk.Button(root, text="Stop Bot", command=self.stop_bot, state=tk.DISABLED)
        self.stop_btn.pack(pady=5)
        
        self.tray_btn = tk.Button(root, text="Minimize to Tray", command=self.add_to_tray)
        self.tray_btn.pack(pady=5)
        
        self.bot_thread = None
        self.bot_running = False
        self.tray_icon = None
        self.application = None
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.loop = None

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
        
        # Start bot in a separate thread
        self.bot_thread = threading.Thread(target=self.run_bot, args=(token, admin_id))
        self.bot_thread.daemon = True
        self.bot_thread.start()
        
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_label.config(text="Running...", fg="green")

    def stop_bot(self):
        if self.application:
            try:
                # Stop bot in another thread
                future = self.executor.submit(self.stop_bot_async)
                future.result(timeout=5)  # Give 5 seconds to stop
            except Exception as e:
                logging.error(f"Failed to stop bot: {e}")
                messagebox.showerror("Error", f"Failed to stop bot: {e}")
            finally:
                self.application = None
                self.status_label.config(text="Stopped", fg="red")
                self.start_btn.config(state=tk.NORMAL)
                self.stop_btn.config(state=tk.DISABLED)

    def stop_bot_async(self):
        if self.loop and self.application:
            asyncio.run_coroutine_threadsafe(self.application.stop(), self.loop)
            self.loop = None

    def add_to_tray(self):
        try:
            # Try to import only when function is called
            from pystray import Icon as TrayIcon, Menu as TrayMenu, MenuItem as TrayMenuItem
            from PIL import Image
            
            def on_restore(icon, item):
                icon.stop()
                self.root.deiconify()

            def on_exit(icon, item):
                icon.stop()
                self.root.quit()

            # Tray icon
            try:
                if os.path.exists("icon.png"):
                    image = Image.open("icon.png")
                else:
                    # Create a simple icon if file is missing
                    image = Image.new('RGB', (64, 64), color = 'blue')
                
                menu = TrayMenu(
                    TrayMenuItem("Restore", on_restore),
                    TrayMenuItem("Exit", on_exit)
                )
                self.tray_icon = TrayIcon("Telegram Bot Manager", image, "Telegram Bot Manager", menu)
                
                # Hide main window
                self.root.withdraw()
                
                # Start tray icon
                self.tray_icon.run_detached()  # Use run_detached to work in background
            except Exception as e:
                logging.error(f"Tray icon error: {e}")
                messagebox.showerror("Error", f"Failed to create tray icon: {e}")
        except ImportError as e:
            logging.error(f"Failed to import tray dependencies: {e}")
            messagebox.showerror("Error", "Failed to initialize tray. Make sure pystray and Pillow are installed.")

    def run_bot(self, token, admin_id):
        try:
            # Import python-telegram-bot
            from telegram import Update
            from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
            
            banned = load_banned()
            
            # Dictionary to store message sending states
            send_states = {}
            
            # Command handlers
            async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
                if update.effective_user.id == admin_id:
                    help_message = (
                        "Welcome, Admin!\n\n"
                        "Available commands:\n"
                        "/ban user-id (`/b`) - Ban a user\n"
                        "/unban user-id (`/u`) - Unban a user\n"
                        "/cancel (`/c`) - Cancel message sending\n"
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
                else:
                    await update.message.reply_text("Nothing to cancel.")
            
            async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
                if update.effective_user.id != admin_id:
                    return
                
                help_message = (
                    "Available commands:\n"
                    "/ban user-id (`/b`) - Ban a user\n"
                    "/unban user-id (`/u`) - Unban a user\n"
                    "/cancel (`/c`) - Cancel message sending\n"
                    "/help (`/h`) - Show this help\n\n"
                    "To send a message to a user, enter the message and then the user ID.\n\n"
                    "Author: [yetazero](https://t.me/yetazero)"
                )
                await update.message.reply_text(help_message, parse_mode="Markdown")
            
            async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
                if update.effective_user.id != admin_id:
                    return
                
                user_id = update.effective_user.id
                message = update.message
                
                # If admin sends any content (file, photo, video, etc.)
                if any([message.document, message.photo, message.video, message.audio, message.voice, message.video_note]):
                    # Save content data
                    send_states[user_id] = {
                        "content": {
                            "document": message.document.file_id if message.document else None,
                            "photo": message.photo[-1].file_id if message.photo else None,
                            "video": message.video.file_id if message.video else None,
                            "audio": message.audio.file_id if message.audio else None,
                            "voice": message.voice.file_id if message.voice else None,
                            "video_note": message.video_note.file_id if message.video_note else None,
                            "caption": message.caption,
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
                        if "document" in content and content["document"]:
                            await context.bot.send_document(chat_id=target_user_id, document=content["document"], caption=content.get("caption"))
                        elif "photo" in content and content["photo"]:
                            await context.bot.send_photo(chat_id=target_user_id, photo=content["photo"], caption=content.get("caption"))
                        elif "video" in content and content["video"]:
                            await context.bot.send_video(chat_id=target_user_id, video=content["video"], caption=content.get("caption"))
                        elif "audio" in content and content["audio"]:
                            await context.bot.send_audio(chat_id=target_user_id, audio=content["audio"], caption=content.get("caption"))
                        elif "voice" in content and content["voice"]:
                            await context.bot.send_voice(chat_id=target_user_id, voice=content["voice"], caption=content.get("caption"))
                        elif "video_note" in content and content["video_note"]:
                            await context.bot.send_video_note(chat_id=target_user_id, video_note=content["video_note"])
                        elif "text" in content and content["text"]:
                            await context.bot.send_message(chat_id=target_user_id, text=content["text"])
                        
                        await message.reply_text(f"Content sent to user {target_user_id}.")
                    except Exception as e:
                        logging.error(f"Failed to send content: {e}")
                        await message.reply_text(f"Failed to send content: {e}")
                    
                    # Clear state
                    del send_states[user_id]
            
            async def forward_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
                user_id = update.effective_user.id
                
                # Check for ban
                if str(user_id) in banned:
                    return
                
                message = update.message
                username = update.effective_user.username or "N/A"
                
                # Format user information with copyable ID
                user_info = (
                    f"Message from user:\n"
                    f"User ID: `{user_id}`\n"
                    f"Username: @{username}"
                )
                
                # Also make clickable user-id for convenience
                clickable_user_id = f"[{user_id}](tg://user?id={user_id})"
                
                # Forward text message
                if message.text:
                    await context.bot.send_message(admin_id, f"{user_info}\nText: {message.text}", parse_mode="Markdown")
                
                # Get caption if available
                caption = message.caption or ""
                caption_info = f"\nCaption: {caption}" if caption else ""
                
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
                
                # Confirmation for user
                await message.reply_text("Your message has been sent to the administrator!")
            
            # Function to run bot
            async def run_telegram_bot():
                # Create application and pass token
                app = Application.builder().token(token).build()
                
                # Register command handlers
                app.add_handler(CommandHandler("start", start))
                app.add_handler(CommandHandler(["ban", "b"], ban_user))
                app.add_handler(CommandHandler(["unban", "u"], unban_user))
                app.add_handler(CommandHandler(["cancel", "c"], cancel_sending))  
                app.add_handler(CommandHandler(["help", "h"], show_help))
                
                # Filter for admin messages (not commands)
                admin_filter = filters.User(admin_id) & ~filters.COMMAND
                app.add_handler(MessageHandler(admin_filter, handle_admin_message))
                
                # Filter for user messages (not commands and not banned)
                user_filter = ~filters.User(admin_id) & ~filters.COMMAND
                app.add_handler(MessageHandler(user_filter, forward_to_admin))
                
                self.application = app
                await app.initialize()
                await app.start()
                await app.updater.start_polling()
                
                # Wait while bot is active
                try:
                    # Infinite loop to keep bot active
                    while True:
                        await asyncio.sleep(1)
                except asyncio.CancelledError:
                    # Handle cancellation
                    logging.info("Bot polling cancelled")
                finally:
                    await app.stop()
                    await app.updater.stop()
            
            # Run bot in async mode
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(run_telegram_bot())
            
        except ImportError as e:
            logging.error(f"Failed to import python-telegram-bot: {e}")
            messagebox.showerror("Error", f"Error importing python-telegram-bot modules: {e}\nMake sure the library is installed.")
            self.root.after(0, lambda: self.status_label.config(text="Error", fg="red"))
            self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))
        except Exception as e:
            logging.error(f"General error: {e}")
            messagebox.showerror("Error", f"Error: {e}")
            self.root.after(0, lambda: self.status_label.config(text="Error", fg="red"))
            self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))

if __name__ == "__main__":
    root = tk.Tk()
    app = TelegramBotApp(root)
    root.mainloop()