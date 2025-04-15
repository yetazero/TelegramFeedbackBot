# TelegramFeedbackBot
Easy-to-use Telegram feedback bot with a graphical management tool.
# Telegram Bot Manager

This application provides a simple graphical interface to manage a Telegram bot. It allows you to start and stop the bot and configure the bot's settings.

## Dependencies

The following Python libraries are required to run the Python script:

-   **python-telegram-bot:** A Python wrapper for the Telegram Bot API. **Install using:** `pip install python-telegram-bot`
-   **pystray:** A library to create system tray icons. **Install using:** `pip install pystray`
-   **Pillow (PIL):** A library for image processing (used for the tray icon). **Install using:** `pip install Pillow`

## Setup

1.  **Install Dependencies (for running the Python script):**
    -   Make sure you have Python 3 installed. Then, install the required external libraries using pip:
        ```bash
        pip install python-telegram-bot pystray Pillow
        ```

2.  **Configuration:**
    -   A `config.ini` file is included in the repository. Ensure it is configured with your Telegram Bot Token and Admin ID.

3.  **Executable for Windows:**
    -   For your convenience, a Windows executable (`bot.exe`) is included, offering similar functionality to running the Python script. Use at your own discretion.

## Usage

**Option 1: Running the Python Script**

1.  Ensure you have Python and all dependencies installed (see Setup).
2.  Navigate to the directory containing `bot.py` in your terminal or command prompt.
3.  Run the script using: `python bot.py`

**Option 2: Running the Executable (.exe) on Windows**

1.  Download the `bot.exe` file.
2.  Place the `config.ini` file in the same directory.
3.  Double-click the executable to run the application.

Once the application is running (via either method), use the graphical interface to start and stop the bot.
