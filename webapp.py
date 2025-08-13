"""
Telegram Mini App Web Interface for Bot Shop
Provides REST API endpoints for the Mini App frontend
"""

import logging
import json
import hashlib
import hmac
import urllib.parse
import time
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, deque
from functools import wraps, lru_cache
from threading import Lock
import threading

from flask import Flask, request, jsonify, render_template, Response
import sqlite3

# Import existing utilities and modules
from utils import (
    get_db_connection, TOKEN, CITIES, DISTRICTS, PRODUCT_TYPES, 
    DEFAULT_PRODUCT_EMOJI, format_currency, LANGUAGES,
    _get_lang_data, send_message_with_retry, get_first_primary_admin_id,
    BASKET_TIMEOUT, MIN_DEPOSIT_EUR
)
from user import SUPPORTED_CRYPTO
import payment
from reseller_management import get_reseller_discount

# Configure logging
logger = logging.getLogger(__name__)

# Create a Blueprint instead of a separate Flask app
from flask import Blueprint

# Create Blueprint for Mini App
miniapp_bp = Blueprint('miniapp', __name__, template_folder='templates')

# Telegram IP Whitelist for Security
TELEGRAM_IP_RANGES = [
    # Telegram's official IP ranges
    "149.154.160.0/20",    # Telegram DC1
    "149.154.161.0/24",    # Telegram DC1
    "149.154.162.0/24",    # Telegram DC1
    "149.154.163.0/24",    # Telegram DC1
    "149.154.164.0/24",    # Telegram DC1
    "149.154.165.0/24",    # Telegram DC1
    "149.154.166.0/24",    # Telegram DC1
    "149.154.167.0/24",    # Telegram DC1
    "149.154.168.0/24",    # Telegram DC1
    "149.154.169.0/24",    # Telegram DC1
    "149.154.170.0/24",    # Telegram DC1
    "149.154.171.0/24",    # Telegram DC1
    "149.154.172.0/24",    # Telegram DC1
    "149.154.173.0/24",    # Telegram DC1
    "149.154.174.0/24",    # Telegram DC1
    "149.154.175.0/24",    # Telegram DC1
    "91.108.4.0/22",       # Telegram DC2
    "91.108.8.0/22",       # Telegram DC2
    "91.108.12.0/22",      # Telegram DC2
    "91.108.16.0/22",      # Telegram DC2
    "91.108.56.0/22",      # Telegram DC2
    "91.108.56.0/24",      # Telegram DC2
    "91.108.57.0/24",      # Telegram DC2
    "91.108.58.0/24",      # Telegram DC2
    "91.108.59.0/24",      # Telegram DC2
    "91.108.56.0/22",      # Telegram DC2
    "91.108.60.0/22",      # Telegram DC2
    "91.108.64.0/22",      # Telegram DC2
    "91.108.68.0/22",      # Telegram DC2
    "91.108.72.0/22",      # Telegram DC2
    "91.108.76.0/22",      # Telegram DC2
    "91.108.80.0/22",      # Telegram DC2
    "91.108.84.0/22",      # Telegram DC2
    "91.108.88.0/22",      # Telegram DC2
    "91.108.92.0/22",      # Telegram DC2
    "91.108.96.0/22",      # Telegram DC2
    "91.108.100.0/22",     # Telegram DC2
    "91.108.104.0/22",     # Telegram DC2
    "91.108.108.0/22",     # Telegram DC2
    "91.108.112.0/22",     # Telegram DC2
    "91.108.116.0/22",     # Telegram DC2
    "91.108.120.0/22",     # Telegram DC2
    "91.108.124.0/22",     # Telegram DC2
    "91.108.128.0/22",     # Telegram DC2
    "91.108.132.0/22",     # Telegram DC2
    "91.108.136.0/22",     # Telegram DC2
    "91.108.140.0/22",     # Telegram DC2
    "91.108.144.0/22",     # Telegram DC2
    "91.108.148.0/22",     # Telegram DC2
    "91.108.152.0/22",     # Telegram DC2
    "91.108.156.0/22",     # Telegram DC2
    "91.108.160.0/22",     # Telegram DC2
    "91.108.164.0/22",     # Telegram DC2
    "91.108.168.0/22",     # Telegram DC2
    "91.108.172.0/22",     # Telegram DC2
    "91.108.176.0/22",     # Telegram DC2
    "91.108.180.0/22",     # Telegram DC2
    "91.108.184.0/22",     # Telegram DC2
    "91.108.188.0/22",     # Telegram DC2
    "91.108.192.0/22",     # Telegram DC2
    "91.108.196.0/22",     # Telegram DC2
    "91.108.200.0/22",     # Telegram DC2
    "91.108.204.0/22",     # Telegram DC2
    "91.108.208.0/22",     # Telegram DC2
    "91.108.212.0/22",     # Telegram DC2
    "91.108.216.0/22",     # Telegram DC2
    "91.108.220.0/22",     # Telegram DC2
    "91.108.224.0/22",     # Telegram DC2
    "91.108.228.0/22",     # Telegram DC2
    "91.108.232.0/22",     # Telegram DC2
    "91.108.236.0/22",     # Telegram DC2
    "91.108.240.0/22",     # Telegram DC2
    "91.108.244.0/22",     # Telegram DC2
    "91.108.248.0/22",     # Telegram DC2
    "91.108.252.0/22",     # Telegram DC2
    "95.161.64.0/20",      # Telegram DC3
    "95.161.68.0/22",      # Telegram DC3
    "95.161.72.0/22",      # Telegram DC3
    "95.161.76.0/22",      # Telegram DC3
    "95.161.80.0/22",      # Telegram DC3
    "95.161.84.0/22",      # Telegram DC3
    "95.161.88.0/22",      # Telegram DC3
    "95.161.92.0/22",      # Telegram DC3
    "95.161.96.0/22",      # Telegram DC3
    "95.161.100.0/22",     # Telegram DC3
    "95.161.104.0/22",     # Telegram DC3
    "95.161.108.0/22",     # Telegram DC3
    "95.161.112.0/22",     # Telegram DC3
    "95.161.116.0/22",     # Telegram DC3
    "95.161.120.0/22",     # Telegram DC3
    "95.161.124.0/22",     # Telegram DC3
    "95.161.128.0/22",     # Telegram DC3
    "95.161.132.0/22",     # Telegram DC3
    "95.161.136.0/22",     # Telegram DC3
    "95.161.140.0/22",     # Telegram DC3
    "95.161.144.0/22",     # Telegram DC3
    "95.161.148.0/22",     # Telegram DC3
    "95.161.152.0/22",     # Telegram DC3
    "95.161.156.0/22",     # Telegram DC3
    "95.161.160.0/22",     # Telegram DC3
    "95.161.164.0/22",     # Telegram DC3
    "95.161.168.0/22",     # Telegram DC3
    "95.161.172.0/22",     # Telegram DC3
    "95.161.176.0/22",     # Telegram DC3
    "95.161.180.0/22",     # Telegram DC3
    "95.161.184.0/22",     # Telegram DC3
    "95.161.188.0/22",     # Telegram DC3
    "95.161.192.0/22",     # Telegram DC3
    "95.161.196.0/22",     # Telegram DC3
    "95.161.200.0/22",     # Telegram DC3
    "95.161.204.0/22",     # Telegram DC3
    "95.161.208.0/22",     # Telegram DC3
    "95.161.212.0/22",     # Telegram DC3
    "95.161.216.0/22",     # Telegram DC3
    "95.161.220.0/22",     # Telegram DC3
    "95.161.224.0/22",     # Telegram DC3
    "95.161.228.0/22",     # Telegram DC3
    "95.161.232.0/22",     # Telegram DC3
    "95.161.236.0/22",     # Telegram DC3
    "95.161.240.0/22",     # Telegram DC3
    "95.161.244.0/22",     # Telegram DC3
    "95.161.248.0/22",     # Telegram DC3
    "95.161.252.0/22",     # Telegram DC3
    "67.198.55.0/24",      # Telegram DC4
    "67.198.56.0/24",      # Telegram DC4
    "67.198.57.0/24",      # Telegram DC4
    "67.198.58.0/24",      # Telegram DC4
    "67.198.59.0/24",      # Telegram DC4
    "67.198.60.0/24",      # Telegram DC4
    "67.198.61.0/24",      # Telegram DC4
    "67.198.62.0/24",      # Telegram DC4
    "67.198.63.0/24",      # Telegram DC2
    "127.0.0.1",           # Localhost for development
    "::1"                   # Localhost IPv6 for development
]

