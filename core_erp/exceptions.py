"""
Core ERP - Custom Exception Classes

This module defines custom exception classes for the ERP system.
Provides granular error handling and better debugging capabilities.

Author: ERP Development Team
Created: 2026-02-04
"""

from typing import Optional, Dict, Any


class ERPBaseException(Exception):
    """
    Base exception for all ERP-related errors.
    
    All custom exceptions should inherit from this class.
    """
    
    def __init__(
        self, 
        message: str, 
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize ERP base exception.
        
        Args:
            message: Human-readable error message
            code: Optional error code for programmatic handling
            details: Optional dictionary with additional error context
        """
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)
    
    def __str__(self) -> str:
        """String representation of the exception."""
        if self.details:
            return f"{self.code}: {self.message} | Details: {self.details}"
        return f"{self.code}: {self.message}"


# ==================== INVENTORY EXCEPTIONS ====================

class InventoryException(ERPBaseException):
    """Base exception for inventory-related errors."""
    pass


class InsufficientStockError(InventoryException):
    """Raised when trying to use more stock than available."""
    
    def __init__(
        self, 
        ingredient_name: str, 
        required: float, 
        available: float
    ) -> None:
        """
        Initialize insufficient stock error.
        
        Args:
            ingredient_name: Name of the ingredient
            required: Quantity required
            available: Quantity available
        """
        message = (
            f"Insufficient stock for '{ingredient_name}'. "
            f"Required: {required}, Available: {available}"
        )
        details = {
            'ingredient': ingredient_name,
            'required': required,
            'available': available,
            'shortage': required - available
        }
        super().__init__(message, code='INSUFFICIENT_STOCK', details=details)


class InvalidStockQuantityError(InventoryException):
    """Raised when stock quantity is invalid (negative, etc)."""
    pass


# ==================== PRODUCTION EXCEPTIONS ====================

class ProductionException(ERPBaseException):
    """Base exception for production-related errors."""
    pass


class InvalidBOMError(ProductionException):
    """Raised when Bill of Materials is invalid."""
    pass


class ProductionOrderError(ProductionException):
    """Raised when production order operation fails."""
    pass


# ==================== SALES EXCEPTIONS ====================

class SalesException(ERPBaseException):
    """Base exception for sales-related errors."""
    pass


class InvalidSaleError(SalesException):
    """Raised when sale data is invalid."""
    pass


class CustomerValidationError(SalesException):
    """Raised when customer data validation fails."""
    pass


class DuplicateCustomerError(SalesException):
    """Raised when attempting to create duplicate customer."""
    
    def __init__(self, dedup_key: str) -> None:
        """
        Initialize duplicate customer error.
        
        Args:
            dedup_key: The duplicate deduplication key
        """
        message = f"Customer with dedup_key '{dedup_key}' already exists"
        super().__init__(message, code='DUPLICATE_CUSTOMER', 
                        details={'dedup_key': dedup_key})


# ==================== FINANCE EXCEPTIONS ====================

class FinanceException(ERPBaseException):
    """Base exception for finance-related errors."""
    pass


class InvalidTransactionError(FinanceException):
    """Raised when financial transaction is invalid."""
    pass


class InsufficientFundsError(FinanceException):
    """Raised when account has insufficient funds."""
    
    def __init__(
        self, 
        account_name: str, 
        required: float, 
        available: float
    ) -> None:
        """
        Initialize insufficient funds error.
        
        Args:
            account_name: Name of the account
            required: Amount required
            available: Amount available
        """
        message = (
            f"Insufficient funds in '{account_name}'. "
            f"Required: ${required:.2f}, Available: ${available:.2f}"
        )
        details = {
            'account': account_name,
            'required': required,
            'available': available,
            'shortage': required - available
        }
        super().__init__(message, code='INSUFFICIENT_FUNDS', details=details)


# ==================== LOGISTICS EXCEPTIONS ====================

class LogisticsException(ERPBaseException):
    """Base exception for logistics-related errors."""
    pass


class InvalidRouteError(LogisticsException):
    """Raised when delivery route is invalid."""
    pass


class VehicleCapacityError(LogisticsException):
    """Raised when vehicle capacity is exceeded."""
    
    def __init__(
        self, 
        vehicle_name: str, 
        capacity: float, 
        attempted_load: float
    ) -> None:
        """
        Initialize vehicle capacity error.
        
        Args:
            vehicle_name: Name of the vehicle
            capacity: Vehicle capacity
            attempted_load: Attempted load amount
        """
        message = (
            f"Vehicle '{vehicle_name}' capacity exceeded. "
            f"Capacity: {capacity}, Attempted: {attempted_load}"
        )
        details = {
            'vehicle': vehicle_name,
            'capacity': capacity,
            'attempted_load': attempted_load,
            'excess': attempted_load - capacity
        }
        super().__init__(message, code='CAPACITY_EXCEEDED', details=details)


# ==================== VALIDATION EXCEPTIONS ====================

class ValidationException(ERPBaseException):
    """Base exception for data validation errors."""
    pass


class RequiredFieldError(ValidationException):
    """Raised when required field is missing."""
    
    def __init__(self, field_name: str, model_name: str) -> None:
        """
        Initialize required field error.
        
        Args:
            field_name: Name of the missing field
            model_name: Name of the model
        """
        message = f"Required field '{field_name}' missing in {model_name}"
        super().__init__(message, code='REQUIRED_FIELD_MISSING',
                        details={'field': field_name, 'model': model_name})


class InvalidDataTypeError(ValidationException):
    """Raised when data type is invalid."""
    pass


# ==================== SYSTEM EXCEPTIONS ====================

class SystemException(ERPBaseException):
    """Base exception for system-level errors."""
    pass


class ConfigurationError(SystemException):
    """Raised when system configuration is invalid."""
    pass


class DatabaseError(SystemException):
    """Raised when database operation fails."""
    pass
