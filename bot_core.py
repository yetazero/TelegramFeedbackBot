import asyncio
import threading
import time
import re
import os
import sys
import io
import socket
import gc
import json
from datetime import datetime, timedelta

from telegram import Update, Message, Bot, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, MenuButtonWebApp, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, UserProfilePhotos, File, ChatMemberUpdated, ChatMember, Dice, InputMediaPhoto, InputMediaVideo, InputMediaAudio, InputMediaDocument, BotCommand
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden
from telegram.ext import Application, ContextTypes, CommandHandler, filters, MessageHandler

from user_details import (
    load_banned, save_banned, load_users, save_users,
    load_user_details, save_user_details, get_user_data,
    update_user_data_field, get_user_info_string, get_user_id_by_topic_id,
    add_to_banned, remove_from_banned, is_banned,
    add_to_users, remove_from_users, is_user
)

from config_manager import ConfigManager
import reactions
import message_edit_handler
import debug

def message_to_telegram_dict(message):
    result = {}
    
    if hasattr(message, 'text') and message.text:
        result['text'] = message.text
    elif hasattr(message, 'caption') and message.caption:
        result['caption'] = message.caption
    
    if hasattr(message, 'photo') and message.photo:
        result['photo'] = message.photo[-1].file_id
    elif hasattr(message, 'video') and message.video:
        result['video'] = message.video.file_id
    elif hasattr(message, 'audio') and message.audio:
        result['audio'] = message.audio.file_id
    elif hasattr(message, 'voice') and message.voice:
        result['voice'] = message.voice.file_id
    elif hasattr(message, 'document') and message.document:
        result['document'] = message.document.file_id
    elif hasattr(message, 'animation') and message.animation:
        result['animation'] = message.animation.file_id
    elif hasattr(message, 'sticker') and message.sticker:
        result['sticker'] = message.sticker.file_id
    elif hasattr(message, 'video_note') and message.video_note:
        result['video_note'] = message.video_note.file_id
    
    return result
import pins
import roles
import delete_handler

send_states = {}
publish_state = {"active": False, "content": None, "pin": False}
send_receipt = True
send_to_admin_queue = asyncio.Queue()
admin_to_user_queue = asyncio.Queue()
message_status_queue = asyncio.Queue()
admin_id = None
sync_message_counter = 0
topic_mode_group_id = None
current_cooldown_seconds = 0
user_last_message = {}
config_mngr = None
stop_telegram_bot_event = threading.Event()
off_command_confirmation_code = None
message_links = {}
_last_pinned_messages = {}
subscribers = set()
bot_paused = False

_restart_in_progress = False
_restart_lock = threading.Lock()


def get_user_message_for_admin_message(admin_chat_id, admin_message_id):
    admin_key = f"{admin_chat_id}:{admin_message_id}"
    
    if admin_key in message_links:
        link_data = message_links[admin_key]
        return link_data.get('user_id'), link_data.get('user_message_id'), link_data.get('is_from_user', True)
    
    for key, data in message_links.items():
        if data.get('admin_message_id') == admin_message_id and data.get('admin_chat_id') == admin_chat_id:
            return data.get('user_id'), data.get('user_message_id'), data.get('is_from_user', True)
    
    return None, None, None


def save_message_link(user_id, user_message_id, admin_chat_id, admin_message_id, is_from_user=True):
    global message_links
    
    user_key = f"{user_id}:{user_message_id}"
    admin_key = f"{admin_chat_id}:{admin_message_id}"
    message_links[user_key] = {
        'admin_chat_id': admin_chat_id,
        'admin_message_id': admin_message_id,
        'is_from_user': is_from_user,
        'timestamp': time.time()
    }
    
    message_links[admin_key] = {
        'user_id': user_id,
        'user_message_id': user_message_id,
        'is_from_user': is_from_user,
        'timestamp': time.time()
    }


def get_admin_message_for_user_message(user_id, user_message_id):
    global message_links
    
    user_key = f"{user_id}:{user_message_id}"
    
    if user_key in message_links:
        info = message_links[user_key]
        return info['admin_chat_id'], info['admin_message_id'], info.get('is_from_user', False)
    
    return None, None, False


async def get_effective_user_details(user_id, update: Update = None, context: ContextTypes.DEFAULT_TYPE = None):
    user_id_str = str(user_id)
    all_details = load_user_details()
    user_data = all_details.get(user_id_str, {})

    effective_user_obj = None
    if update and update.effective_user and str(update.effective_user.id) == user_id_str:
        effective_user_obj = update.effective_user
    elif context and 'effective_user_cache' in context.bot_data and user_id_str in context.bot_data['effective_user_cache']:
         effective_user_obj = context.bot_data['effective_user_cache'][user_id_str]

    needs_save = False
    if user_id_str not in all_details:
        all_details[user_id_str] = user_data
        needs_save = True

    if effective_user_obj:
        current_username = effective_user_obj.username
        current_full_name = f"{effective_user_obj.first_name or ''} {effective_user_obj.last_name or ''}".strip()

        if user_data.get("telegram_username") != current_username:
            user_data["telegram_username"] = current_username
            needs_save = True
        if user_data.get("full_name") != current_full_name:
            user_data["full_name"] = current_full_name
            needs_save = True

        if needs_save:
            all_details[user_id_str] = user_data
            save_user_details(all_details)

    if update and update.effective_user:
        if 'effective_user_cache' not in context.bot_data:
            context.bot_data['effective_user_cache'] = {}
        context.bot_data['effective_user_cache'][str(update.effective_user.id)] = update.effective_user

    return user_data


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id_str = str(user.id)
    
    global bot_paused
    if bot_paused and user.id != admin_id:
        return

    await get_effective_user_details(user_id_str, update, context)

    banned_users = load_banned()
    if user_id_str in banned_users:
        await update.message.reply_text("You are banned and cannot use this bot.")
        return

    users_list_for_publish = load_users()
    if user_id_str not in users_list_for_publish:
        users_list_for_publish.add(user_id_str)
        save_users(users_list_for_publish)
    
    from roles import is_admin, is_operator
    
    if is_admin(user.id):
        admin_display_name = user.first_name
        if user.username:
            admin_display_name = f"{user.first_name} (@{user.username})" if user.first_name else f"@{user.username}"
        elif not user.first_name:
            admin_display_name = "Administrator"

        help_message_admin = f"{admin_display_name}, welcome!\n\nMain Commands:\n/ban <userid> - Ban a user.\n/unban <userid> - Unban a user.\n/publish (pin) - Start broadcasting a message to all subscribers.\n/cooldown <seconds> - Set anti-spam timer (0 to disable).\n/mode <group_id|off> - Set topic mode with a group or disable it.\n/whois <userid> - Get detailed information about a user.\n/pause - Temporarily disable bot for users (admin commands still work).\n/resume - Resume normal bot operation after pause.\n/update - Restart the bot (applies code changes).\n/off - Emergency shutdown (requires confirmation).\n/cancel - Cancel current multi-step operation.\n\nMessage Management:\n/pin - Pin a message (reply to message in a user topic).\n/unpin - Unpin a message (reply to message in a user topic).\n/delete - Delete a message from both admin and user chats.\n/reactions - Show reaction statistics for messages.\n\nDebugging:\n/debug on - Enable debug mode (forward all messages to you).\n/debug off - Disable debug mode.\n/debug <chat_id> - Forward all messages to specified chat.\n\nGeneral Commands (also available to users):\n/help - This help message.\n/start - Initial greeting/help.\n/subscribe - Subscribe to mass mailings.\n/unsubscribe - Unsubscribe from mass mailings.\n/hide - Toggle message delivery confirmations.\n\nAuthor: @yetazero"
        
        try:
            await update.message.reply_text(help_message_admin)
        except Exception as e:
            await update.message.reply_text(f"Error displaying help: {str(e)}")
    elif is_operator(user.id):
        operator_display_name = user.first_name
        if user.username:
            operator_display_name = f"{user.first_name} (@{user.username})" if user.first_name else f"@{user.username}"
        elif not user.first_name:
            operator_display_name = "Operator"
            
        help_message_operator = f"{operator_display_name}, welcome!\n\nOperator Commands:\n/ban <userid> - Ban a user.\n/unban <userid> - Unban a user.\n/cancel - Cancel pending messages.\n/pin - Pin message in user chat.\n/unpin - Unpin message.\n/delete - Delete a message from both topic and user chat.\n/reactions - View/manage message reactions.\n\nGeneral Commands:\n/help - This help message.\n/start - Initial greeting/help."
        
        try:
            await update.message.reply_text(help_message_operator)
        except Exception as e:
            await update.message.reply_text(f"Error displaying operator help: {str(e)}")
    else:
        user_help_text = "This is a feedback bot.\n\nAvailable commands:\n/help - This help message.\n/subscribe - Subscribe to mass mailings.\n/unsubscribe - Unsubscribe from mass mailings.\n/hide - Toggle message delivery confirmations.\n/reactions - View/manage message reactions."
        
        try:
            await update.message.reply_text(user_help_text)
        except Exception as e:
            await update.message.reply_text("Error displaying help. Available commands: /help, /subscribe, /unsubscribe, /hide.")


