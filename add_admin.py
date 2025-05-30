import sys
import os
from roles import add_admin, ensure_main_admin

def main():
    if len(sys.argv) != 2:
        print("Usage: python add_admin.py <admin_id>")
        return
    
    try:
        admin_id = int(sys.argv[1])
        result = ensure_main_admin(admin_id)
        
        if result:
            print(f"🔹 Administrator {admin_id} has been successfully added")
        else:
            print(f"🔹 Administrator {admin_id} is already added")
            
    except ValueError:
        print("🔹 Error: Administrator ID must be an integer")
    except Exception as e:
        print(f"🔹 Error adding administrator: {e}")

if __name__ == "__main__":
    main()
