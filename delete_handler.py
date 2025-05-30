import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from telegram.error import BadRequest
import html
from datetime import datetime

_message_links = {}
bot_core = None

def initialize(message_links_from_core, bot_core_module_param=None):
    global _message_links, bot_core
    _message_links = message_links_from_core
    if bot_core_module_param:
        bot_core = bot_core_module_param

async def _delete_message_safe(bot, chat_id, message_id):
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except Exception:
        return False

async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_core:
        await context.bot.send_message(update.effective_chat.id, "Error: Delete command is not configured correctly. Please contact admin.")
        return

    if hasattr(bot_core, 'bot_paused') and bot_core.bot_paused:
        from roles import is_admin
        if not is_admin(update.effective_user.id):
            return

    from roles import is_admin, is_operator
    if not is_admin(update.effective_user.id) and not is_operator(update.effective_user.id):
        return
    
    if not update.message or not update.message.reply_to_message:
        message_thread_id = getattr(update.message, 'message_thread_id', None)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🔹 This command must be used in reply to a message you want to delete.",
            message_thread_id=message_thread_id
        )
        return
    
    if not bot_core.is_topic_mode_active() or not getattr(update.message, 'message_thread_id', None):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🔹 This command only works in topic mode.",
            message_thread_id=getattr(update.message, 'message_thread_id', None)
        )
        return

    reply_to_message = update.message.reply_to_message
    message_thread_id = update.message.message_thread_id
    
    try:
        from user_details import get_user_id_by_topic_id
    except ImportError:
        await context.bot.send_message(update.effective_chat.id, "Error: User details module not found.")
        return
    
    user_id_str = get_user_id_by_topic_id(message_thread_id, str(bot_core.topic_mode_group_id))
    if not user_id_str:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🔹 Could not identify the user for this topic.",
            message_thread_id=message_thread_id
        )
        return
    
    user_id = int(user_id_str)
    admin_chat_id = update.effective_chat.id
    admin_message_id = reply_to_message.message_id
    
    admin_key = f"{admin_chat_id}:{admin_message_id}"
    user_message_id = None
    is_from_user = False
    
    if admin_key in _message_links:
        user_message_id = _message_links[admin_key].get('user_message_id')
        is_from_user = _message_links[admin_key].get('is_from_user', False)
    
    if not user_message_id:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="User's linked message not found. Only the message in the topic will be deleted.",
            message_thread_id=message_thread_id
        )
        return
    
    message_content = ""
    if hasattr(reply_to_message, 'text') and reply_to_message.text:
        message_content = reply_to_message.text
    elif hasattr(reply_to_message, 'caption') and reply_to_message.caption:
        message_content = reply_to_message.caption
    else:
        message_content = "[Media content]"
    
    admin_message = reply_to_message
    admin_delete_success = await _delete_message_safe(context.bot, admin_chat_id, admin_message_id)
    
    user_delete_success = False
    if user_message_id:
        user_delete_success = await _delete_message_safe(context.bot, user_id, user_message_id)
    
    try:
        await _delete_message_safe(context.bot, update.effective_chat.id, update.message.message_id)
    except Exception:
        pass
    
    current_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
    
    if len(message_content) > 100:
        message_content = message_content[:97] + "..."
    
    result_text = ""
    if admin_delete_success and user_delete_success:
        result_text = f"🔹 Message deleted from user chat and topic.\n<b>Content:</b> <code>{html.escape(message_content)}</code>\n[deleted, {current_time}]"
    elif admin_delete_success:
        result_text = f"🔹 Message deleted in topic, but not in user chat.\n<b>Content:</b> <code>{html.escape(message_content)}</code>\n[partially deleted, {current_time}]"
    elif user_delete_success:
        result_text = f"🔹 Message deleted in user chat, but not in topic.\n<b>Content:</b> <code>{html.escape(message_content)}</code>\n[partially deleted, {current_time}]"
    else:
        result_text = f"🔹 Failed to delete message in any location.\n<b>Content:</b> <code>{html.escape(message_content)}</code>\n[error, {current_time}]"
    
    try:
        await context.bot.send_message(
            chat_id=admin_chat_id,
            text=result_text,
            parse_mode=ParseMode.HTML,
            message_thread_id=message_thread_id
        )
    except Exception as e:
        try:
            await context.bot.send_message(
                chat_id=admin_chat_id,
                text=f"Message deleted. Error sending full report: {e}",
                message_thread_id=message_thread_id
            )
        except:
            pass

def register_handlers(app):
    from telegram.ext import CommandHandler
    
    app.add_handler(CommandHandler("delete", delete_command))
