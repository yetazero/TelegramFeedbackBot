import tkinter as tk
from tkinter import messagebox
import threading
import asyncio
import os
import sys
import subprocess
import time
import atexit
import socket
import struct

if not sys.platform.startswith('win'):
    import fcntl

from config_manager import ConfigManager
from bot_core import run_telegram_bot, stop_telegram_bot_event

if sys.platform.startswith('win'):
    try:
        import ctypes
        myappid = 'yetazero.telegramfeedbackbot.1' 
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception as e:
        pass

LOCK_FILE = 'telegram_bot.lock'
SOCKET_PORT = 50007

lock_file_handle = None
server_socket = None

def acquire_lock():
    global lock_file_handle
    
    try:
        if sys.platform.startswith('win'):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex(('localhost', SOCKET_PORT))
            sock.close()
            
            if result == 0:
                if "--restart" not in sys.argv:
                    print("Another instance of TelegramFeedbackBot is already running!")
                    messagebox.showinfo("Already Running", "TelegramFeedbackBot is already running.")
                return False
                
            global server_socket
            try:
                server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, 
                                       struct.pack('ii', 1, 0))
                server_socket.bind(('localhost', SOCKET_PORT))
                server_socket.listen(1)
            except socket.error as e:
                print(f"Socket error: {e}")
                return False
            
            def socket_thread():
                while True:
                    try:
                        conn, addr = server_socket.accept()
                        conn.close()
                    except Exception as e:
                        print(f"Socket thread exception: {e}")
                        break
            
            socket_thread_handle = threading.Thread(target=socket_thread, daemon=True)
            socket_thread_handle.start()
            
            def close_socket():
                global server_socket
                if server_socket:
                    try:
                        server_socket.close()
                        server_socket = None
                    except Exception as e:
                        print(f"Error closing socket: {e}")
            
            atexit.register(close_socket)
            return True
        
        else:
            lock_file_handle = open(LOCK_FILE, 'w')
            fcntl.flock(lock_file_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock_file_handle.write(str(os.getpid()))
            lock_file_handle.flush()
            
            def release_lock():
                fcntl.flock(lock_file_handle, fcntl.LOCK_UN)
                lock_file_handle.close()
                try:
                    os.remove(LOCK_FILE)
                except:
                    pass
            
            atexit.register(release_lock)
            return True
            
    except (IOError, OSError, socket.error):
        if "--restart" not in sys.argv:
            print("Another instance of TelegramFeedbackBot is already running!")
            messagebox.showinfo("Already Running", "TelegramFeedbackBot is already running.")
        return False

def check_single_instance():
    if not acquire_lock():
        sys.exit(0)

def restart_application(in_tray=False):
    script_path = sys.argv[0]
    args = [sys.executable, script_path]
    if in_tray:
        args.append("--start-in-tray")
    print(f"Restarting application with args: {args}")
    process = subprocess.Popen(args)
    print(f"New process started with PID: {process.pid}")
    print("Exiting current process")
    os._exit(0)

class TelegramBotApp:
    def __init__(self, root_window):
        self.root = root_window
        self.root.title("Telegram Feedback Bot")
        self.root.geometry("400x250")
        
        try:
            self.root.iconbitmap(default='') 
        except tk.TclError:
            pass 

        self.config_manager = ConfigManager("config.ini")
        self.admin_id = self.config_manager.get_config('admin_id', fallback='')
        self.token = self.config_manager.get_config('token', fallback='')
        
        self.frame = tk.Frame(root_window)
        self.frame.pack(padx=10, pady=10, fill=tk.X)
        
        tk.Label(self.frame, text="Admin ID:").grid(row=0, column=0, sticky=tk.W, pady=3)
        self.admin_entry = tk.Entry(self.frame, width=35)
        self.admin_entry.grid(row=0, column=1, padx=5, pady=3, sticky=tk.EW)
        self.admin_entry.insert(0, self.admin_id)
        
        tk.Label(self.frame, text="Bot Token:").grid(row=1, column=0, sticky=tk.W, pady=3)
        self.token_entry = tk.Entry(self.frame, width=35)
        self.token_entry.grid(row=1, column=1, padx=5, pady=3, sticky=tk.EW)
        self.token_entry.insert(0, self.token)

        self.frame.columnconfigure(1, weight=1)
        
        self.status_label = tk.Label(root_window, text="Not running", fg="red")
        self.status_label.pack(pady=10)
        
        self.button_frame = tk.Frame(root_window)
        self.button_frame.pack(pady=5)
        
        self.start_btn = tk.Button(self.button_frame, text="Start Bot", command=self.start_bot, width=12)
        self.start_btn.grid(row=0, column=0, padx=5)
        
        self.stop_btn = tk.Button(self.button_frame, text="Stop Bot", command=self.stop_bot_action, width=12, state=tk.DISABLED)
        self.stop_btn.grid(row=0, column=1, padx=5)

        self.tray_btn = tk.Button(root_window, text="Minimize to Tray", command=self.add_to_tray)
        self.tray_btn.pack(pady=(5,10))

        self.author_label = tk.Label(root_window, text="yetazero", fg="gray", font=("Arial", 8))
        self.author_label.pack(side=tk.BOTTOM, anchor=tk.SE, padx=5, pady=5)
        
        self.bot_thread = None
        self.tray_icon = None

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        if "--start-in-tray" in sys.argv:
            self.start_bot()
            if self.bot_thread and self.bot_thread.is_alive():
                self.root.after(1000, self.add_to_tray)

    def save_config_values(self):
        self.config_manager.set_config('admin_id', self.admin_entry.get())
        self.config_manager.set_config('token', self.token_entry.get())
        self.config_manager.save_config()

    def start_bot(self):
        admin_id_str = self.admin_entry.get().strip()
        token = self.token_entry.get().strip()
        
        if not admin_id_str or not token:
            messagebox.showerror("Error", "Admin ID and Bot Token are required.")
            return
        try:
            admin_id_val = int(admin_id_str)
        except ValueError:
            messagebox.showerror("Error", "Invalid Admin ID format.")
            return
            
        self.save_config_values()
        stop_telegram_bot_event.clear()
        initial_cooldown_val = int(self.config_manager.get_config('cooldown', fallback='0'))

        self.bot_thread = threading.Thread(
            target=lambda: asyncio.run(run_telegram_bot(token, admin_id_val, initial_cooldown_val, self.config_manager)),
            daemon=True
        )
        self.bot_thread.start()
        
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.tray_btn.config(state=tk.NORMAL)
        self.status_label.config(text="Running...", fg="green")

    def stop_bot_action(self):
        if self.bot_thread and self.bot_thread.is_alive():
            stop_telegram_bot_event.set()
        self.status_label.config(text="Stopped", fg="red")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.tray_btn.config(state=tk.DISABLED)

    def restart_bot(self):
        is_in_tray = self.tray_icon is not None
        if self.bot_thread and self.bot_thread.is_alive():
            stop_telegram_bot_event.set()
            if self.tray_icon:
                self.tray_icon.stop()
                self.tray_icon = None
            restart_application(in_tray=is_in_tray)

    def on_closing(self):
        if messagebox.askokcancel("Quit", "Stop the bot and exit application?"):
            stop_telegram_bot_event.set()
            
            def graceful_exit():
                if self.bot_thread and self.bot_thread.is_alive():
                    self.bot_thread.join(timeout=8) 
                if self.tray_icon:
                    self.tray_icon.stop()
                self.root.destroy()

            threading.Thread(target=graceful_exit, daemon=True).start()

    def _create_tray_image(self):
        try:
            from PIL import Image, ImageDraw
            width, height = 64, 64
            image = Image.new('RGB', (width, height), 'white')
            return image
        except ImportError:
            return None


    def add_to_tray(self):
        if not (self.bot_thread and self.bot_thread.is_alive()):
             messagebox.showwarning("Bot Not Running", "Start the bot before minimizing to tray.")
             return
        try:
            import pystray
            from PIL import Image 
            
            if hasattr(self, 'tray_icon') and self.tray_icon:
                self.root.withdraw()
                self.tray_btn.config(state=tk.DISABLED)
                return
            
            image = self._create_tray_image()
            if image is None:
                messagebox.showerror("Error", "Pillow (PIL) must be installed to create a tray icon.")
                return

            def on_restore(icon, item):
                try:
                    icon.stop()
                    self.root.after(0, lambda: self._restore_from_tray())
                except Exception as e:
                    print(f"Error restoring from tray: {e}")

            def on_exit_tray(icon, item):
                try:
                    icon.stop()
                    self.root.after(0, lambda: self._exit_from_tray())
                except Exception as e:
                    print(f"Error exiting from tray: {e}")

            menu = pystray.Menu(
                pystray.MenuItem("Restore", on_restore, default=True),
                pystray.MenuItem("Exit", on_exit_tray)
            )
            
            import uuid
            unique_id = str(uuid.uuid4())[:8]
            self.tray_icon = pystray.Icon(f"TelegramFeedbackBot_{unique_id}", image, "Bot Controller", menu)
            
            self.root.withdraw() 
            self.tray_btn.config(state=tk.DISABLED)
            
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except ImportError:
            messagebox.showerror("Error", "pystray or Pillow not installed. Minimizing to tray is unavailable.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create tray icon: {e}")
    
    def _restore_from_tray(self):
        self.tray_icon = None
        self.root.deiconify()
        self.tray_btn.config(state=tk.NORMAL)
    
    def _exit_from_tray(self):
        self.tray_icon = None
        self.on_closing()


if __name__ == "__main__":
    check_single_instance()
    
    root = tk.Tk()
    app = TelegramBotApp(root)
    if not (app.bot_thread and app.bot_thread.is_alive()):
        app.tray_btn.config(state=tk.DISABLED)
    
    try:
        if os.path.exists("restart_flag.txt"):
            with open("restart_flag.txt", "r") as f:
                mode = f.read().strip()
            
            os.remove("restart_flag.txt")
            
            app.start_bot()
            
            if mode == "tray" and app.bot_thread and app.bot_thread.is_alive():
                root.after(1000, app.add_to_tray)
    except Exception as e:
        print(f"Error processing restart flag: {e}")
    
    global app_instance
    app_instance = app
    
    root.mainloop()
