import pandas as pd
import datetime
import os
import sys
import re

# Import Configuration
try:
    from RECETAS_CONFIG import RECETAS, UMBRAL_MERMA_KG
except ImportError:
    print("ERROR: No se encontró el archivo RECETAS_CONFIG.py")
    sys.exit(1)

FILE_STOCK = 'DB_STOCK.xlsx'
FILE_HIST = 'DB_HISTORIAL_PRODUCCION.xlsx'

def load_data():
    if not os.path.exists(FILE_STOCK) or not os.path.exists(FILE_HIST):
        print("ERROR: No se encuentran los archivos de Base de Datos (DB_STOCK o DB_HISTORIAL).")
        print("Ejecuta 'setup_databases.py' primero.")
        return None
    
    df_stock = pd.read_excel(FILE_STOCK)
    return df_stock

def save_stock(df_stock):
    try:
        df_stock.to_excel(FILE_STOCK, index=False)
        return True
    except PermissionError:
        print(f"ERROR: Cierra el archivo '{FILE_STOCK}' antes de guardar.")
        input("Presiona ENTER cuando hayas cerrado el archivo...")
        return save_stock(df_stock)  # Retry

def append_production_record(header_data, detail_data_list):
    try:
        df_head_old = pd.read_excel(FILE_HIST, sheet_name='Producción (Cabecera)')
        df_det_old = pd.read_excel(FILE_HIST, sheet_name='Producción (Receta)')
    except:
        df_head_old = pd.DataFrame()
        df_det_old = pd.DataFrame()
        
    df_head_new = pd.DataFrame([header_data])
    df_det_new = pd.DataFrame(detail_data_list)
    
    df_head_final = pd.concat([df_head_old, df_head_new], ignore_index=True)
    df_det_final = pd.concat([df_det_old, df_det_new], ignore_index=True)
    
    try:
        with pd.ExcelWriter(FILE_HIST, engine='xlsxwriter') as writer:
            df_head_final.to_excel(writer, sheet_name='Producción (Cabecera)', index=False)
            df_det_final.to_excel(writer, sheet_name='Producción (Receta)', index=False)
        return True
    except PermissionError:
        print(f"ERROR: Cierra el archivo '{FILE_HIST}' antes de guardar.")
        input("Presiona ENTER cuando hayas cerrado el archivo...")
        return append_production_record(header_data, detail_data_list)  # Retry

def get_next_mp_id(df_stock, material_name):
    """Generate next available MP ID for a material"""
    # Extract prefix from material name (first 3 letters)
    prefix_map = {
        'Citrato de Magnesio': 'CIT',
        'Sulfato de Magnesio': 'SUL',
        'Gluconato de Magnesio': 'GLU',
        'Vitamina C': 'VITC',
        'Vitamina D3': 'D3',
        'Maltodextrina': 'MAL',
        'Inositol': 'INO',
        'Acido Folico': 'B9',
        'Vitamina B12': 'B12',
        'Zinc Gluconato': 'ZN'
    }
    
    prefix = prefix_map.get(material_name, 'MP')
    
    # Find existing IDs with this prefix
    existing_ids = df_stock[df_stock['ID_Interno'].str.contains(f'MP-{prefix}', na=False)]['ID_Interno'].tolist()
    
    if not existing_ids:
        return f'MP-{prefix}-001'
    
    # Extract numbers and find max
    numbers = []
    for id_str in existing_ids:
        match = re.search(r'-(\d+)$', id_str)
        if match:
            numbers.append(int(match.group(1)))
    
    next_num = max(numbers) + 1 if numbers else 1
    return f'MP-{prefix}-{next_num:03d}'

def check_stock_availability(df_stock, recipe, kilos_prod):
    missing = []
    needs = {}
    
    print("\n--- Verificando Stock ---")
    
    for ing, g_per_kg in recipe.items():
        needed_kg = (g_per_kg / 1000.0) * kilos_prod
        available_kg = df_stock[df_stock['Materia_Prima'] == ing]['Stock_Actual'].sum()
        
        needs[ing] = needed_kg
        
        if available_kg < needed_kg:
            missing.append(f"{ing}: Necesitas {needed_kg:.3f} kg, tienes {available_kg:.3f} kg")
        else:
            print(f"  [OK] {ing}: Req {needed_kg:.3f} kg / Disp {available_kg:.3f} kg")
            
    if missing:
        print("\n❌ ERROR: FALTAN MATERIALES")
        for m in missing:
            print(f"  - {m}")
        return False, None
    
    return True, needs

