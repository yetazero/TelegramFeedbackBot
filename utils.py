import logging
import os

BANNED_FILE = "banned.txt"
USERS_FILE = "users.txt"  

def load_banned():
    try:
        with open(BANNED_FILE, "r") as f:
            return {line.strip() for line in f if line.strip()}
    except FileNotFoundError:
        with open(BANNED_FILE, "w") as f:
            pass # Create the file if it doesn't exist
        return set()

def save_banned(banned_users):
    try:
        with open(BANNED_FILE, "w") as f:
            f.write("\n".join(banned_users))
    except Exception as e:
        logging.error(f"Ban save error: {e}")

def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            # Ensure only numeric IDs are loaded for users
            return {line.strip() for line in f if line.strip().isdigit()}
    except FileNotFoundError:
        with open(USERS_FILE, "w") as f:
            pass # Create the file if it doesn't exist
        return set()

def save_users(users):
    try:
        with open(USERS_FILE, "w") as f:
            f.write("\n".join(users))
    except Exception as e:
        logging.error(f"Users save error: {e}")