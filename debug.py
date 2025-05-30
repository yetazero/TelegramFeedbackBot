from telegram import Update, Bot
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters, Application
import datetime

debug_status = "off"
debug_target_chat_id = None

message_links_manager = None
configuration_manager = None

def initialize_debug(msg_links_mgr, cfg_mgr=None):
    global message_links_manager, configuration_manager, debug_status, debug_target_chat_id
    message_links_manager = msg_links_mgr
    
    if cfg_mgr:
        configuration_manager = cfg_mgr
        saved_debug_status = configuration_manager.get_config("debug_status", fallback="off")
        saved_debug_target_chat_id = configuration_manager.get_config("debug_target_chat_id", fallback=None)
        
        if saved_debug_status != "off":
            debug_status = saved_debug_status
            try:
                debug_target_chat_id = int(saved_debug_target_chat_id) if saved_debug_target_chat_id else None
            except ValueError:
                debug_target_chat_id = None

async def manage_debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global debug_status, debug_target_chat_id, configuration_manager
    
    from roles import is_admin
    
    if not update.effective_user or not is_admin(update.effective_user.id):
        return
    
    if not context.args or len(context.args) == 0:
        await update.message.reply_text(
            "Debug mode commands:\n"
            "/debug on - Forward all messages to admin\n"
            "/debug off - Turn off debug mode\n"
            "/debug [chat_id] - Forward all messages to specified chat",
            message_thread_id=getattr(update.message, 'message_thread_id', None)
        )
        return
    
    command_arg = context.args[0].lower()
    
    if command_arg == "off":
        debug_status = "off"
        debug_target_chat_id = None
        if configuration_manager:
            configuration_manager.set_config("debug_status", "off")
            configuration_manager.set_config("debug_target_chat_id", "")
            configuration_manager.save_config()
        
        await update.message.reply_text(
            "🔹 Debug mode turned off",
            message_thread_id=getattr(update.message, 'message_thread_id', None)
        )
    elif command_arg == "on":
        debug_status = "on"
        debug_target_chat_id = update.effective_user.id
        if configuration_manager:
            configuration_manager.set_config("debug_status", "on")
            configuration_manager.set_config("debug_target_chat_id", str(debug_target_chat_id))
            configuration_manager.save_config()
        
        await update.message.reply_text(
            f"🔹 Debug mode enabled. All messages will be forwarded to you (ID: {debug_target_chat_id})",
            message_thread_id=getattr(update.message, 'message_thread_id', None)
        )
    else:
        try:
            target_chat_id_val = int(command_arg)
            debug_status = "chat"
            debug_target_chat_id = target_chat_id_val
            if configuration_manager:
                configuration_manager.set_config("debug_status", "chat")
                configuration_manager.set_config("debug_target_chat_id", str(debug_target_chat_id))
                configuration_manager.save_config()
            
            await update.message.reply_text(
                f"🔹 Debug mode enabled. All messages will be forwarded to chat ID: {debug_target_chat_id}",
                message_thread_id=getattr(update.message, 'message_thread_id', None)
            )
        except ValueError:
            await update.message.reply_text(
                "🔹 Invalid command format. Use /debug on, /debug off, or /debug [chat_id]",
                message_thread_id=getattr(update.message, 'message_thread_id', None)
            )

