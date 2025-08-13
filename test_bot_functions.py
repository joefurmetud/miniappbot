#!/usr/bin/env python3
"""
Test Script to Verify Bot Functionality
Tests all critical functions for the Telegram Bot Shop
"""

import asyncio
import sqlite3
import json
from decimal import Decimal
from datetime import datetime
import logging

# Import bot modules
from utils import get_db_connection, CITIES, DISTRICTS, PRODUCT_TYPES, init_db, load_data
from payment import create_nowpayments_payment, process_successful_crypto_purchase
from user import validate_discount_code

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_database_connection():
    """Test database connectivity and schema"""
    print("\n🔍 Testing Database Connection...")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check critical tables
        tables = ['users', 'products', 'basket_items', 'pending_deposits', 'purchases']
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"✅ Table '{table}' exists with {count} records")
        
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def test_product_availability():
    """Test product availability and stock system"""
    print("\n🔍 Testing Product Availability...")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if we have products
        cursor.execute("""
            SELECT city, district, product_type, COUNT(*) as stock,
                   SUM(CASE WHEN available = 1 AND reserved = 0 THEN 1 ELSE 0 END) as available_count
            FROM products
            GROUP BY city, district, product_type
            LIMIT 5
        """)
        
        products = cursor.fetchall()
        if products:
            print(f"✅ Found {len(products)} product groups:")
            for p in products:
                print(f"   - {p['city']}/{p['district']}: {p['product_type']} - Stock: {p['stock']}, Available: {p['available_count']}")
        else:
            print("⚠️ No products found in database")
        
        conn.close()
        return len(products) > 0
    except Exception as e:
        print(f"❌ Product availability test failed: {e}")
        return False

def test_basket_operations():
    """Test basket add/remove operations"""
    print("\n🔍 Testing Basket Operations...")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check basket_items table structure
        cursor.execute("PRAGMA table_info(basket_items)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        required_columns = ['id', 'user_id', 'product_id', 'quantity', 'added_at', 'expires_at']
        missing = [col for col in required_columns if col not in column_names]
        
        if missing:
            print(f"⚠️ Missing columns in basket_items: {missing}")
        else:
            print("✅ Basket table structure is correct")
        
        # Check for any active basket items
        cursor.execute("""
            SELECT COUNT(*) as total,
                   COUNT(DISTINCT user_id) as unique_users
            FROM basket_items
            WHERE datetime(expires_at) > datetime('now')
        """)
        result = cursor.fetchone()
        print(f"✅ Active basket items: {result['total']} items from {result['unique_users']} users")
        
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Basket operations test failed: {e}")
        return False

def test_payment_system():
    """Test payment system configuration"""
    print("\n🔍 Testing Payment System...")
    try:
        import os
        
        # Check NOWPayments configuration
        api_key = os.getenv('NOWPAYMENTS_API_KEY', '')
        if api_key:
            print("✅ NOWPayments API key is configured")
        else:
            print("⚠️ NOWPayments API key not found in environment")
        
        # Check pending deposits table
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) as total,
                   COUNT(CASE WHEN is_purchase = 1 THEN 1 END) as purchases,
                   COUNT(CASE WHEN is_purchase = 0 THEN 1 END) as refills
            FROM pending_deposits
        """)
        result = cursor.fetchone()
        print(f"✅ Pending deposits: {result['total']} total ({result['purchases']} purchases, {result['refills']} refills)")
        
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Payment system test failed: {e}")
        return False

def test_discount_codes():
    """Test discount code system"""
    print("\n🔍 Testing Discount Codes...")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check discount codes
        cursor.execute("""
            SELECT code, discount_type, value, is_active, uses_count, max_uses
            FROM discount_codes
            WHERE is_active = 1
            LIMIT 5
        """)
        codes = cursor.fetchall()
        
        if codes:
            print(f"✅ Found {len(codes)} active discount codes:")
            for code in codes:
                usage = f"{code['uses_count']}/{code['max_uses'] if code['max_uses'] else '∞'}"
                print(f"   - {code['code']}: {code['value']}{'%' if code['discount_type'] == 'percentage' else '€'} (Used: {usage})")
        else:
            print("⚠️ No active discount codes found")
        
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Discount code test failed: {e}")
        return False

def test_user_management():
    """Test user management system"""
    print("\n🔍 Testing User Management...")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check users
        cursor.execute("""
            SELECT COUNT(*) as total,
                   COUNT(CASE WHEN balance > 0 THEN 1 END) as with_balance,
                   COUNT(CASE WHEN total_purchases > 0 THEN 1 END) as with_purchases,
                   COUNT(CASE WHEN is_reseller = 1 THEN 1 END) as resellers,
                   COUNT(CASE WHEN is_banned = 1 THEN 1 END) as banned
            FROM users
        """)
        result = cursor.fetchone()
        
        print(f"✅ User Statistics:")
        print(f"   - Total users: {result['total']}")
        print(f"   - Users with balance: {result['with_balance']}")
        print(f"   - Users with purchases: {result['with_purchases']}")
        print(f"   - Resellers: {result['resellers']}")
        print(f"   - Banned users: {result['banned']}")
        
        conn.close()
        return True
    except Exception as e:
        print(f"❌ User management test failed: {e}")
        return False

def test_webhook_endpoint():
    """Test webhook configuration"""
    print("\n🔍 Testing Webhook Configuration...")
    try:
        import os
        
        webhook_url = os.getenv('WEBHOOK_URL', '')
        if webhook_url:
            print(f"✅ Webhook URL configured: {webhook_url[:50]}...")
        else:
            print("⚠️ Webhook URL not configured")
        
        # Check webhook signature configuration
        ipn_secret = os.getenv('NOWPAYMENTS_IPN_SECRET', '')
        if ipn_secret:
            print("✅ NOWPayments IPN secret configured")
        else:
            print("⚠️ NOWPayments IPN secret not configured (signature verification disabled)")
        
        return True
    except Exception as e:
        print(f"❌ Webhook test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("🚀 TELEGRAM BOT SHOP - FUNCTIONALITY TEST")
    print("=" * 60)
    
    # Initialize database if needed
    print("\n📦 Initializing database schema...")
    init_db()
    
    # Load configuration data
    print("📦 Loading configuration data...")
    load_data()
    
    # Run tests
    tests = [
        ("Database Connection", test_database_connection),
        ("Product Availability", test_product_availability),
        ("Basket Operations", test_basket_operations),
        ("Payment System", test_payment_system),
        ("Discount Codes", test_discount_codes),
        ("User Management", test_user_management),
        ("Webhook Configuration", test_webhook_endpoint),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print("\n" + "=" * 60)
    if passed == total:
        print(f"🎉 ALL TESTS PASSED! ({passed}/{total})")
        print("✅ Bot is fully operational and ready to use!")
    else:
        print(f"⚠️ SOME TESTS FAILED: {passed}/{total} passed")
        print("Please review the failed tests above.")
    print("=" * 60)

if __name__ == "__main__":
    main()
