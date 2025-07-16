#!/usr/bin/env python3
import os
import asyncio
import sys
from telegram import Bot
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_token():
    """Debug token loading and API connectivity"""
    print("=== Telegram Bot Token Debug ===")
    
    # Check environment variable
    token = os.environ.get("TOKEN", "")
    if not token:
        print("❌ ERROR: TOKEN environment variable is empty or not set")
        return False
    
    print(f"✅ TOKEN environment variable loaded")
    print(f"Token format: {token[:10]}...{token[-10:]} (length: {len(token)})")
    
    # Check for whitespace issues
    original_token = token
    token = token.strip()
    if token != original_token:
        print(f"⚠️  WARNING: Token had leading/trailing whitespace (removed)")
    
    # Test network connectivity to Telegram
    print("\n=== Testing Telegram API Connectivity ===")
    try:
        bot = Bot(token=token)
        print("Bot instance created successfully")
        
        # Test get_me API call
        print("Calling get_me()...")
        me = await bot.get_me()
        
        print(f"✅ SUCCESS! Bot is valid and accessible:")
        print(f"  - Bot Name: {me.first_name}")
        print(f"  - Username: @{me.username}")
        print(f"  - Bot ID: {me.id}")
        
        return True
        
    except Exception as e:
        print(f"❌ FAILED to connect to Telegram API:")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {e}")
        
        # Additional debugging for specific errors
        if "InvalidToken" in str(type(e)):
            print("\nDebugging InvalidToken error:")
            print(f"- Token starts with: {token[:15]}...")
            print(f"- Token ends with: ...{token[-15:]}")
            print(f"- Token length: {len(token)}")
            print(f"- Contains colon: {':' in token}")
            if ':' in token:
                parts = token.split(':')
                print(f"- Bot ID part: {parts[0]} (length: {len(parts[0])})")
                print(f"- Secret part: {parts[1][:10]}...{parts[1][-10:]} (length: {len(parts[1])})")
        
        return False
    
    finally:
        try:
            await bot.shutdown()
        except:
            pass

if __name__ == "__main__":
    result = asyncio.run(debug_token())
    sys.exit(0 if result else 1) 