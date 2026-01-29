# 🏭 Sistema de Trazabilidad v2.0

## 📖 Manual de Uso

### Instalación y Primera Ejecución

1. **Requisitos**: Python 3.7+ con pandas y openpyxl instalados
   ```
   pip install pandas openpyxl xlsxwriter
   ```

2. **Primera vez**: Ejecutar `setup_databases.py` para crear las bases de datos
   ```
   python setup_databases.py
   ```

3. **Ejecutar el sistema**:
   ```
   python sistema_trazabilidad.py
   ```

---

## 🎯 Funcionalidades

### 1️⃣ Registrar Producción
**Qué hace**: Registra un lote de producción y descuenta automáticamente el stock.

**Pasos**:
1. Selecciona el producto a fabricar (de las recetas configuradas)
2. Ingresa la cantidad en kg
3. Define tu lote interno (ej: L-240130-01)
4. El sistema verifica si hay stock suficiente
5. Confirma la operación

**Automatización**:
- ✅ Calcula ingredientes necesarios automáticamente
- ✅ Busca bolsas más viejas (FIFO)
- ✅ Descarta restos < 100g (merma)
- ✅ Actualiza stock en tiempo real
- ✅ Graba historial con trazabilidad completa

---

### 2️⃣ Ingresar Compra
**Qué hace**: Registra una nueva bolsa de materia prima en el stock.

**Pasos**:
1. Selecciona la materia prima (o crea una nueva)
2. El sistema genera automáticamente el ID (ej: MP-MAL-007)
3. Ingresa: cantidad (kg), lote del proveedor, vencimiento
4. **IMPORTANTE**: Pega una etiqueta con el ID en la bolsa física

**Tip**: Imprime etiquetas con el ID para pegar en las bolsas reales.

---

### 3️⃣ Consultar Stock
**Qué hace**: Muestra el estado actual del inventario.

**Información que brinda**:
- 📊 Resumen por ingrediente (kg totales)
- 🚨 Alertas de stock crítico (< 5 kg)
- ⏰ Bolsas próximas a vencer (< 3 meses)
- 📋 Detalle de todas las bolsas activas

---

### 4️⃣ Ver Historial de Producción
**Qué hace**: Muestra las producciones realizadas.

**Información que brinda**:
- 📦 Últimas 10 producciones (más recientes primero)
- 📈 Estadísticas generales (total de lotes, kg por producto)

---

## 🗂️ Archivos del Sistema

### Configuración
- `RECETAS_CONFIG.py`: Define las fórmulas de los productos
  - Para agregar un producto nuevo, edita este archivo
  - Formato: `'Nombre': {'Ingrediente': gramos_por_kg}`

- `UMBRAL_MERMA_KG`: Umbral para descartar restos (default: 0.100 kg)

### Base de Datos (Excel)
- `DB_STOCK.xlsx`: Inventario en tiempo real
  - Columnas: ID_Interno, Materia_Prima, Stock_Actual, Stock_Inicial, Lote_Prov, Vto

- `DB_HISTORIAL_PRODUCCION.xlsx`: Registro de producciones
  - Hoja 1 "Cabecera": Lote, Fecha, Producto, Kg
  - Hoja 2 "Receta": Detalle de ingredientes usados

⚠️ **IMPORTANTE**: Cierra los archivos Excel antes de usar el sistema.

---

## 💡 Consejos de Uso

### Para Trazabilidad Perfecta
1. **SIEMPRE pega la etiqueta** con el ID en las bolsas físicas al recibirlas
2. Registra las compras apenas llegan
3. Si abres una bolsa, **úsala siempre antes que las nuevas** (FIFO)

### Para Evitar Errores
- Verifica que el lote interno sea único para cada producción
- No edites manualmente los archivos Excel mientras el sistema está corriendo
- Haz backup semanal de `DB_STOCK.xlsx` y `DB_HISTORIAL_PRODUCCION.xlsx`

### Si Necesitas
- **Agregar un producto**: Edita `RECETAS_CONFIG.py` y reinicia el programa
- **Corregir un error**: Edita el Excel directamente (con cuidado)
- **Ver reportes**: Abre `DB_HISTORIAL_PRODUCCION.xlsx` y usa tablas dinámicas

---

## 🔧 Solución de Problemas

**"ERROR: Cierra el archivo..."**
→ Cierra el Excel que esté abierto y presiona ENTER

**"No se encuentra RECETAS_CONFIG.py"**
→ Asegúrate de ejecutar el programa desde la carpeta `Sistema_Trazabilidad`

**"FALTAN MATERIALES"**
→ Necesitas comprar más stock antes de producir

**Stock negativo**
→ No debería pasar, pero si ocurre edita `DB_STOCK.xlsx` manualmente

---

## 📞 Soporte

Este sistema fue diseñado para gestión interna de trazabilidad básica.
Para mejoras o funcionalidades adicionales, contacta al desarrollador.

**Versión**: 2.0  
**Última actualización**: 2026-01-28
