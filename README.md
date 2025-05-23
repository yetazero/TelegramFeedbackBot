# TelegramFeedbackBot v0.5.2

An easy-to-use Telegram bot for collecting user feedback, now enhanced with a graphical management tool and even more features for richer interaction and control. This application provides a simple graphical interface (Telegram Bot Manager) to manage your Telegram bot. It allows you to start and stop the bot, configure its settings, and now offers enhanced communication capabilities with users.

## New in v0.5.2:

* **Mass Publishing with Pin Option**:
    * Added `pin` option to the `/publish` command (e.g., `/publish pin <message>`). This allows the administrator to send a mass message to all subscribed users and automatically pin it in their respective chats (if the user is not banned).
* **Improved Admin Message Display and Pinning**:
    * Fixed issues related to the correct display and automatic pinning of administrator messages (e.g., replies to users or forwarded content), ensuring better visibility and management of communication.

## New in v0.5.1:

Telegram Feedback Bot: New Features in Version 0.5.1

Version 0.5.1 significantly enhances the bot's functionality and usability, making it more convenient and feature-rich.

**Expanded Message and User Management:**

* **⚡ Very important change! Topic Mode**: If you're using groups with topics in Telegram, the bot can now direct messages from each user into a separate topic. This makes communication much more organized and convenient for a large number of inquiries.
* The new `/mode` command allows you to activate or deactivate topic mode for your group.
* The new `/whois` command allows you to get detailed information about any bot user to better understand who is writing.
* **Reply Support**: You can now reply directly to user messages, and the bot will correctly link your reply, sending it to the right user.
* **Pinned Messages**: The administrator can now see and manage pinned messages directly within the bot's group chat.
* **Notification Control**: The `/hide` command allows users to enable or disable delivery notifications.

**Application Convenience and Stability:**

* **Reliable Restart and Tray Operation:**
    * The `/update` command allows you to restart the bot directly from Telegram to apply changes.
    * The `/off` command provides a safe shutdown of the bot with confirmation.
    * The bot now reliably prevents multiple instances from running accidentally.
    * Automatic launch into the system tray (notification area) is supported on startup or after a bot restart, saving desktop space.

---

**We highly recommend switching to Topic Mode!**

This will allow you to leverage all the advantages of the new version: commands like `/ban`, `/unban`, `/whois`, support for replies, and pinned messages directly within the group. You'll gain a more **structured conversation** with each user and the ability to **rename the topic** for easier identification.

## New in v0.4:

* **Subscription Management for Mass Publications:**
    * Introduced `/subscribe` (`/sub`) and `/unsubscribe` (`/unsub`) commands, allowing users to explicitly manage their opt-in for mass publications from the administrator.
    * The `/publish` command now targets only users who are subscribed to mass publications.
    * Banning a user (`/ban`) automatically removes them from the mass publication list.
* **Enhanced User Information for Admin:**
    * When user messages are forwarded to the administrator, the bot now includes the user's **full name** in addition to their User ID and Username for better identification.
* **GUI Redesign:**
    * The graphical user interface of the Telegram Bot Manager has been refreshed for a more modern and intuitive look.
* **Updated Help Command:**
    * The `/help` command's description has been revised to clearly state that `/subscribe` and `/unsubscribe` relate to **mass publications**, not all admin messages.

## New in v0.3:

* **Poll Support:** Users can now send polls to the bot.
* **Location Sharing:** The bot now supports receiving users' shared locations.
* **Contact Sharing:** Users can share their contacts with the bot.
* **Anti-Spam Cooldown (`/cooldown`):** Administrators can now use the `/cooldown` command to set a time limit between user messages, helping to prevent spam and ensure smoother interactions.

## Key Improvements from v0.2:

* **Mass Messaging:** Introduced the `/publish` (`/p`) command, enabling administrators to send messages to all active bot users.
* **Sticker Support:** Fixed a bug that prevented the bot from correctly processing messages containing custom sticker packs.
* **Interactive Emojis:** Added support for interactive emotions (Dice) for a more engaging user experience.

## Dependencies

The following Python libraries are required to run the Python script. You can install them using pip:

* **`python-telegram-bot`**: A Python wrapper for the Telegram Bot API. Install using: `pip install python-telegram-bot`
* **`pystray`**: A library to create system tray icons for background operation. Install using: `pip install pystray`
* **`Pillow` (PIL)**: A library for image processing (used for the tray icon). Install using: `pip install Pillow`
* **`tkinter`**: Python's standard GUI package, used for the management interface. It is usually included with Python.
* **`configparser`**: For reading and writing configuration files. It is usually included with Python.

## Setup

1.  **Install Dependencies:**
    Make sure you have Python 3 installed on your system. Then, install the necessary external libraries using pip:
    ```bash
    pip install python-telegram-bot pystray Pillow
    ```

2.  **Configuration:**
    A `config.ini` file is included in the repository. You need to configure it with your Telegram Bot Token and Admin ID. Open `config.ini` and edit the following values under the `[DEFAULT]` section:
    ```ini
    admin_id = YOUR_ADMIN_TELEGRAM_ID
    token = YOUR_TELEGRAM_BOT_TOKEN
    ```
    If `config.ini` doesn't exist, the application will create a default one when run.

## Usage

You can run the bot in the following ways:

**Option 1: Running via Python Script**

1.  Ensure you have Python and all dependencies installed (see Setup).
2.  Navigate to the directory containing `bot.py` in your terminal or command prompt.
3.  Run the script using:
    ```bash
    python bot.py
    ```

**Option 2: Running via Batch File (Windows)**

1.  A `Start.bat` file is included in the repository for convenience on Windows.
2.  Double-click the `Start.bat` file to run the bot.

**Note:** The Windows executable (`bot.exe`) file was previously removed from the repository due to false positive detections by some analysis systems. Running the application using the Python script (`bot.py`) or the batch file (`Start.bat`) after installing the necessary dependencies is the recommended and safer approach.

## Features

* **Graphical Management Tool:** An intuitive `tkinter`-based interface to start and stop the bot.
* **Configuration Management:** Easily configure the bot's Telegram Token and Admin ID through the GUI, which saves to `config.ini`.
* **System Tray Integration:** Option to minimize the bot management tool to the system tray for background operation.
* **User Feedback Forwarding:** Users can send messages to the bot, which are then forwarded to the configured Admin ID.
* **Banning/Unbanning Users:** Administrators can ban or unban users using the `/ban` (`/b`) and `/unban` (`/u`) commands. Banned users' messages will be ignored by the bot.
* **Mass Messaging (`/publish` or `/p`):** Administrators can send announcements or information to all subscribed users.
* **Message Cancellation (`/cancel` or `/c`):** Allows the administrator to cancel ongoing message sending or mass mailing processes.
* **Interactive Dice:** Supports sending and receiving Telegram's interactive dice emojis.
* **User Tracking:** The bot keeps track of users who have started a conversation in the `users.txt` file.

## Author

[yetazero](https://t.me/yetazero)
