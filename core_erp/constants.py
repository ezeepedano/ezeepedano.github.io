"""
Core ERP - System Constants

This module contains all system-wide constants to avoid magic numbers
and improve code maintainability.

Author: ERP Development Team
Created: 2026-02-04
"""

from decimal import Decimal


# ==================== SYSTEM CONSTANTS ====================

# Pagination
DEFAULT_PAGE_SIZE: int = 20
MAX_PAGE_SIZE: int = 100

# Date/Time
DATE_FORMAT: str = "%Y-%m-%d"
DATETIME_FORMAT: str = "%Y-%m-%d %H:%M:%S"
TIMEZONE: str = "America/Argentina/Buenos_Aires"

# Currency
DEFAULT_CURRENCY: str = "ARS"
DECIMAL_PLACES: int = 2


# ====================INVENTORY CONSTANTS ====================

# Stock Management
LOW_STOCK_THRESHOLD: Decimal = Decimal('10.00')
CRITICAL_STOCK_THRESHOLD: Decimal = Decimal('5.00')
DEFAULT_STOCK_QUANTITY: Decimal = Decimal('0.00')

# Unit Types
UNIT_TYPES = {
    'WEIGHT': ['kg', 'g', 'mg', 'lb', 'oz'],
    'VOLUME': ['l', 'ml', 'gal'],
    'COUNT': ['unit', 'pcs', 'box', 'pack'],
}

# Ingredient Types
INGREDIENT_TYPE_RAW_MATERIAL: str = 'raw_material'
INGREDIENT_TYPE_SUPPLY: str = 'supply'
INGREDIENT_TYPE_PACKAGING: str = 'packaging'

INGREDIENT_TYPES = [
    INGREDIENT_TYPE_RAW_MATERIAL,
    INGREDIENT_TYPE_SUPPLY,
    INGREDIENT_TYPE_PACKAGING,
]


# ==================== PRODUCTION CONSTANTS ====================

# Production Order Status
PRODUCTION_STATUS_PENDING: str = 'PENDIENTE'
PRODUCTION_STATUS_IN_PROGRESS: str = 'EN_PROCESO'
PRODUCTION_STATUS_COMPLETED: str = 'COMPLETADO'
PRODUCTION_STATUS_CANCELLED: str = 'CANCELADO'

PRODUCTION_STATUSES = [
    PRODUCTION_STATUS_PENDING,
    PRODUCTION_STATUS_IN_PROGRESS,
    PRODUCTION_STATUS_COMPLETED,
    PRODUCTION_STATUS_CANCELLED,
]

# BOM Defaults
DEFAULT_BOM_QUANTITY: Decimal = Decimal('1.00')
DEFAULT_SCRAP_FACTOR: Decimal = Decimal('0.00')
MAX_SCRAP_FACTOR: Decimal = Decimal('50.00')  # 50%


# ==================== SALES CONSTANTS ====================

# Sale Status
SALE_STATUS_PENDING: str = 'PENDIENTE'
SALE_STATUS_CONFIRMED: str = 'CONFIRMADO'
SALE_STATUS_PAID: str = 'PAID'
SALE_STATUS_DELIVERED: str = 'delivered'
SALE_STATUS_CANCELLED: str = 'cancelled'

SALE_STATUSES = [
    SALE_STATUS_PENDING,
    SALE_STATUS_CONFIRMED,
    SALE_STATUS_PAID,
    SALE_STATUS_DELIVERED,
    SALE_STATUS_CANCELLED,
]

# Payment Status
PAYMENT_STATUS_PENDING: str = 'PENDING'
PAYMENT_STATUS_PARTIAL: str = 'PARTIAL'
PAYMENT_STATUS_PAID: str = 'PAID'

PAYMENT_STATUSES = [
    PAYMENT_STATUS_PENDING,
    PAYMENT_STATUS_PARTIAL,
    PAYMENT_STATUS_PAID,
]

# Customer Segments
CUSTOMER_SEGMENT_NEW: str = 'NEW'
CUSTOMER_SEGMENT_ACTIVE: str = 'ACTIVE'
CUSTOMER_SEGMENT_REGULAR: str = 'Regular'
CUSTOMER_SEGMENT_VIP: str = 'VIP'
CUSTOMER_SEGMENT_LOYAL: str = 'LOYAL'
CUSTOMER_SEGMENT_DORMANT: str = 'DORMANT'

CUSTOMER_SEGMENTS = [
    CUSTOMER_SEGMENT_NEW,
    CUSTOMER_SEGMENT_ACTIVE,
    CUSTOMER_SEGMENT_REGULAR,
    CUSTOMER_SEGMENT_VIP,
    CUSTOMER_SEGMENT_LOYAL,
    CUSTOMER_SEGMENT_DORMANT,
]