async def forward_message_to_debug_chat(bot: Bot, message, header_text):
    if debug_status == "off" or not debug_target_chat_id:
        return
    
    try:
        if message.text:
            await bot.send_message(chat_id=debug_target_chat_id, text=f"{header_text}\n\n{message.text}")
        elif message.photo:
            photo_file_id = message.photo[-1].file_id
            caption_text = f"{header_text}\n\nPhoto: {message.caption if message.caption else ''}"
            await bot.send_photo(chat_id=debug_target_chat_id, photo=photo_file_id, caption=caption_text)
        elif message.video:
            video_file_id = message.video.file_id
            caption_text = f"{header_text}\n\nVideo: {message.caption if message.caption else ''}"
            await bot.send_video(chat_id=debug_target_chat_id, video=video_file_id, caption=caption_text)
        elif message.document:
            document_file_id = message.document.file_id
            caption_text = f"{header_text}\n\nDocument: {message.document.file_name or 'No filename'} ({message.document.mime_type or 'No MIME type'})\n{message.caption if message.caption else ''}"
            await bot.send_document(chat_id=debug_target_chat_id, document=document_file_id, caption=caption_text)
        elif message.sticker:
            sticker_details = f"Sticker: ID - {message.sticker.file_id}, Emoji - {message.sticker.emoji or 'N/A'}"
            if message.sticker.set_name:
                sticker_details += f", Set - {message.sticker.set_name}"
            await bot.send_message(chat_id=debug_target_chat_id, text=f"{header_text}\n\n{sticker_details}")
        elif message.voice:
            voice_file_id = message.voice.file_id
            caption_text = f"{header_text}\n\nVoice message: Duration {message.voice.duration}s"
            await bot.send_voice(chat_id=debug_target_chat_id, voice=voice_file_id, caption=caption_text)
        elif message.audio:
            audio_file_id = message.audio.file_id
            caption_text = f"{header_text}\n\nAudio: {message.audio.title or 'No title'} by {message.audio.performer or 'Unknown artist'}\n{message.caption if message.caption else ''}"
            await bot.send_audio(chat_id=debug_target_chat_id, audio=audio_file_id, caption=caption_text)
        elif message.location:
            location_details = f"Location: Lat {message.location.latitude}, Lon {message.location.longitude}"
            await bot.send_message(chat_id=debug_target_chat_id, text=f"{header_text}\n\n{location_details}")
            await bot.send_location(chat_id=debug_target_chat_id, latitude=message.location.latitude, longitude=message.location.longitude)
        elif message.contact:
            contact_details = f"Contact: {message.contact.first_name} {message.contact.last_name or ''} ({message.contact.phone_number})"
            await bot.send_message(chat_id=debug_target_chat_id, text=f"{header_text}\n\n{contact_details}")
        elif message.poll:
            poll_details = f"Poll: {message.poll.question} (Options: {', '.join([opt.text for opt in message.poll.options])})"
            await bot.send_message(chat_id=debug_target_chat_id, text=f"{header_text}\n\n{poll_details}")
        elif message.new_chat_members:
            members_joined = ', '.join([user.full_name for user in message.new_chat_members])
            await bot.send_message(debug_target_chat_id, f"{header_text}\n\nNew chat members: {members_joined}")
        elif message.left_chat_member:
            await bot.send_message(debug_target_chat_id, f"{header_text}\n\nChat member left: {message.left_chat_member.full_name}")
        elif message.new_chat_title:
            await bot.send_message(debug_target_chat_id, f"{header_text}\n\nNew chat title: {message.new_chat_title}")
        elif message.new_chat_photo:
            await bot.send_message(debug_target_chat_id, f"{header_text}\n\nNew chat photo set")
        elif message.delete_chat_photo:
            await bot.send_message(debug_target_chat_id, f"{header_text}\n\nChat photo deleted")
        elif message.group_chat_created:
            await bot.send_message(debug_target_chat_id, f"{header_text}\n\nGroup chat created")
        elif message.supergroup_chat_created:
            await bot.send_message(debug_target_chat_id, f"{header_text}\n\nSupergroup chat created")
        elif message.channel_chat_created:
            await bot.send_message(debug_target_chat_id, f"{header_text}\n\nChannel chat created")
        elif message.message_auto_delete_timer_changed:
            new_timer = message.message_auto_delete_timer_changed.message_auto_delete_time
            await bot.send_message(debug_target_chat_id, f"{header_text}\n\nMessage auto-delete timer changed to: {new_timer} seconds")
        elif message.migrate_to_chat_id:
            await bot.send_message(debug_target_chat_id, f"{header_text}\n\nChat migrated to chat ID: {message.migrate_to_chat_id}")
        elif message.migrate_from_chat_id:
            await bot.send_message(debug_target_chat_id, f"{header_text}\n\nChat migrated from chat ID: {message.migrate_from_chat_id}")
        elif message.pinned_message:
            pinned_msg_preview = message.pinned_message.text or "[Non-text content]"
            await bot.send_message(debug_target_chat_id, f"{header_text}\n\nPinned message: {pinned_msg_preview[:100]}{'...' if len(pinned_msg_preview) > 100 else ''}")
        else:
            await bot.send_message(chat_id=debug_target_chat_id, text=f"{header_text}\n\n[Unsupported or empty message type]")
    except Exception as e:
        pass

