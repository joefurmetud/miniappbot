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
            # If created_at is NULL for existing user, set it now
            if not user_data.get('created_at'):
                current_time = datetime.now().isoformat()
                cursor.execute("""
                    UPDATE users SET created_at = ? WHERE user_id = ?
                """, (current_time, user_id))
                conn.commit()
                user_data = dict(user_data)  # Convert Row to dict
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

@miniapp_bp.route('/api/cities')
def get_cities():
    """Get all available cities"""
    try:
        cities = [{'id': city_id, 'name': city_name} 
                 for city_id, city_name in CITIES.items()]
        return jsonify({'cities': cities})
    except Exception as e:
        logger.error(f"Error getting cities: {e}")
        return jsonify({'error': 'Failed to get cities'}), 500

@miniapp_bp.route('/api/districts/<city_id>')
def get_districts(city_id):
    """Get districts for a specific city"""
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
        
        # Get products with stock count using the actual names
        cursor.execute("""
            SELECT p.id, p.product_type, p.size, p.price, p.city, p.district,
                   COUNT(CASE WHEN p.reserved = 0 AND p.available = 1 THEN 1 END) as stock_count
            FROM products p
            WHERE p.city = ? AND p.district = ?
            GROUP BY p.product_type, p.size, p.price, p.city, p.district
            HAVING stock_count > 0
            ORDER BY p.product_type, p.size
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
@require_auth
def get_basket(user):
    """Get user's basket items"""
    try:
        user_id = user['id']
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get user's basket
        cursor.execute("SELECT basket FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        
        if not result or not result['basket']:
            return jsonify({'items': [], 'total': 0.0})
        
        basket_str = result['basket']
        items = []
        total = Decimal('0.0')
        
        for item_str in basket_str.split(','):
            if ':' in item_str:
                product_id, timestamp = item_str.split(':', 1)
                try:
                    product_id = int(product_id)
                    
                    # Get product details
                    cursor.execute("""
                        SELECT product_type, size, price, city, district
                        FROM products WHERE id = ?
                    """, (product_id,))
                    product = cursor.fetchone()
                    
                    if product:
                        # Apply reseller discount
                        discount_percent = get_reseller_discount(user_id, product['product_type'])
                        original_price = Decimal(str(product['price']))
                        discount_amount = (original_price * discount_percent / Decimal('100')).quantize(Decimal('0.01'))
                        final_price = original_price - discount_amount
                        
                        items.append({
                            'id': product_id,
                            'type': product['product_type'],
                            'size': product['size'],
                            'price': float(final_price),
                            'city': product['city'],
                            'district': product['district'],
                            'emoji': PRODUCT_TYPES.get(product['product_type'], DEFAULT_PRODUCT_EMOJI),
                            'timestamp': timestamp
                        })
                        total += final_price
                        
                except (ValueError, TypeError):
                    continue
        
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
            conn.close()

@miniapp_bp.route('/api/basket/count')
@require_auth
def get_basket_count(user):
    """Get number of items in basket"""
    try:
        user_id = user['id']
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT basket FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        
        count = 0
        if result and result['basket']:
            items = [item for item in result['basket'].split(',') if ':' in item]
            count = len(items)
        
        return jsonify({'count': count})
        
    except Exception as e:
        logger.error(f"Error getting basket count: {e}")
        return jsonify({'error': 'Failed to get basket count'}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@miniapp_bp.route('/api/basket/add', methods=['POST'])
@require_auth
def add_to_basket(user):
    """Add item to basket"""
    try:
        user_id = user['id']
        data = request.get_json()
        product_id = data.get('product_id')
        
        if not product_id:
            return jsonify({'error': 'Product ID required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if product is available
        cursor.execute("""
            SELECT id FROM products 
            WHERE id = ? AND reserved_by IS NULL
            LIMIT 1
        """, (product_id,))
        
        available_product = cursor.fetchone()
        if not available_product:
            return jsonify({'error': 'Product not available'}), 400
        
        # Reserve the product
        cursor.execute("""
            UPDATE products SET reserved_by = ?, reserved_at = ?
            WHERE id = ?
        """, (user_id, time.time(), available_product['id']))
        
        # Add to user's basket
        cursor.execute("SELECT basket FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        
        current_basket = result['basket'] if result and result['basket'] else ''
        new_item = f"{available_product['id']}:{time.time()}"
        new_basket = f"{current_basket},{new_item}" if current_basket else new_item
        
        cursor.execute("UPDATE users SET basket = ? WHERE user_id = ?", (new_basket, user_id))
        conn.commit()
        
        return jsonify({'success': True, 'message': 'Item added to basket'})
        
    except Exception as e:
        logger.error(f"Error adding to basket: {e}")
        return jsonify({'error': 'Failed to add to basket'}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@miniapp_bp.route('/api/basket/remove', methods=['POST'])
@require_auth
def remove_from_basket(user):
    """Remove item from basket"""
    try:
        user_id = user['id']
        data = request.get_json()
        item_id = data.get('item_id')
        
        if not item_id:
            return jsonify({'error': 'Item ID required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get current basket
        cursor.execute("SELECT basket FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        
        if not result or not result['basket']:
            return jsonify({'error': 'Basket is empty'}), 400
        
        # Remove item from basket
        items = result['basket'].split(',')
        new_items = [item for item in items if not item.startswith(f"{item_id}:")]
        
        if len(new_items) == len(items):
            return jsonify({'error': 'Item not found in basket'}), 400
        
        # Unreserve the product
        cursor.execute("""
            UPDATE products SET reserved_by = NULL, reserved_at = NULL
            WHERE id = ? AND reserved_by = ?
        """, (item_id, user_id))
        
        # Update basket
        new_basket = ','.join(new_items) if new_items else ''
        cursor.execute("UPDATE users SET basket = ? WHERE user_id = ?", (new_basket, user_id))
        conn.commit()
        
        return jsonify({'success': True, 'message': 'Item removed from basket'})
        
    except Exception as e:
        logger.error(f"Error removing from basket: {e}")
        return jsonify({'error': 'Failed to remove from basket'}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@miniapp_bp.route('/api/payment/create', methods=['POST'])
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
        finally:
            loop.close()
        
        if 'error' in payment_result:
            error_msg = payment_result.get('error', 'Payment creation failed')
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
def get_payment_currencies():
    """Get available payment currencies"""
    try:
        # Import the currency mapping from the bot
        from user import SUPPORTED_CURRENCIES
        
        currencies = []
        for code, info in SUPPORTED_CURRENCIES.items():
            currencies.append({
                'code': code,
                'name': info['name'],
                'network': info.get('network', ''),
                'symbol': code.upper()
            })
        
        return jsonify({'currencies': currencies})
    except Exception as e:
        logger.error(f"Error getting currencies: {e}")
        return jsonify({'error': 'Failed to get currencies'}), 500

@miniapp_bp.route('/api/payment/refill', methods=['POST'])
@require_auth
def create_refill_payment(user):
    """Create payment for balance refill"""
    try:
        user_id = user['id']
        data = request.get_json()
        amount = data.get('amount')
        
        if not amount or amount < float(MIN_DEPOSIT_EUR):
            return jsonify({'error': f'Minimum refill amount is €{MIN_DEPOSIT_EUR}'}), 400
        
        # Create refill payment URL (simplified)
        payment_url = f"https://t.me/your_bot?start=refill_{user_id}_{amount}"
        
        return jsonify({
            'success': True,
            'payment_url': payment_url,
            'message': 'Refill payment created successfully'
        })
        
    except Exception as e:
        logger.error(f"Error creating refill payment: {e}")
        return jsonify({'error': 'Failed to create refill payment'}), 500

# Error handlers for the blueprint
@miniapp_bp.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@miniapp_bp.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500
