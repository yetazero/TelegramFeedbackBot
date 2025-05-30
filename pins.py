from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import BadRequest

_message_links = {}
bot_core = None

def initialize(message_links_from_core, bot_core_module_param=None):
    global _message_links, bot_core
    _message_links = message_links_from_core
    if bot_core_module_param:
        bot_core = bot_core_module_param
    

async def pin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_core or not hasattr(bot_core, 'admin_id') or not hasattr(bot_core, 'topic_mode_group_id'):
        await context.bot.send_message(update.effective_chat.id, "Error: Pin command is not configured correctly. Please contact admin.")
        return

    if hasattr(bot_core, 'bot_paused') and bot_core.bot_paused:
        from roles import is_admin
        if not is_admin(update.effective_user.id):
            return

    from roles import is_admin, is_operator
    if not is_admin(update.effective_user.id) and not is_operator(update.effective_user.id):
        return
    
    reply_to_message = update.message.reply_to_message
    message_thread_id = getattr(update.message, 'message_thread_id', None)
    
    if not reply_to_message:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🔹 This command must be used in reply to a message you want to pin.",
            message_thread_id=message_thread_id
        )
        return
    
    if not message_thread_id:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🔹 This command currently only works in user topics."
        )
        return

    try:
        from user_details import get_user_id_by_topic_id
    except ImportError:
        logger.exception("Failed to import get_user_id_by_topic_id from user_details.")
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
    
    topic_success = False
    topic_error = "Unknown error"
    try:
        await context.bot.pin_chat_message(
            chat_id=update.effective_chat.id, 
            message_id=reply_to_message.message_id, 
            disable_notification=True
        )
        topic_success = True
    except Exception as e:
        topic_error = str(e)
        
    user_pin_success = False
    user_pin_error = "Unknown error"
    user_message_to_pin_id = None

    admin_message_key = f"{update.effective_chat.id}:{reply_to_message.message_id}"

    if _message_links and admin_message_key in _message_links:
        link_info = _message_links[admin_message_key]
        if link_info.get('user_id') == user_id and link_info.get('user_message_id') and link_info.get('is_from_user', False):
            user_message_to_pin_id = link_info['user_message_id']

    try:
        if user_message_to_pin_id:
            await context.bot.pin_chat_message(
                chat_id=user_id,
                message_id=user_message_to_pin_id,
                disable_notification=True
            )
            user_pin_success = True
        else:
            forwarded_message = await context.bot.copy_message(
                chat_id=user_id,
                from_chat_id=update.effective_chat.id,
                message_id=reply_to_message.message_id
            )
            await context.bot.pin_chat_message(
                chat_id=user_id,
                message_id=forwarded_message.message_id,
                disable_notification=True
            )
            user_pin_success = True
            
            if hasattr(bot_core, '_last_pinned_messages'):
                bot_core._last_pinned_messages[user_id] = forwarded_message.message_id
    except Exception as e:
        user_pin_error = str(e)
    if topic_success and user_pin_success:
        result_text = "🔹 Message successfully pinned in user chat and topic."
    elif topic_success:
        result_text = f"🔹 Message pinned in topic. Error in user chat: {user_pin_error}"
    elif user_pin_success:
        result_text = f"🔹 Message pinned in user chat. Error in topic: {topic_error}"
    else:
        result_text = f"🔹 Failed to pin message. Topic error: {topic_error}. User chat error: {user_pin_error}"

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=result_text,
        message_thread_id=message_thread_id
    )

async def unpin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_core or not hasattr(bot_core, 'admin_id') or not hasattr(bot_core, 'topic_mode_group_id'):
        await context.bot.send_message(update.effective_chat.id, "Error: Unpin command is not configured correctly. Please contact admin.")
        return

    if hasattr(bot_core, 'bot_paused') and bot_core.bot_paused:
        from roles import is_admin
        if not is_admin(update.effective_user.id):
            return

    from roles import is_admin, is_operator
    if not is_admin(update.effective_user.id) and not is_operator(update.effective_user.id):
        return
    
    args = context.args
    
    reply_to_message = update.message.reply_to_message
    if not reply_to_message:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🔹 This command must be used in reply to a message you want to unpin.",
            message_thread_id=getattr(update.message, 'message_thread_id', None)
        )
        return
        
    message_thread_id = getattr(update.message, 'message_thread_id', None)
    
    if not message_thread_id:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🔹 This command currently only works in user topics.",
            message_thread_id=message_thread_id
        )
        return

    try:
        from user_details import get_user_id_by_topic_id
    except ImportError:
        logger.exception("Failed to import get_user_id_by_topic_id from user_details.")
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
    
    topic_unpin_success = False
    topic_unpin_error = "Unknown error"
    try:
        await context.bot.unpin_chat_message(
            chat_id=update.effective_chat.id,
            message_id=reply_to_message.message_id
        )
        topic_unpin_success = True
    except Exception as e:
        if "not found" in str(e).lower() or "not pinned" in str(e).lower():
            topic_unpin_success = True 
            topic_unpin_error = "Message was not pinned or already unpinned in topic."
        else:
            topic_unpin_error = str(e)

    user_unpin_success = False
    user_unpin_error = "Unknown error"
    user_message_to_unpin_id = None

    admin_message_key = f"{update.effective_chat.id}:{reply_to_message.message_id}"
    if _message_links and admin_message_key in _message_links:
        link_info = _message_links[admin_message_key]
        if link_info.get('user_id') == user_id and link_info.get('user_message_id') and link_info.get('is_from_user', False):
            user_message_to_unpin_id = link_info['user_message_id']

    try:
        if user_message_to_unpin_id:
            await context.bot.unpin_chat_message(
                chat_id=user_id,
                message_id=user_message_to_unpin_id
            )
        else:
            await context.bot.unpin_chat_message(chat_id=user_id)
        user_unpin_success = True
    except Exception as e:
        if "not found" in str(e).lower() or "not pinned" in str(e).lower():
            user_unpin_success = True
            user_unpin_error = "Message was not pinned or already unpinned in user chat."
        else:
            user_unpin_error = str(e)

    if topic_unpin_success and user_unpin_success:
        result_text = "🔹 Message successfully unpinned in user chat and topic."
    elif topic_unpin_success:
        result_text = f"🔹 Message unpinned in topic. User chat: {user_unpin_error}"
    elif user_unpin_success:
        result_text = f"🔹 Message unpinned in user chat. Topic: {topic_unpin_error}"
    else:
        result_text = f"🔹 Failed to unpin. Topic error: {topic_unpin_error}. User chat error: {user_unpin_error}"
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=result_text,
        message_thread_id=message_thread_id
    )

def register_handlers(app):
    from telegram.ext import CommandHandler
    
    app.add_handler(CommandHandler("pin", pin_command))
    app.add_handler(CommandHandler("unpin", unpin_command))
