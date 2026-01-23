# Data Integration Plan: Mercado Pago Financials

## 1. Overview
This module (`MercadoPagoSettlement`) currently operates as a standalone financial reconciliation tool. However, for true profitability analysis, it must be joined with operational data sources.

## 2. Integration Points

### A. Sales & Orders (Revenue)
- **Source**: `sales.Sale` (Internal ERP Model) or External Channels (MercadoLibre API / Tienda Nube API exports).
- **Goal**: Calculate true margin per product (SKU).
- **Join Key**: 
  - `MercadoPagoSettlement.source_id` (Operation ID) ↔ `Order.payment_id` or `Order.external_reference`.
  - **Challenge**: Multiple settlements might exist for one order (e.g. initial payment + adjustment).
- **Metric**: `Net Profit = Order.Revenue - MP.Fees - MP.Taxes - COGS`

### B. Shipping & Logistics (Costs)
- **Source**: `MercadoPagoSettlement.transaction_type == 'SETTLEMENT_SHIPPING'` OR External Logistics Invoice (Correo Argentino/Andreani).
- **Goal**: Separate "Marketplace Fees" from "Logistics Costs".
- **Join Key**: `source_id` (Shipping ID) or `external_reference`.
- **Logic**:
  - IF `TRANSACTION_TYPE == 'SETTLEMENT_SHIPPING'`: This is a cost deducted by MP directly.
  - IF NOT in MP: Cost is paid externally (invoice).

### C. Returns & Claims (Risk/Loss)
- **Source**: `MercadoPagoSettlement` types `REFUND`, `DISPUTE`, `CASHBACK`.
- **Goal**: Calculate "Cost of Returns" and "Defect Rate".
- **Join Key**: `source_id` (Original Operation ID).

### D. Advertising (CAC)
- **Source**: Mercado Ads Exports (CSV/API).
- **Goal**: `ROAS = Revenue / Ad Spend`.
- **Integration**: Start by matching `Campaign ID` or simply aggregating `Ad Spend` by date to compare with `Total Net Income`.

## 3. Data Dictionary (Mercado Pago Module)

| Column | Type | Description |
| :--- | :--- | :--- |
| `source_id` | String | Unique Identifier of the Operation (Payment, Refund, etc.). Indexed. |
| `transaction_type` | String | Nature of movement: `SETTLEMENT` (Sales), `PAYOUTS` (Withdrawals), `REFUND`. |
| `payment_method_type`| String | `credit_card`, `debit_card`, `available_money`, `account_money`. |
| `transaction_amount` | Decimal | Gross amount of the operation (before deductions). |
| `fee_amount` | Decimal | **Negative** value representing platform commission. |
| `taxes_amount` | Decimal | **Negative** value representing tax withholdings (IIBB, Ganancias). |
| `real_amount` | Decimal | Net amount released to account (`Gross + Fees + Taxes`). |
| `money_release_date` | DateTime | When the funds become available (Liquid). Key for Cashflow. |
