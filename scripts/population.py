import os
import json
from pathlib import Path
import numpy as np
import rasterio
from rasterio.mask import mask
from rasterio.transform import array_bounds
import matplotlib.cm as cm
import matplotlib.colors as mcolors
from dotenv import load_dotenv

def procesar_worldpop():
    load_dotenv()
    
    # 1. Configuración de rutas
    RAW_TIF = Path("data/raw/worldpop_country.tif") # Asegúrate de descargar el .tif de tu país aquí
    PROCESSED_DIR = Path("web/data/processed")
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    
    OUT_TIF = PROCESSED_DIR / "population.tif"
    OUT_PNG = PROCESSED_DIR / "population.png"
    MANIFEST = PROCESSED_DIR / "population_manifest.json"

    if not RAW_TIF.exists():
        print(f"Falta el archivo crudo: {RAW_TIF}. Descárgalo de WorldPop.")
        return

    # Usar el BBOX acordado en W0-B2 (Oeste, Sur, Este, Norte)
    # Ejemplo: BBOX = (-72.0, -38.0, -70.0, -33.0)
    # Deberías importarlo de tu config.py, aquí lo simulo:
    bbox = (-72.0, -38.0, -70.0, -33.0) 
    west, south, east, north = bbox

    # 2. Crear el polígono GeoJSON para el recorte
    bbox_polygon = [{
        "type": "Polygon",
        "coordinates": [[
            [west, south],
            [east, south],
            [east, north],
            [west, north],
            [west, south]
        ]]
    }]

    # 3. Recortar el raster
    with rasterio.open(RAW_TIF) as src:
        # crop=True recorta el array a la caja límite del polígono
        out_image, out_transform = mask(src, bbox_polygon, crop=True)
        out_meta = src.meta.copy()

    # Extraemos la matriz de datos 2D (banda 1)
    data = out_image[0]
    nodata_value = src.nodata if src.nodata is not None else -99999.0

    # 4. Exportar population.tif (Para la tarea analítica W3-B1)
    out_meta.update({
        "driver": "GTiff",
        "height": out_image.shape[1],
        "width": out_image.shape[2],
        "transform": out_transform,
        "compress": "lzw" # Compresión sin pérdida para no pesar gigas
    })
    with rasterio.open(OUT_TIF, "w", **out_meta) as dest:
        dest.write(out_image)

    # 5. Generar population.png para el mapa web (Frontend)
    # Crear una máscara para ignorar el nodata y las zonas con 0 personas
    valid_mask = (data != nodata_value) & (data > 0)
    
    # La población tiene una cola muy larga (muchos ceros, pocas ciudades hiperdensas).
    # Usamos PowerNorm o LogNorm para que las zonas rurales también se vean.
    norm = mcolors.PowerNorm(gamma=0.3, vmin=np.min(data[valid_mask]), vmax=np.max(data[valid_mask]))
    
    # Elegir un mapa de color (magma, inferno, o YlOrRd)
    cmap = cm.get_cmap('magma')
    
    # Aplicar color y convertir a RGBA (0-255)
    rgba_image = cmap(norm(data))
    
    # Hacer completamente transparentes (Alpha = 0) las áreas sin datos o con 0 habs.
    rgba_image[~valid_mask, 3] = 0.0 
    
    # Guardar PNG usando matplotlib
    import matplotlib.pyplot as plt
    plt.imsave(OUT_PNG, rgba_image)

    # 6. Exportar las coordenadas exactas del PNG (El Manifest)
    # Calculamos los límites REALES del raster recortado, que cuadran con los píxeles
    real_west, real_south, real_east, real_north = array_bounds(
        out_meta['height'], out_meta['width'], out_transform
    )

    manifest_data = {
        "type": "image",
        "url": "data/processed/population.png",
        # Formato habitual para Leaflet/Mapbox: [[sur, oeste], [norte, este]]
        "corners": [
            [real_south, real_west],
            [real_north, real_east]
        ]
    }
    
    MANIFEST.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
    
    print(f"Recorte completado. PNG exportado a {OUT_PNG}")
    print(f"BBOX Original: {bbox}")
    print(f"BBOX Real (Píxeles): ({real_west}, {real_south}, {real_east}, {real_north})")

if __name__ == "__main__":
    procesar_worldpop()