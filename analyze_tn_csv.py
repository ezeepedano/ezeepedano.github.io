import csv

file_path = r"C:\Users\Giuliana\Downloads\ventas-d00115c7-5b32-4e86-8f60-96e49d5aa024.csv"

try:
    with open(file_path, 'r', encoding='latin-1', newline='') as f:
        # Try sniffing first
        sample = f.read(1024)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample)
        reader = csv.reader(f, dialect)
        
        headers = next(reader)
        row1 = next(reader)
        
    with open('tn_headers.txt', 'w', encoding='utf-8') as out:
        out.write(f"Delimiter: {repr(dialect.delimiter)}\n")
        out.write("Headers:\n")
        for i, h in enumerate(headers):
            out.write(f"{i}: {h}\n")
            
        out.write("\nFirst Row Sample:\n")
        for i, val in enumerate(row1):
            out.write(f"{headers[i]}: {val}\n")
            
    print("Done writing to tn_headers.txt")
            
except Exception as e:
    print(f"Error: {e}")