# Pre-compile IP networks for faster checking
TELEGRAM_IP_NETWORKS = []

def initialize_ip_networks():
    """Pre-compile IP networks on startup"""
    import ipaddress
    global TELEGRAM_IP_NETWORKS
    for range_str in TELEGRAM_IP_RANGES:
        try:
            TELEGRAM_IP_NETWORKS.append(ipaddress.ip_network(range_str, strict=False))
        except ValueError:
            pass

# Initialize on import
initialize_ip_networks()

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
    """Decorator to require requests from Telegram IPs only - DISABLED FOR PERFORMANCE"""
    def decorated_function(*args, **kwargs):
        # SKIP IP CHECK FOR PERFORMANCE - Rely on Telegram auth only
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Rate Limiting for Security

# Optimized rate limiter with automatic cleanup
class RateLimiter:
    def __init__(self, window=60, max_requests=100):
        self.window = window
        self.max_requests = max_requests
        self.requests = {}
        self.lock = Lock()
    
    def check_rate_limit(self, ip_address: str) -> bool:
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

rate_limiter = RateLimiter(60, 100)

def check_rate_limit(ip_address: str) -> bool:
    """Check if IP address has exceeded rate limit"""
    return rate_limiter.check_rate_limit(ip_address)

def require_rate_limit(f):
    """Decorator to add rate limiting"""
    def decorated_function(*args, **kwargs):
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if client_ip and ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        if not check_rate_limit(client_ip):
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return jsonify({'error': 'Rate limit exceeded. Please try again later.'}), 429
        
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def validate_telegram_data(init_data: str) -> Optional[Dict]:
    """
    Validate Telegram Web App init data
    Returns user data if valid, None if invalid
    """
    try:
        # Parse the init data
        parsed_data = urllib.parse.parse_qs(init_data)
        
        # Extract hash and other parameters
        received_hash = parsed_data.get('hash', [None])[0]
        if not received_hash:
            return None
            
        # Remove hash from data for verification
        data_check_string_parts = []
        for key, values in parsed_data.items():
            if key != 'hash':
                for value in values:
                    data_check_string_parts.append(f"{key}={value}")
        
        data_check_string = '\n'.join(sorted(data_check_string_parts))
        
        # Create secret key
        secret_key = hmac.new(
            b"WebAppData", 
            TOKEN.encode(), 
            hashlib.sha256
        ).digest()
        
        # Calculate hash
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Verify hash
        if calculated_hash != received_hash:
            logger.warning("Telegram data hash verification failed")
            return None
            
        # Parse user data
        user_data = parsed_data.get('user', [None])[0]
        if user_data:
            return json.loads(user_data)
            
        return None
        
    except Exception as e:
        logger.error(f"Error validating Telegram data: {e}")
        return None