def consume_stock(df_stock, needs):
    consumption_log = []
    
    for ing, amount in needs.items():
        amount_remaining = amount
        used_lots = []
        consumed_total = 0.0
        
        bag_indices = df_stock[(df_stock['Materia_Prima'] == ing) & (df_stock['Stock_Actual'] > 0)].sort_values('Vto').index
        
        for idx in bag_indices:
            if amount_remaining <= 0.000001:
                break
                
            current_bag_stock = df_stock.at[idx, 'Stock_Actual']
            bag_id = df_stock.at[idx, 'ID_Interno']
            
            if current_bag_stock < UMBRAL_MERMA_KG:
                df_stock.at[idx, 'Stock_Actual'] = 0
                print(f"  🗑️ Descartando resto de bolsa {bag_id} ({current_bag_stock:.3f} kg) por merma.")
                continue
            
            take = min(current_bag_stock, amount_remaining)
            df_stock.at[idx, 'Stock_Actual'] = current_bag_stock - take
            amount_remaining -= take
            consumed_total += take
            used_lots.append(bag_id)
            
            remaining_after = df_stock.at[idx, 'Stock_Actual']
            if 0 < remaining_after < UMBRAL_MERMA_KG:
                print(f"  🗑️ Bolsa {bag_id} terminó con {remaining_after:.3f} kg. Descartando remanente.")
                df_stock.at[idx, 'Stock_Actual'] = 0
                
        consumption_log.append({
            'Materia_Prima': ing,
            'Cantidad_Total_Kg': round(consumed_total, 3),
            'Lotes_MP_Usados': ", ".join(used_lots)
        })
        
    return df_stock, consumption_log

# ============== MAIN FEATURES ==============

def registrar_produccion():
    df_stock = load_data()
    if df_stock is None: return

    print("\n" + "="*50)
    print("          📦 REGISTRAR PRODUCCIÓN")
    print("="*50)
    
    # 1. Select Product
    prods = list(RECETAS.keys())
    for i, p in enumerate(prods):
        print(f"{i+1}. {p}")
        
    try:
        sel = int(input("\n▶ Seleccione producto (número): ")) - 1
        if sel < 0 or sel >= len(prods): raise ValueError
        prod_name = prods[sel]
    except:
        print("❌ Selección inválida.")
        return

    # 2. Input details
    try:
        kg_prod = float(input(f"▶ Cantidad a fabricar de '{prod_name}' (kg): "))
        if kg_prod <= 0:
            print("❌ La cantidad debe ser mayor a 0.")
            return
            
        lote_prod = input("▶ Lote Interno de Producción (ej: L-240130-01): ").strip().upper()
        if not lote_prod:
            print("❌ Debe ingresar un lote.")
            return
    except ValueError:
        print("❌ Valor inválido.")
        return

    # 3. Validation
    recipe = RECETAS[prod_name]
    ok, needs = check_stock_availability(df_stock, recipe, kg_prod)
    if not ok:
        return

    print(f"\n✅ Stock suficiente para producir {kg_prod} kg de {prod_name}")
    confirm = input("▶ ¿Confirmar producción? Esto descontará stock. (S/N): ")
    if confirm.upper() != 'S':
        print("⚠️ Operación cancelada.")
        return

    # 4. Execute
    print("\n🔄 Procesando...")
    df_stock_updated, consumption_log = consume_stock(df_stock, needs)
    
    # 5. Save Stock
    if save_stock(df_stock_updated):
        print("✅ Stock actualizado correctamente.")
    else:
        return

    # 6. Save History
    header = {
        'Lote_Interno_Prod': lote_prod, 
        'Fecha_Elaboración': datetime.date.today().strftime('%Y-%m-%d'), 
        'Producto_Nombre': prod_name, 
        'Cantidad_Total_Obtenida_Kg': kg_prod
    }
    
    details = []
    for item in consumption_log:
        item['Lote_Interno_Prod'] = lote_prod
        details.append(item)
        
    if append_production_record(header, details):
        print("✅ Historial de producción guardado.")
    else:
        return

    print("\n" + "="*50)
    print(f"✅ PRODUCCIÓN REGISTRADA: Lote {lote_prod}")
    print("="*50)

def ingresar_compra():
    """Register new stock entry"""
    df_stock = load_data()
    if df_stock is None: return
    
    print("\n" + "="*50)
    print("          📥 INGRESAR COMPRA (Nueva Bolsa)")
    print("="*50)
    
    # Show available materials
    print("\nMateriales disponibles:")
    unique_materials = sorted(df_stock['Materia_Prima'].unique())
    for i, mat in enumerate(unique_materials):
        print(f"{i+1}. {mat}")
    print(f"{len(unique_materials)+1}. [Otra materia prima]")
    
    try:
        sel = int(input("\n▶ Seleccione materia prima: ")) - 1
        if sel == len(unique_materials):
            material = input("▶ Nombre de la nueva materia prima: ").strip()
            if not material:
                print("❌ Debe ingresar un nombre.")
                return
        elif 0 <= sel < len(unique_materials):
            material = unique_materials[sel]
        else:
            raise ValueError
    except:
        print("❌ Selección inválida.")
        return
    
    # Generate ID
    new_id = get_next_mp_id(df_stock, material)
    print(f"\n🏷️ ID Asignado: {new_id}")
    print("  (Escribe esto en la etiqueta de la bolsa)")
    
    try:
        kg = float(input("▶ Cantidad (kg): "))
        if kg <= 0: raise ValueError
            
        lote_prov = input("▶ Lote del Proveedor: ").strip()
        vto = input("▶ Fecha de Vencimiento (YYYY-MM): ").strip()
        
    except:
        print("❌ Entrada inválida.")
        return
    
    # Add to dataframe
    new_row = {
        'ID_Interno': new_id,
        'Materia_Prima': material,
        'Stock_Actual': kg,
        'Stock_Inicial': kg,
        'Lote_Prov': lote_prov,
        'Vto': vto
    }
    
    df_stock = pd.concat([df_stock, pd.DataFrame([new_row])], ignore_index=True)
    
    if save_stock(df_stock):
        print("\n✅ Compra registrada exitosamente.")
        print(f"📌 No olvides pegar la etiqueta '{new_id}' en la bolsa.")
    else:
        print("❌ Error al guardar.")

