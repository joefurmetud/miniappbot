"""
Optimized Telegram Mini App Web Interface for Bot Shop
High-performance version with caching, connection pooling, and query optimization
"""

import logging
import json
import hashlib
import hmac
import urllib.parse
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from functools import wraps, lru_cache
from threading import Lock
import sqlite3

from flask import Flask, request, jsonify, render_template, Response
from flask_caching import Cache

# Import existing utilities and modules
from utils import (
    get_db_connection, TOKEN, CITIES, DISTRICTS, PRODUCT_TYPES, 
    DEFAULT_PRODUCT_EMOJI, format_currency, LANGUAGES,
    _get_lang_data, send_message_with_retry, get_first_primary_admin_id,
    BASKET_TIMEOUT, MIN_DEPOSIT_EUR, DATABASE_PATH
)
from user import SUPPORTED_CRYPTO
import payment
from reseller_management import get_reseller_discount

# Configure logging
logger = logging.getLogger(__name__)

# Create a Blueprint
from flask import Blueprint

# Create Blueprint for Mini App with caching
miniapp_bp = Blueprint('miniapp', __name__, template_folder='templates')

# Initialize cache
cache = Cache(config={
    'CACHE_TYPE': 'simple',  # Use 'redis' in production for better performance
    'CACHE_DEFAULT_TIMEOUT': 300  # 5 minutes default cache
})

# Database connection pool
class DatabasePool:
    """Simple database connection pool for better performance"""
    def __init__(self, database_path: str, pool_size: int = 10):
        self.database_path = database_path
        self.pool_size = pool_size
        self.connections = []
        self.lock = Lock()
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize connection pool"""
        for _ in range(self.pool_size):
            conn = sqlite3.connect(self.database_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=10000")
            conn.execute("PRAGMA temp_store=MEMORY")
            self.connections.append(conn)
    
    def get_connection(self):
        """Get a connection from the pool"""
        with self.lock:
            if self.connections:
                return self.connections.pop()
            else:
                # Create a new connection if pool is empty
                conn = sqlite3.connect(self.database_path, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL")
                return conn
    
    def return_connection(self, conn):
        """Return a connection to the pool"""
        with self.lock:
            if len(self.connections) < self.pool_size:
                self.connections.append(conn)
            else:
                conn.close()
    
    def close_all(self):
        """Close all connections in the pool"""
        with self.lock:
            for conn in self.connections:
                conn.close()
            self.connections.clear()

# Initialize database pool
db_pool = DatabasePool(DATABASE_PATH, pool_size=20)

# Optimized IP whitelist checking with caching
TELEGRAM_IP_NETWORKS = []  # Pre-compiled IP networks

def initialize_ip_whitelist():
    """Pre-compile IP networks for faster checking"""
    import ipaddress
    global TELEGRAM_IP_NETWORKS
    
    ip_ranges = [
        "149.154.160.0/20", "91.108.4.0/22", "91.108.8.0/22",
        "91.108.12.0/22", "91.108.16.0/22", "91.108.56.0/22",
        "95.161.64.0/20", "67.198.55.0/24",
        "127.0.0.1", "::1"  # Localhost for development
    ]
    
    for range_str in ip_ranges:
        try:
            TELEGRAM_IP_NETWORKS.append(ipaddress.ip_network(range_str, strict=False))
        except ValueError:
            pass

# Initialize IP whitelist on module load
initialize_ip_whitelist()

@lru_cache(maxsize=1000)
def is_ip_in_whitelist(ip_address: str) -> bool:
    """Check if IP address is in Telegram's whitelist (cached)"""
    import ipaddress
    
    try:
        ip = ipaddress.ip_address(ip_address)
        for network in TELEGRAM_IP_NETWORKS:
            if ip in network:
                return True
        return False
    except ValueError:
        return False

