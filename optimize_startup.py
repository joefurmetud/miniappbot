#!/usr/bin/env python3
"""
Ultra Performance Startup Script
Applies all database optimizations at startup for maximum speed
"""

import sqlite3
import os
import logging
from utils import DATABASE_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def optimize_database():
    """Apply all database optimizations for maximum performance"""
    
    if not os.path.exists(DATABASE_PATH):
        logger.error(f"Database not found at {DATABASE_PATH}")
        return False
    
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        logger.info("Applying ultra-performance database optimizations...")
        
        # WAL mode for concurrent reads
        cursor.execute("PRAGMA journal_mode=WAL")
        logger.info("✓ WAL mode enabled")
        
        # Reduce sync for speed (slightly less safe but much faster)
        cursor.execute("PRAGMA synchronous=NORMAL")
        logger.info("✓ Synchronous mode set to NORMAL")
        
        # Massive cache for in-memory operations
        cursor.execute("PRAGMA cache_size=100000")  # ~100MB cache
        logger.info("✓ Cache size set to 100MB")
        
        # Keep temp tables in memory
        cursor.execute("PRAGMA temp_store=MEMORY")
        logger.info("✓ Temp store in memory")
        
        # Memory-mapped I/O for ultra-fast access
        cursor.execute("PRAGMA mmap_size=30000000000")  # 30GB mmap
        logger.info("✓ Memory-mapped I/O enabled (30GB)")
        
        # Optimize page size
        cursor.execute("PRAGMA page_size=32768")  # 32KB pages
        logger.info("✓ Page size optimized to 32KB")
        
        # Create critical indexes for lightning-fast queries
        indexes = [
            # Products table - most critical for performance
            ("idx_products_location", "products(city, district, available, reserved)"),
            ("idx_products_type", "products(product_type, available, reserved)"),
            ("idx_products_composite", "products(city, district, product_type, size, price, available, reserved)"),
            
            # Users table
            ("idx_users_id", "users(user_id)"),
            
            # Basket table
            ("idx_basket_user", "basket(user_id, added_at)"),
            ("idx_basket_composite", "basket(user_id, product_id)"),
            
            # Payments table
            ("idx_payments_user", "payments(user_id, status)"),
            ("idx_payments_id", "payments(payment_id)"),
            
            # Orders table
            ("idx_orders_user", "orders(user_id, created_at)"),
            
            # Reviews table
            ("idx_reviews_product", "reviews(product_type, rating)"),
        ]
        
        for index_name, index_def in indexes:
            try:
                cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {index_def}")
                logger.info(f"✓ Index {index_name} created/verified")
            except Exception as e:
                logger.warning(f"⚠ Could not create index {index_name}: {e}")
        
        # Analyze tables for query planner optimization
        cursor.execute("ANALYZE")
        logger.info("✓ Database analyzed for query optimization")
        
        # Vacuum to defragment (only if not too large)
        cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
        db_size = cursor.fetchone()[0]
        if db_size < 100 * 1024 * 1024:  # Only vacuum if < 100MB
            cursor.execute("VACUUM")
            logger.info("✓ Database vacuumed")
        else:
            logger.info("⚠ Skipping vacuum (database too large)")
        
        conn.commit()
        conn.close()
        
        logger.info("✅ All database optimizations applied successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error optimizing database: {e}")
        return False

if __name__ == "__main__":
    optimize_database()
