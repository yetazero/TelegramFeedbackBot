import asyncio
import html
import time
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden

EDIT_FORMAT = """Edited:
{edited}
[fixed, {timestamp}]"""
DELETE_FORMAT = """[deleted, {timestamp}]"""

message_links = None

def initialize(core_message_links):
    global message_links
    message_links = core_message_links

def update_message_link_with_original_text(key, original_text):
    global message_links
    if key in message_links:
        message_links[key]['original_text'] = original_text
        
        if 'admin_chat_id' in message_links[key] and 'admin_message_id' in message_links[key]:
            admin_key = f"{message_links[key]['admin_chat_id']}:{message_links[key]['admin_message_id']}"
            if admin_key in message_links:
                message_links[admin_key]['original_text'] = original_text
                
        elif 'user_id' in message_links[key] and 'user_message_id' in message_links[key]:
            user_key = f"{message_links[key]['user_id']}:{message_links[key]['user_message_id']}"
            if user_key in message_links:
                message_links[user_key]['original_text'] = original_text
                
async def handle_deleted_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import bot_core
    import html
    
    if not hasattr(update, 'deleted_message') or not update.deleted_message:
        return
        
    deleted_message = update.deleted_message
    user = deleted_message.from_user
    
    if not user:
        return
        
    user_id = user.id
    user_id_str = str(user_id)
    message_id = deleted_message.message_id
    
    if user_id_str in bot_core.load_banned(): 
        return
    
    user_key = f"{user_id}:{message_id}"
    
    if user_key not in message_links:
        return
        
    admin_data = message_links[user_key]
    admin_chat_id = bot_core.topic_mode_group_id if bot_core.topic_mode_group_id is not None else admin_data['admin_chat_id']
    admin_message_id = admin_data['admin_message_id']
    
    from datetime import datetime
    local_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
    delete_text = DELETE_FORMAT.format(timestamp=local_time)
    
    try:
        await context.bot.send_message(
            chat_id=admin_chat_id,
            text=delete_text,
            reply_to_message_id=admin_message_id
        )
    except Exception as e:
        pass

def get_message_content(message):
    content = ""
    
    if message.text:
        content = message.text
    elif message.caption:
        content = message.caption
    elif message.photo:
        content = "[Photo]"
        if message.caption:
            content += f" with caption: {message.caption}"
    elif message.document:
        doc_name = message.document.file_name if message.document.file_name else "Document"
        content = f"[Document: {doc_name}]"
        if message.caption:
            content += f" with caption: {message.caption}"
    elif message.video:
        content = "[Video]"
        if message.caption:
            content += f" with caption: {message.caption}"
    elif message.audio:
        content = "[Audio]"
        if message.caption:
            content += f" with caption: {message.caption}"
    elif message.voice:
        content = "[Voice message]"
    elif message.sticker:
        content = "[🔹]"
    elif message.animation:
        content = "[GIF]"
        if message.caption:
            content += f" with caption: {message.caption}"
    elif message.video_note:
        content = "[Video message]"
    else:
        content = "[Unknown content type]"
    
    return content

