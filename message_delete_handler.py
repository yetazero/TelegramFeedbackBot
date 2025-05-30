from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from telegram.error import BadRequest

_message_links = {}
bot_core = None

def initialize(message_links_from_core, bot_core_module_param=None):
    global _message_links, bot_core
    _message_links = message_links_from_core
    if bot_core_module_param:
        bot_core = bot_core_module_param

async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🔹 /delete command received. Checking access rights...",
            message_thread_id=getattr(update.message, 'message_thread_id', None)
        )
    except Exception:
        pass
    
    if not bot_core:
        await context.bot.send_message(update.effective_chat.id, "Error: Delete command is not configured correctly. Please contact admin.")
        return

    try:
        from roles import is_admin, is_operator
        is_user_admin = is_admin(update.effective_user.id)
        is_user_operator = is_operator(update.effective_user.id)
    except Exception as e:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"🔹 Error checking access rights: {str(e)}",
            message_thread_id=getattr(update.message, 'message_thread_id', None)
        )
        return
    
    if not is_user_admin and not is_user_operator:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🔹 You don't have permission to use this command.",
            message_thread_id=getattr(update.message, 'message_thread_id', None)
        )
        return
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🔹 You have permission to use this command.",
            message_thread_id=getattr(update.message, 'message_thread_id', None)
        )
    
    reply_to_message = update.message.reply_to_message
    message_thread_id = getattr(update.message, 'message_thread_id', None)
    
    if not reply_to_message:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🔹 This command must be used in reply to a message you want to delete.",
            message_thread_id=message_thread_id
        )
        return
    
    is_in_topic_mode = bot_core.is_topic_mode_active() and message_thread_id

    user_id = None
    
    if is_in_topic_mode:
        try:
            from user_details import get_user_id_by_topic_id
            user_id_str = get_user_id_by_topic_id(message_thread_id, str(bot_core.topic_mode_group_id))
            if user_id_str:
                user_id = int(user_id_str)
            else:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="🔹 Could not identify the user for this topic.",
                    message_thread_id=message_thread_id
                )
                return
        except Exception as e:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Error: {str(e)}",
                message_thread_id=message_thread_id
            )
            return
    
    chat_delete_success = False
    user_delete_success = False
    chat_delete_error = "Unknown error"
    user_delete_error = "Unknown error"
    user_message_to_delete_id = None
    
    admin_message_key = f"{update.effective_chat.id}:{reply_to_message.message_id}"
    
    if not is_in_topic_mode and not user_id:
        if _message_links and admin_message_key in _message_links:
            link_info = _message_links[admin_message_key]
            user_id = link_info.get('user_id')
    
    if _message_links and admin_message_key in _message_links:
        link_info = _message_links[admin_message_key]
        
        if user_id and link_info.get('user_id') == user_id and link_info.get('user_message_id'):
            user_message_to_delete_id = link_info['user_message_id']
    
    try:
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=reply_to_message.message_id
        )
        chat_delete_success = True
        if is_in_topic_mode:
            logger.info(f"Deleted message {reply_to_message.message_id} in topic {update.effective_chat.id}")
        else:
            logger.info(f"Deleted message {reply_to_message.message_id} in chat {update.effective_chat.id}")
    except Exception as e:
        chat_delete_error = str(e)
        logger.error(f"Error deleting message in chat {update.effective_chat.id}: {e}")
    
    if user_id and user_message_to_delete_id:
        try:
            await context.bot.delete_message(
                chat_id=user_id,
                message_id=user_message_to_delete_id
            )
            user_delete_success = True
        except Exception as e:
            user_delete_error = str(e)
    elif user_id:
        user_delete_error = "Could not find the related message from the user"
    else:
        user_delete_success = True
    
    if is_in_topic_mode:
        if chat_delete_success and user_delete_success:
            result_text = "🔹 Message successfully deleted from user chat and topic."
        elif chat_delete_success:
            result_text = f"🔹 Message deleted in topic. Error in user chat: {user_delete_error}"
        elif user_delete_success:
            result_text = f"🔹 Message deleted in user chat. Error in topic: {chat_delete_error}"
        else:
    else:
        result_text = f"🔹 Failed to delete message. Error: {chat_delete_error}"
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=result_text,
        message_thread_id=message_thread_id
    )
    
    try:
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=update.message.message_id
        )
    except Exception:
        pass

def register_handlers(app):
    try:
        delete_handler = CommandHandler("delete", delete_command)
        handlers_to_remove = []
        for i, handler in enumerate(app.handlers.get(0, [])):
            if hasattr(handler, 'callback') and handler.callback.__name__ == 'delete_command':
                handlers_to_remove.append(i)
            elif (hasattr(handler, 'filters') and hasattr(handler.filters, 'commands') and 
                 'delete' in handler.filters.commands):
                handlers_to_remove.append(i)
        
        for i in sorted(handlers_to_remove, reverse=True):
            logger.warning(f"Удален существующий обработчик команды /delete с индексом {i}")
            app.handlers[0].pop(i)
        
        app.add_handler(delete_handler, group=0)
        logger.info("🚮 Message delete module successfully loaded, command handler registered")
        
        found = False
        for i, handler in enumerate(app.handlers.get(0, [])):
            if hasattr(handler, 'callback') and handler.callback.__name__ == 'delete_command':
                found = True
                break
        
        if not found:
            pass
    except Exception:
        pass