def require_telegram_ip(f):
    """Optimized decorator to require requests from Telegram IPs only"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Skip in development
        if request.remote_addr in ['127.0.0.1', '::1']:
            return f(*args, **kwargs)
            
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if client_ip and ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        if not is_ip_in_whitelist(client_ip):
            logger.warning(f"Blocked request from non-whitelisted IP: {client_ip}")
            return jsonify({'error': 'Access denied'}), 403
        
        return f(*args, **kwargs)
    return decorated_function

# Optimized rate limiting with cleanup
from collections import deque
import threading

class RateLimiter:
    """Optimized rate limiter with automatic cleanup"""
    def __init__(self, window: int = 60, max_requests: int = 100):
        self.window = window
        self.max_requests = max_requests
        self.requests = {}
        self.lock = Lock()
        self._start_cleanup_thread()
    
    def _start_cleanup_thread(self):
        """Start background thread for cleanup"""
        def cleanup():
            while True:
                time.sleep(60)  # Clean every minute
                self._cleanup_old_requests()
        
        thread = threading.Thread(target=cleanup, daemon=True)
        thread.start()
    
    def _cleanup_old_requests(self):
        """Remove old requests from memory"""
        current_time = time.time()
        with self.lock:
            for ip in list(self.requests.keys()):
                self.requests[ip] = deque(
                    (t for t in self.requests[ip] if current_time - t < self.window),
                    maxlen=self.max_requests
                )
                if not self.requests[ip]:
                    del self.requests[ip]
    
    def check_rate_limit(self, ip_address: str) -> bool:
        """Check if IP has exceeded rate limit"""
        current_time = time.time()
        
        with self.lock:
            if ip_address not in self.requests:
                self.requests[ip_address] = deque(maxlen=self.max_requests)
            
            # Remove old requests
            self.requests[ip_address] = deque(
                (t for t in self.requests[ip_address] if current_time - t < self.window),
                maxlen=self.max_requests
            )
            
            if len(self.requests[ip_address]) >= self.max_requests:
                return False
            
            self.requests[ip_address].append(current_time)
            return True

# Initialize rate limiter
rate_limiter = RateLimiter(window=60, max_requests=100)

def require_rate_limit(f):
    """Optimized rate limiting decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if client_ip and ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        if not rate_limiter.check_rate_limit(client_ip):
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return jsonify({'error': 'Rate limit exceeded. Please try again later.'}), 429
        
        return f(*args, **kwargs)
    return decorated_function

# Cached Telegram data validation
@lru_cache(maxsize=100)
def validate_telegram_data_cached(init_data: str, current_time: int) -> Optional[Dict]:
    """
    Cached validation of Telegram Web App init data
    current_time is used to invalidate cache every minute
    """
    try:
        parsed_data = urllib.parse.parse_qs(init_data)
        received_hash = parsed_data.get('hash', [None])[0]
        if not received_hash:
            return None
        
        data_check_string_parts = []
        for key, values in parsed_data.items():
            if key != 'hash':
                for value in values:
                    data_check_string_parts.append(f"{key}={value}")
        
        data_check_string = '\n'.join(sorted(data_check_string_parts))
        
        secret_key = hmac.new(
            b"WebAppData", 
            TOKEN.encode(), 
            hashlib.sha256
        ).digest()
        
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if calculated_hash != received_hash:
            return None
        
        user_data = parsed_data.get('user', [None])[0]
        if user_data:
            return json.loads(user_data)
        
        return None
    except Exception as e:
        logger.error(f"Error validating Telegram data: {e}")
        return None

def get_user_from_request() -> Optional[Dict]:
    """Extract and validate user from request headers with caching"""
    init_data = request.headers.get('X-Telegram-Init-Data')
    if not init_data:
        return None
    
    # Use current minute as cache key to auto-invalidate every minute
    current_minute = int(time.time() / 60)
    return validate_telegram_data_cached(init_data, current_minute)

def require_auth(f):
    """Decorator to require Telegram authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_user_from_request()
        if not user:
            return jsonify({'error': 'Authentication required'}), 401
        return f(user, *args, **kwargs)
    return decorated_function

# Optimized database helper
def get_db_from_pool():
    """Get a database connection from the pool"""
    return db_pool.get_connection()

def return_db_to_pool(conn):
    """Return a database connection to the pool"""
    db_pool.return_connection(conn)

# Cache decorator for database queries
def cache_db_result(timeout: int = 300):
    """Decorator to cache database query results"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            cache_key = f"{f.__name__}:{str(args)}:{str(kwargs)}"
            
            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = f(*args, **kwargs)
            cache.set(cache_key, result, timeout=timeout)
            return result
        return wrapper
    return decorator

# Routes

@miniapp_bp.route('/')
@require_rate_limit
def index():
    """Serve the Mini App interface"""
    return render_template('index.html')

@miniapp_bp.route('/api/user/balance')
@require_rate_limit
@require_telegram_ip
@require_auth
def get_user_balance(user):
    """Get user's current balance with connection pooling"""
    try:
        user_id = user['id']
        conn = get_db_from_pool()
        cursor = conn.cursor()
        
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        
        balance = float(result['balance']) if result else 0.0
        
        return jsonify({
            'balance': balance,
            'formatted': format_currency(Decimal(str(balance)))
        })
        
    except Exception as e:
        logger.error(f"Error getting user balance: {e}")
        return jsonify({'error': 'Failed to get balance'}), 500
    finally:
        if 'conn' in locals():
            return_db_to_pool(conn)