async def debug_all_incoming_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if debug_status == "off" or not debug_target_chat_id:
        return

    current_message = update.effective_message
    if not current_message:
        return

    current_user = update.effective_user
    current_chat = update.effective_chat
    
    header_info_parts = []
    
    if current_user:
        user_details_str = f"User: {current_user.full_name} (ID: {current_user.id})"
        if current_user.username:
            user_details_str += f" Username: @{current_user.username}"
        header_info_parts.append(f"👤 USER: {user_details_str}")

    if current_chat:
        chat_details_str = f"Chat: {current_chat.title or 'N/A'} (ID: {current_chat.id}) Type: {current_chat.type}"
        header_info_parts.append(f"FROM CHAT: {chat_details_str}")

    if current_message.is_topic_message and current_message.message_thread_id:
        topic_identifier = current_message.message_thread_id
        topic_display_name = f"Topic (ID: {topic_identifier})"
        header_info_parts.append(f"🔹 TOPIC: {topic_display_name}")
    
    message_meta_details = f"Message ID: {current_message.message_id}"
    if hasattr(current_message, 'message_thread_id') and current_message.message_thread_id:
        message_meta_details += f" Thread ID: {current_message.message_thread_id}"
    
    if message_links_manager and hasattr(message_links_manager, 'get_message_link'):
        try:
            msg_link = message_links_manager.get_message_link(current_chat.id, current_message.message_id, current_message.message_thread_id)
            if msg_link:
                message_meta_details += f" Link: {msg_link}"
        except Exception as e:
            pass
    elif message_links_manager:
        pass
    header_info_parts.append(message_meta_details)

    complete_header = "\n".join(header_info_parts)
    await forward_message_to_debug_chat(context.bot, current_message, complete_header)

def register_debug_handlers(app: Application):
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, debug_all_incoming_messages), group=10)
    app.add_handler(CommandHandler("debug", manage_debug_command))

async def log_bot_action_to_debug(bot: Bot, target_chat_id, text_of_message, is_cmd_action=False, reply_msg_id=None, effective_user_id=None):
    global debug_status, debug_target_chat_id
    if debug_status == "off" or not debug_target_chat_id:
        return

    user_id_for_log = effective_user_id
    chat_id_for_log = target_chat_id

    if effective_user_id is None and target_chat_id > 0:
        user_id_for_log = target_chat_id
    elif effective_user_id is None and target_chat_id < 0:
        user_id_for_log = 123456789 
    elif effective_user_id is not None and effective_user_id < 0:
        user_id_for_log = 123456789

    if user_id_for_log is None or user_id_for_log < 0:
        user_id_for_log = 123456789

    action_description = "COMMAND" if is_cmd_action else "MESSAGE"
    
    log_message_header = f"USER {bot.id} >>> {target_chat_id} [{action_description}]"
    
    if reply_msg_id:
        log_message_header += f" (Reply to {reply_msg_id})"
    

    final_log_entry = f"{log_message_header}\n{text_of_message}"

    try:
        await bot.send_message(debug_target_chat_id, final_log_entry)
    except Exception as e:
        pass
    

def setup_command_wrapping(app: Application):
    def debug_command_response_decorator(handler_function_to_wrap):
        async def decorated_wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if update.message and update.message.text and update.message.text.startswith('/'):
                cmd_name = update.message.text.split()[0]
                full_cmd_text = update.message.text
                
                context.bot_data['last_command_details'] = {
                    'user_id': update.effective_user.id if update.effective_user else None,
                    'chat_id': update.effective_chat.id if update.effective_chat else None,
                    'message_id': update.message.message_id,
                    'command': cmd_name,
                    'full_text': full_cmd_text,
                    'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            
            handler_result = await handler_function_to_wrap(update, context)
            
            if isinstance(handler_result, str) and update.effective_chat:
                await log_bot_action_to_debug(
                    bot=context.bot,
                    target_chat_id=update.effective_chat.id,
                    text_of_message=handler_result,
                    is_cmd_action=True,
                    reply_msg_id=update.effective_message.message_id if update.effective_message else None,
                    effective_user_id=update.effective_user.id if update.effective_user else None # Pass user_id here
                )
                
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=handler_result,
                    reply_to_message_id=update.effective_message.message_id if update.effective_message else None
                )
                return None
            
            return handler_result
        return decorated_wrapper
    
    async def send_message_with_debug_logging(target_chat_id, text_content, **kwargs_for_send):
        is_cmd_response = False
        user_id_for_action = None
        if 'last_command_details' in app.bot_data and app.bot_data['last_command_details'].get('chat_id') == target_chat_id:
            is_cmd_response = True
            user_id_for_action = app.bot_data['last_command_details'].get('user_id')
        
        await log_bot_action_to_debug(
            bot=app.bot,
            target_chat_id=target_chat_id,
            text_of_message=text_content,
            is_cmd_action=is_cmd_response,
            reply_msg_id=kwargs_for_send.get('reply_to_message_id'),
            effective_user_id=user_id_for_action
        )
        
        return await app.bot.send_message(target_chat_id, text_content, **kwargs_for_send)
    
    app.bot_data['debug_command_decorator'] = debug_command_response_decorator
    app.bot_data['send_message_with_logging'] = send_message_with_debug_logging

    globals()['datetime'] = datetime
