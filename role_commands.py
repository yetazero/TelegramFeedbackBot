from telegram import Update
from telegram.ext import ContextTypes
from roles import (
    add_admin, remove_admin,
    add_operator, remove_operator,
    is_admin, is_operator,
    get_all_admins, get_all_operators
)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender_id = update.effective_user.id
    
    if not is_admin(sender_id):
        return
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "🔹 Usage: /admin add <user_id> or /admin remove <user_id>",
            message_thread_id=getattr(update.message, 'message_thread_id', None)
        )
        return
    
    action = context.args[0].lower()
    try:
        target_user_id = int(context.args[1])
    except ValueError:
        await update.message.reply_text(
            "🔹 Invalid user ID format. It must be a number.",
            message_thread_id=getattr(update.message, 'message_thread_id', None)
        )
        return
    
    if action == "add":
        if add_admin(target_user_id):
            await update.message.reply_text(
                f"🔹 User {target_user_id} has been successfully added as an administrator.",
                message_thread_id=getattr(update.message, 'message_thread_id', None)
            )
        else:
            await update.message.reply_text(
                f"🔹 User {target_user_id} is already an administrator.",
                message_thread_id=getattr(update.message, 'message_thread_id', None)
            )
    
    elif action == "remove":
        if remove_admin(target_user_id):
            await update.message.reply_text(
                f"🔹 User {target_user_id} has been successfully removed from administrators.",
                message_thread_id=getattr(update.message, 'message_thread_id', None)
            )
        else:
            await update.message.reply_text(
                f"🔹 User {target_user_id} is not an administrator.",
                message_thread_id=getattr(update.message, 'message_thread_id', None)
            )
    
    elif action == "list":
        admins = get_all_admins()
        if admins:
            admins_list = ", ".join(admins)
            await update.message.reply_text(
                f"🔹 List of administrators:\n{admins_list}",
                message_thread_id=getattr(update.message, 'message_thread_id', None)
            )
        else:
            await update.message.reply_text(
                "🔹 The list of administrators is empty.",
                message_thread_id=getattr(update.message, 'message_thread_id', None)
            )
    
    else:
        await update.message.reply_text(
            "🔹 Invalid action. Use add, remove or list.",
            message_thread_id=getattr(update.message, 'message_thread_id', None)
        )

async def operator_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender_id = update.effective_user.id
    
    if not is_admin(sender_id):
        return
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "🔹 Usage: /operator add <user_id> or /operator remove <user_id>",
            message_thread_id=getattr(update.message, 'message_thread_id', None)
        )
        return
    
    action = context.args[0].lower()
    
    try:
        target_user_id = int(context.args[1])
    except ValueError:
        await update.message.reply_text(
            "🔹 Invalid user ID format. It must be a number.",
            message_thread_id=getattr(update.message, 'message_thread_id', None)
        )
        return
    
    if action == "add":
        if is_admin(target_user_id):
            await update.message.reply_text(
                f"🔹 User {target_user_id} is already an administrator. Cannot add them as an operator.",
                message_thread_id=getattr(update.message, 'message_thread_id', None)
            )
            return
            
        if add_operator(target_user_id):
            await update.message.reply_text(
                f"🔹 User {target_user_id} has been successfully added as an operator.",
                message_thread_id=getattr(update.message, 'message_thread_id', None)
            )
        else:
            await update.message.reply_text(
                f"🔹 User {target_user_id} is already an operator.",
                message_thread_id=getattr(update.message, 'message_thread_id', None)
            )
    
    elif action == "remove":
        if remove_operator(target_user_id):
            await update.message.reply_text(
                f"🔹 User {target_user_id} has been successfully removed from operators.",
                message_thread_id=getattr(update.message, 'message_thread_id', None)
            )
        else:
            await update.message.reply_text(
                f"🔹 User {target_user_id} is not an operator.",
                message_thread_id=getattr(update.message, 'message_thread_id', None)
            )
    
    elif action == "list":
        operators = get_all_operators()
        if operators:
            operators_list = ", ".join(operators)
            await update.message.reply_text(
                f"🔹 List of operators:\n{operators_list}",
                message_thread_id=getattr(update.message, 'message_thread_id', None)
            )
        else:
            await update.message.reply_text(
                "🔹 The list of operators is empty.",
                message_thread_id=getattr(update.message, 'message_thread_id', None)
            )
    
    else:
        await update.message.reply_text(
            "🔹 Invalid action. Use add, remove or list.",
            message_thread_id=getattr(update.message, 'message_thread_id', None)
        )

def register_handlers(app):
    from telegram.ext import CommandHandler
    
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("operator", operator_command))
