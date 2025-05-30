# TelegramFeedbackBot v0.7.0

An easy-to-use Telegram bot for collecting user feedback, now significantly enhanced with a robust management system, expanded communication features, advanced moderation tools, and improved stability. This application provides a graphical interface (Telegram Bot Manager) for seamless bot control and offers richer, more organized interaction with users.

---

## New in v0.7.0:

This version introduces a comprehensive overhaul of the bot's architecture and a wealth of new features focused on **advanced moderation, user management, enhanced communication, and improved stability and debugging**.

* **Advanced Role Management (`/admin` and `/operator`)**:
    * **Admin Role (`/admin`)**: A new `roles.json` file now manages administrators. The main administrator (set via `add_admin.py` on first run or manually) can add or remove other administrators and operators. Only administrators can use `/admin` commands.
    * **Operator Role (`/operator`)**: Operators can now be designated. They have specific permissions, allowing them to manage user interactions in topic mode, ban/unban users, and use various moderation tools without full administrative access.
    * **Commands**:
        * `/admin add <user_id>`: Add a user as an administrator.
        * `/admin remove <user_id>`: Remove a user from administrators.
        * `/operator add <user_id>`: Add a user as an operator.
        * `/operator remove <user_id>`: Remove a user from operators.

* **Enhanced Message Management**:
    * **Message Deletion (`/delete`)**:
        * Admins and operators can now use `/delete` as a reply to a message in a topic/admin chat to delete the linked message for both the user and the admin/topic.
        * Provides detailed feedback on deletion status (fully deleted, partially deleted, failed).
    * **Message Editing Tracking**:
        * The bot now tracks when users or staff edit their messages.
        * Edited user messages are updated in the admin chat, showing the `[Edited]` status.
        * Edited admin/operator replies are updated in the user chat.
    * **Improved Pinning/Unpinning (`/pin` and `/unpin`)**:
        * The `/pin` command, when used as a reply, will pin the message in both the user's private chat and the associated topic (if topic mode is active).
        * The `/unpin` command unpins messages from both locations.

* **Reactions Management (`/reactions`, `/clear_reaction`)**:
    * **Reactions for Admins/Operators**: Staff can now react to messages in the admin chat/topics using specific commands (e.g., `/fire`, `/zap`, `/like`, `/dislike`). These reactions are mirrored to the linked user message.
    * **Clear Reactions**: The `/clear_reaction` command allows staff to remove all reactions from a linked message.
    * **View Reactions**: The `/reactions` command shows available reactions.

* **Comprehensive User Details (`/whois` enhancement)**:
    * The `/whois` command (for admins/operators) now provides significantly more detailed information about a user, including:
        * User ID, Username, Full Name
        * Account registration date (if available)
        * Associated Topic ID (if in topic mode)
        * First and Last interaction timestamps.
        * Total interaction count.
        * Notification preference (`/hide` status).
        * Banned status.

* **Enhanced Debugging and Logging (`/debug`)**:
    * A new `/debug` command allows administrators to control verbose logging.
    * Options include `on`, `off`, `set <chat_id>`, `status`.
    * When debug mode is "on", all bot actions (sent messages, received messages, command usage, errors) are logged to a specified debug chat. This is invaluable for troubleshooting.
    * The `bot_logging.py` and `debug.py` modules manage this new functionality.

* **Improved Application Stability and Startup**:
    * **Single Instance Prevention**: The bot now reliably prevents multiple instances from running concurrently using file locks and socket checks, preventing conflicts.
    * **Restart Consistency**: The `main.py` now includes logic for handling `restart_flag.txt`, ensuring proper startup behavior after a bot restart (e.g., returning to tray).
    * **Resource Management**: Includes `gc.collect()` calls for better memory management.
    * **Robust Configuration Management**: `config_manager.py` is updated to ensure `topic_mode_group_id` is always present in `config.ini`.

* **Minor Improvements & Refinements**:
    * Updated command handlers for better organization.
    * Improved error handling and feedback messages.
    * More robust user ID handling and file operations (`utils.py`, `user_details.py`).
    * `ascii_art.py` included, possibly for startup splash or other visual elements.
    * Refined `bot_core.py` to integrate new features seamlessly.

---

## New in v0.5.3:

* **Chat Control (`/pause` and `/resume`)**:
    * The new `/pause` command allows the administrator to **temporarily disable chat and commands for all users**. During this pause, only the administrator can continue to use bot commands.
    * The `/resume` command **re-enables all chat and commands for users**, restoring normal bot operation.

---

## New in v0.5.2:

* **Mass Publishing with Pin Option**:
    * Added `pin` option to the `/publish` command (e.g., `/publish pin`). This allows the administrator to send a mass message to all subscribed users and automatically pin it in their respective chats (if the user is not banned).
* **Improved Admin Message Display and Pinning**:
    * Fixed issues related to the correct display and automatic pinning of administrator messages (e.g., replies to users or forwarded content), ensuring better visibility and management of communication.

---

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

---

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

---