async def handle_user_edited_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import bot_core
    import html
    
    if update.edited_message is None:
        return
        
    if bot_core.bot_paused:
        return
        
    user = update.effective_user
    user_id_str = str(user.id)
    edited_message = update.edited_message
    
    if user_id_str in bot_core.load_banned(): 
        return
    
    user_key = f"{user.id}:{edited_message.message_id}"
    if user_key not in message_links:
        return
        
    admin_data = message_links[user_key]
    admin_chat_id = bot_core.topic_mode_group_id if bot_core.topic_mode_group_id is not None else admin_data['admin_chat_id']
    admin_message_id = admin_data['admin_message_id']
    
    from datetime import datetime
    local_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
    fixed_tag = f"[fixed, {local_time}]"
    reply_id = admin_message_id
    
    original_text = None
    
    if 'original_text' in admin_data and admin_data['original_text']:
        original_text = admin_data['original_text']
    else:
        try:
            original_text = getattr(edited_message, '_effective_message', {}).get('text', None) or \
                          getattr(edited_message, '_effective_message', {}).get('caption', None)
            
            if not original_text:
                admin_message = await context.bot.get_messages(
                    chat_id=admin_chat_id, 
                    message_ids=admin_message_id
                )
                
                if admin_message:
                    if hasattr(admin_message, 'text') and admin_message.text:
                        original_text = admin_message.text
                    elif hasattr(admin_message, 'caption') and admin_message.caption:
                        original_text = admin_message.caption
                    else:
                        original_text = get_message_content(admin_message)
        except Exception as e:
            pass
    
    if not original_text:
        original_text = '[original message not available]'
    
    if edited_message.text:
        formatted = (
            f"<b>Edited:</b>\n<code>{html.escape(edited_message.text)}</code>\n"
            f"{fixed_tag}"
        )
        msg = await context.bot.send_message(
            chat_id=admin_chat_id,
            text=formatted,
            reply_to_message_id=reply_id,
            parse_mode='HTML'
        )
    elif edited_message.photo:
        formatted = (
            f"<b>Edited:</b>\n<code>{html.escape(edited_message.caption or '[no caption]')}</code>\n"
            f"{fixed_tag}"
        )
        msg = await context.bot.send_photo(
            chat_id=admin_chat_id,
            photo=edited_message.photo[-1].file_id,
            caption=formatted,
            reply_to_message_id=reply_id,
            parse_mode='HTML'
        )
    elif edited_message.document:
        formatted = (
            f"<b>Edited:</b>\n<code>{html.escape(edited_message.caption or '[no caption]')}</code>\n"
            f"{fixed_tag}"
        )
        msg = await context.bot.send_document(
            chat_id=admin_chat_id,
            document=edited_message.document.file_id,
            caption=formatted,
            reply_to_message_id=reply_id,
            parse_mode='HTML'
        )
    elif edited_message.audio:
        msg = await context.bot.send_audio(
            chat_id=admin_chat_id,
            audio=edited_message.audio.file_id,
            caption=fixed_tag,
            reply_to_message_id=reply_id
        )
    elif edited_message.voice:
        msg = await context.bot.send_voice(
            chat_id=admin_chat_id,
            voice=edited_message.voice.file_id,
            caption=fixed_tag,
            reply_to_message_id=reply_id
        )
    elif edited_message.video:
        msg = await context.bot.send_video(
            chat_id=admin_chat_id,
            video=edited_message.video.file_id,
            caption=fixed_tag,
            reply_to_message_id=reply_id
        )
    else:
        msg = await context.bot.send_message(
            chat_id=admin_chat_id,
            text=f"[fixed, {local_time}]\n[Unsupported edited message type]",
            reply_to_message_id=reply_id
        )

async def handle_admin_edited_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.edited_message is None:
        return
    
    from roles import is_admin, is_operator
    if not (update.effective_user and (is_admin(update.effective_user.id) or is_operator(update.effective_user.id))):
        return
    
    await _handle_admin_edited_message(update, context)


async def _delete_message_safe(bot, chat_id, message_id):
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except Exception as e:
        return False

def _get_link_key_for_admin(admin_chat_id, admin_message_id):
    return f"{admin_chat_id}:{admin_message_id}"