async def _get_target_user_id_from_context(update: Update, context: ContextTypes.DEFAULT_TYPE, expect_arg_after_id: bool = False):
    if not context.args or (expect_arg_after_id and len(context.args) == 1):
        if is_topic_mode_active() and \
           update.message.is_topic_message and \
           str(update.message.chat_id) == str(topic_mode_group_id) and update.message.message_thread_id:
            topic_user_id = get_user_id_by_topic_id(update.message.message_thread_id, str(topic_mode_group_id))
            return str(topic_user_id) if topic_user_id else None, True, None
        else:
            return None, False, None
    else:
        arg_value = str(context.args[0])
        remaining = context.args[1:] if len(context.args) > 1 else None
        return arg_value, True, remaining


async def whois_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from roles import is_admin
    if not is_admin(update.effective_user.id):
        return

    target_user_id, has_arg, _ = await _get_target_user_id_from_context(update, context)
    
    if not target_user_id:
        if update.message.reply_to_message:
            user_id, _, _ = get_user_message_for_admin_message(
                update.effective_chat.id, 
                update.message.reply_to_message.message_id
            )
            if user_id:
                target_user_id = user_id
                has_arg = True

    if target_user_id and has_arg:
        all_details = load_user_details()
        
        try:
            target_user_obj = None
            target_user_int_id = int(target_user_id)
            
            if 'effective_user_cache' in context.bot_data and str(target_user_id) in context.bot_data['effective_user_cache']:
                target_user_obj = context.bot_data['effective_user_cache'][str(target_user_id)]
            else:
                try:
                    chat = await context.bot.get_chat(target_user_int_id)
                    target_user_obj = chat
                except Exception as e:
                    print(f"Could not get user info for {target_user_id}: {e}")
                    pass
            
            user_info = get_user_info_string(target_user_id, all_details.get(str(target_user_id), {}), target_user_obj)
            
            user_photo = None
            if target_user_obj and hasattr(target_user_obj, 'photo') and target_user_obj.photo:
                try:
                    photos = await context.bot.get_user_profile_photos(target_user_int_id, limit=1)
                    if photos and photos.photos and len(photos.photos) > 0:
                        user_photo = photos.photos[0][-1]
                except Exception as e:
                    print(f"Error getting profile photo: {e}")
                    pass
            
            if user_photo:
                await update.message.reply_photo(
                    photo=user_photo.file_id,
                    caption=user_info,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(user_info, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            user_info = get_user_info_string(target_user_id, all_details.get(str(target_user_id), {}))
            await update.message.reply_text(f"{user_info}\n\n🔹 Error getting additional info: {str(e)}", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(
            "Use /whois <user_id> to get information about a user."
        )


async def forward_to_admin_or_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_paused, topic_mode_group_id, admin_id
    if bot_paused:
        return
        
    user = update.effective_user
    user_id_str = str(user.id)
    message = update.message

    from roles import has_role
    if has_role(user_id_str):
        return

    if user_id_str in load_banned(): return

    user_current_data = await get_effective_user_details(user_id_str, update, context)

    global current_cooldown_seconds
    if current_cooldown_seconds > 0:
        current_time = time.time()
        if user_id_str in user_last_message:
            time_diff = current_time - user_last_message[user_id_str]
            if time_diff < current_cooldown_seconds:
                remaining = round(current_cooldown_seconds - time_diff)
                try: await message.reply_text(f"Please wait {remaining} sec. before sending the next message.")
                except Exception as e: pass
                return
        user_last_message[user_id_str] = time.time()
        
    if is_topic_mode_active() and message.chat_id == topic_mode_group_id and message.message_thread_id:
        topic_id = message.message_thread_id
        
        topic_owner_id_str = get_user_id_by_topic_id(topic_id, str(topic_mode_group_id))
        
        if topic_owner_id_str and user_id_str != topic_owner_id_str:
            try:
                sender_name = user.first_name
                if user.last_name:
                    sender_name += f" {user.last_name}"
                if user.username:
                    sender_name = f"@{user.username} ({sender_name})"
                
                sent_msg = await context.bot.copy_message(
                    chat_id=int(topic_owner_id_str),
                    from_chat_id=message.chat_id,
                    message_id=message.message_id
                )
                
                await context.bot.send_message(
                    chat_id=int(topic_owner_id_str),
                    text=f"💬 Message from {sender_name} in your topic:",
                    reply_to_message_id=sent_msg.message_id
                )
                
                save_message_link(
                    user_id=int(topic_owner_id_str),
                    user_message_id=sent_msg.message_id,
                    admin_chat_id=message.chat_id,
                    admin_message_id=message.message_id,
                    is_from_user=False
                )
                
                return
            except Exception as e:
                print(f"Error relaying message to topic owner: {e}")

    bot_sent_message = None 

    if is_topic_mode_active():
        topic_id = None
        
        all_user_details = load_user_details()
        user_data = all_user_details.get(user_id_str, {})
        
        if user_data and "topic_id_in_group" in user_data:
            topic_id = user_data["topic_id_in_group"]
        
        if not topic_id:
            topic_title = "User " + user_id_str
            if user.username:
                topic_title = f"@{user.username}"
            if user.first_name:
                topic_title = user.first_name
                if user.last_name:
                    topic_title += f" {user.last_name}"
            
            try:
                new_topic = await context.bot.create_forum_topic(chat_id=topic_mode_group_id, name=topic_title)
                topic_id = new_topic.message_thread_id
                
                all_user_details = load_user_details()
                if user_id_str not in all_user_details:
                    all_user_details[user_id_str] = {}
                all_user_details[user_id_str]["topic_id_in_group"] = topic_id
                save_user_details(all_user_details)
            except Forbidden as e:
                await message.reply_text("Error: Bot does not have permission to create topics. Administrator needs to check bot permissions in the group.")
                await context.bot.send_message(admin_id, f"CRITICAL: Forbidden to create topic for User {user_id_str} (Name: {topic_title}) in group {topic_mode_group_id}. Check bot permissions (Manage Topics). Error: {e}")
                return
            except BadRequest as e:
                await message.reply_text("Error: Could not create communication channel. Perhaps the group is not a forum or another problem occurred. Inform the administrator.")
                await context.bot.send_message(admin_id, f"CRITICAL: BadRequest error creating topic for User {user_id_str} (Name: {topic_title}) in group {topic_mode_group_id}. Is this a forum? Error: {e}")
                return
            except Exception as e:
                await message.reply_text("Unexpected error creating communication channel. Please try again later.")
                await context.bot.send_message(admin_id, f"CRITICAL: Unexpected error creating topic for User {user_id_str} (Name: {topic_title}). Error: {e}")
                return
        
        try: 
            reply_info = ""
            replied_to_admin_message_id = None
            
            if message.reply_to_message:
                user_replied_to_msg_id = message.reply_to_message.message_id
                
                admin_chat_id, admin_msg_id, is_from_user = get_admin_message_for_user_message(
                    int(user_id_str), user_replied_to_msg_id
                )
                
                if admin_chat_id and admin_msg_id:
                    replied_to_admin_message_id = admin_msg_id
                    reply_info = f"\n\n[This is a reply to a message]"
                else:
                    reply_info = f"\n\n[User replied to their own message]"
            
            bot_sent_message = await context.bot.copy_message(
                chat_id=topic_mode_group_id,
                from_chat_id=message.chat_id,
                message_id=message.message_id,
                message_thread_id=topic_id,
                reply_to_message_id=replied_to_admin_message_id
            )
            
            if reply_info and not replied_to_admin_message_id:
                await context.bot.send_message(
                    chat_id=topic_mode_group_id,
                    message_thread_id=topic_id,
                    text=reply_info,
                    reply_to_message_id=bot_sent_message.message_id
                )
            
            save_message_link(
                user_id=int(user_id_str),
                user_message_id=message.message_id,
                admin_chat_id=topic_mode_group_id,
                admin_message_id=bot_sent_message.message_id,
                is_from_user=True
            )
            if message.dice:
                await context.bot.send_message(
                    chat_id=topic_mode_group_id,
                    message_thread_id=topic_id,
                    text=f"Dice Value: {message.dice.value}",
                    disable_notification=True
                )

            user_settings = get_user_data(user_id_str)
            if not (user_settings and user_settings.get("hide_delivery_notifications", False)):
                try:
                    await update.message.reply_text("Message has been delivered. /hide to hide system notifications.")
                except Exception as notify_e:
                    pass
        except BadRequest as e:
            await message.reply_text("Error with your designated topic. Please inform the administrator. Your message was not delivered to the topic.")
        except Forbidden as e:
            await message.reply_text("Error: Bot cannot send messages to your topic. Inform the administrator.")
        except Exception as e:
            await message.reply_text("An error occurred while sending your message.")
    
    else: 

        user_info_md = get_user_info_string(user_id_str, user_current_data, effective_user_obj=user) 
        header_text_for_admin = f"Message from:\n{user_info_md}"
        
        reply_info = ""
        if message.reply_to_message:
            user_replied_to_msg_id = message.reply_to_message.message_id
            
            admin_chat_id, admin_msg_id, is_from_user = get_admin_message_for_user_message(
                int(user_id_str), user_replied_to_msg_id
            )
            
            if admin_chat_id and admin_msg_id:
                reply_info = f"\n\n[This is a reply to an admin message]"
            else:
                reply_info = f"\n\n[User replied to their own message]"
        if reply_info:
            header_text_for_admin += reply_info
        
        if message.dice:
            header_text_for_admin += f"\n (Value: {message.dice.value})"
            try:
                await context.bot.send_message(
                    admin_id,
                    f"Dice Value from User {user_id_str}: {message.dice.value}",
                    disable_notification=True
                )
            except Exception as e:
                pass


        try:
            if message.text: 
                 bot_sent_message = await context.bot.send_message(
                     admin_id, 
                     f"{header_text_for_admin}\n\nContent:\n{message.text}", 
                     parse_mode=ParseMode.MARKDOWN
                 )
            else: 
                 copied_content_msg = await context.bot.copy_message(
                     admin_id, 
                     from_chat_id=message.chat_id, 
                     message_id=message.message_id
                 )
                 bot_sent_message = copied_content_msg 
                 
                 if header_text_for_admin: 
                     await context.bot.send_message(
                         admin_id, 
                         header_text_for_admin, 
                         parse_mode=ParseMode.MARKDOWN, 
                         reply_to_message_id=copied_content_msg.message_id,
                         disable_notification=True 
                     )
            
            user_settings = get_user_data(user_id_str)
            if not (user_settings and user_settings.get("hide_delivery_notifications", False)):
                try:
                    await update.message.reply_text("Message has been delivered. /hide to hide system notifications.")
                except Exception as notify_e:
                    pass

        except Exception as e:
            try:
                await message.reply_text("An error occurred while sending the message to the administrator.")
            except Exception as e_reply:
                 pass

    if bot_sent_message: 
        if 'message_mappings' not in context.bot_data:
            context.bot_data['message_mappings'] = {}
        
        save_message_link(
            user_id=int(user_id_str),
            user_message_id=message.message_id,
            admin_chat_id=admin_id,
            admin_message_id=bot_sent_message.message_id,
            is_from_user=True
        )


async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from roles import is_admin
    if not is_admin(update.effective_user.id):
        return

    message = update.message

    global publish_state
    if publish_state["active"] and publish_state["content"] is None and message:
        # Check if it's not a command
        is_command = False
        if message.text and message.text.startswith('/'):
            is_command = True
            
        if not is_command:
            publish_state["content"] = message
            
            # Create a preview based on message type
            preview = ""
            if message.text:
                text_preview = message.text[:100] + "..." if len(message.text) > 100 else message.text
                preview = f"Text: '{text_preview}'"
            elif message.photo:
                preview = "Photo with"
                if message.caption:
                    caption_preview = message.caption[:100] + "..." if len(message.caption) > 100 else message.caption
                    preview += f" caption: '{caption_preview}'"
                else:
                    preview += " no caption"
            elif message.video:
                preview = "Video"
            elif message.document:
                preview = f"Document: {message.document.file_name}"
            elif message.audio:
                preview = "Audio"
            elif message.voice:
                preview = "Voice message"
            elif message.sticker:
                preview = "Sticker"
            elif message.animation:
                preview = "Animation/GIF"
            else:
                preview = "Content (unspecified type)"
                
            await message.reply_text(f"Content received for publishing:\n{preview}\nUse /confirm to send or /cancel to abort.")
        return
    if message is None:
        return
        
    admin_user_id_str = str(update.effective_user.id)
    
    if bot_paused and message.text and not message.text.startswith('/'):
        await message.reply_text("Bot is paused. Regular messaging is disabled.\nUse /resume to enable all features.")
        return

    if hasattr(message, 'pinned_message') and message.pinned_message:
        pinned_msg = message.pinned_message
        target_user_id_str = None
        message_to_pin_id = None
        debug_info = []
        
        if is_topic_mode_active() and message and hasattr(message, 'chat_id') and message.chat_id and \
           message.chat_id == topic_mode_group_id and hasattr(message, 'is_topic_message') and message.is_topic_message and \
           hasattr(message, 'message_thread_id') and message.message_thread_id:
            from user_details import get_user_id_by_topic_id
            target_user_id_str = get_user_id_by_topic_id(message.message_thread_id, str(topic_mode_group_id))
            debug_info.append(f"Found user {target_user_id_str} from topic ID {message.message_thread_id}")
        
        pinned_by_admin = pinned_msg.from_user and pinned_msg.from_user.id == admin_id
        pinned_msg_info = f"ID: {pinned_msg.message_id}"
        if hasattr(pinned_msg, 'text') and pinned_msg.text:
            pinned_msg_text = pinned_msg.text
            if len(pinned_msg_text) > 30:
                pinned_msg_text = pinned_msg_text[:30] + "..."
            pinned_msg_info += f", Text: '{pinned_msg_text}'"
        debug_info.append(f"Pinned message sent by admin: {pinned_by_admin}, {pinned_msg_info}")
        
        user_id, user_msg_id, is_from_user = get_user_message_for_admin_message(
            pinned_msg.chat_id, pinned_msg.message_id
        )
        
        if user_id and not target_user_id_str:
            target_user_id_str = str(user_id)
            debug_info.append(f"Found user {target_user_id_str} from message mapping")
        
        if target_user_id_str:
            if user_msg_id:
                message_to_pin_id = user_msg_id
                debug_info.append(f"Using message ID {message_to_pin_id} for pinning from mapping")
                
                if is_from_user:
                    debug_info.append("This is a user message")
                else:
                    debug_info.append("This is an admin message")
            
            elif pinned_by_admin and is_topic_mode_active() and not message_to_pin_id:
                try:
                    target_user_int_id = int(target_user_id_str)
                    message_content = None
                    
                    debug_info.append(f"Trying to find pinned message directly: ID {pinned_msg.message_id}")
                    admin_key = f"{message.chat_id}:{pinned_msg.message_id}"
                    if admin_key in message_links:
                        info = message_links[admin_key]
                        user_id_from_key = info.get('user_id')
                        user_msg_id_from_key = info.get('user_message_id')
                        if user_id_from_key == target_user_int_id and user_msg_id_from_key:
                            message_to_pin_id = user_msg_id_from_key
                            is_from_user = info.get('is_from_user', False)
                            debug_info.append(f"Found direct mapping for pinned message: {message_to_pin_id} (from user: {is_from_user})")
                    
                    if not message_to_pin_id:
                        pinned_text = None
                        if hasattr(pinned_msg, 'text') and pinned_msg.text:
                            pinned_text = pinned_msg.text
                            debug_info.append(f"Using text matching for: '{pinned_text[:20]}...'")
                        
                        bot_messages = []
                        
                        for key, mapping in message_links.items():
                            if mapping.get('user_id') == target_user_int_id and \
                               mapping.get('user_message_id') and \
                               not mapping.get('is_from_user', True):
                                bot_messages.append((mapping.get('timestamp', 0), mapping.get('user_message_id')))
                        
                        debug_info.append(f"Found {len(bot_messages)} bot messages for this user")
                        
                        bot_messages.sort(reverse=True)
                        
                        if bot_messages:
                            message_to_pin_id = bot_messages[0][1]
                            debug_info.append(f"Found recent bot message to pin: {message_to_pin_id}")
                    
                    if hasattr(pinned_msg, 'text') and pinned_msg.text:
                        message_content = pinned_msg.text
                    
                    if not message_to_pin_id and message_content:
                        try:
                            sent_message = await context.bot.send_message(target_user_int_id, message_content)
                            message_to_pin_id = sent_message.message_id
                            debug_info.append(f"Sent new message to pin: {message_to_pin_id}")
                        except Exception as e:
                            debug_info.append(f"Error sending new message to pin: {e}")
                    
                    if not message_to_pin_id:
                        debug_info.append("Could not find or create message to pin")
                
                except Exception as e:
                    debug_info.append(f"Error finding message to pin: {e}")
            
            if message_to_pin_id:
                try:
                    target_user_int_id = int(target_user_id_str)
                    await context.bot.pin_chat_message(
                        chat_id=target_user_int_id,
                        message_id=message_to_pin_id,
                        disable_notification=False
                    )
                    await message.reply_text(f"🔹 Message pinned for user {target_user_id_str}. {' | '.join(debug_info)}", quote=False)
                except Exception as e:
                    await message.reply_text(f"🔹 Error pinning message for user {target_user_id_str}: {e}", quote=False)
            else:
                await message.reply_text(f"🔹 Could not find the original message to pin in the user's chat. Debug: {' | '.join(debug_info)}", quote=False)
        else:
            await message.reply_text("🔹 Could not determine which user to pin the message for.", quote=False)
        
        return

    if is_topic_mode_active() and message and hasattr(message, 'chat_id') and message.chat_id and \
       message.chat_id == topic_mode_group_id and hasattr(message, 'is_topic_message') and message.is_topic_message and \
       hasattr(message, 'message_thread_id') and message.message_thread_id:
        
        from user_details import get_user_id_by_topic_id
        target_user_id_str = get_user_id_by_topic_id(message.message_thread_id, str(topic_mode_group_id))
        if not target_user_id_str:
            await message.reply_text("🔹 Could not determine the user for this topic.", quote=True)
            return
        
        target_user_id = int(target_user_id_str)
        reply_to_user_message_id = None
        
        if message.reply_to_message and message.reply_to_message.from_user.is_bot: 
            if message.reply_to_message.text and ("Communication channel opened for" in message.reply_to_message.text):
                pass
            else:
                user_id, user_message_id, is_from_user = get_user_message_for_admin_message(
                    message.chat.id, message.reply_to_message.message_id
                )
                
                if user_id and user_message_id and user_id == target_user_id:
                    reply_to_user_message_id = user_message_id
        content_dict = message_to_telegram_dict(message)
        
        sent_message = await send_content_to_user(
            context.bot,
            target_user_id,
            content_dict,
            reply_to_message_id=reply_to_user_message_id,
            return_message=True
        )
        
        if sent_message:
            save_message_link(
                target_user_id,
                sent_message.message_id,
                message.chat_id,
                message.message_id,
                is_from_user=False
            )
            return
    
    if message.reply_to_message:
        user_id, user_message_id, is_from_user = get_user_message_for_admin_message(
            message.chat.id, message.reply_to_message.message_id
        )
        
        if user_id and user_message_id:
            content_dict = message_to_telegram_dict(message)
            
            sent_message = await send_content_to_user(
                context.bot,
                user_id,
                content_dict,
                reply_to_message_id=user_message_id if is_from_user else None,
                return_message=True
            )
            
            if sent_message:
                save_message_link(
                    user_id,
                    sent_message.message_id,
                    message.chat.id,
                    message.message_id,
                    is_from_user=False
                )
            return
    
    await message.reply_text("ℹ🔹 This message was not forwarded to any user. Reply to a user's message to communicate with them.")

async def send_content_to_user(bot, target_user_id, content_dict, reply_to_message_id=None, return_message=False):
    final_text = content_dict.get('text')
    final_caption = content_dict.get('caption')
    pm = ParseMode.MARKDOWN
    sent_message = None

    if content_dict.get("document"):
        sent_message = await bot.send_document(
            chat_id=target_user_id, 
            document=content_dict["document"], 
            caption=final_caption, 
            parse_mode=pm if final_caption else None, 
            reply_to_message_id=reply_to_message_id
        )
    elif content_dict.get("photo"):
        sent_message = await bot.send_photo(
            chat_id=target_user_id, 
            photo=content_dict["photo"], 
            caption=final_caption, 
            parse_mode=pm if final_caption else None, 
            reply_to_message_id=reply_to_message_id
        )
    elif content_dict.get("video"):
        sent_message = await bot.send_video(
            chat_id=target_user_id, 
            video=content_dict["video"], 
            caption=final_caption, 
            parse_mode=pm if final_caption else None, 
            reply_to_message_id=reply_to_message_id
        )
    elif content_dict.get("audio"):
        sent_message = await bot.send_audio(
            chat_id=target_user_id, 
            audio=content_dict["audio"], 
            caption=final_caption, 
            parse_mode=pm if final_caption else None, 
            reply_to_message_id=reply_to_message_id
        )
    elif content_dict.get("voice"):
        sent_message = await bot.send_voice(
            chat_id=target_user_id, 
            voice=content_dict["voice"], 
            caption=final_caption, 
            parse_mode=pm if final_caption else None, 
            reply_to_message_id=reply_to_message_id
        )
    elif content_dict.get("video_note"): 
        caption_msg = None
        if final_caption: 
            caption_msg = await bot.send_message(
                chat_id=target_user_id, 
                text=final_caption, 
                parse_mode=pm, 
                reply_to_message_id=reply_to_message_id
            )
            reply_to_message_id = caption_msg.message_id
            
        sent_message = await bot.send_video_note(
            chat_id=target_user_id, 
            video_note=content_dict["video_note"], 
            reply_to_message_id=reply_to_message_id
        )
    elif content_dict.get("sticker"):
        caption_msg = None
        if final_caption: 
            caption_msg = await bot.send_message(
                chat_id=target_user_id, 
                text=final_caption, 
                parse_mode=pm, 
                reply_to_message_id=reply_to_message_id
            )
            reply_to_message_id = caption_msg.message_id
            
        sent_message = await bot.send_sticker(
            chat_id=target_user_id, 
            sticker=content_dict["sticker"], 
            reply_to_message_id=reply_to_message_id
        )
    elif content_dict.get("dice"):
        caption_msg = None
        if final_caption: 
            caption_msg = await bot.send_message(
                chat_id=target_user_id, 
                text=final_caption, 
                parse_mode=pm, 
                reply_to_message_id=reply_to_message_id
            )
            reply_to_message_id = caption_msg.message_id
            
        sent_message = await bot.send_dice(
            chat_id=target_user_id, 
            emoji=content_dict.get("dice", "🎲"), 
            reply_to_message_id=reply_to_message_id
        )
    elif content_dict.get("location"):
        caption_msg = None
        if final_caption: 
            caption_msg = await bot.send_message(
                chat_id=target_user_id, 
                text=final_caption, 
                parse_mode=pm, 
                reply_to_message_id=reply_to_message_id
            )
            reply_to_message_id = caption_msg.message_id
            
        sent_message = await bot.send_location(
            chat_id=target_user_id, 
            latitude=content_dict["location"]["latitude"], 
            longitude=content_dict["location"]["longitude"], 
            reply_to_message_id=reply_to_message_id
        )
    elif content_dict.get("contact"):
        caption_msg = None
        if final_caption: 
            caption_msg = await bot.send_message(
                chat_id=target_user_id, 
                text=final_caption, 
                parse_mode=pm, 
                reply_to_message_id=reply_to_message_id
            )
            reply_to_message_id = caption_msg.message_id
            
        sent_message = await bot.send_contact(
            chat_id=target_user_id, 
            phone_number=content_dict["contact"]["phone_number"], 
            first_name=content_dict["contact"]["first_name"], 
            last_name=content_dict["contact"].get("last_name", ""), 
            reply_to_message_id=reply_to_message_id
        )
    elif final_text:
        is_media_already_sent = False
        if final_caption: 
            is_media_already_sent = True
        if not is_media_already_sent: 
            sent_message = await bot.send_message(
                chat_id=target_user_id, 
                text=final_text, 
                parse_mode=pm, 
                reply_to_message_id=reply_to_message_id
            )
    elif final_caption and not any(content_dict.get(k) for k in ["document", "photo", "video", "audio", "voice", "video_note", "sticker", "dice", "location", "contact", "poll"]):
        sent_message = await bot.send_message(
            chat_id=target_user_id, 
            text=final_caption, 
            parse_mode=pm
        )
    
    if return_message:
        return sent_message


async def process_publishing(message, bot, content_to_broadcast_msg_obj: Message):
    sent_count = 0
    failed_count = 0
    pin_count = 0
    pin_failed = 0
    should_pin = publish_state.get("pin", False)
    pin_message_ids = {}
    
    users_to_publish = load_users()
    banned = load_banned()

    attempt_users_list = [uid for uid in users_to_publish if uid not in banned]
    total_users_to_try = len(attempt_users_list)

    if not content_to_broadcast_msg_obj:
        await message.reply_text("Error: No content found to publish. Please try /publish again.")
        publish_state["active"] = False
        publish_state["content"] = None
        publish_state["pin"] = False
        return

    if total_users_to_try == 0:
        await message.reply_text("No users to publish to (all subscribed users are banned or list is empty).")
        publish_state["active"] = False
        publish_state["content"] = None
        publish_state["pin"] = False
        return

    pin_text = " with PIN" if should_pin else ""
    status_msg = await message.reply_text(f"Publishing{pin_text} to {total_users_to_try} users...")
    processed_count = 0
    
    from_chat_id_for_copy = content_to_broadcast_msg_obj.chat.id
    message_id_for_copy = content_to_broadcast_msg_obj.message_id

    for user_id_str in attempt_users_list:
        processed_count += 1
        try:
            sent_message = await bot.copy_message(
                chat_id=int(user_id_str),
                from_chat_id=from_chat_id_for_copy,
                message_id=message_id_for_copy
            )
            sent_count += 1
            
            if should_pin and sent_message:
                pin_message_ids[user_id_str] = sent_message.message_id
                
        except Forbidden:
            failed_count += 1
        except BadRequest as e: 
            failed_count += 1
        except Exception as e:
            failed_count += 1

        if processed_count % 10 == 0 or processed_count == total_users_to_try: 
            try:
                await status_msg.edit_text(f"Publishing{pin_text}: {processed_count}/{total_users_to_try} processed, {sent_count} sent, {failed_count} errors...")
            except BadRequest:
                pass
        await asyncio.sleep(0.1)
    
    if should_pin and pin_message_ids:
        await status_msg.edit_text(f"Publishing complete. Now pinning messages for {len(pin_message_ids)} users...")
        
        for user_id_str, msg_id in pin_message_ids.items():
            try:
                await bot.pin_chat_message(
                    chat_id=int(user_id_str),
                    message_id=msg_id,
                    disable_notification=False
                )
                pin_count += 1
                _last_pinned_messages[int(user_id_str)] = {
                    'message_id': msg_id,
                    'timestamp': time.time()
                }
            except Exception:
                pin_failed += 1
            await asyncio.sleep(0.1)
    
    status_text = f"Publishing complete: {sent_count} successfully sent, {failed_count} errors out of {total_users_to_try} attempted users."
    if should_pin:
        status_text += f" PIN results: {pin_count} pinned, {pin_failed} failed to pin."
        
    try:
        await status_msg.edit_text(status_text)
    except BadRequest:
        await message.reply_text(status_text)
        
    publish_state["active"] = False
    publish_state["content"] = None
    publish_state["pin"] = False


async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from roles import is_admin, is_operator
    if not is_admin(update.effective_user.id) and not is_operator(update.effective_user.id): return

    target_user_id, has_arg, _ = await _get_target_user_id_from_context(update, context, expect_arg_after_id=False)

    if not target_user_id:
        await update.message.reply_text("Usage: /ban <userid>\nOr, in a user's topic: /ban")
        return
    
    target_user_id_str = str(target_user_id)
    if not target_user_id_str.isdigit():
         await update.message.reply_text("Invalid User ID specified.")
         return

    try:
        banned_users = load_banned()
        if target_user_id_str in banned_users:
            await update.message.reply_text(f"User {target_user_id_str} is already banned."); return

        banned_users.add(target_user_id_str); save_banned(banned_users)
        users_list = load_users();
        if target_user_id_str in users_list: 
            users_list.remove(target_user_id_str); save_users(users_list)

        await update.message.reply_text(
            f"User {target_user_id_str} banned and removed from subscriptions. "
        )
    except Exception as e:
        await update.message.reply_text(f"An error occurred while trying to ban user {target_user_id_str}.")


async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from roles import is_admin, is_operator
    if not is_admin(update.effective_user.id) and not is_operator(update.effective_user.id): return

    target_user_id, has_arg, _ = await _get_target_user_id_from_context(update, context, expect_arg_after_id=False)

    if not target_user_id:
        await update.message.reply_text("Usage: /unban <userid>\nOr, in a user's topic: /unban")
        return
    
    target_user_id_str = str(target_user_id)
    if not target_user_id_str.isdigit():
         await update.message.reply_text("Invalid User ID specified.")
         return

    try:
        banned_users = load_banned()
        if target_user_id_str not in banned_users:
            await update.message.reply_text(f"User {target_user_id_str} is not banned."); return

        banned_users.remove(target_user_id_str); save_banned(banned_users)
        await update.message.reply_text(f"User {target_user_id_str} unbanned.")
    except Exception as e:
        await update.message.reply_text(f"An error occurred while trying to unban user {target_user_id_str}.")


async def set_cooldown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from roles import is_admin
    if not is_admin(update.effective_user.id): return
    global current_cooldown_seconds, config_mngr
    if not context.args or len(context.args) != 1:
        await update.message.reply_text("Usage: /cooldown <seconds>")
        return
    try:
        new_cooldown = int(context.args[0])
        if new_cooldown < 0: await update.message.reply_text("Cooldown must be >= 0."); return
        current_cooldown_seconds = new_cooldown
        config_mngr.set_config('cooldown', str(new_cooldown))
        config_mngr.save_config()
        await update.message.reply_text(f"Anti-spam cooldown set to {new_cooldown} sec.")
    except ValueError:
        await update.message.reply_text("Invalid number for seconds. Usage: /cooldown <seconds>")


async def cancel_sending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from roles import is_admin, is_operator
    if not is_admin(update.effective_user.id) and not is_operator(update.effective_user.id): return

    admin_user_id_str = str(update.effective_user.id)
    cancelled_something = False

    if admin_user_id_str in send_states:
        del send_states[admin_user_id_str]
        cancelled_something = True

    if publish_state["active"]:
        publish_state["active"] = False
        publish_state["content"] = None
        cancelled_something = True

    if 'confirm_topic_group' in context.chat_data: 
        del context.chat_data['confirm_topic_group']
        cancelled_something = True

    if cancelled_something:
        await update.message.reply_text("Operation cancelled.")
    else:
        await update.message.reply_text("Nothing to cancel.")


async def start_publish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from roles import is_admin
    if not is_admin(update.effective_user.id): return
    publish_state["active"] = True
    publish_state["content"] = None
    publish_state["pin"] = False
    
    if context.args and len(context.args) > 0 and context.args[0].lower() == "pin":
        publish_state["pin"] = True
        await update.message.reply_text("Send content for mass mailing with PIN, or /cancel.")
    else:
        await update.message.reply_text("Send content for mass mailing, or /cancel.")


async def confirm_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from roles import is_admin
    if not is_admin(update.effective_user.id): return
    if publish_state["active"] and publish_state["content"]:
        await process_publishing(update.message, context.bot, publish_state["content"])
    else:
        await update.message.reply_text("Nothing to confirm for publishing.")


async def subscribe_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id_str = str(user.id)
    
    global bot_paused
    if bot_paused and user.id != admin_id:
        return
    
    if user_id_str in load_banned(): 
        await update.message.reply_text("You are banned and cannot subscribe."); return
    users = load_users()
    if user_id_str not in users:
        users.add(user_id_str); save_users(users)
        await update.message.reply_text("You have successfully subscribed to mass mailings!")
    else:
        await update.message.reply_text("You are already subscribed.")
    await get_effective_user_details(user_id_str, update, context)


async def unsubscribe_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id_str = str(user.id)
    
    global bot_paused
    if bot_paused and user.id != admin_id:
        return
    
    users = load_users()
    if user_id_str in users:
        users.remove(user_id_str); save_users(users)
        await update.message.reply_text("You have unsubscribed from mass mailings.")
    else:
        await update.message.reply_text("You were not subscribed.")


async def hide_notifications_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id_str = str(user.id)
    
    global bot_paused
    if bot_paused and user.id != admin_id:
        return
    
    user_data = get_user_data(user_id_str) 
    if user_data is None: 
        user_data = {} 

    current_preference = user_data.get("hide_delivery_notifications", False)
    new_preference = not current_preference 

    update_user_data_field(user_id_str, "hide_delivery_notifications", new_preference)

    if new_preference:
        await update.message.reply_text("Message delivery notifications are now hidden.")
    else:
        await update.message.reply_text("Message delivery notifications are now shown.")


async def mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from roles import is_admin
    if not is_admin(update.effective_user.id):
        return
        
    if not context.args or len(context.args) != 1:
        current_mode = "Topic Mode" if is_topic_mode_active() else "Direct Mode"
        await update.message.reply_text(f"Current mode: {current_mode}\nUsage: /mode <group_id> to set topic mode with a group, or /mode off to disable topic mode.")
        return
        
    mode_arg = context.args[0].lower()
    
    if mode_arg == "off" or mode_arg == "disable" or mode_arg == "direct":
        try:
            config_mngr.set_config('topic_mode_group_id', '')
            config_mngr.save_config()
            
            global topic_mode_group_id
            topic_mode_group_id = None
            
            await update.message.reply_text("Topic mode disabled. Bot will now restart in direct message mode.")
            
            import subprocess
            
            stop_telegram_bot_event.set()
            
            import threading
            import time
            
            def restart_process():
                time.sleep(2)
                
                script_path = sys.argv[0]
                args = [sys.executable, script_path]
                
                print(f"Restarting application with args: {args}")
                
                process = subprocess.Popen(args)
                print(f"New process started with PID: {process.pid}")
                
                print("Exiting current process for mode change")
                os._exit(0)
            
            threading.Thread(target=restart_process, daemon=True).start()
            
        except Exception as e:
            await update.message.reply_text(f"Error during mode change: {str(e)}")
            
        return
    
    try:
        group_id = int(mode_arg)
        config_mngr.set_config('topic_mode_group_id', str(group_id))
        config_mngr.save_config()
        await update.message.reply_text(f"Topic mode enabled with group ID: {group_id}. Bot will restart now.")
        
        with open("restart_flag.txt", "w") as f:
            f.write("tray")
            f.flush()
        
        import subprocess
        
        stop_telegram_bot_event.set()
        
        import threading
        import time
        
        def restart_process():
            time.sleep(2)
            
            script_path = sys.argv[0]
            args = [sys.executable, script_path]
            args.append("--start-in-tray")
            
            print(f"Restarting application with args: {args}")
            
            process = subprocess.Popen(args)
            print(f"New process started with PID: {process.pid}")
            
            print("Exiting current process for mode change")
            os._exit(0)
        
        threading.Thread(target=restart_process, daemon=True).start()
    except ValueError:
        await update.message.reply_text("Invalid group ID. Please provide a numeric ID.")


def is_topic_mode_active():
    return topic_mode_group_id is not None


async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _restart_in_progress, _restart_lock

    from roles import is_admin
    if not is_admin(update.effective_user.id):
        return
        
    with _restart_lock:
        if _restart_in_progress:
            await update.message.reply_text("🔹 Restart already in progress. Please wait...")
            return
        _restart_in_progress = True
    
    await update.message.reply_text("Reloading bot, please wait...")
    
    try:
        import psutil
        import subprocess
        import time
        
        current_pid = os.getpid()
        current_process = psutil.Process(current_pid)
        current_cmd = ' '.join(current_process.cmdline())
        
        with open("restart_flag.txt", "w") as f:
            mode = "tray" if is_topic_mode_active() else "normal"
            f.write(mode)
            f.flush()
        
        stop_telegram_bot_event.set()
        
        def restart_process():
            try:
                time.sleep(2)
                
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        if proc.info['pid'] == current_pid:
                            continue
                            
                        if proc.info['cmdline'] and len(proc.info['cmdline']) > 1:
                            proc_cmd = ' '.join(proc.info['cmdline'])
                            
                            script_path = sys.argv[0]
                            if script_path in proc_cmd and proc_cmd != current_cmd:
                                print(f"Found another instance with PID {proc.info['pid']}, terminating it")
                                try:
                                    proc_obj = psutil.Process(proc.info['pid'])
                                    proc_obj.terminate()
                                    proc_obj.wait(timeout=3)
                                except Exception as e:
                                    print(f"Error terminating process {proc.info['pid']}: {e}")
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
                
                try:
                    if 'app_instance' in globals() and app_instance and hasattr(app_instance, 'tray_icon') and app_instance.tray_icon:
                        app_instance.tray_icon.stop()
                        app_instance.tray_icon = None
                except Exception as e:
                    print(f"Error closing tray icon: {e}")
                
                script_path = sys.argv[0]
                args = [sys.executable, script_path]
                
                if is_topic_mode_active():
                    args.append("--start-in-tray")
                
                print(f"Restarting application with args: {args}")
                
                process = subprocess.Popen(args)
                print(f"New process started with PID: {process.pid}")
                
                try:
                    import tkinter as tk
                    if tk._default_root:
                        for widget in tk._default_root.winfo_children():
                            widget.destroy()
                        tk._default_root.destroy()
                except Exception as e:
                    print(f"Error closing GUI: {e}")
                
                try:
                    try:
                        for sock in socket._active:
                            try:
                                sock.close()
                            except:
                                pass
                    except AttributeError:
                        for obj in gc.get_objects():
                            if isinstance(obj, socket.socket):
                                try:
                                    obj.close()
                                except:
                                    pass
                except Exception as e:
                    print(f"Error closing sockets: {e}")
                
                try:
                    for obj in gc.get_objects():
                        if isinstance(obj, io.IOBase) and not obj.closed:
                            try:
                                obj.close()
                            except:
                                pass
                except Exception as e:
                    print(f"Error closing file handles: {e}")
                
                for thread in threading.enumerate():
                    if thread != threading.current_thread() and not thread.daemon:
                        try:
                            thread.join(0.2)
                        except Exception as e:
                            print(f"Error joining thread {thread.name}: {e}")
                
                print("Exiting current process for update")
                time.sleep(1.5)
                os._exit(0)
            except Exception as e:
                print(f"Error in restart process: {e}")
                global _restart_in_progress
                with _restart_lock:
                    _restart_in_progress = False
        
        threading.Thread(target=restart_process, daemon=True).start()
        
    except Exception as e:
        with _restart_lock:
            _restart_in_progress = False
        await update.message.reply_text(f"Error during restart: {str(e)}")


async def off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from roles import is_admin
    if not is_admin(update.effective_user.id):
        return
    
    global off_command_confirmation_code
    
    if not context.args or len(context.args) != 1:
        import random
        off_command_confirmation_code = str(random.randint(100000, 999999))
        
        await update.message.reply_text(
            f"🔹 *EMERGENCY SHUTDOWN* 🔹\n\n" 
            f"This will completely terminate the bot and application.\n" 
            f"You will need to restart it manually.\n\n" 
            f"To confirm, reply with:\n/off {off_command_confirmation_code}",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        confirmation_code = context.args[0]
        if confirmation_code == off_command_confirmation_code:
            await update.message.reply_text("Emergency shutdown initiated. Goodbye!")
            
            import threading
            import time
            import psutil
            
            def terminate_completely():
                time.sleep(2)
                print("Emergency shutdown initiated by admin")
                
                current_pid = os.getpid()
                current_process = psutil.Process(current_pid)
                
                try:
                    if 'app_instance' in globals() and app_instance and hasattr(app_instance, 'tray_icon') and app_instance.tray_icon:
                        app_instance.tray_icon.stop()
                        app_instance.tray_icon = None
                except Exception as e:
                    print(f"Error closing tray icon: {e}")
                
                try:
                    import tkinter as tk
                    for widget in tk._default_root.winfo_children():
                        widget.destroy()
                    tk._default_root.destroy()
                except Exception as e:
                    print(f"Error closing GUI: {e}")
                
                for thread in threading.enumerate():
                    if thread != threading.current_thread() and not thread.daemon:
                        try:
                            thread.join(0.1)
                        except Exception as e:
                            print(f"Error joining thread {thread.name}: {e}")
                
                import os
                os._exit(0)
                
            stop_telegram_bot_event.set()
            threading.Thread(target=terminate_completely, daemon=True).start()
        else:
            await update.message.reply_text("Invalid confirmation code. Please try again.")


async def pause_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_paused
    
    from roles import is_admin
    if not is_admin(update.effective_user.id):
        return
    
    if bot_paused:
        await update.message.reply_text("Bot is already paused.")
        return
        
    bot_paused = True
    await update.message.reply_text("🔹 Bot paused. All user commands and messages will be ignored. \nAdmin commands will still work, but regular messaging is disabled.\nTo resume operation, use /resume command.")


async def resume_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_paused
    
    from roles import is_admin
    if not is_admin(update.effective_user.id):
        return
    
    if not bot_paused:
        await update.message.reply_text("Bot is already running in normal mode.")
        return
        
    bot_paused = False
    await update.message.reply_text("🔹 Bot operation resumed. All features are now available again.")


async def run_telegram_bot(token: str, admin_id_param: int, initial_cooldown: int, config_manager_instance: ConfigManager):

    global admin_id, current_cooldown_seconds, topic_mode_group_id, config_mngr
    
    admin_id = admin_id_param
    current_cooldown_seconds = initial_cooldown
    config_mngr = config_manager_instance

    reactions.initialize(message_links)
    message_edit_handler.initialize(message_links)
    pins.initialize(message_links, sys.modules[__name__])
    debug.initialize_debug(message_links, config_manager_instance)

    topic_mode_group_id_str = config_mngr.get_config('topic_mode_group_id')
    if topic_mode_group_id_str and topic_mode_group_id_str.lstrip('-').isdigit(): 
        topic_mode_group_id = int(topic_mode_group_id_str)

    else:
        topic_mode_group_id = None
        if topic_mode_group_id_str: 
            config_mngr.set_config('topic_mode_group_id', '') 
            config_mngr.save_config()

    app = Application.builder().token(token).build()

    if 'user_to_bot_message_map' not in app.bot_data:
        app.bot_data['user_to_bot_message_map'] = {}
    if 'bot_to_user_message_map' not in app.bot_data:
        app.bot_data['bot_to_user_message_map'] = {}
    if 'effective_user_cache' not in app.bot_data: 
        app.bot_data['effective_user_cache'] = {}
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("h", start))
    app.add_handler(CommandHandler(["ban", "b"], ban_user))
    app.add_handler(CommandHandler(["unban", "u"], unban_user))
    app.add_handler(CommandHandler(["publish", "p"], start_publish))
    app.add_handler(CommandHandler("cooldown", set_cooldown))
    app.add_handler(CommandHandler(["cancel", "c"], cancel_sending))
    app.add_handler(CommandHandler("confirm", confirm_command))
    app.add_handler(CommandHandler("mode", mode_command))
    app.add_handler(CommandHandler("whois", whois_command))

    app.add_handler(CommandHandler(["update", "reload", "r"], update_command))

    app.add_handler(CommandHandler("off", off_command))
    
    app.add_handler(CommandHandler("pause", pause_bot))
    app.add_handler(CommandHandler("resume", resume_bot))

    app.add_handler(CommandHandler(["subscribe", "sub"], subscribe_user))
    app.add_handler(CommandHandler(["unsubscribe", "unsub"], unsubscribe_user))
    app.add_handler(CommandHandler("hide", hide_notifications_command))

    from role_commands import register_handlers as register_role_handlers
    register_role_handlers(app)
    
    reactions.register_handlers(app, admin_id)
    
    message_edit_handler.register_handlers(app)
    pins.register_handlers(app)
    
    debug.register_debug_handlers(app)
    
    import bot_logging
    bot_logging.initialize_logging(app)
    
    delete_handler.initialize(message_links, sys.modules[__name__])
    delete_handler.register_handlers(app)
    
    import operator_handler
    operator_handler.initialize(message_links, sys.modules[__name__])
    
    from roles import get_all_admins, get_all_operators, is_admin, is_operator, ensure_main_admin
    
    ensure_main_admin(admin_id)
    
    all_admins = [int(admin_id) for admin_id in get_all_admins()]
    all_operators = [int(op_id) for op_id in get_all_operators()]
    
    admin_filter = filters.User(all_admins) & ~filters.COMMAND & ~filters.StatusUpdate.ALL
    app.add_handler(MessageHandler(admin_filter | filters.StatusUpdate.PINNED_MESSAGE, handle_admin_message))
    
    operator_filter = filters.User(all_operators) & ~filters.COMMAND & ~filters.StatusUpdate.ALL
    app.add_handler(MessageHandler(operator_filter, operator_handler.handle_operator_message))
    
    all_role_users = all_admins + all_operators
    user_filter = ~filters.User(all_role_users) & ~filters.COMMAND & ~filters.StatusUpdate.ALL
    app.add_handler(MessageHandler(user_filter, forward_to_admin_or_topic))
    
    try:
        await app.initialize()
        await app.start()

        user_commands = [
            BotCommand("start", "Start the bot / Show help"),
            BotCommand("help", "Show help message"),
            BotCommand("whois", "Get user information"),
            BotCommand("subscribe", "Subscribe to updates"),
            BotCommand("unsubscribe", "Unsubscribe from updates"),
            BotCommand("hide", "Hide notifications"),
            BotCommand("reactions", "View/manage message reactions"),
            BotCommand("clear_reaction", "Clear reaction on a message"),
        ]
        await app.bot.set_my_commands(user_commands)

        await app.updater.start_polling(drop_pending_updates=True, allowed_updates=["message", "edited_message", "message_reaction"])

        while not stop_telegram_bot_event.is_set(): 
            await asyncio.sleep(1)

    except Exception as e:
        print(f"CRITICAL ERROR in run_telegram_bot: {e}")
        import traceback
        traceback.print_exc()
    finally: 
        if hasattr(app, 'updater') and app.updater and app.updater.running:
            await app.updater.stop() 
        if hasattr(app, 'running') and app.running: 
            await app.stop()