def get_user_from_request() -> Optional[Dict]:
    """Extract and validate user from request headers"""
    init_data = request.headers.get('X-Telegram-Init-Data')
    if not init_data:
        return None
    return validate_telegram_data(init_data)

def require_auth(f):
    """Decorator to require Telegram authentication"""
    def decorated_function(*args, **kwargs):
        user = get_user_from_request()
        if not user:
            return jsonify({'error': 'Authentication required'}), 401
        return f(user, *args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Routes

@miniapp_bp.route('/')
@require_rate_limit
def index():
    """Serve the Mini App interface"""
    return render_template('index.html')

@miniapp_bp.route('/api/user/balance')
@require_auth
def get_user_balance(user):
    """Get user's current balance"""
    try:
        user_id = user['id']
        conn = get_db_connection()
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
            conn.close()

@miniapp_bp.route('/api/user/profile')
@require_auth
def get_user_profile(user):
    """Get user profile information"""
    try:
        user_id = user['id']
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get user data
        cursor.execute("""
            SELECT balance, created_at, total_spent, total_purchases 
            FROM users WHERE user_id = ?
        """, (user_id,))
        user_data = cursor.fetchone()
        
        if not user_data:
            # Create user if doesn't exist
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
            # Convert Row to dict for easier access
            user_data = dict(user_data)
            
            # If created_at is NULL for existing user, set it now
            if not user_data.get('created_at'):
                current_time = datetime.now().isoformat()
                cursor.execute("""
                    UPDATE users SET created_at = ? WHERE user_id = ?
                """, (current_time, user_id))
                conn.commit()
                user_data['created_at'] = current_time
        
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
            conn.close()

# Cache for static data
cities_cache = None
districts_cache = {}

@miniapp_bp.route('/api/cities')
def get_cities():
    """Get all available cities (cached)"""
    global cities_cache
    try:
        if cities_cache is None:
            cities_cache = [{'id': city_id, 'name': city_name} 
                          for city_id, city_name in CITIES.items()]
        return jsonify({'cities': cities_cache})
    except Exception as e:
        logger.error(f"Error getting cities: {e}")
        return jsonify({'error': 'Failed to get cities'}), 500

@miniapp_bp.route('/api/districts/<city_id>')
def get_districts(city_id):
    """Get districts for a specific city (cached)"""
    global districts_cache
    try:
        if city_id not in districts_cache:
            districts = []
            if city_id in DISTRICTS:
                districts = [{'id': dist_id, 'name': dist_name} 
                            for dist_id, dist_name in DISTRICTS[city_id].items()]
            districts_cache[city_id] = districts
        return jsonify({'districts': districts_cache[city_id]})
    except Exception as e:
        logger.error(f"Error getting districts: {e}")
        return jsonify({'error': 'Failed to get districts'}), 500

@miniapp_bp.route('/api/products/<city_id>/<district_id>')
@require_auth
def get_products(user, city_id, district_id):
    """Get products for a specific location"""
    try:
        user_id = user['id']
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # First, get the city and district names from IDs
        cursor.execute("SELECT name FROM cities WHERE id = ?", (city_id,))
        city_row = cursor.fetchone()
        if not city_row:
            return jsonify({'error': 'City not found'}), 404
        city_name = city_row['name']
        
        cursor.execute("SELECT name FROM districts WHERE id = ? AND city_id = ?", (district_id, city_id))
        district_row = cursor.fetchone()
        if not district_row:
            return jsonify({'error': 'District not found'}), 404
        district_name = district_row['name']
        
        # Ultra-optimized query for speed
        cursor.execute("""
            SELECT MIN(p.id) as id, p.product_type, p.size, p.price, p.city, p.district,
                   COUNT(*) as stock_count
            FROM products p
            WHERE p.city = ? AND p.district = ?
              AND p.available = 1
              AND p.reserved = 0
            GROUP BY p.product_type, p.size, p.price
            ORDER BY p.product_type, p.size
            LIMIT 100
        """, (city_name, district_name))
        
        products = []
        for row in cursor.fetchall():
            product_type = row['product_type']
            
            # Get reseller discount
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
        
        return jsonify({'products': products})
        
    except Exception as e:
        logger.error(f"Error getting products: {e}")
        return jsonify({'error': 'Failed to get products'}), 500
    finally:
        if 'conn' in locals() and conn:
            conn.close()

@miniapp_bp.route('/api/basket')
@require_telegram_ip
@require_auth
def get_basket(user):
    """Get user's basket items using modern basket system"""
    try:
        user_id = user['id']
        
        # Use the new modern basket system
        from utils import get_basket_items, get_reseller_discount
        from decimal import Decimal
        
        basket_items = get_basket_items(user_id)
        items = []
        total = Decimal('0.0')
        
        for item in basket_items:
            # Apply reseller discount
            discount_percent = get_reseller_discount(user_id, item['type'])
            original_price = Decimal(str(item['price']))
            discount_amount = (original_price * discount_percent / Decimal('100')).quantize(Decimal('0.01'))
            final_price = original_price - discount_amount
            
            items.append({
                'basket_id': item['basket_id'],
                'product_id': item['product_id'],
                'type': item['type'],
                'size': item['size'],
                'price': float(final_price),
                'city': item['city'],
                'district': item['district'],
                'emoji': item['emoji'],
                'quantity': item['quantity'],
                'added_at': item['added_at']
            })
            total += final_price * item['quantity']
        
        return jsonify({
            'items': items,
            'total': float(total),
            'count': len(items)
        })
        
    except Exception as e:
        logger.error(f"Error getting basket: {e}")
        return jsonify({'error': 'Failed to get basket'}), 500

@miniapp_bp.route('/api/basket/count')
@require_telegram_ip
@require_auth
def get_basket_count(user):
    """Get number of items in basket using modern basket system"""
    try:
        user_id = user['id']
        
        # Use the new modern basket system
        from utils import get_basket_count as get_basket_count_modern
        
        count = get_basket_count_modern(user_id)
        return jsonify({'count': count})
        
    except Exception as e:
        logger.error(f"Error getting basket count: {e}")
        return jsonify({'error': 'Failed to get basket count'}), 500

@miniapp_bp.route('/api/basket/add', methods=['POST'])
@require_telegram_ip
@require_auth
def add_to_basket(user):
    """Add item to basket using modern basket system"""
    try:
        user_id = user['id']
        data = request.get_json()
        product_id = data.get('product_id')
        quantity = data.get('quantity', 1)
        
        if not product_id:
            return jsonify({'error': 'Product ID required'}), 400
        
        if not isinstance(quantity, int) or quantity < 1 or quantity > 100:
            return jsonify({'error': 'Invalid quantity (1-100)'}), 400
        
        # Use the new modern basket system
        from utils import add_to_basket as add_to_basket_modern
        
        success = add_to_basket_modern(user_id, product_id, quantity)
        
        if success:
            return jsonify({'success': True, 'message': 'Item added to basket'})
        else:
            return jsonify({'error': 'Failed to add to basket'}), 500
        
    except Exception as e:
        logger.error(f"Error adding to basket: {e}")
        return jsonify({'error': 'Failed to add to basket'}), 500
        


@miniapp_bp.route('/api/basket/remove', methods=['POST'])
@require_telegram_ip
@require_auth
def remove_from_basket(user):
    """Remove item from basket using modern basket system"""
    try:
        user_id = user['id']
        data = request.get_json()
        basket_item_id = data.get('basket_item_id')
        
        if not basket_item_id:
            return jsonify({'error': 'Basket item ID required'}), 400
        
        # Use the new modern basket system
        from utils import remove_from_basket as remove_from_basket_modern
        
        success = remove_from_basket_modern(basket_item_id)
        
        if success:
            return jsonify({'success': True, 'message': 'Item removed from basket'})
        else:
            return jsonify({'error': 'Failed to remove from basket'}), 500
        
    except Exception as e:
        logger.error(f"Error removing from basket: {e}")
        return jsonify({'error': 'Failed to remove from basket'}), 500


@miniapp_bp.route('/api/basket/update-quantity', methods=['POST'])
@require_telegram_ip
@require_auth
def update_basket_quantity(user):
    """Update quantity of basket item using modern basket system"""
    try:
        user_id = user['id']
        data = request.get_json()
        basket_item_id = data.get('basket_item_id')
        new_quantity = data.get('quantity')
        
        if not basket_item_id:
            return jsonify({'error': 'Basket item ID required'}), 400
        
        if not isinstance(new_quantity, int) or new_quantity < 0 or new_quantity > 100:
            return jsonify({'error': 'Invalid quantity (0-100)'}), 400
        
        # Use the new modern basket system
        from utils import update_basket_quantity as update_basket_quantity_modern
        
        success = update_basket_quantity_modern(basket_item_id, new_quantity)
        
        if success:
            return jsonify({'success': True, 'message': 'Quantity updated successfully'})
        else:
            return jsonify({'error': 'Failed to update quantity'}), 500
        
    except Exception as e:
        logger.error(f"Error updating basket quantity: {e}")
        return jsonify({'error': 'Failed to update quantity'}), 500

@miniapp_bp.route('/api/payment/create', methods=['POST'])
@require_rate_limit
@require_telegram_ip
@require_auth
def create_payment(user):
    """Create NOWPayments invoice for basket or single item"""
    try:
        user_id = user['id']
        data = request.get_json()
        payment_type = data.get('type', 'basket')  # 'basket' or 'single'
        currency = data.get('currency', 'btc')  # Default to BTC
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if payment_type == 'single':
            product_id = data.get('product_id')
            if not product_id:
                return jsonify({'error': 'Product ID required for single payment'}), 400
            
            # Get product details and create single payment
            cursor.execute("""
                SELECT id, product_type, price, city, district, size, name FROM products 
                WHERE id = ? AND available = 1 AND reserved_by IS NULL
            """, (product_id,))
            product = cursor.fetchone()
            
            if not product:
                return jsonify({'error': 'Product not available'}), 400
            
            # Apply reseller discount
            discount_percent = get_reseller_discount(user_id, product['product_type'])
            original_price = Decimal(str(product['price']))
            discount_amount = (original_price * discount_percent / Decimal('100')).quantize(Decimal('0.01'))
            final_price = original_price - discount_amount
            
            # Create basket snapshot for single item
            basket_snapshot = [{
                'product_id': product['id'],
                'product_type': product['product_type'],
                'price': float(original_price),
                'city': product['city'],
                'district': product['district'],
                'size': product['size'],
                'name': product['name']
            }]
            
        else:  # basket payment
            # Get basket items and calculate total
            cursor.execute("SELECT basket FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            
            if not result or not result['basket']:
                return jsonify({'error': 'Basket is empty'}), 400
            
            basket_items = result['basket'].split(',')
            basket_snapshot = []
            final_price = Decimal('0.0')
            
            for item_str in basket_items:
                if ':' in item_str:
                    product_id, timestamp = item_str.split(':', 1)
                    try:
                        product_id = int(product_id)
                        
                        # Get product details
                        cursor.execute("""
                            SELECT id, product_type, price, city, district, size, name
                            FROM products WHERE id = ? AND available = 1
                        """, (product_id,))
                        product = cursor.fetchone()
                        
                        if product:
                            # Apply reseller discount
                            discount_percent = get_reseller_discount(user_id, product['product_type'])
                            original_price = Decimal(str(product['price']))
                            discount_amount = (original_price * discount_percent / Decimal('100')).quantize(Decimal('0.01'))
                            item_price = original_price - discount_amount
                            final_price += item_price
                            
                            basket_snapshot.append({
                                'product_id': product['id'],
                                'product_type': product['product_type'],
                                'price': float(original_price),
                                'city': product['city'],
                                'district': product['district'],
                                'size': product['size'],
                                'name': product['name']
                            })
                    except (ValueError, TypeError):
                        continue
            
            if not basket_snapshot:
                return jsonify({'error': 'No valid items in basket'}), 400
        
        logger.info(f"Creating payment for user {user_id}, amount: {final_price} EUR, currency: {currency}")
        
        # Import the payment creation function from the bot
        import asyncio
        from payment import create_nowpayments_payment
        
        # Create the NOWPayments invoice
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            payment_result = loop.run_until_complete(
                create_nowpayments_payment(
                    user_id=user_id,
                    target_eur_amount=final_price,
                    pay_currency_code=currency,
                    is_purchase=True,
                    basket_snapshot=basket_snapshot
                )
            )
            logger.info(f"Payment creation result: {payment_result}")
        except Exception as e:
            logger.error(f"Exception during payment creation: {e}", exc_info=True)
            return jsonify({'error': f'Payment creation failed: {str(e)}'}), 500
        finally:
            loop.close()
        
        if 'error' in payment_result:
            error_msg = payment_result.get('error', 'Payment creation failed')
            logger.error(f"Payment creation error: {error_msg}")
            return jsonify({'error': error_msg}), 400
        
        # Return the payment invoice details
        return jsonify({
            'success': True,
            'payment_id': payment_result['payment_id'],
            'pay_address': payment_result['pay_address'],
            'pay_amount': payment_result['pay_amount'],
            'pay_currency': payment_result['pay_currency'].upper(),
            'price_amount': float(final_price),
            'price_currency': 'EUR',
            'order_id': payment_result['order_id'],
            'expiration_estimate_date': payment_result.get('expiration_estimate_date'),
            'payment_status': payment_result['payment_status'],
            'message': 'Payment invoice created successfully'
        })
        
    except Exception as e:
        logger.error(f"Error creating payment: {e}")
        return jsonify({'error': 'Failed to create payment'}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@miniapp_bp.route('/api/payment/currencies')
@require_telegram_ip
def get_payment_currencies():
    """Get available payment currencies"""
    try:
        # Define supported currencies directly (matching the bot's currencies)
        currencies = [
            {'code': 'btc', 'name': 'Bitcoin', 'network': '', 'symbol': 'BTC'},
            {'code': 'eth', 'name': 'Ethereum', 'network': 'ERC20', 'symbol': 'ETH'},
            {'code': 'ltc', 'name': 'Litecoin', 'network': '', 'symbol': 'LTC'},
            {'code': 'usdt', 'name': 'USDT', 'network': 'TRC20', 'symbol': 'USDT'},
            {'code': 'usdttrc20', 'name': 'USDT', 'network': 'TRC20', 'symbol': 'USDT'},
            {'code': 'usdterc20', 'name': 'USDT', 'network': 'ERC20', 'symbol': 'USDT'},
            {'code': 'ton', 'name': 'TON', 'network': 'TON', 'symbol': 'TON'},
        ]
        
        return jsonify({'currencies': currencies})
    except Exception as e:
        logger.error(f"Error getting currencies: {e}")
        return jsonify({'error': 'Failed to get currencies'}), 500


@miniapp_bp.route('/api/admin-messages')
@require_telegram_ip
def get_admin_messages():
    """Get active admin messages for display in mini-app"""
    try:
        from utils import get_active_admin_messages
        messages = get_active_admin_messages()
        return jsonify({'messages': messages})
    except Exception as e:
        logger.error(f"Error getting admin messages: {e}")
        return jsonify({'error': 'Failed to get admin messages'}), 500


@miniapp_bp.route('/api/promo-banners')
@require_telegram_ip
def get_promo_banners():
    """Get active promotional banners for display in mini-app"""
    try:
        from utils import get_active_promo_banners
        banners = get_active_promo_banners()
        return jsonify({'banners': banners})
    except Exception as e:
        logger.error(f"Error getting promotional banners: {e}")
        return jsonify({'error': 'Failed to get promotional banners'}), 500

@miniapp_bp.route('/api/payment/refill', methods=['POST'])
@require_telegram_ip
@require_auth
def create_refill_payment(user):
    """Create payment for balance refill"""
    try:
        user_id = user['id']
        data = request.get_json()
        amount = data.get('amount')
        currency = data.get('currency', 'btc')  # Default to BTC
        
        if not amount or amount < float(MIN_DEPOSIT_EUR):
            return jsonify({'error': f'Minimum refill amount is €{MIN_DEPOSIT_EUR}'}), 400
        
        if amount > 10000:
            return jsonify({'error': 'Maximum refill amount is €10,000'}), 400
        
        # Create NOWPayments invoice for refill
        import asyncio
        from payment import create_nowpayments_payment
        from decimal import Decimal
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            payment_result = loop.run_until_complete(
                create_nowpayments_payment(
                    user_id=user_id,
                    target_eur_amount=Decimal(str(amount)),
                    pay_currency_code=currency,
                    is_purchase=False  # This is a refill
                )
            )
            logger.info(f"Refill payment creation result: {payment_result}")
        except Exception as e:
            logger.error(f"Exception during refill payment creation: {e}", exc_info=True)
            return jsonify({'error': f'Payment creation failed: {str(e)}'}), 500
        finally:
            loop.close()
        
        if 'error' in payment_result:
            error_msg = payment_result.get('error', 'Payment creation failed')
            logger.error(f"Refill payment creation error: {error_msg}")
            return jsonify({'error': error_msg}), 400
        
        # Return the payment invoice details
        return jsonify({
            'success': True,
            'payment_id': payment_result['payment_id'],
            'pay_address': payment_result['pay_address'],
            'pay_amount': payment_result['pay_amount'],
            'pay_currency': payment_result['pay_currency'].upper(),
            'price_amount': float(amount),
            'price_currency': 'EUR',
            'order_id': payment_result['order_id'],
            'expiration_estimate_date': payment_result.get('expiration_estimate_date'),
            'payment_status': payment_result['payment_status'],
            'message': 'Refill payment invoice created successfully'
        })
        
    except Exception as e:
        logger.error(f"Error creating refill payment: {e}")
        return jsonify({'error': 'Failed to create refill payment'}), 500

@miniapp_bp.route('/api/reviews', methods=['GET'])
@require_telegram_ip
def get_reviews():
    """Get all reviews"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("""
            SELECT r.*, u.username, u.first_name, u.last_name 
            FROM reviews r 
            LEFT JOIN users u ON r.user_id = u.user_id 
            WHERE r.is_active = 1 
            ORDER BY r.created_at DESC 
            LIMIT 50
        """)
        reviews = []
        for row in c.fetchall():
            reviews.append({
                'id': row['id'],
                'rating': row['rating'],
                'text': row['text'],
                'author_name': row['first_name'] or row['username'] or 'Anonymous',
                'created_at': row['created_at']
            })
        return jsonify({'reviews': reviews})
    except Exception as e:
        logger.error(f"Error fetching reviews: {e}")
        return jsonify({'error': 'Failed to load reviews'}), 500
    finally:
        if conn:
            conn.close()

@miniapp_bp.route('/api/reviews', methods=['POST'])
@require_telegram_ip
@require_auth
def create_review(user):
    """Create a new review"""
    data = request.get_json()
    rating = data.get('rating')
    text = data.get('text')

    if not rating or not text or rating < 1 or rating > 5:
        return jsonify({'error': 'Invalid review data'}), 400

    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("""
            INSERT INTO reviews (user_id, rating, text, created_at, is_active) 
            VALUES (?, ?, ?, datetime('now'), 1)
        """, (user['id'], rating, text))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error creating review: {e}")
        return jsonify({'error': 'Failed to submit review'}), 500
    finally:
        if conn:
            conn.close()

@miniapp_bp.route('/api/pricelist')
@miniapp_bp.route('/api/pricelist/<city_id>')
@require_telegram_ip
def get_price_list(city_id=None):
    """Get price list for all cities or specific city"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        if city_id:
            c.execute("""
                SELECT p.*, pt.name as type_name, pt.emoji as type_emoji
                FROM products p
                JOIN product_types pt ON p.type_id = pt.id
                JOIN districts d ON p.district_id = d.id
                JOIN cities c ON d.city_id = c.id
                WHERE c.id = ? AND p.is_active = 1
                ORDER BY pt.name, p.name
            """, (city_id,))
        else:
            c.execute("""
                SELECT p.*, pt.name as type_name, pt.emoji as type_emoji, c.name as city_name
                FROM products p
                JOIN product_types pt ON p.type_id = pt.id
                JOIN districts d ON p.district_id = d.id
                JOIN cities c ON d.city_id = c.id
                WHERE p.is_active = 1
                ORDER BY c.name, pt.name, p.name
            """)
        
        prices = []
        for row in c.fetchall():
            prices.append({
                'id': row['id'],
                'name': row['name'],
                'price': float(row['price']),
                'category': row['type_name'],
                'city': row.get('city_name', '')
            })
        
        return jsonify({'prices': prices})
    except Exception as e:
        logger.error(f"Error fetching price list: {e}")
        return jsonify({'error': 'Failed to load price list'}), 500
    finally:
        if conn:
            conn.close()

@miniapp_bp.route('/api/user/language', methods=['POST'])
@require_telegram_ip
@require_auth
def update_user_language(user):
    """Update user language preference"""
    data = request.get_json()
    language = data.get('language')
    
    if not language or language not in LANGUAGES:
        return jsonify({'error': 'Invalid language'}), 400

    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE users SET language = ? WHERE user_id = ?", (language, user['id']))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error updating user language: {e}")
        return jsonify({'error': 'Failed to update language'}), 500
    finally:
        if conn:
            conn.close()

@miniapp_bp.route('/api/discount/apply', methods=['POST'])
@require_telegram_ip
@require_auth
def apply_discount(user):
    """Apply discount code"""
    data = request.get_json()
    code = data.get('code')
    
    if not code:
        return jsonify({'error': 'Discount code required'}), 400

    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("""
            SELECT * FROM discount_codes 
            WHERE code = ? AND is_active = 1 AND (expires_at IS NULL OR expires_at > datetime('now'))
        """, (code,))
        discount = c.fetchone()
        
        if not discount:
            return jsonify({'error': 'Invalid or expired discount code'}), 400
        
        # Check if user already used this code
        c.execute("""
            SELECT COUNT(*) as used_count FROM user_discounts 
            WHERE user_id = ? AND discount_code_id = ?
        """, (user['id'], discount['id']))
        used = c.fetchone()
        
        if used['used_count'] > 0:
            return jsonify({'error': 'You have already used this discount code'}), 400
        
        # Apply discount to user
        c.execute("""
            INSERT INTO user_discounts (user_id, discount_code_id, applied_at) 
            VALUES (?, ?, datetime('now'))
        """, (user['id'], discount['id']))
        conn.commit()
        
        return jsonify({
            'success': True,
            'discount_value': discount['discount_percent'],
            'message': f'{discount["discount_percent"]}% discount applied!'
        })
    except Exception as e:
        logger.error(f"Error applying discount: {e}")
        return jsonify({'error': 'Failed to apply discount'}), 500
    finally:
        if conn:
            conn.close()

@miniapp_bp.route('/api/user/newsletter', methods=['POST'])
@require_telegram_ip
@require_auth
def update_newsletter_preference(user):
    """Update user newsletter preference"""
    data = request.get_json()
    enabled = data.get('enabled', False)

    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE users SET newsletter_enabled = ? WHERE user_id = ?", (1 if enabled else 0, user['id']))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error updating newsletter preference: {e}")
        return jsonify({'error': 'Failed to update newsletter preference'}), 500
    finally:
        if conn:
            conn.close()

@miniapp_bp.route('/api/user/settings')
@require_telegram_ip
@require_auth
def get_user_settings(user):
    """Get user settings"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT language, newsletter_enabled FROM users WHERE user_id = ?", (user['id'],))
        user_data = c.fetchone()
        
        return jsonify({
            'language': user_data['language'] if user_data else 'en',
            'newsletter_enabled': bool(user_data['newsletter_enabled']) if user_data else False
        })
    except Exception as e:
        logger.error(f"Error fetching user settings: {e}")
        return jsonify({'error': 'Failed to load settings'}), 500
    finally:
        if conn:
            conn.close()

@miniapp_bp.route('/api/payment/status/<payment_id>')
@require_telegram_ip
@require_auth
def check_payment_status_endpoint(user, payment_id):
    """Check payment status and process if completed"""
    try:
        user_id = user['id']
        
        # Import required modules
        import asyncio
        from payment import check_and_process_payment_status
        from telegram.ext import ContextTypes
        
        # Create dummy context for processing
        dummy_context = ContextTypes.DEFAULT_TYPE(application=None, chat_id=user_id, user_id=user_id)
        
        # Check and process payment status
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                check_and_process_payment_status(payment_id, dummy_context)
            )
        finally:
            loop.close()
        
        if 'error' in result:
            return jsonify({'error': result['error'], 'details': result.get('details')}), 400
        
        return jsonify({
            'success': True,
            'payment_id': payment_id,
            'status': result.get('status'),
            'processed': result.get('processed', False),
            'type': result.get('type')
        })
        
    except Exception as e:
        logger.error(f"Error checking payment status: {e}")
        return jsonify({'error': 'Failed to check payment status'}), 500

# Error handlers for the blueprint
@miniapp_bp.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@miniapp_bp.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500