async def _handle_admin_edited_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import html
    import bot_core
    from roles import is_admin, is_operator
    
    edited_message = update.edited_message
    admin_chat_id = edited_message.chat_id
    admin_message_id = edited_message.message_id
    admin_key = _get_link_key_for_admin(admin_chat_id, admin_message_id)
    
    if admin_key in message_links:
        user_data = message_links[admin_key]
    else:
        found_key = None
        
        for key, data in message_links.items():
            if ('admin_message_id' in data and data['admin_message_id'] == admin_message_id):
                if ('admin_chat_id' in data and (data['admin_chat_id'] == admin_chat_id or 
                        (bot_core.topic_mode_group_id is not None and data['admin_chat_id'] == bot_core.topic_mode_group_id))):
                    found_key = key
                    break
        
        if not found_key and hasattr(edited_message, 'reply_to_message') and edited_message.reply_to_message:
            reply_msg = edited_message.reply_to_message
            
            reply_key = f"{admin_chat_id}:{reply_msg.message_id}"
            
            if reply_key in message_links:
                found_key = reply_key
        
        if not found_key:
            await context.bot.send_message(
                chat_id=admin_chat_id,
                text="🔹 Could not find the associated user message. Editing is not possible.",
                reply_to_message_id=admin_message_id
            )
            return
        
        user_data = message_links[found_key]
    
    user_id = user_data['user_id']
    user_message_id = user_data['user_message_id']
    
    local_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
    fixed_tag = f"[fixed, {local_time}]"
    
    original_text = None
    
    try:
        if 'original_text' in user_data and user_data['original_text']:
            original_text = user_data['original_text']
    except Exception as e:
        pass
        
    if not original_text:
        original_text = user_data.get('original_text', None) or getattr(edited_message, 'text', None) or getattr(edited_message, 'caption', None) or '[no data]'
    
    if edited_message.text:
        edited_text = edited_message.text
    elif edited_message.caption:
        edited_text = edited_message.caption
    else:
        edited_text = '[no text content]'
    
    formatted = (
        f"<b>Edited:</b>\n<code>{html.escape(edited_text)}</code>\n"
        f"{fixed_tag}"
    )
    
    try:
        await context.bot.send_message(
            chat_id=admin_chat_id,
            text=formatted,
            reply_to_message_id=admin_message_id,
            parse_mode='HTML'
        )
        
        if edited_message.text:
            try:
                try:
                    result = await context.bot.edit_message_text(
                        chat_id=user_id,
                        message_id=user_message_id,
                        text=edited_message.text,
                        parse_mode=ParseMode.HTML if '<' in edited_message.text and '>' in edited_message.text else None
                    )
                    return
                except Exception as e1:
                    pass
                    
                try:
                    result = await context.bot.edit_message_text(
                        chat_id=user_id,
                        message_id=user_message_id,
                        text=edited_message.text
                    )
                    return
                except Exception as e2:
                    pass
                
                sent_msg = await context.bot.send_message(
                    chat_id=user_id,
                    text=edited_message.text,
                    parse_mode=ParseMode.HTML if '<' in edited_message.text and '>' in edited_message.text else None
                )
                
                import bot_core
                bot_core.save_message_link(user_id, sent_msg.message_id, admin_chat_id, admin_message_id, is_from_user=False)
                    
            except Exception as e:
                await context.bot.send_message(
                    chat_id=admin_chat_id,
                    text=f"Critical error while editing message: {e}",
                    reply_to_message_id=admin_message_id
                )
        
        elif edited_message.photo or edited_message.document or edited_message.video or edited_message.audio or edited_message.voice or edited_message.caption is not None:
            try:
                await _delete_message_safe(context.bot, user_id, user_message_id)
                
                sent_msg = None
                if edited_message.photo:
                    sent_msg = await context.bot.send_photo(
                        chat_id=user_id,
                        photo=edited_message.photo[-1].file_id,
                        caption=edited_message.caption,
                        parse_mode=ParseMode.HTML if edited_message.caption and '<' in edited_message.caption and '>' in edited_message.caption else None
                    )
                elif edited_message.document:
                    sent_msg = await context.bot.send_document(
                        chat_id=user_id,
                        document=edited_message.document.file_id,
                        caption=edited_message.caption,
                        parse_mode=ParseMode.HTML if edited_message.caption and '<' in edited_message.caption and '>' in edited_message.caption else None
                    )
                elif edited_message.video:
                    sent_msg = await context.bot.send_video(
                        chat_id=user_id,
                        video=edited_message.video.file_id,
                        caption=edited_message.caption,
                        parse_mode=ParseMode.HTML if edited_message.caption and '<' in edited_message.caption and '>' in edited_message.caption else None
                    )
                elif edited_message.audio:
                    sent_msg = await context.bot.send_audio(
                        chat_id=user_id,
                        audio=edited_message.audio.file_id,
                        caption=edited_message.caption,
                        parse_mode=ParseMode.HTML if edited_message.caption and '<' in edited_message.caption and '>' in edited_message.caption else None
                    )
                
                if sent_msg:
                    import bot_core
                    bot_core.save_message_link(user_id, sent_msg.message_id, admin_chat_id, admin_message_id, is_from_user=False)
                    
            except Exception as e:
                await context.bot.send_message(
                    chat_id=admin_chat_id,
                    text=f"Critical error while editing caption: {e}",
                    reply_to_message_id=admin_message_id
                )
        
                sent_msg = None
                if edited_message.photo:
                    sent_msg = await context.bot.send_photo(
                        chat_id=user_id,
                        photo=edited_message.photo[-1].file_id,
                        caption=edited_message.caption or None,
                        parse_mode=ParseMode.HTML if edited_message.caption and '<' in edited_message.caption and '>' in edited_message.caption else None
                    )
                
                elif edited_message.document:
                    sent_msg = await context.bot.send_document(
                        chat_id=user_id,
                        document=edited_message.document.file_id,
                        caption=edited_message.caption or None,
                        parse_mode=ParseMode.HTML if edited_message.caption and '<' in edited_message.caption and '>' in edited_message.caption else None
                    )
                
                elif edited_message.video:
                    sent_msg = await context.bot.send_video(
                        chat_id=user_id,
                        video=edited_message.video.file_id,
                        caption=edited_message.caption or None,
                        parse_mode=ParseMode.HTML if edited_message.caption and '<' in edited_message.caption and '>' in edited_message.caption else None
                    )
                
                elif edited_message.audio:
                    sent_msg = await context.bot.send_audio(
                        chat_id=user_id,
                        audio=edited_message.audio.file_id,
                        caption=edited_message.caption or None,
                        parse_mode=ParseMode.HTML if edited_message.caption and '<' in edited_message.caption and '>' in edited_message.caption else None
                    )
                
                elif edited_message.voice:
                    sent_msg = await context.bot.send_voice(
                        chat_id=user_id,
                        voice=edited_message.voice.file_id,
                        caption=edited_message.caption or None,
                        parse_mode=ParseMode.HTML if edited_message.caption and '<' in edited_message.caption and '>' in edited_message.caption else None
                    )
                
                if sent_msg:
                    import bot_core
                    bot_core.save_message_link(user_id, sent_msg.message_id, admin_chat_id, admin_message_id, is_from_user=False)
    except Exception as e:
        await context.bot.send_message(
            chat_id=admin_chat_id,
            text=f"🔹 Failed to update message for user: {str(e)}",
            reply_to_message_id=admin_message_id
        )

