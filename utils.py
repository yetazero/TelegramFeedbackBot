import logging
import os
import json

BANNED_FILE = "banned.txt"
USERS_FILE = "users.txt"
USER_DETAILS_FILE = "user_details.json"


def load_banned():
    if not os.path.exists(BANNED_FILE):
        return set()
    try:
        with open(BANNED_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f)
    except FileNotFoundError:
        return set()

def save_banned(banned_set):
    try:
        with open(BANNED_FILE, "w", encoding="utf-8") as f:
            for user_id in banned_set:
                f.write(str(user_id) + "\n")
    except Exception as e:
        logging.error(f"Error saving banned users: {e}")

def load_users():
    if not os.path.exists(USERS_FILE):
        return set()
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f)
    except FileNotFoundError:
        return set()

def save_users(users_set):
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            for user_id in users_set:
                f.write(str(user_id) + "\n")
    except Exception as e:
        logging.error(f"Error saving users: {e}")

def load_user_details():
    if not os.path.exists(USER_DETAILS_FILE):
        return {}
    try:
        with open(USER_DETAILS_FILE, "r", encoding="utf-8") as f:
            details = json.load(f)
            return {str(k): v for k, v in details.items()}
    except json.JSONDecodeError:
        logging.error(f"Error decoding {USER_DETAILS_FILE}. Returning empty details.")
        return {}
    except FileNotFoundError:
        return {}

def save_user_details(details):
    try:
        with open(USER_DETAILS_FILE, "w", encoding="utf-8") as f:
            json.dump(details, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Error saving user details: {e}")

def get_user_data(user_id):
    details = load_user_details()
    return details.get(str(user_id))

def update_user_data_field(user_id, field, value, delete_if_none=False):
    details = load_user_details()
    user_id_str = str(user_id)
    if user_id_str not in details:
        if value is None and delete_if_none:
            return
        details[user_id_str] = {}
    
    if value is None and delete_if_none:
        if field in details[user_id_str]:
            del details[user_id_str][field]
            if not details[user_id_str]:
                del details[user_id_str]
    else:
        details[user_id_str][field] = value
    save_user_details(details)



def get_user_id_by_topic_id(topic_id, group_id_config_str):
    if not group_id_config_str:
        return None
    details = load_user_details()
    try:
        topic_id_int = int(topic_id)
    except ValueError:
        return None

    for user_id_str_key, data in details.items():
        if data.get("topic_id_in_group") == topic_id_int:
            return str(user_id_str_key)
    return None


def get_user_info_string(user_id_str, bot_user_data_all=None, effective_user_obj=None):
    user_specific_data = None
    if bot_user_data_all:
        user_specific_data = bot_user_data_all.get(str(user_id_str))
    else:
        user_specific_data = get_user_data(str(user_id_str))

    if not user_specific_data and not effective_user_obj:
        return f"User ID: `{user_id_str}` (No further details found)"

    info_lines = [f"🆔 User ID: `{user_id_str}`"]

    tg_username = None
    full_name_str = None
    language_code = None
    is_premium = False
    is_bot = False
    has_profile_photo = False
    account_creation = None

    if effective_user_obj:
        tg_username = effective_user_obj.username
        first = effective_user_obj.first_name or ""
        last = effective_user_obj.last_name or ""
        full_name_str = f"{first} {last}".strip()
        language_code = getattr(effective_user_obj, 'language_code', None)
        is_premium = getattr(effective_user_obj, 'is_premium', False)
        is_bot = getattr(effective_user_obj, 'is_bot', False)
        has_profile_photo = hasattr(effective_user_obj, 'photo') and effective_user_obj.photo is not None
        
        try:
            user_id_int = int(user_id_str)
            if user_id_int < 100000000:
                account_creation = "Before 2015"
            elif user_id_int < 200000000:
                account_creation = "Around 2015-2016"
            elif user_id_int < 400000000:
                account_creation = "Around 2016-2017"
            elif user_id_int < 600000000:
                account_creation = "Around 2017-2018"
            elif user_id_int < 800000000:
                account_creation = "Around 2018-2019"
            elif user_id_int < 1000000000:
                account_creation = "Around 2019-2020"
            elif user_id_int < 1500000000:
                account_creation = "Around 2020-2021"
            elif user_id_int < 2000000000:
                account_creation = "Around 2021-2022"
            elif user_id_int < 3000000000:
                account_creation = "Around 2022-2023"
            elif user_id_int < 4000000000:
                account_creation = "Around 2023-2024"
            else:
                account_creation = "2024 or later"
        except:
            pass
    
    if not tg_username and user_specific_data:
        tg_username = user_specific_data.get("telegram_username")
    if not full_name_str and user_specific_data:
        full_name_str = user_specific_data.get("full_name")

    if full_name_str:
        info_lines.append(f"👤 Full Name: {full_name_str}")
    if tg_username:
        info_lines.append(f"🔤 Username: @{tg_username}")
    if language_code:
        info_lines.append(f"🌐 Language: {language_code.upper()}")
    if is_premium:
        info_lines.append(f"⭐ Premium User: Yes")
    if is_bot:
        info_lines.append(f"🤖 Bot Account: Yes")
    if has_profile_photo:
        info_lines.append(f"🖼️ Has Profile Photo: Yes")
    if account_creation:
        info_lines.append(f"📅 Estimated Registration: {account_creation}")
    
    topic_id = user_specific_data.get("topic_id_in_group") if user_specific_data else None
    if topic_id:
        info_lines.append(f"🔗 Associated Topic ID: {topic_id}")
        
    if user_specific_data:
        if user_specific_data.get("first_interaction_time"):
            first_time = user_specific_data.get("first_interaction_time")
            info_lines.append(f"🕒 First Interaction: {first_time}")
        
        if user_specific_data.get("last_interaction_time"):
            last_time = user_specific_data.get("last_interaction_time")
            info_lines.append(f"⏱️ Last Interaction: {last_time}")
            
        if user_specific_data.get("interaction_count"):
            count = user_specific_data.get("interaction_count")
            info_lines.append(f"📊 Total Interactions: {count}")
            
        if user_specific_data.get("hide_delivery_notifications") is not None:
            hide_status = "Enabled" if user_specific_data.get("hide_delivery_notifications") else "Disabled"
            info_lines.append(f"🔕 Notifications Hidden: {hide_status}")
            
    banned_users = load_banned()
    if user_id_str in banned_users:
        info_lines.append(f"⛔ Status: BANNED")
        
    users_list = load_users()
    if user_id_str in users_list:
        info_lines.append(f"📬 Subscribed to mailings: Yes")
    else:
        info_lines.append(f"📭 Subscribed to mailings: No")
        
    return "\n".join(info_lines)