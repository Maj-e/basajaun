import json
from pathlib import Path
import pandas as pd

def generar_serie_horaria():
    PROCESSED_DIR = Path("web/data/processed")
    # Soporta tanto si W0-B3 decidió un solo archivo como varios
    geojson_files = list(PROCESSED_DIR.glob("hotspots*.geojson"))
    
    if not geojson_files:
        print("No se encontraron archivos GeoJSON. Ejecuta W1-B3 primero.")
        return

    records = []
    
    # 1. Extraer los datos del GeoJSON
    for file in geojson_files:
        data = json.loads(file.read_text(encoding="utf-8"))
        for feature in data.get("features", []):
            props = feature["properties"]
            records.append({
                "t": props["t"],
                # Si el FRP viene nulo, lo convertimos a 0.0 para poder sumar
                "frp": props.get("frp") or 0.0 
            })

    df = pd.DataFrame(records)
    output_path = PROCESSED_DIR / "hourly_series.json"

    # No data at all (e.g. a period without fires)
    if df.empty:
        output_path.write_text("[]", encoding="utf-8")
        return

    # 2. Agrupar por la hora 't'
    grouped = df.groupby("t").agg(
        count=("t", "size"),
        total_frp=("frp", "sum")
    )

    # 3. Rellenar las horas vacías (Zero-filling)
    t_min = df["t"].min()
    t_max = df["t"].max()
    todas_las_horas = range(t_min, t_max + 1)
    
    # reindex inserta las horas que faltan y les asigna 0
    serie_completa = grouped.reindex(todas_las_horas, fill_value=0)
    
    # Redondear el FRP a 1 decimal para no enviar flotantes enormes al front
    serie_completa["total_frp"] = serie_completa["total_frp"].round(1)
    
    # Convertir el índice 't' de vuelta a columna
    serie_completa = serie_completa.reset_index().rename(columns={"index": "t"})

    # 4. Exportar a JSON optimizado para gráficos (lista de diccionarios)
    # Ejemplo: [{"t": 491950, "count": 12, "total_frp": 340.5}, ...]
    serie_completa.to_json(output_path, orient="records")
    
    print(f"Serie horaria exportada a {output_path}")
    print(f"Rango cubierto: {len(serie_completa)} horas.")

if __name__ == "__main__":
    generar_serie_horaria()