async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import bot_core
    from datetime import datetime
    from roles import is_admin, is_operator
    
    if not update.effective_user or (not is_admin(update.effective_user.id) and not is_operator(update.effective_user.id)):
        return
    
    if not update.message or not update.message.reply_to_message:
        await update.message.reply_text("Please use this command as a reply to a message that should be deleted.")
        return
    
    admin_message = update.message.reply_to_message
    
    try:
        import bot_core
        
        user_id, user_message_id, is_from_user = bot_core.get_user_message_for_admin_message(
            admin_message.chat_id, admin_message.message_id
        )
        
        if not user_id or not user_message_id:
            await update.message.reply_text("Could not find the original user message. Make sure you're replying to a forwarded message from a user.")
            return
        
        await _delete_message_safe(context.bot, user_id, user_message_id)
        
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        
        message_content = admin_message.text or admin_message.caption or ""

        thread_id = update.message.message_thread_id if update.message and hasattr(update.message, 'message_thread_id') else None

        try:
            if admin_message.photo:
                await context.bot.send_photo(
                    chat_id=admin_message.chat_id,
                    photo=admin_message.photo[-1].file_id,
                    caption=f"<b>Deleted:</b>\n<code>{html.escape(message_content)}</code>\n[fixed, {current_time}]",
                    parse_mode='HTML',
                        message_thread_id=thread_id,

                    reply_to_message_id=admin_message.reply_to_message.message_id if admin_message.reply_to_message else None
                )
            elif admin_message.document:
                await context.bot.send_document(
                    chat_id=admin_message.chat_id,
                    document=admin_message.document.file_id,
                    caption=f"<b>Deleted:</b>\n<code>{html.escape(message_content)}</code>\n[fixed, {current_time}]",
                    parse_mode='HTML',
                        message_thread_id=thread_id,

                    reply_to_message_id=admin_message.reply_to_message.message_id if admin_message.reply_to_message else None
                )
            elif admin_message.video:
                await context.bot.send_video(
                    chat_id=admin_message.chat_id,
                    video=admin_message.video.file_id,
                    caption=f"<b>Deleted:</b>\n<code>{html.escape(message_content)}</code>\n[fixed, {current_time}]",
                    parse_mode='HTML',
                        message_thread_id=thread_id,

                    reply_to_message_id=admin_message.reply_to_message.message_id if admin_message.reply_to_message else None
                )
            elif admin_message.audio:
                await context.bot.send_audio(
                    chat_id=admin_message.chat_id,
                    audio=admin_message.audio.file_id,
                    caption=f"<b>Deleted:</b>\n<code>{html.escape(message_content)}</code>\n[fixed, {current_time}]",
                    parse_mode='HTML',
                        message_thread_id=thread_id,

                    reply_to_message_id=admin_message.reply_to_message.message_id if admin_message.reply_to_message else None
                )
            elif admin_message.voice:
                await context.bot.send_voice(
                    chat_id=admin_message.chat_id,
                    voice=admin_message.voice.file_id,
                    caption=f"[fixed, {current_time}]",
                    reply_to_message_id=admin_message.reply_to_message.message_id if admin_message.reply_to_message else None
                )
                if message_content:
                    await admin_message.reply_text(
                        f"<b>Deleted:</b>\n<code>{html.escape(message_content)}</code>\n[fixed, {current_time}]",
                        parse_mode='HTML',
                        message_thread_id=thread_id,
                        reply_to_message_id=admin_message.message_id
                    )
            elif admin_message.sticker:
                await context.bot.send_sticker(
                    chat_id=admin_message.chat_id,
                    sticker=admin_message.sticker.file_id,
                    reply_to_message_id=admin_message.reply_to_message.message_id if admin_message.reply_to_message else None
                )
                await admin_message.reply_text(
                    f"<b>Deleted:</b>\n[🔹]\n[fixed, {current_time}]",
                    parse_mode='HTML',
                    message_thread_id=thread_id,
                    reply_to_message_id=admin_message.message_id
                )
            elif admin_message.animation:
                await context.bot.send_animation(
                    chat_id=admin_message.chat_id,
                    animation=admin_message.animation.file_id,
                    caption=f"<b>Deleted:</b>\n<code>{html.escape(message_content)}</code>\n[fixed, {current_time}]",
                    parse_mode='HTML',
                        message_thread_id=thread_id,

                    reply_to_message_id=admin_message.reply_to_message.message_id if admin_message.reply_to_message else None
                )
            elif admin_message.video_note:
                await context.bot.send_video_note(
                    chat_id=admin_message.chat_id,
                    video_note=admin_message.video_note.file_id,
                    reply_to_message_id=admin_message.reply_to_message.message_id if admin_message.reply_to_message else None
                )
                if message_content:
                    await admin_message.reply_text(
                        f"<b>Deleted:</b>\n<code>{html.escape(message_content)}</code>\n[fixed, {current_time}]",
                        parse_mode='HTML',
                        message_thread_id=thread_id,
                        reply_to_message_id=admin_message.message_id
                    )
            else:
                await admin_message.reply_text(
                    f"<b>Deleted:</b>\n<code>{html.escape(message_content)}</code>\n[fixed, {current_time}]",
                    parse_mode='HTML',
                        message_thread_id=thread_id,
                    reply_to_message_id=admin_message.message_id
                )
        except Exception as e:
            await admin_message.reply_text(
                f"<b>Deleted with error:</b> <code>{html.escape(message_content)}</code>\n[fixed, {current_time}]",
                parse_mode='HTML',
                        message_thread_id=thread_id,
                reply_to_message_id=admin_message.message_id
            )
        await update.message.delete()

        try:
            await _delete_message_safe(context.bot, admin_message.chat_id, admin_message.message_id)
        except Exception as e:
            pass
        
    except Exception as e:
        try:
            await update.message.reply_text(f"Failed to delete message: {str(e)}")
        except:
            pass


def register_handlers(app):
    from telegram.ext import MessageHandler, filters, CommandHandler
    
    import bot_core
    admin_id = bot_core.admin_id
    
    from roles import get_all_admins, get_all_operators
    
    all_admins = [int(admin) for admin in get_all_admins()]
    all_operators = [int(operator) for operator in get_all_operators()]
    all_staff = all_admins + all_operators
    
    user_edit_filter = filters.UpdateType.EDITED_MESSAGE & ~filters.User(all_staff)
    
    app.add_handler(MessageHandler(user_edit_filter, handle_user_edited_message), group=998)
    
    staff_edit_filter = filters.UpdateType.EDITED_MESSAGE & filters.User(all_staff)
    app.add_handler(MessageHandler(staff_edit_filter, handle_admin_edited_message), group=998)
    
    async def handle_any_edited_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        pass
    app.add_handler(MessageHandler(filters.UpdateType.EDITED_MESSAGE, handle_any_edited_message), group=1000)
    
    app.add_handler(CommandHandler("delete", delete_command))