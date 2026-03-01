# ERP System - API Documentation

## Table of Contents

- [Overview](#overview)
- [Authentication](#authentication)
- [Inventory API](#inventory-api)
- [Production API](#production-api)
- [Sales API](#sales-api)
- [Finance API](#finance-api)
- [Logistics API](#logistics-api)
- [Error Handling](#error-handling)

---

## Overview

The ERP System provides a RESTful API for managing all business operations including inventory, production, sales, finance, and logistics.

**Base URL**: `http://localhost:8000/api/v1/`  
**Content-Type**: `application/json`  
**Authentication**: Django Session Authentication / Token Authentication

---

## Authentication

### Login

**Endpoint**: `POST /api/auth/login/`

**Request**:
```json
{
  "username": "user@example.com",
  "password": "secure_password"
}
```

**Response** (200 OK):
```json
{
  "token": "your-auth-token-here",
  "user": {
    "id": 1,
    "username": "user@example.com",
    "email": "user@example.com"
  }
}
```

### Logout

**Endpoint**: `POST /api/auth/logout/`

**Response** (204 No Content)

---

## Inventory API

### Categories

#### List Categories

**Endpoint**: `GET /api/inventory/categories/`

**Response** (200 OK):
```json
{
  "count": 10,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "name": "Supplements",
      "description": "Health supplements",
      "created_at": "2026-02-04T10:00:00Z"
    }
  ]
}
```

#### Create Category

**Endpoint**: `POST /api/inventory/categories/`

**Request**:
```json
{
  "name": "Vitamins",
  "description": "Vitamin supplements"
}
```

**Response** (201 Created):
```json
{
  "id": 2,
  "name": "Vitamins",
  "description": "Vitamin supplements",
  "created_at": "2026-02-04T14:00:00Z"
}
```

### Ingredients

#### List Ingredients

**Endpoint**: `GET /api/inventory/ingredients/`

**Query Parameters**:
- `search`: Filter by name
- `ingredient_type`: Filter by type (raw_material, supply, packaging)
- `ordering`: Sort by field (name, code, stock_quantity)

**Response** (200 OK):
```json
{
  "count": 50,
  "next": "http://localhost:8000/api/inventory/ingredients/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "code": "MGS",
      "name": "Magnesium Citrate",
      "ingredient_type": "raw_material",
      "unit": "kg",
      "stock_quantity": "100.500",
      "cost_per_unit": "150.00",
      "min_stock": "10.000",
      "created_at": "2026-01-15T10:00:00Z"
    }
  ]
}
```

#### Create Ingredient

**Endpoint**: `POST /api/inventory/ingredients/`

**Request**:
```json
{
  "code": "VITC",
  "name": "Vitamin C",
  "ingredient_type": "raw_material",
  "unit": "kg",
  "stock_quantity": "50.000",
  "cost_per_unit": "200.00",
  "min_stock": "5.000"
}
```

**Response** (201 Created)

#### Update Ingredient

**Endpoint**: `PUT /api/inventory/ingredients/{id}/`

**Request**:
```json
{
  "stock_quantity": "75.000"
}
```

**Response** (200 OK)

### Products

#### List Products

**Endpoint**: `GET /api/inventory/products/`

**Query Parameters**:
- `search`: Filter by name or SKU
- `category`: Filter by category ID
- `ordering`: Sort by field

**Response** (200 OK):
```json
{
  "results": [
    {
      "id": 1,
      "name": "Magnesium Plus 500g",
      "sku": "MAG500",
      "category": {
        "id": 1,
        "name": "Supplements"
      },
      "net_weight": "500.000",
      "cost_price": "1250.00",
      "sale_price": "2500.00",
      "stock_quantity": 50,
      "min_stock": 10,
      "created_at": "2026-01-20T10:00:00Z"
    }
  ]
}
```

---

## Production API

### Bill of Materials (BOM)

#### List BOMs

**Endpoint**: `GET /api/production/boms/`

**Response** (200 OK):
```json
{
  "results": [
    {
      "id": 1,
      "product": {
        "id": 1,
        "name": "Magnesium Plus 500g",
        "sku": "MAG500"
      },
      "total_cost": "1250.00",
      "created_at": "2026-01-20T11:00:00Z",
      "lines": [
        {
          "id": 1,
          "ingredient": {
            "id": 1,
            "name": "Magnesium Citrate",
            "code": "MGS"
          },
          "quantity_per_product": "250.000",
          "cost": "375.00"
        }
      ]
    }
  ]
}
```

#### Create BOM

**Endpoint**: `POST /api/production/boms/`

**Request**:
```json
{
  "product_id": 1,
  "lines": [
    {
      "ingredient_id": 1,
      "quantity_per_product": "250.000"
    },
    {
      "ingredient_id": 2,
      "quantity_per_product": "200.000"
    }
  ]
}
```

### Production Orders

#### Create Production Order

**Endpoint**: `POST /api/production/orders/`

**Request**:
```json
{
  "product_id": 1,
  "quantity": 100,
  "scheduled_date": "2026-02-10"
}
```

**Response** (201 Created):
```json
{
  "id": 1,
  "product": {
    "id": 1,
    "name": "Magnesium Plus 500g"
  },
  "quantity": 100,
  "status": "PENDING",
  "scheduled_date": "2026-02-10",
  "created_at": "2026-02-04T14:00:00Z"
}
```

#### Complete Production Order

**Endpoint**: `POST /api/production/orders/{id}/complete/`

**Request**:
```json
{
  "actual_quantity": 98,
  "notes": "2 units scrapped due to quality issues"
}
```

**Response** (200 OK):
```json
{
  "id": 1,
  "status": "COMPLETED",
  "actual_quantity": 98,
  "completed_at": "2026-02-04T16:00:00Z"
}
```

---

## Sales API

### Customers

#### List Customers

**Endpoint**: `GET /api/sales/customers/`

**Query Parameters**:
- `search`: Filter by name or document
- `segment`: Filter by segment (VIP, REGULAR, ACTIVE, NEW)

**Response** (200 OK):
```json
{
  "results": [
    {
      "id": 1,
      "name": "Juan Pérez",
      "document_type": "DNI",
      "document_number": "12345678",
      "email": "juan@example.com",
      "phone": "+54 11 1234-5678",
      "segment": "VIP",
      "total_sales": 15,
      "total_revenue": "125000.00",
      "created_at": "2025-01-01T10:00:00Z"
    }
  ]
}
```

#### Create Customer

**Endpoint**: `POST /api/sales/customers/`

**Request**:
```json
{
  "name": "María González",
  "document_type": "DNI",
  "document_number": "87654321",
  "email": "maria@example.com",
  "phone": "+54 11 8765-4321",
  "address": "Av. Corrientes 1234, CABA"
}
```

### Sales Orders

#### Create Sale

**Endpoint**: `POST /api/sales/orders/`

**Request**:
```json
{
  "customer_id": 1,
  "order_id": "ML-12345678",
  "status": "CONFIRMED",
  "payment_status": "PAID",
  "items": [
    {
      "product_id": 1,
      "quantity": 5,
      "unit_price": "2500.00"
    }
  ]
}
```

**Response** (201 Created):
```json
{
  "id": 1,
  "customer": {
    "id": 1,
    "name": "Juan Pérez"
  },
  "order_id": "ML-12345678",
  "total": "12500.00",
  "status": "CONFIRMED",
  "payment_status": "PAID",
  "created_at": "2026-02-04T15:00:00Z",
  "items": [
    {
      "product": {
        "id": 1,
        "name": "Magnesium Plus 500g",
        "sku": "MAG500"
      },
      "quantity": 5,
      "unit_price": "2500.00",
      "total": "12500.00"
    }
  ]
}
```

---

## Finance API

### Accounts

#### List Accounts

**Endpoint**: `GET /api/finance/accounts/`

**Response** (200 OK):
```json
{
  "results": [
    {
      "id": 1,
      "name": "Banco Galicia - Cuenta Corriente",
      "account_type": "BANK",
      "currency": "ARS",
      "created_at": "2025-01-01T10:00:00Z"
    }
  ]
}
```

### Cash Movements

#### Create Movement

**Endpoint**: `POST /api/finance/movements/`

**Request**:
```json
{
  "account_id": 1,
  "type": "IN",
  "amount": "12500.00",
  "category": "Sales",
  "description": "Sale #ML-12345678",
  "date": "2026-02-04"
}
```

**Response** (201 Created)

---

## Logistics API

### Delivery Routes

#### Create Route

**Endpoint**: `POST /api/logistics/routes/`

**Request**:
```json
{
  "vehicle_id": 1,
  "zone_id": 1,
  "scheduled_date": "2026-02-05",
  "deliveries": [
    {
      "sale_id": 1,
      "address": "Av. Corrientes 1234",
      "estimated_time": "14:00"
    }
  ]
}
```

**Response** (201 Created)

---

## Error Handling

### Error Response Format

All errors follow a consistent format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      "field": "Additional context"
    }
  }
}
```

### HTTP Status Codes

- `200 OK`: Success
- `201 Created`: Resource created successfully
- `204 No Content`: Success with no response body
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `409 Conflict`: Resource conflict (e.g., duplicate)
- `422 Unprocessable Entity`: Validation error
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

### Common Error Codes

- `VALIDATION_ERROR`: Input validation failed
- `NOT_FOUND`: Resource not found
- `DUPLICATE`: Duplicate resource
- `INSUFFICIENT_STOCK`: Not enough stock
- `INSUFFICIENT_FUNDS`: Not enough funds
- `UNAUTHORIZED`: Authentication required
- `FORBIDDEN`: Permission denied
- `RATE_LIMIT_EXCEEDED`: Too many requests

---

## Rate Limiting

API requests are limited to:
- 60 requests per minute per user
- 1000 requests per hour per user

When rate limit is exceeded, you'll receive a `429 Too Many Requests` response with a `Retry-After` header indicating when you can retry.

---

## Pagination

List endpoints support pagination with the following parameters:

- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 20, max: 100)

Response includes:
- `count`: Total number of items
- `next`: URL to next page (or null)
- `previous`: URL to previous page (or null)
- `results`: Array of items

---

## Filtering & Searching

Most list endpoints support:

- `search`: Full-text search across relevant fields
- `ordering`: Sort by field (prefix with `-` for descending)
- Field-specific filters (see endpoint documentation)

Example:
```
GET /api/inventory/products/?search=magnesium&ordering=-created_at&category=1
```

---

**For detailed endpoint specifications, see the interactive API documentation at:**
- Swagger UI: `http://localhost:8000/api/docs/`
- ReDoc: `http://localhost:8000/api/redoc/`
