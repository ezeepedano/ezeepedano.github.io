# Configuración de Recetas
# Formato: 'Nombre del Producto': {'Ingrediente': Gramos_por_Kilo}

RECETAS = {
    'Magnesio Complex': {
        'Citrato de Magnesio': 450,
        'Sulfato de Magnesio': 100,
        'Gluconato de Magnesio': 50,
        'Vitamina C': 100,
        'Vitamina D3': 0.33,
        'Maltodextrina': 299.67
    },
    'Vitamina C + Malto': {
        'Vitamina C': 300,
        'Maltodextrina': 700
    },
    'Inositol Complex': {
        'Inositol': 540,
        'Acido Folico': 1,
        'Vitamina B12': 0.01,
        'Zinc Gluconato': 10,
        'Maltodextrina': 448.99
    }
}

# Configuración de Sistema
UMBRAL_MERMA_KG = 0.100  # Si queda menos de 100g en una bolsa, se descarta.
