from telegram import Update
from telegram.ext import ContextTypes
from roles import is_admin, is_operator

_message_links = {}
bot_core = None

def initialize(message_links_from_core, bot_core_module_param=None):
    global _message_links, bot_core
    _message_links = message_links_from_core
    if bot_core_module_param:
        bot_core = bot_core_module_param

async def handle_operator_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_core:
        return False
        
    if bot_core.bot_paused:
        return False
        
    user_id = update.effective_user.id
    if not is_operator(user_id):
        return False
    
    message = update.message
    if message is None:
        return False
    
    if not bot_core.is_topic_mode_active() or not getattr(message, 'message_thread_id', None):
        if hasattr(message, 'reply_to_message') and message.reply_to_message:
            original_user_id, original_msg_id, is_from_user = bot_core.get_user_message_for_admin_message(
                message.chat_id, message.reply_to_message.message_id
            )
            
            if original_user_id and original_msg_id:
                content_dict = bot_core.message_to_telegram_dict(message)
                
                sent_message = await bot_core.send_content_to_user(
                    context.bot,
                    original_user_id,
                    content_dict,
                    reply_to_message_id=original_msg_id if is_from_user else None,
                    return_message=True
                )
                
                if sent_message:
                    bot_core.save_message_link(
                        original_user_id,
                        sent_message.message_id,
                        message.chat_id,
                        message.message_id,
                        is_from_user=False
                    )
                    return True
        
        return False
    
    message_thread_id = message.message_thread_id
    try:
        from user_details import get_user_id_by_topic_id
    except ImportError:
        return False
    
    user_id_str = get_user_id_by_topic_id(message_thread_id, str(bot_core.topic_mode_group_id))
    if not user_id_str:
        return False
    
    target_user_id = int(user_id_str)
    
    reply_to_user_message_id = None
    
    if message.reply_to_message:
        reply_msg = message.reply_to_message
        
        original_user_id, original_msg_id, is_from_user = bot_core.get_user_message_for_admin_message(
            message.chat_id, reply_msg.message_id
        )
        
        if original_user_id == target_user_id and original_msg_id:
            reply_to_user_message_id = original_msg_id
    
    try:
        content_dict = bot_core.message_to_telegram_dict(message)
        sent_message = await bot_core.send_content_to_user(
            context.bot, 
            target_user_id,
            content_dict, 
            reply_to_message_id=reply_to_user_message_id,
            return_message=True
        )
        
        if sent_message:
            bot_core.save_message_link(
                target_user_id,
                sent_message.message_id,
                message.chat_id,
                message.message_id,
                is_from_user=False
            )
            return True
    
    except Exception:
        pass
    
    return False

async def process_operator_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await handle_operator_message(update, context)

def register_handlers(app):
    pass
