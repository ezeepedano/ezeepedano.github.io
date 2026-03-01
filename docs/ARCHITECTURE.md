# ERP System - System Architecture

## Table of Contents

- [Overview](#overview)
- [System Design](#system-design)
- [Tech Stack](#tech-stack)
- [Module Architecture](#module-architecture)
- [Data Flow](#data-flow)
- [Database Schema](#database-schema)
- [Security Architecture](#security-architecture)
- [Deployment Architecture](#deployment-architecture)

---

## Overview

The ERP System follows a modular monolithic architecture built on Django, providing comprehensive business management capabilities through six integrated modules.

### Design Principles

1. **Modularity**: Each module is self-contained with clear responsibilities
2. **Scalability**: Database optimization and caching ready for growth
3. **Security**: Multi-layer security with authentication, authorization, and audit trails
4. **Maintainability**: Clean code, type hints, comprehensive testing
5. **Performance**: Query optimization, indexing, and caching strategies

---

## System Design

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Web Browser                         │
└────────────────────┬────────────────────────────────────┘
                     │ HTTPS
┌────────────────────▼────────────────────────────────────┐
│                  Nginx Reverse Proxy                    │
│            (Load Balancing, SSL, Static Files)          │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│                 Django Application                      │
│  ┌──────────┬──────────┬──────────┬──────────┬──────┐ │
│  │Inventory │Production│  Sales   │ Finance  │Logis.│ │
│  │  Module  │  Module  │  Module  │  Module  │Module│ │
│  └──────────┴──────────┴──────────┴──────────┴──────┘ │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │        Business Logic Layer (Signals)            │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────┬───────────────────────────────────┘
                     │
       ┌─────────────┴───────────────┐
       │                             │
┌──────▼─────────┐          ┌────────▼────────┐
│   PostgreSQL   │          │     Redis       │
│    Database    │          │  Cache/Queue    │
└────────────────┘          └─────────────────┘
```

### Request Flow

1. **Client Request** → Nginx → Django App
2. **Authentication** → Middleware verification
3. **Authorization** → Permission checks
4. **Business Logic** → Module processing + Signals
5. **Database** → ORM queries (with caching)
6. **Response** → JSON/HTML to client

---

## Tech Stack

### Backend
- **Framework**: Django 5.0
- **Language**: Python 3.13
- **ORM**: Django ORM
- **Template Engine**: Django Templates

### Database
- **Primary**: PostgreSQL 14+ (Production)
- **Development**: SQLite
- **Caching**: Redis 7

### Frontend
- **HTML5** + **TailwindCSS**
- **JavaScript** (Vanilla)
- **Chart.js** for analytics

### Infrastructure
- **Web Server**: Nginx
- **WSGI Server**: Gunicorn
- **Container**: Docker + Docker Compose
- **CI/CD**: GitHub Actions

### Development Tools
- **Testing**: Django TestCase + comprehensive_test.py
- **Linting**: Pylint, Flake8, Black, isort
- **Type Checking**: MyPy
- **Security**: Bandit
- **Version Control**: Git

---

## Module Architecture

### 1. Inventory Module

**Purpose**: Manage products, ingredients, categories, and stock levels.

**Models**:
- `Category`: Product categorization
- `Ingredient`: Raw materials and supplies
- `Product`: Final sellable products
- `IngredientLot`: Lot tracking for traceability

**Key Features**:
- Automatic lot creation on ingredient reception
- Low stock alerts (<10 units)
- Cost tracking per unit
- Unique ingredient codes (e.g., "MGS", "VITC")

**Signals**:
- `suggest_reorder_stock`: Low stock alert
- `auto_create_ingredient_lot`: Automatic lot generation

---

### 2. Production Module

**Purpose**: Manage production processes, BOMs, and manufacturing orders.

**Models**:
- `BillOfMaterial`: Product recipes
- `BomLine`: Ingredient components
- `ProductionOrder`: Manufacturing orders
- `ProductionBatch`: Completed batches

**Key Features**:
- Percentage-based BOM calculations
- Auto cost calculation from BOM
- Stock deduction on production completion
- Scrap factor management

**Signals**:
- `update_bom_cost_on_save`: Automatic BOM cost calc
- `update_product_cost_from_bom`: Product cost update
- `deduct_stock_on_production`: Stock management

---

### 3. Sales Module

**Purpose**: CRM, sales orders, customer management.

**Models**:
- `Customer`: Customer records with deduplication
- `Sale`: Sales orders
- `SaleItem`: Order line items
- `CustomerStats`: Customer analytics

**Key Features**:
- Automatic customer segmentation (VIP, Regular, Active, New)
- Multi-channel sales (MercadoLibre, TiendaNube, Wholesale)
- Automatic stock deduction on sale
- Customer deduplication by dedup_key

**Signals**:
- `auto_assign_customer_segment`: Customer categorization
- `deduct_stock_on_sale`: Inventory update
- `auto_create_cash_movement`: Finance integration

---

### 4. Finance Module

**Purpose**: Financial management, accounting, cash flow.

**Models**:
- `Account`: Bank accounts and cash
- `CashMovement`: Transaction records
- `Provider`: Suppliers
- `Purchase`: Supplier purchases
- `MonthlyExpense`: Recurring expenses

**Key Features**:
- Automatic IVA (21%) tax calculation
- Cash flow tracking
- Multi-account management
- Monthly expense forecasting

**Signals**:
- `calculate_tax_on_purchase`: Tax automation
- `auto_suggest_iva`: IVA calculation

---

### 5. Logistics Module

**Purpose**: Delivery management, routing, fleet tracking.

**Models**:
- `DeliveryZone`: Geographic zones
- `Vehicle`: Fleet vehicles
- `DeliveryRoute`: Planned routes

**Key Features**:
- Route planning
- Vehicle capacity management
- Zone-based delivery

---

### 6. Traceability Module

**Purpose**: FIFO inventory tracking, lot management.

**Models**:
- `IngredientLot`: Lot tracking
- `StockMovement`: Stock history

**Key Features**:
- FIFO automatic selection
- Lot-to-lot traceability
- Waste (merma) management

---

## Data Flow

### Production Flow

```
BOM Created
    ↓
Production Order Created
    ↓
Ingredients Reserved (FIFO)
    ↓
Production Completed
    ↓
Stock Deducted (Ingredients)
    ↓
Stock Added (Finished Product)
    ↓
Cost Calculated
    ↓
Product Price Updated
```

### Sales Flow

```
Customer Created (if new)
    ↓
Sale Created
    ↓
Stock Deducted
    ↓
Cash Movement Created
    ↓
Customer Stats Updated
    ↓
Customer Segment Assigned
```

---

## Database Schema

### Core Relationships

```
Category (1) ──< (N) Product
                      │
                     (1)
                      │
                      ▼
              BillOfMaterial (1) ──< (N) BomLine
                                            │
                                           (N)
                                            │
                                            ▼
                                      Ingredient
                                            │
                                           (1)
                                            │
                                            ▼
                                      IngredientLot (N)

Customer (1) ──< (N) Sale (1) ──< (N) SaleItem >── (N) Product

Sale (N) ──> (1) CashMovement

Provider (1) ──< (N) Purchase
```

### Indexes

Key indexes for performance:
- `Ingredient.code` (UNIQUE)
- `Product.sku` (UNIQUE)
- `Customer.dedup_key` (UNIQUE)
- `Sale.date` (for analytics)
- `IngredientLot.expiry_date` (FIFO)
- `CashMovement.date` (financial reports)

---

## Security Architecture

### Authentication
- Django session-based authentication
- Token authentication for API
- Password hashing (PBKDF2)

### Authorization
- User-based data isolation (multi-tenant ready)
- Permission decorators on all views
- Row-level security via `user` FK

### Security Layers

1. **Network**: HTTPS, HSTS, firewall
2. **Application**: CSRF, XSS protection, SQL injection prevention (ORM)
3. **Data**: Encryption at rest, secure backups
4. **Access**: Rate limiting, IP whitelisting (optional)
5. **Audit**: Request logging, change tracking

### Security Headers

- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `X-XSS-Protection: 1; mode=block`
- `Content-Security-Policy`
- `Referrer-Policy: strict-origin`

---

## Deployment Architecture

### Production Environment

```
┌─────────────────────────────────────────┐
│          Load Balancer (AWS ELB)        │
└──────────────┬──────────────────────────┘
               │
       ┌───────┴────────┐
       │                │
┌──────▼─────┐   ┌──────▼─────┐
│  Nginx 1   │   │  Nginx 2   │
└──────┬─────┘   └──────┬─────┘
       │                │
┌──────▼─────┐   ┌──────▼─────┐
│ Django App │   │ Django App │
│ Instance 1 │   │ Instance 2 │
└──────┬─────┘   └──────┬─────┘
       │                │
       └───────┬────────┘
               │
┌──────────────▼──────────────┐
│     PostgreSQL (RDS)        │
│  (Multi-AZ, Auto Backup)    │
└─────────────────────────────┘

┌─────────────────────────────┐
│   Redis (ElastiCache)       │
│   (Cache + Celery Queue)    │
└─────────────────────────────┘
```

### Scalability Strategy

1. **Horizontal Scaling**: Multiple Gunicorn workers
2. **Caching**: Redis for frequent queries
3. **Database**: Read replicas for reporting
4. **CDN**: Static files on CloudFront/CloudFlare
5. **Async**: Celery for background tasks

---

## Performance Optimizations

### Database
- Indexes on frequently queried fields
- `select_related()` / `prefetch_related()` for joins
- Query caching with Redis
- Connection pooling
- Bulk operations where possible

### Application
- Lazy loading of heavy computations
- Denormalized data (CustomerStats) for fast reads
- Static file caching
- Template fragment caching

### Monitoring
- Django Silk for query profiling
- Sentry for error tracking
- Prometheus + Grafana for metrics

---

## Future Enhancements

### v2.0 Roadmap
- [ ] GraphQL API
- [ ] Real-time notifications (WebSockets)
- [ ] Multi-tenant architecture
- [ ] ML-based demand forecasting
- [ ] Mobile app (React Native)
- [ ] Advanced analytics dashboard
- [ ] Warehouse management system (WMS)
- [ ] E-commerce integration

---

**Author**: ERP Development Team  
**Last Updated**: 2026-02-04  
**Version**: 1.0
