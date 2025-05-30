import debug
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from datetime import datetime

last_command_details = {}

async def send_message_with_logging(bot, chat_id, text, **kwargs):
    is_command = False
    user_id = None
    
    if 'last_command_details' in bot.bot_data and bot.bot_data['last_command_details'].get('chat_id') == chat_id:
        is_command = True
        user_id = bot.bot_data['last_command_details'].get('user_id')
    
    reply_to = kwargs.get('reply_to_message_id')
    await debug.log_bot_action(
        bot=bot, 
        chat_id=chat_id, 
        message_text=text, 
        is_command=is_command, 
        reply_to_message_id=reply_to,
        user_id=user_id
    )
    
    return await bot.send_message(chat_id, text, **kwargs)

async def send_photo_with_logging(bot, chat_id, photo, caption=None, **kwargs):
    text_to_log = caption if caption else "[Photo without caption]"
    
    is_command = False
    user_id = None
    
    if 'last_command_details' in bot.bot_data and bot.bot_data['last_command_details'].get('chat_id') == chat_id:
        is_command = True
        user_id = bot.bot_data['last_command_details'].get('user_id')
    
    reply_to = kwargs.get('reply_to_message_id')
    await debug.log_bot_action(
        bot=bot, 
        chat_id=chat_id, 
        message_text=text_to_log,
        is_command=is_command, 
        reply_to_message_id=reply_to,
        user_id=user_id
    )
    
    return await bot.send_photo(chat_id, photo, caption=caption, **kwargs)

async def edit_message_text_with_logging(bot, text_content, chat_id=None, message_id=None, inline_message_id=None, **kwargs):
    if chat_id:
        log_text_content = f"[Editing] {text_content}"
        is_command = False
        user_id = None
        
        if 'last_command_details' in bot.bot_data and bot.bot_data['last_command_details'].get('chat_id') == chat_id:
            is_command = True
            user_id = bot.bot_data['last_command_details'].get('user_id')
        
        await debug.log_bot_action(
            bot=bot, 
            chat_id=chat_id, 
            message_text=log_text_content,
            is_command=is_command, 
            reply_to_message_id=message_id,
            user_id=user_id
        )
    
    return await bot.edit_message_text(text_content, chat_id=chat_id, message_id=message_id, inline_message_id=inline_message_id, **kwargs)

def initialize_logging(app):
    app.bot_data['send_message_with_logging'] = lambda chat_id, text, **kwargs: send_message_with_logging(app.bot, chat_id, text, **kwargs)
    app.bot_data['send_photo_with_logging'] = lambda chat_id, photo, caption=None, **kwargs: send_photo_with_logging(app.bot, chat_id, photo, caption, **kwargs)
    app.bot_data['edit_message_text_with_logging'] = lambda text_content, chat_id=None, message_id=None, inline_message_id=None, **kwargs: edit_message_text_with_logging(app.bot, text_content, chat_id, message_id, inline_message_id, **kwargs)
    
    async def remember_last_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.message.text or not update.message.text.startswith('/'):
            return
        
        command_name = update.message.text.split()[0]
        full_command_text = update.message.text
        
        context.bot_data['last_command_details'] = {
            'user_id': update.effective_user.id if update.effective_user else None,
            'chat_id': update.effective_chat.id if update.effective_chat else None,
            'message_id': update.message.message_id,
            'command': command_name,
            'full_text': full_command_text,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    app.add_handler(MessageHandler(filters.COMMAND, remember_last_command), group=-999)

def create_logged_command_handlers(app, original_handlers):
    new_handlers = {}
    
    for command_key, original_handler_func in original_handlers.items():
        async def logged_command_wrapper(update, context, original_handler=original_handler_func):
            result = await original_handler(update, context)
            
            if isinstance(result, str) and update.effective_chat:
                await app.bot_data['send_message_with_logging'](
                    chat_id=update.effective_chat.id,
                    text=result,
                    reply_to_message_id=update.effective_message.message_id if update.effective_message else None
                )
                return None
            
            return result
        
        new_handlers[command_key] = logged_command_wrapper
    
    return new_handlers