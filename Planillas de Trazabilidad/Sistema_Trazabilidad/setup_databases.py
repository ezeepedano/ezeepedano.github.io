import pandas as pd
import os

# --- INITIAL STOCK DATA (From Simulation) ---
stock_data = [
    {'ID_Interno': 'MP-CIT-001', 'Materia_Prima': 'Citrato de Magnesio', 'Stock_Actual': 25.0, 'Stock_Inicial': 25.0, 'Lote_Prov': 'P-991', 'Vto': '2025-01'},
    {'ID_Interno': 'MP-CIT-002', 'Materia_Prima': 'Citrato de Magnesio', 'Stock_Actual': 25.0, 'Stock_Inicial': 25.0, 'Lote_Prov': 'P-992', 'Vto': '2025-02'},
    {'ID_Interno': 'MP-SUL-001', 'Materia_Prima': 'Sulfato de Magnesio', 'Stock_Actual': 25.0, 'Stock_Inicial': 25.0, 'Lote_Prov': 'S-101', 'Vto': '2025-03'},
    {'ID_Interno': 'MP-GLU-001', 'Materia_Prima': 'Gluconato de Magnesio', 'Stock_Actual': 25.0, 'Stock_Inicial': 25.0, 'Lote_Prov': 'G-202', 'Vto': '2025-04'},
    {'ID_Interno': 'MP-VITC-001', 'Materia_Prima': 'Vitamina C', 'Stock_Actual': 25.0, 'Stock_Inicial': 25.0, 'Lote_Prov': 'C-303', 'Vto': '2025-05'},
    {'ID_Interno': 'MP-VITC-002', 'Materia_Prima': 'Vitamina C', 'Stock_Actual': 25.0, 'Stock_Inicial': 25.0, 'Lote_Prov': 'C-304', 'Vto': '2025-06'},
    {'ID_Interno': 'MP-D3-001', 'Materia_Prima': 'Vitamina D3', 'Stock_Actual': 1.0, 'Stock_Inicial': 1.0, 'Lote_Prov': 'D3-404', 'Vto': '2026-01'},
    {'ID_Interno': 'MP-MAL-001', 'Materia_Prima': 'Maltodextrina', 'Stock_Actual': 25.0, 'Stock_Inicial': 25.0, 'Lote_Prov': 'M-501', 'Vto': '2025-05'},
    {'ID_Interno': 'MP-MAL-002', 'Materia_Prima': 'Maltodextrina', 'Stock_Actual': 25.0, 'Stock_Inicial': 25.0, 'Lote_Prov': 'M-502', 'Vto': '2025-05'},
    {'ID_Interno': 'MP-MAL-003', 'Materia_Prima': 'Maltodextrina', 'Stock_Actual': 25.0, 'Stock_Inicial': 25.0, 'Lote_Prov': 'M-503', 'Vto': '2025-05'},
    {'ID_Interno': 'MP-MAL-004', 'Materia_Prima': 'Maltodextrina', 'Stock_Actual': 25.0, 'Stock_Inicial': 25.0, 'Lote_Prov': 'M-504', 'Vto': '2025-05'},
    {'ID_Interno': 'MP-MAL-005', 'Materia_Prima': 'Maltodextrina', 'Stock_Actual': 25.0, 'Stock_Inicial': 25.0, 'Lote_Prov': 'M-505', 'Vto': '2025-05'},
    {'ID_Interno': 'MP-MAL-006', 'Materia_Prima': 'Maltodextrina', 'Stock_Actual': 25.0, 'Stock_Inicial': 25.0, 'Lote_Prov': 'M-506', 'Vto': '2025-05'},
    {'ID_Interno': 'MP-INO-001', 'Materia_Prima': 'Inositol', 'Stock_Actual': 25.0, 'Stock_Inicial': 25.0, 'Lote_Prov': 'I-601', 'Vto': '2025-07'},
    {'ID_Interno': 'MP-INO-002', 'Materia_Prima': 'Inositol', 'Stock_Actual': 25.0, 'Stock_Inicial': 25.0, 'Lote_Prov': 'I-602', 'Vto': '2025-07'},
    {'ID_Interno': 'MP-INO-003', 'Materia_Prima': 'Inositol', 'Stock_Actual': 25.0, 'Stock_Inicial': 25.0, 'Lote_Prov': 'I-603', 'Vto': '2025-07'},
    {'ID_Interno': 'MP-B9-001', 'Materia_Prima': 'Acido Folico', 'Stock_Actual': 1.0, 'Stock_Inicial': 1.0, 'Lote_Prov': 'B9-701', 'Vto': '2026-02'},
    {'ID_Interno': 'MP-B12-001', 'Materia_Prima': 'Vitamina B12', 'Stock_Actual': 1.0, 'Stock_Inicial': 1.0, 'Lote_Prov': 'B12-801', 'Vto': '2026-03'},
    {'ID_Interno': 'MP-ZN-001', 'Materia_Prima': 'Zinc Gluconato', 'Stock_Actual': 25.0, 'Stock_Inicial': 25.0, 'Lote_Prov': 'Z-901', 'Vto': '2025-08'},
]

def create_databases():
    # 1. DB STOCK
    df_stock = pd.DataFrame(stock_data)
    df_stock.to_excel('DB_STOCK.xlsx', index=False)
    print("Created DB_STOCK.xlsx")
    
    # 2. DB HISTORIAL PRODUCCION
    # Structure: 
    # Sheet 1: Cabecera (Lote, Producto, Kg, Fecha)
    # Sheet 2: Detalle (Lote, Ingrediente, Kg, Lotes_Usados)
    
    with pd.ExcelWriter('DB_HISTORIAL_PRODUCCION.xlsx', engine='xlsxwriter') as writer:
        pd.DataFrame(columns=['Lote_Interno_Prod', 'Fecha_Elaboración', 'Producto_Nombre', 'Cantidad_Total_Obtenida_Kg']).to_excel(writer, sheet_name='Producción (Cabecera)', index=False)
        pd.DataFrame(columns=['Lote_Interno_Prod', 'Materia_Prima', 'Cantidad_Total_Kg', 'Lotes_MP_Usados']).to_excel(writer, sheet_name='Producción (Receta)', index=False)
    
    print("Created DB_HISTORIAL_PRODUCCION.xlsx")

if __name__ == "__main__":
    create_databases()