# Customer Thresholds
CUSTOMER_VIP_THRESHOLD: Decimal = Decimal('100000.00')  # 100k ARS
CUSTOMER_LOYAL_MIN_SALES: int = 5
CUSTOMER_LOYAL_MAX_DAYS: int = 90
CUSTOMER_DORMANT_DAYS: int = 180


# ==================== FINANCE CONSTANTS ====================

# Account Types
ACCOUNT_TYPE_BANK: str = 'BANK'
ACCOUNT_TYPE_CASH: str = 'CASH'
ACCOUNT_TYPE_WALLET: str = 'WALLET'

ACCOUNT_TYPES = [
    ACCOUNT_TYPE_BANK,
    ACCOUNT_TYPE_CASH,
    ACCOUNT_TYPE_WALLET,
]

# Movement Types
MOVEMENT_TYPE_IN: str = 'IN'
MOVEMENT_TYPE_OUT: str = 'OUT'

MOVEMENT_TYPES = [
    MOVEMENT_TYPE_IN,
    MOVEMENT_TYPE_OUT,
]

# Tax Rates
TAX_RATE_IVA: Decimal = Decimal('1.21')  # 21% IVA
TAX_RATE_IVA_PERCENTAGE: Decimal = Decimal('21.00')
TAX_THRESHOLD: Decimal = Decimal('100.00')  # Minimum for tax suggestion


# ==================== LOGISTICS CONSTANTS ====================

# Vehicle Status
VEHICLE_STATUS_AVAILABLE: str = 'AVAILABLE'
VEHICLE_STATUS_IN_USE: str = 'IN_USE'
VEHICLE_STATUS_MAINTENANCE: str = 'MAINTENANCE'

VEHICLE_STATUSES = [
    VEHICLE_STATUS_AVAILABLE,
    VEHICLE_STATUS_IN_USE,
    VEHICLE_STATUS_MAINTENANCE,
]

# Route Status
ROUTE_STATUS_DRAFT: str = 'DRAFT'
ROUTE_STATUS_PLANNED: str = 'PLANNED'
ROUTE_STATUS_IN_PROGRESS: str = 'IN_PROGRESS'
ROUTE_STATUS_COMPLETED: str = 'COMPLETED'

ROUTE_STATUSES = [
    ROUTE_STATUS_DRAFT,
    ROUTE_STATUS_PLANNED,
    ROUTE_STATUS_IN_PROGRESS,
    ROUTE_STATUS_COMPLETED,
]


# ==================== VALIDATION CONSTANTS ====================

# String Lengths
MAX_NAME_LENGTH: int = 255
MAX_CODE_LENGTH: int = 100
MAX_SKU_LENGTH: int = 100
MAX_EMAIL_LENGTH: int = 254
MAX_PHONE_LENGTH: int = 20
MAX_ADDRESS_LENGTH: int = 500
MAX_DESCRIPTION_LENGTH: int = 1000

# Numeric Limits
MAX_DECIMAL_DIGITS: int = 12
MAX_QUANTITY: Decimal = Decimal('999999.9999')
MIN_QUANTITY: Decimal = Decimal('0.0000')
MAX_PRICE: Decimal = Decimal('999999999.99')
MIN_PRICE: Decimal = Decimal('0.00')


# ==================== PERFORMANCE CONSTANTS ====================

# Query Optimization
BULK_CREATE_BATCH_SIZE: int = 1000
PREFETCH_BATCH_SIZE: int = 100

# Caching
CACHE_TIMEOUT_SHORT: int = 300  # 5 minutes
CACHE_TIMEOUT_MEDIUM: int = 1800  # 30 minutes
CACHE_TIMEOUT_LONG: int = 3600  # 1 hour
CACHE_TIMEOUT_DAY: int = 86400  # 24 hours


# ==================== SECURITY CONSTANTS ====================

# Rate Limiting
RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
RATE_LIMIT_REQUESTS_PER_HOUR: int = 1000

# Password
MIN_PASSWORD_LENGTH: int = 8
PASSWORD_REQUIRE_UPPERCASE: bool = True
PASSWORD_REQUIRE_LOWERCASE: bool = True
PASSWORD_REQUIRE_DIGIT: bool = True
PASSWORD_REQUIRE_SPECIAL: bool = False

# Session
SESSION_COOKIE_AGE: int = 86400  # 24 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE: bool = False


# ==================== Logging Constants ====================

# Log Levels
LOG_LEVEL_DEBUG: str = 'DEBUG'
LOG_LEVEL_INFO: str = 'INFO'
LOG_LEVEL_WARNING: str = 'WARNING'
LOG_LEVEL_ERROR: str = 'ERROR'
LOG_LEVEL_CRITICAL: str = 'CRITICAL'

# Log Format
LOG_FORMAT: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT: str = '%Y-%m-%d %H:%M:%S'
