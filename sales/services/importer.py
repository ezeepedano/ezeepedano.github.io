import pandas as pd
from .importers.mercadolibre import MercadoLibreImporter
from .importers.tiendanube import TiendaNubeImporter

def process_sales_file(file_obj, user):
    """
    Dispatcher that detects file type and delegates to appropriate importer.
    """
    # 1. Detect Format
    try:
        # Read first few lines to sniff header
        pos = file_obj.tell()
        
        # Read as bytes first to avoid encoding issues
        first_lines = file_obj.read(2048) 
        file_obj.seek(pos)
        
        # Try decoding with typical encodings
        decoded_sample = ""
        try:
            decoded_sample = first_lines.decode('utf-8')
        except:
            try:
                decoded_sample = first_lines.decode('latin-1')
            except:
                pass
                
        # Check for Tienda Nube signature
        if "Número de orden" in decoded_sample:
             importer = TiendaNubeImporter(user)
             return importer.process_file(file_obj)
             
    except Exception as e:
        print(f"Detection Error: {e}")
        file_obj.seek(0)
        
    # Check for Mercado Libre (Excel)
    # If we are here, it's either ML or unrecognized.
    # We remove chunksize from ML importer to avoid pandas errors if engine doesn't support it,
    # or we handle the error.
    
    try:
        importer = MercadoLibreImporter(user)
        return importer.process_file(file_obj)
    except Exception as e:
        return {'error': f"Could not determine file format or error reading file: {str(e)}"}
