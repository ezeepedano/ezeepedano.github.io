# Análisis y Requerimientos del Dashboard del Usuario

## 1) LO QUE TENÉS HOY (Datos + Relaciones) y QUÉ PERMITE GENERAR

### 1.1 Módulo Sales (Ventas)
**A) Sale (Venta) — Hecho principal de ingresos**
*   **Campos**: total, product_revenue, shipping_cost, taxes, discounts, platform_fees, shipping_revenue, date, order_id, status, channel, payment_method.
*   **Conexiones**: Sale.customer_id → Customer, Sale.user_id → User.
*   **Genera hoy**:
    *   Ingresos totales por período.
    *   Ingresos por productos vs envío.
    *   Estructura de costos (descuentos, impuestos, fees).
    *   Ventas por canal.
    *   Calidad logística básica (status).

**B) SaleItem (Ítems de venta)**
*   **Campos**: product_title, sku, quantity, unit_price.
*   **Genera hoy**:
    *   Unidades vendidas por SKU/Categoría.
    *   Revenue por SKU.
    *   Top productos y Pareto 80/20.
    *   Mix por canal.

**C) Customer (Cliente)**
*   **Campos**: Identidad, Facturación, Estado (Mayorista, Bloqueado).
*   **Genera hoy**:
    *   Distribución mayorista vs minorista.
    *   Geografía.

**D) CustomerStats**
*   **Campos**: Volumen (gasto, ordenes), Calidad (devoluciones), RFM.
*   **Genera hoy**:
    *   Segmentación RFM.
    *   Calidad de cartera.

### 1.2 Módulo Inventory (Inventario & Producción)
**A) Product**
*   **Genera hoy**: Stock actual, Valor de inventario, Margen bruto por SKU.

**B) Ingredient**
*   **Genera hoy**: Stock de insumos, Valor de insumos.

**C) Recipe**
*   **Genera hoy**: Plan de compras (MRP básico), Costo teórico.

**D) ProductionOrder**
*   **Genera hoy**: Pipeline de producción.

### 1.3 Módulo Finance
**A) FixedCost & MonthlyExpense**
*   **Genera hoy**: Calendario de vencimientos, OPEX mensual real, Cumplimiento de pagos.

**B) Purchase (Compras)**
*   **Genera hoy**: Spend por proveedor/categoría.
*   **FALTA**: Aging de cuentas a pagar (no hay due_date).

**C) Asset**
*   **Genera hoy**: Listado de activos.
*   **FALTA**: Depreciación.

### 1.4 Módulo HR
**A) Employee & Payroll**
*   **Genera hoy**: Costo de nómina mensual, Estado de pago.

---

## 2) QUÉ DASHBOARD PODÉS ARMAR HOY (Pantallas Propuestas)

1.  **Resumen Ejecutivo**: Ingresos, Share por canal, Margen Bruto, OPEX, Resultado Operativo.
2.  **Ventas & Canales**: Órdenes, Ticket promedio, Geografía.
3.  **Productos & Mix**: Top 20 SKUs, Pareto, Stock vs Ventas.
4.  **Clientes**: Matriz RFM, Mayoristas, Reclamos.
5.  **Inventario & Producción**: Valorización de stock, Kanban de producción, Faltantes.
6.  **Finanzas**: Presupuesto vs Real, Compras por proveedor.
7.  **RRHH**: Nómina total, Nómina/Ventas.

---

## 3) LO QUE TE FALTA (Nuevos Desarrollos)

### 3.1 FALTA #1 — Caja real / Bancos (CRÍTICO)
*   **Nueva Tabla**: `CashMovement` (id, date, amount, direction, account, type, reference_id).
*   **Objetivo**: Cashflow real, Conciliación, Runway.

### 3.2 FALTA #2 — Acreditaciones (Ventas ≠ Caja)
*   **Nueva Tabla**: `Payout` (payout_id, channel, date, gross, fees, net).
*   **Objetivo**: Días de acreditación, Dinero pendiente.

### 3.3 FALTA #3 — Vencimientos y Saldos (A/R y A/P)
*   **Modificar `Purchase`**: Agregar due_date, paid_amount, balance_open.
*   **Modificar `Sale`**: Agregar invoice_due_date, paid_amount, balance_open.
*   **Objetivo**: Aging de deuda (Proveedores) y cobranza (Clientes).

### 3.4 FALTA #4 — Devoluciones
*   **Nueva Tabla**: `Return` (sale_id, status, reason, refund_amount).
*   **Objetivo**: Tasa real de devolución, motivos, costo logístico inverso.

### 3.5 FALTA #5 — Publicidad (Ads)
*   **Nueva Tabla**: `AdSpend` (date, platform, spend, attribution).
*   **Objetivo**: CAC, ROAS real.

### 3.6 FALTA #6 — Trazabilidad (Lotes y Vencimientos)
*   **Modificar `ProductionOrder`**: Agregar lot_number, dates.
*   **Nueva Tabla**: `ProductStockLot`.
*   **Objetivo**: FEFO, alertas de vencimiento.

### 3.7 FALTA #7 — Compras Inteligentes
*   **Nueva Tabla**: `ProviderIngredient` (lead_time, moq).
*   **Objetivo**: Punto de pedido automático.

### 3.8 FALTA #8 — Stock Reservado
*   **Modificar `Product`**: Agregar reserved_qty, available_qty.

### 3.9 FALTA #9 — Costeo Real de Producción
*   **Modificar `ProductionOrder`**: Agregar labor_cost, overhead, packaging.

### 3.10 FALTA #10 — Depreciación
*   **Modificar `Asset`**: Agregar vida útil, valor residual, método.

### 3.11 FALTA #11 — Retenciones
*   **Modificar `CashMovement`**: Agregar soporte para retenciones.

---

## 4) PLAN DE IMPLEMENTACIÓN RECOMENDADO

1.  **CashMovement** (Caja real).
2.  **Purchase/Sale Due Dates** (Vencimientos).
3.  **Sale Financials** (Saldos).
4.  **Payout** (Liquidaciones).
5.  **Return** (Devoluciones).
6.  **Lotes y Vencimientos**.
7.  **Lead Time Proveedores**.
8.  **AdSpend**.
9.  **Costeo Avanzado**.
10. **Depreciación**.