## New in v0.3:

* **Poll Support:** Users can now send polls to the bot.
* **Location Sharing:** The bot now supports receiving users' shared locations.
* **Contact Sharing:** Users can share their contacts with the bot.
* **Anti-Spam Cooldown (`/cooldown`):** Administrators can now use the `/cooldown` command to set a time limit between user messages, helping to prevent spam and ensure smoother interactions.

---

## Key Improvements from v0.2:

* **Mass Messaging:** Introduced the `/publish` (`/p`) command, enabling administrators to send messages to all active bot users.
* **Sticker Support:** Fixed a bug that prevented the bot from correctly processing messages containing custom sticker packs.
* **Interactive Emojis:** Added support for interactive emotions (Dice) for a more engaging user experience.

---

## Dependencies

The following Python libraries are required to run the Python script. You can install them using pip:

* **`python-telegram-bot`**: A Python wrapper for the Telegram Bot API. Install using: `pip install python-telegram-bot`
* **`pystray`**: A library to create system tray icons for background operation. Install using: `pip install pystray`
* **`Pillow` (PIL)**: A library for image processing (used for the tray icon). Install using: `pip install Pillow`
* **`tkinter`**: Python's standard GUI package, used for the management interface. It is usually included with Python.
* **`configparser`**: For reading and writing configuration files. It is usually included with Python.

---

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
    topic_mode_group_id = YOUR_TOPIC_GROUP_ID # New in v0.7.0, required for Topic Mode
    ```
    If `config.ini` doesn't exist, the application will create a default one when run.

3.  **Initial Admin Setup (New in v0.7.0 - Crucial!)**:
    For the first run, you need to add your main administrator ID using a dedicated script:
    ```bash
    python add_admin.py YOUR_MAIN_ADMIN_TELEGRAM_ID
    ```
    Replace `YOUR_MAIN_ADMIN_TELEGRAM_ID` with your actual Telegram User ID. This ensures your account has initial administrative privileges to manage other roles.

---

## Usage

You can run the bot in the following ways:

**Option 1: Running via Python Script**

1.  Ensure you have Python and all dependencies installed (see Setup).
2.  Navigate to the directory containing `main.py` in your terminal or command prompt.
3.  Run the script using:
    ```bash
    python main.py
    ```

**Option 2: Running via Batch File (Windows)**

1.  A `Start.bat` file is included in the repository for convenience on Windows.
2.  Double-click the `Start.bat` file to run the bot.

**Note:** The Windows executable (`bot.exe`) file was previously removed from the repository due to false positive detections by some analysis systems. Running the application using the Python script (`main.py`) or the batch file (`Start.bat`) after installing the necessary dependencies is the recommended and safer approach.

---

## Features

* **Graphical Management Tool:** An intuitive `tkinter`-based interface to start and stop the bot.
* **Configuration Management:** Easily configure the bot's Telegram Token, Admin ID, and Topic Mode Group ID through the GUI, which saves to `config.ini`.
* **System Tray Integration:** Option to minimize the bot management tool to the system tray for background operation.
* **User Feedback Forwarding:** Users can send messages to the bot, which are then forwarded to the configured Admin ID or a dedicated topic.
* **Role-Based Access Control:** Differentiated roles for **Administrators** and **Operators** with specific command permissions.
* **Banning/Unbanning Users:** Administrators and Operators can ban or unban users using the `/ban` (`/b`) and `/unban` (`/u`) commands. Banned users' messages will be ignored by the bot.
* **Mass Messaging (`/publish` or `/p`):** Administrators can send announcements or information to all subscribed users, with an option to pin messages.
* **Message Cancellation (`/cancel` or `/c`):** Allows the administrator to cancel ongoing message sending or mass mailing processes.
* **Interactive Dice:** Supports sending and receiving Telegram's interactive dice emojis.
* **User Tracking:** The bot keeps track of users who have started a conversation in the `users.txt` file and detailed user data in `user_details.json`.
* **Polls, Locations, Contacts:** Supports receiving polls, shared locations, and contacts from users.
* **Anti-Spam Cooldown (`/cooldown`):** Administrators can set a time limit between user messages.
* **Bot Control Commands:** `/pause`, `/resume`, `/update` (restart), `/off` (safe shutdown).
* **Topic Mode:** Directs each user's messages into a separate topic in the admin group for organized communication.
* **Reply Support:** Admins/operators can reply directly to user messages.
* **Pinned Messages Management:** Admins/operators can manage pinned messages directly within the bot's group chat.
* **Notification Control (`/hide`):** Users can enable/disable delivery notifications.
* **Message Editing/Deletion Tracking:** Monitors and reflects message edits/deletions from both users and staff.
* **Reaction Management:** Staff can add/clear reactions on linked messages.
* **Detailed User Information:** The `/whois` command provides comprehensive user data.
* **Debugging Mode (`/debug`):** Allows administrators to enable and configure verbose logging of bot activities to a specific chat.

---

## Author

[yetazero](https://t.me/yetazero)