@miniapp_bp.route('/api/user/profile')
@require_telegram_ip
@require_auth
def get_user_profile(user):
    """Get user profile information with optimized queries"""
    try:
        user_id = user['id']
        conn = get_db_from_pool()
        cursor = conn.cursor()
        
        # Single optimized query
        cursor.execute("""
            SELECT balance, created_at, total_spent, total_purchases 
            FROM users WHERE user_id = ?
        """, (user_id,))
        user_data = cursor.fetchone()
        
        if not user_data:
            # Create user if doesn't exist (batch insert)
            current_time = datetime.now().isoformat()
            cursor.execute("""
                INSERT OR IGNORE INTO users (user_id, username, balance, created_at, total_spent) 
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, user.get('username', ''), 0.0, current_time, 0.0))
            conn.commit()
            
            user_data = {
                'balance': 0.0,
                'created_at': current_time,
                'total_spent': 0.0,
                'total_purchases': 0
            }
        else:
            user_data = dict(user_data)
        
        return jsonify({
            'user_id': user_id,
            'username': user.get('username', ''),
            'first_name': user.get('first_name', ''),
            'balance': float(user_data['balance']),
            'total_purchases': user_data.get('total_purchases', 0),
            'total_spent': float(user_data.get('total_spent', 0)),
            'joined_date': user_data.get('created_at', '').split('T')[0] if user_data.get('created_at') else 'Unknown'
        })
        
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        return jsonify({'error': 'Failed to get profile'}), 500
    finally:
        if 'conn' in locals():
            return_db_to_pool(conn)

@miniapp_bp.route('/api/cities')
@require_telegram_ip
@cache.cached(timeout=3600)  # Cache for 1 hour
def get_cities():
    """Get all available cities (cached)"""
    try:
        cities = [{'id': city_id, 'name': city_name} 
                 for city_id, city_name in CITIES.items()]
        return jsonify({'cities': cities})
    except Exception as e:
        logger.error(f"Error getting cities: {e}")
        return jsonify({'error': 'Failed to get cities'}), 500

@miniapp_bp.route('/api/districts/<city_id>')
@require_telegram_ip
@cache.cached(timeout=3600)  # Cache for 1 hour
def get_districts(city_id):
    """Get districts for a specific city (cached)"""
    try:
        districts = []
        if city_id in DISTRICTS:
            districts = [{'id': dist_id, 'name': dist_name} 
                        for dist_id, dist_name in DISTRICTS[city_id].items()]
        return jsonify({'districts': districts})
    except Exception as e:
        logger.error(f"Error getting districts: {e}")
        return jsonify({'error': 'Failed to get districts'}), 500

@miniapp_bp.route('/api/products/<city_id>/<district_id>')
@require_telegram_ip
@require_auth
def get_products(user, city_id, district_id):
    """Get products with optimized query and caching"""
    try:
        user_id = user['id']
        
        # Create cache key including user_id for personalized pricing
        cache_key = f"products:{city_id}:{district_id}:{user_id}"
        
        # Try to get from cache
        cached_result = cache.get(cache_key)
        if cached_result:
            return jsonify(cached_result)
        
        conn = get_db_from_pool()
        cursor = conn.cursor()
        
        # Optimized query with indexes
        cursor.execute("""
            WITH city_district AS (
                SELECT c.name as city_name, d.name as district_name
                FROM cities c
                JOIN districts d ON d.city_id = c.id
                WHERE c.id = ? AND d.id = ?
            )
            SELECT p.id, p.product_type, p.size, p.price, p.city, p.district,
                   COUNT(CASE WHEN p.reserved = 0 AND p.available = 1 THEN 1 END) as stock_count
            FROM products p, city_district cd
            WHERE p.city = cd.city_name AND p.district = cd.district_name
            GROUP BY p.product_type, p.size, p.price, p.city, p.district
            HAVING stock_count > 0
            ORDER BY p.product_type, p.size
        """, (city_id, district_id))
        
        products = []
        
        # Batch process discounts
        rows = cursor.fetchall()
        for row in rows:
            product_type = row['product_type']
            
            # Get reseller discount (consider caching this too)
            discount_percent = get_reseller_discount(user_id, product_type)
            original_price = Decimal(str(row['price']))
            discount_amount = (original_price * discount_percent / Decimal('100')).quantize(Decimal('0.01'))
            final_price = original_price - discount_amount
            
            products.append({
                'id': row['id'],
                'type': product_type,
                'size': row['size'],
                'price': float(final_price),
                'original_price': float(original_price),
                'discount_percent': float(discount_percent),
                'city': row['city'],
                'district': row['district'],
                'stock': row['stock_count'],
                'emoji': PRODUCT_TYPES.get(product_type, DEFAULT_PRODUCT_EMOJI)
            })
        
        result = {'products': products}
        
        # Cache the result for 60 seconds
        cache.set(cache_key, result, timeout=60)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting products: {e}")
        return jsonify({'error': 'Failed to get products'}), 500
    finally:
        if 'conn' in locals():
            return_db_to_pool(conn)

@miniapp_bp.route('/api/basket')
@require_telegram_ip
@require_auth
def get_basket(user):
    """Get user's basket items with optimized loading"""
    try:
        user_id = user['id']
        
        # Use connection pooling
        conn = get_db_from_pool()
        cursor = conn.cursor()
        
        # Optimized basket query
        cursor.execute("""
            SELECT b.id as basket_id, b.product_id, b.quantity, b.added_at,
                   p.product_type, p.size, p.price, p.city, p.district
            FROM basket_items b
            JOIN products p ON b.product_id = p.id
            WHERE b.user_id = ?
            ORDER BY b.added_at DESC
        """, (user_id,))
        
        items = []
        total = Decimal('0.0')
        
        for row in cursor.fetchall():
            # Apply reseller discount
            discount_percent = get_reseller_discount(user_id, row['product_type'])
            original_price = Decimal(str(row['price']))
            discount_amount = (original_price * discount_percent / Decimal('100')).quantize(Decimal('0.01'))
            final_price = original_price - discount_amount
            
            items.append({
                'basket_id': row['basket_id'],
                'product_id': row['product_id'],
                'type': row['product_type'],
                'size': row['size'],
                'price': float(final_price),
                'city': row['city'],
                'district': row['district'],
                'emoji': PRODUCT_TYPES.get(row['product_type'], DEFAULT_PRODUCT_EMOJI),
                'quantity': row['quantity'],
                'added_at': row['added_at']
            })
            total += final_price * row['quantity']
        
        return jsonify({
            'items': items,
            'total': float(total),
            'count': len(items)
        })
        
    except Exception as e:
        logger.error(f"Error getting basket: {e}")
        return jsonify({'error': 'Failed to get basket'}), 500
    finally:
        if 'conn' in locals():
            return_db_to_pool(conn)

@miniapp_bp.route('/api/reviews', methods=['GET'])
@require_telegram_ip
@cache.cached(timeout=120)  # Cache for 2 minutes
def get_reviews():
    """Get reviews with caching"""
    try:
        conn = get_db_from_pool()
        c = conn.cursor()
        
        # Optimized query with limit
        c.execute("""
            SELECT r.id, r.rating, r.text, r.created_at,
                   COALESCE(u.first_name, u.username, 'Anonymous') as author_name
            FROM reviews r 
            LEFT JOIN users u ON r.user_id = u.user_id 
            WHERE r.is_active = 1 
            ORDER BY r.created_at DESC 
            LIMIT 50
        """)
        
        reviews = [
            {
                'id': row['id'],
                'rating': row['rating'],
                'text': row['text'],
                'author_name': row['author_name'],
                'created_at': row['created_at']
            }
            for row in c.fetchall()
        ]
        
        return jsonify({'reviews': reviews})
    except Exception as e:
        logger.error(f"Error fetching reviews: {e}")
        return jsonify({'error': 'Failed to load reviews'}), 500
    finally:
        if 'conn' in locals():
            return_db_to_pool(conn)

# Initialize cache when blueprint is registered
def init_app(app):
    """Initialize the optimized mini app with the Flask app"""
    cache.init_app(app)
    app.register_blueprint(miniapp_bp)
    
    # Create database indexes for better performance
    try:
        conn = get_db_from_pool()
        cursor = conn.cursor()
        
        # Create indexes if they don't exist
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_location ON products(city, district)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_available ON products(available, reserved)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_basket_user ON basket_items(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reviews_active ON reviews(is_active, created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id)")
        
        conn.commit()
        logger.info("Database indexes created/verified for optimization")
        
    except Exception as e:
        logger.error(f"Error creating database indexes: {e}")
    finally:
        if 'conn' in locals():
            return_db_to_pool(conn)

# Export the optimized blueprint
__all__ = ['miniapp_bp', 'init_app', 'db_pool']
