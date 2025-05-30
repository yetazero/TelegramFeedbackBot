import asyncio
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden

REACTION_COMMANDS = {
    "fire": "🔥",
    "zap": "⚡",
    "like": "👍",
    "dislike": "👎",
}

message_links = None

def initialize(core_message_links):
    global message_links
    message_links = core_message_links

def find_linked_message_for_reaction(chat_id, message_id):
    if not message_links:
        return None, None
        
    key1 = f"{chat_id}:{message_id}"
    if key1 in message_links:
        info = message_links[key1]
        if info.get('user_id') and info.get('user_message_id'):
            return info.get('user_id'), info.get('user_message_id')
        if info.get('admin_chat_id') and info.get('admin_message_id'):
            return info.get('admin_chat_id'), info.get('admin_message_id')
    
    for k, v in message_links.items():
        key_user = f"{v.get('user_id')}:{v.get('user_message_id')}"
        key_admin = f"{v.get('admin_chat_id')}:{v.get('admin_message_id')}"
        if key_user == key1:
            return v.get('admin_chat_id'), v.get('admin_message_id')
        if key_admin == key1:
            return v.get('user_id'), v.get('user_message_id')
    
    for k, v in message_links.items():
        if v.get('admin_chat_id') == chat_id and v.get('admin_message_id') == message_id:
            return v.get('user_id'), v.get('user_message_id')
        if v.get('user_id') == chat_id and v.get('user_message_id') == message_id:
            return v.get('admin_chat_id'), v.get('admin_message_id')
    
    return None, None


async def reaction_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.reply_to_message:
        await update.message.reply_text("Reply with a reaction command to the message you want to mark.")
        return
    
    cmd = update.message.text.split()[0].lstrip("/").lower()
    
    if cmd == "zap":
        from roles import is_admin
        if not is_admin(update.effective_user.id):
            return 
    
    emoji = REACTION_COMMANDS.get(cmd)
    
    if not emoji:
        return

    target_chat_id = update.message.reply_to_message.chat_id
    target_message_id = update.message.reply_to_message.message_id
    
    try:
        await context.bot.set_message_reaction(
            chat_id=target_chat_id,
            message_id=target_message_id,
            reaction=[emoji]
        )
    except Exception as e:
        print(f"Error: Failed to set {emoji} reaction on message {target_chat_id}:{target_message_id}. Details: {e}")
        return
    
    linked_chat_id, linked_message_id = find_linked_message_for_reaction(target_chat_id, target_message_id)
    if linked_chat_id and linked_message_id:
        try:
            await context.bot.set_message_reaction(
                chat_id=linked_chat_id,
                message_id=linked_message_id,
                reaction=[emoji]
            )
        except Exception as e:
            print(f"Error: Failed to set {emoji} reaction on linked message {linked_chat_id}:{linked_message_id}. Details: {e}")


async def reactions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
            
    from roles import is_admin
    
    if is_admin(user_id):
        reactions_list_text = "/fire — 🔥\n/like — 👍\n/dislike — 👎\n/zap — ⚡\n/clear_reaction - Clear reaction on a message."
    else:
        reactions_list_text = "/fire — 🔥\n/like — 👍\n/dislike — 👎\n/clear_reaction - Clear reaction on a message."
    
    message_text = f"Available reactions (reply to a message to use them):\n{reactions_list_text}"
        
    await update.message.reply_text(
        message_text,
        parse_mode=ParseMode.HTML 
    )

async def clear_reaction_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.reply_to_message:
        await update.message.reply_text("Reply with /clear_reaction to the message you want to clear reactions from.")
        return

    target_chat_id = update.message.reply_to_message.chat_id
    target_message_id = update.message.reply_to_message.message_id
    
    # All users can clear reactions with this command
    # from roles import is_admin
    # if not is_admin(update.effective_user.id):
    #     await update.message.reply_text("You don't have permission to clear reactions.")
    #     return

    original_cleared_successfully = False
    try:
        await context.bot.set_message_reaction(
            chat_id=target_chat_id,
            message_id=target_message_id,
            reaction=[] 
        )
        original_cleared_successfully = True
    except Forbidden:
        await update.message.reply_text("Error: Bot lacks permission to change reactions in the original chat.")
        return
    except BadRequest as e:
        error_message = str(e).lower()
        if "message to react not found" in error_message or \
           "message can't be reacted" in error_message or \
           "message is too old" in error_message:
            await update.message.reply_text("Could not clear reactions. The message might be too old, already cleared, or doesn't support reactions.")
        else:
            print(f"BadRequest clearing reaction (original {target_chat_id}:{target_message_id}): {e}")
            await update.message.reply_text(f"Failed to clear reactions from original message: An API error occurred.")
        return 
    except Exception as e:
        print(f"Unexpected error clearing reaction (original {target_chat_id}:{target_message_id}): {e}")
        await update.message.reply_text("An unexpected error occurred while clearing reactions from the original message.")
        return 

    linked_chat_id, linked_message_id = find_linked_message_for_reaction(target_chat_id, target_message_id)
    linked_cleared_successfully = False
    linked_message_error_info = ""

    if linked_chat_id and linked_message_id:
        try:
            await context.bot.set_message_reaction(
                chat_id=linked_chat_id,
                message_id=linked_message_id,
                reaction=[]
            )
            linked_cleared_successfully = True
        except Exception as e:
            print(f"Error clearing reaction (linked {linked_chat_id}:{linked_message_id}): {e}")
            linked_message_error_info = " Could not clear from linked message (see logs)."
    
    final_message = "Reactions cleared from the replied message."
    if linked_chat_id and linked_message_id:
        if linked_cleared_successfully:
            final_message += " Also cleared from the linked message."
        else:
            final_message += linked_message_error_info
            
    await update.message.reply_text(final_message)


def register_handlers(app, admin_id):
    for cmd in REACTION_COMMANDS.keys():
        app.add_handler(CommandHandler(cmd, reaction_command))
    
    app.add_handler(CommandHandler("reactions", reactions_command))
    app.add_handler(CommandHandler("clear_reaction", clear_reaction_command))
