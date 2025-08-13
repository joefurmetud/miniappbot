#!/usr/bin/env python3
"""
Database optimization script for the Bot Shop
Creates indexes and optimizes database settings for better performance
"""

import sqlite3
import logging
from utils import DATABASE_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def optimize_database():
    """Apply database optimizations"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        logger.info(f"Optimizing database: {DATABASE_PATH}")
        
        # Enable WAL mode for better concurrency
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=10000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA mmap_size=30000000000")
        
        logger.info("Applied PRAGMA optimizations")
        
        # Create indexes for better query performance
        indexes = [
            # Products table indexes
            ("idx_products_location", "products(city, district)"),
            ("idx_products_available", "products(available, reserved)"),
            ("idx_products_type", "products(product_type)"),
            ("idx_products_composite", "products(city, district, available, product_type)"),
            
            # Users table indexes
            ("idx_users_user_id", "users(user_id)"),
            ("idx_users_balance", "users(balance)"),
            
            # Basket items indexes
            ("idx_basket_user", "basket_items(user_id)"),
            ("idx_basket_product", "basket_items(product_id)"),
            ("idx_basket_composite", "basket_items(user_id, product_id)"),
            
            # Reviews indexes
            ("idx_reviews_active", "reviews(is_active, created_at DESC)"),
            ("idx_reviews_user", "reviews(user_id)"),
            
            # Purchases indexes
            ("idx_purchases_user", "purchases(user_id)"),
            ("idx_purchases_date", "purchases(purchase_date DESC)"),
            ("idx_purchases_composite", "purchases(user_id, purchase_date DESC)"),
            
            # Pending deposits indexes
            ("idx_pending_deposits_user", "pending_deposits(user_id)"),
            ("idx_pending_deposits_payment", "pending_deposits(payment_id)"),
            ("idx_pending_deposits_created", "pending_deposits(created_at)"),
            
            # Cities and districts indexes (if they exist as tables)
            ("idx_cities_id", "cities(id)"),
            ("idx_districts_city", "districts(city_id)"),
            ("idx_districts_composite", "districts(id, city_id)"),
        ]
        
        for index_name, index_def in indexes:
            try:
                cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {index_def}")
                logger.info(f"✅ Created/verified index: {index_name}")
            except sqlite3.OperationalError as e:
                if "no such table" in str(e).lower():
                    logger.warning(f"⚠️ Skipped {index_name}: Table doesn't exist")
                else:
                    logger.error(f"❌ Failed to create {index_name}: {e}")
        
        # Analyze tables to update statistics
        cursor.execute("ANALYZE")
        logger.info("Updated database statistics")
        
        # Vacuum to reclaim space and defragment
        conn.execute("VACUUM")
        logger.info("Performed VACUUM operation")
        
        conn.commit()
        conn.close()
        
        logger.info("\n✅ Database optimization completed successfully!")
        logger.info("\nPerformance improvements applied:")
        logger.info("1. WAL mode enabled - better concurrent access")
        logger.info("2. Indexes created - faster queries")
        logger.info("3. Cache size increased - more data in memory")
        logger.info("4. Statistics updated - better query planning")
        logger.info("5. Database vacuumed - reduced fragmentation")
        
        return True
        
    except Exception as e:
        logger.error(f"Error optimizing database: {e}")
        return False

if __name__ == "__main__":
    if optimize_database():
        print("\n🚀 Your database is now optimized for maximum performance!")
        print("The mini-app should respond much faster now.")
    else:
        print("\n❌ Database optimization failed. Please check the error messages above.")
