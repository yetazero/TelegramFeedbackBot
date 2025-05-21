import tkinter as tk
from tkinter import messagebox
import threading
import asyncio
import logging
import os
import sys

from config_manager import ConfigManager
from bot_core import run_telegram_bot, stop_telegram_bot_event
from utils import load_banned, save_banned, load_users, save_users

if sys.platform.startswith('win'):
    try:
        import ctypes
        myappid = 'mycompany.myproduct.subproduct.version'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class TelegramBotApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TelegramFeedbackBot")
        self.root.geometry("400x300")
        
        self.root.wm_iconmask = self._create_blank_icon()
        self.root.iconbitmap(default='')
        
        self.config_manager = ConfigManager("config.ini")
        self.admin_id = self.config_manager.get_config('admin_id', fallback='')
        self.token = self.config_manager.get_config('token', fallback='')
        self.cooldown = self.config_manager.get_config('cooldown', fallback='0')
        
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

        self.author_label = tk.Label(root, text="yetazero", fg="gray", font=("Arial", 8))
        self.author_label.pack(side=tk.BOTTOM, anchor=tk.SE, padx=5, pady=5)
        
        self.bot_thread = None
        self.tray_icon = None

    def _create_blank_icon(self):
        try:
            from PIL import Image, ImageTk
            image = Image.new('RGBA', (1, 1), (0, 0, 0, 0))
            photo = ImageTk.PhotoImage(image)
            return photo
        except ImportError:
            return None

    def save_config(self):
        self.config_manager.set_config('admin_id', self.admin_entry.get())
        self.config_manager.set_config('token', self.token_entry.get())
        self.config_manager.save_config()

    def start_bot(self):
        admin_id_str = self.admin_entry.get().strip()
        token = self.token_entry.get().strip()
        
        if not admin_id_str or not token:
            messagebox.showerror("Error", "Please fill in all fields")
            return
            
        try:
            admin_id = int(admin_id_str)
        except ValueError:
            messagebox.showerror("Error", "Invalid Admin ID format")
            return
            
        self.save_config()
        
        stop_telegram_bot_event.clear()
        
        initial_cooldown = int(self.config_manager.get_config('cooldown', fallback='0'))

        self.bot_thread = threading.Thread(target=lambda: asyncio.run(run_telegram_bot(token, admin_id, initial_cooldown)))
        self.bot_thread.daemon = True
        self.bot_thread.start()
        
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_label.config(text="Running...", fg="green")

    def stop_bot(self):
        if self.bot_thread and self.bot_thread.is_alive():
            stop_telegram_bot_event.set()
            
            self.bot_thread.join(timeout=3) 
            
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
                self.stop_bot()
                self.root.after(0, self.root.quit)

            image = Image.new('RGB', (64, 64), color='white')
            
            menu = pystray.Menu(
                pystray.MenuItem("Restore", on_restore),
                pystray.MenuItem("Exit", on_exit)
            )
            
            self.tray_icon = pystray.Icon("TelegramFeedbackBot", image, "TelegramFeedbackBot", menu) # Changed title
            
            self.root.withdraw()
            
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
            
        except ImportError as e:
            logging.error(f"Failed to import tray dependencies: {e}")
            messagebox.showerror("Error", "Failed to initialize tray. Make sure pystray and Pillow are installed.")

if __name__ == "__main__":
    root = tk.Tk()
    app = TelegramBotApp(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.stop_bot(), root.destroy()))
    root.mainloop()