def consultar_stock():
    df_stock = load_data()
    if df_stock is None: return
    
    print("\n" + "="*50)
    print("          📊 STOCK ACTUAL")
    print("="*50)
    
    # Summary
    summary = df_stock.groupby('Materia_Prima')['Stock_Actual'].sum().sort_values(ascending=False)
    print("\n--- Resumen por Ingrediente ---")
    for mat, kg in summary.items():
        status = "⚠️ BAJO" if kg < 10 else "✅"
        print(f"{status} {mat}: {kg:.2f} kg")
    
    # Alerts
    print("\n--- 🚨 Alertas ---")
    low_stock = summary[summary < 5]
    if len(low_stock) > 0:
        print("⚠️ STOCK CRÍTICO (< 5 kg):")
        for mat in low_stock.index:
            print(f"  - {mat}: {low_stock[mat]:.2f} kg")
    else:
        print("✅ No hay materiales con stock crítico.")
    
    # Expiring soon
    today = datetime.date.today()
    df_stock['Vto_date'] = pd.to_datetime(df_stock['Vto'], errors='coerce')
    expiring = df_stock[(df_stock['Stock_Actual'] > 0) & 
                        (df_stock['Vto_date'] < today + pd.DateOffset(months=3))]
    
    if len(expiring) > 0:
        print("\n⏰ Bolsas por vencer (< 3 meses):")
        for _, row in expiring.iterrows():
            print(f"  - {row['ID_Interno']} ({row['Materia_Prima']}): Vence {row['Vto']}")
    
    # Detail
    input("\n[Presiona ENTER para ver detalle de bolsas...]")
    print("\n--- Detalle de Bolsas Activas ---")
    active = df_stock[df_stock['Stock_Actual'] > 0][['ID_Interno', 'Materia_Prima', 'Stock_Actual', 'Vto']].sort_values('Materia_Prima')
    print(active.to_string(index=False))

def ver_historial():
    """View production history"""
    if not os.path.exists(FILE_HIST):
        print("❌ No hay historial de producción aún.")
        return
    
    try:
        df_hist = pd.read_excel(FILE_HIST, sheet_name='Producción (Cabecera)')
    except:
        print("❌ Error leyendo historial.")
        return
    
    print("\n" + "="*50)
    print("          📋 HISTORIAL DE PRODUCCIÓN")
    print("="*50)
    
    if len(df_hist) == 0:
        print("\n⚠️ Aún no hay producciones registradas.")
        return
    
    # Show last 10
    print("\n--- Últimas Producciones ---")
    recent = df_hist.tail(10).sort_values('Fecha_Elaboración', ascending=False)
    for _, row in recent.iterrows():
        print(f"📦 {row['Lote_Interno_Prod']} | {row['Fecha_Elaboración']} | {row['Producto_Nombre']} | {row['Cantidad_Total_Obtenida_Kg']} kg")
    
    # Stats
    print("\n--- Estadísticas Generales ---")
    print(f"Total de lotes fabricados: {len(df_hist)}")
    print(f"\nProducción por Producto:")
    prod_summary = df_hist.groupby('Producto_Nombre')['Cantidad_Total_Obtenida_Kg'].agg(['count', 'sum'])
    print(prod_summary.to_string())

def main():
    while True:
        print("\n" + "="*50)
        print("     🏭 SISTEMA DE TRAZABILIDAD v2.0")
        print("="*50)
        print("1. 📦 Registrar Producción")
        print("2. 📥 Ingresar Compra (Nueva Bolsa)")
        print("3. 📊 Consultar Stock")
        print("4. 📋 Ver Historial de Producción")
        print("5. 🚪 Salir")
        
        op = input("\n▶ Opción: ").strip()
        
        if op == '1':
            registrar_produccion()
        elif op == '2':
            ingresar_compra()
        elif op == '3':
            consultar_stock()
        elif op == '4':
            ver_historial()
        elif op == '5':
            print("\n👋 Cerrando sistema...")
            break
        else:
            print("❌ Opción inválida")

if __name__ == '__main__':
    main()
