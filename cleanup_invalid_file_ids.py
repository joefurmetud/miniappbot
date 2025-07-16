#!/usr/bin/env python3
"""
Script to clean up invalid Telegram file IDs from the database.
Run this once after changing bot tokens to remove old file IDs that no longer work.
"""

import sqlite3
import os
import sys
from utils import get_db_connection

def cleanup_invalid_file_ids():
    """Remove all telegram_file_id values from product_media table to force fallback to local files."""
    
    print("=== Telegram File ID Cleanup ===")
    print("This script will remove all telegram_file_id values from your database.")
    print("This forces the bot to use local media files instead of invalid file IDs.")
    print("Your media files will still work, but will be loaded from disk instead of Telegram's cache.")
    
    # Confirm with user
    confirm = input("\nDo you want to proceed? (yes/no): ").strip().lower()
    if confirm not in ['yes', 'y']:
        print("Cleanup cancelled.")
        return False
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Count current records with file IDs
        cursor.execute("SELECT COUNT(*) as count FROM product_media WHERE telegram_file_id IS NOT NULL AND telegram_file_id != ''")
        count_result = cursor.fetchone()
        records_with_file_ids = count_result['count'] if count_result else 0
        
        print(f"\nFound {records_with_file_ids} media records with Telegram file IDs.")
        
        if records_with_file_ids == 0:
            print("No file IDs to clean up.")
            return True
        
        # Clear all telegram_file_id values
        cursor.execute("UPDATE product_media SET telegram_file_id = NULL WHERE telegram_file_id IS NOT NULL")
        updated_count = cursor.rowcount
        
        conn.commit()
        print(f"✅ Successfully cleared {updated_count} invalid file IDs from database.")
        print("Your bot will now use local media files instead of cached Telegram file IDs.")
        
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    print("Telegram Bot Media Cleanup Script")
    print("=" * 40)
    
    # Verify we can connect to database
    try:
        conn = get_db_connection()
        conn.close()
        print("✅ Database connection successful.")
    except Exception as e:
        print(f"❌ Cannot connect to database: {e}")
        print("Make sure you're running this script from the same directory as your bot.")
        sys.exit(1)
    
    # Run cleanup
    cleanup_success = cleanup_invalid_file_ids()
    
    print("\n" + "=" * 40)
    if cleanup_success:
        print("✅ Cleanup completed successfully!")
        print("Your bot should now display media properly using local files.")
    else:
        print("❌ Cleanup failed. Check the errors above.")
    
    print("\nYou can now deploy your bot to Render.") 