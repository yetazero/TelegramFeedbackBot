# TelegramFeedbackBot

Easy-to-use Telegram feedback bot with a graphical management tool.
Telegram Bot Manager

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

## Usage

**Option 1: Running the Python Script**

1.  Ensure you have Python and all dependencies installed (see Setup).
2.  Navigate to the directory containing `bot.py` in your terminal or command prompt.
3.  Run the script using: `python bot.py`

**Note:** The Windows executable (`bot.exe`) file has been removed from the repository due to some analysis systems incorrectly flagging it as potentially malicious. It is recommended to run the application using the Python script (`bot.py`) after installing the necessary dependencies.
