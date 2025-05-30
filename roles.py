import json
import os

ROLES_FILE = "roles.json"

_roles_cache = None
_last_modified = 0

def load_roles(use_cache=True):
    global _roles_cache, _last_modified
    
    if not os.path.exists(ROLES_FILE):
        _roles_cache = {"admins": [], "operators": []}
        return {"admins": [], "operators": []}
    
    file_modified = os.path.getmtime(ROLES_FILE) if os.path.exists(ROLES_FILE) else 0
    
    if use_cache and _roles_cache is not None and file_modified <= _last_modified:
        return _roles_cache.copy()
    
    try:
        with open(ROLES_FILE, "r", encoding="utf-8") as f:
            roles = json.load(f)
            if "admins" in roles:
                roles["admins"] = [str(admin_id) for admin_id in roles["admins"]]
            else:
                roles["admins"] = []
            
            if "operators" in roles:
                roles["operators"] = [str(op_id) for op_id in roles["operators"]]
            else:
                roles["operators"] = []
                
            _roles_cache = roles
            _last_modified = file_modified
            return roles
    except (FileNotFoundError, json.JSONDecodeError):
        _roles_cache = {"admins": [], "operators": []}
        return {"admins": [], "operators": []}

def save_roles(roles):
    global _roles_cache, _last_modified
    
    try:
        with open(ROLES_FILE, "w", encoding="utf-8") as f:
            json.dump(roles, f, ensure_ascii=False, indent=4)
        
        _roles_cache = roles.copy()
        _last_modified = os.path.getmtime(ROLES_FILE)
    except Exception:
        pass

def is_admin(user_id):
    roles = load_roles()
    return str(user_id) in roles.get("admins", [])

def is_operator(user_id):
    roles = load_roles()
    return str(user_id) in roles.get("operators", [])

def has_role(user_id):
    return is_admin(user_id) or is_operator(user_id)

def add_admin(user_id):
    roles = load_roles()
    user_id_str = str(user_id)
    
    if user_id_str in roles.get("operators", []):
        roles["operators"].remove(user_id_str)
    
    if user_id_str not in roles.get("admins", []):
        if "admins" not in roles:
            roles["admins"] = []
        roles["admins"].append(user_id_str)
        save_roles(roles)
        return True
    return False

def remove_admin(user_id):
    roles = load_roles()
    user_id_str = str(user_id)
    
    if user_id_str in roles.get("admins", []):
        roles["admins"].remove(user_id_str)
        save_roles(roles)
        return True
    return False

def add_operator(user_id):
    roles = load_roles()
    user_id_str = str(user_id)
    
    if user_id_str in roles.get("admins", []):
        return False
    
    if user_id_str not in roles.get("operators", []):
        if "operators" not in roles:
            roles["operators"] = []
        roles["operators"].append(user_id_str)
        save_roles(roles)
        return True
    return False

def remove_operator(user_id):
    roles = load_roles()
    user_id_str = str(user_id)
    
    if user_id_str in roles.get("operators", []):
        roles["operators"].remove(user_id_str)
        save_roles(roles)
        logger.info(f"User {user_id} removed from operators")
        return True
    return False

def ensure_main_admin(main_admin_id):
    roles = load_roles()
    main_admin_str = str(main_admin_id)
    
    if main_admin_str not in roles.get("admins", []):
        if "admins" not in roles:
            roles["admins"] = []
        roles["admins"].append(main_admin_str)
        save_roles(roles)
        return True
    return False

def get_all_admins():
    roles = load_roles()
    return roles.get("admins", [])

def get_all_operators():
    roles = load_roles()
    return roles.get("operators", [])
