import io
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
import pandas as pd
from config import BBOX, FECHA_FIN, FECHA_INICIO, FIRMS_MAP_KEY, RAW

FUENTES_BASE = ["MODIS", "VIIRS_SNPP", "VIIRS_NOAA20", "VIIRS_NOAA21"]


def obtener_fuente_api(fuente_base: str, fecha_inicio: datetime) -> str:
    """Usa _NRT para datos recientes (< 60 días) y _SP para archivo histórico."""
    dias_antiguedad = (datetime.now(timezone.utc).date() - fecha_inicio.date()).days
    sufijo = "NRT" if dias_antiguedad < 60 else "SP"
    return f"{fuente_base}_{sufijo}"


def descargar_bloque(fuente_api: str, bbox_str: str, dias: int, fecha_str: str) -> pd.DataFrame:
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{FIRMS_MAP_KEY}/{fuente_api}/{bbox_str}/{dias}/{fecha_str}"
    print(f"  -> Descargando {fuente_api} ({dias} días desde {fecha_str})...")
    req = urllib.request.Request(url, headers={"User-Agent": "Ulinautas-SpaceApps/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            texto = resp.read().decode("utf-8").strip()
    except urllib.error.HTTPError as e:
        detalle = e.read().decode("utf-8", errors="ignore").strip()
        print(f"     [Aviso HTTP {e.code}] {detalle[:150]}")
        return pd.DataFrame()

    if not texto or "Invalid" in texto or "Error" in texto:
        print(f"     [Aviso] Respuesta inesperada: {texto[:120]}")
        return pd.DataFrame()

    return pd.read_csv(io.StringIO(texto))


def main():
    if not FIRMS_MAP_KEY:
        print("Error: FIRMS_MAP_KEY no definida en .env o entorno.", file=sys.stderr)
        sys.exit(1)

    RAW.mkdir(parents=True, exist_ok=True)
    oeste, sur, este, norte = BBOX
    bbox_str = f"{oeste},{sur},{este},{norte}"

    dt_inicio = datetime.strptime(FECHA_INICIO, "%Y-%m-%d")
    dt_fin = datetime.strptime(FECHA_FIN, "%Y-%m-%d")
    total_dias = (dt_fin - dt_inicio).days + 1

    print(f"Zona BBOX: {bbox_str} | Periodo: {FECHA_INICIO} a {FECHA_FIN} ({total_dias} días)")

    for fuente_base in FUENTES_BASE:
        fuente_api = obtener_fuente_api(fuente_base, dt_inicio)
        salida = RAW / f"{fuente_api}_{FECHA_INICIO}_{FECHA_FIN}.csv"

        if salida.exists() and salida.stat().st_size > 100:
            print(f"[OK] Ya existe en caché: {salida.name}")
            df_total = pd.read_csv(salida)
        else:
            bloques = []
            cursor = dt_inicio
            while cursor <= dt_fin:
                restantes = (dt_fin - cursor).days + 1
                dias_bloque = min(5, restantes)
                df_b = descargar_bloque(fuente_api, bbox_str, dias_bloque, cursor.strftime("%Y-%m-%d"))
                if not df_b.empty:
                    bloques.append(df_b)
                cursor += timedelta(days=dias_bloque)

            if bloques:
                df_total = pd.concat(bloques, ignore_index=True)
                df_total.to_csv(salida, index=False)
                print(f"[GUARDADO] {salida.name} ({len(df_total)} filas)")
            else:
                print(f"[VACÍO] No se obtuvieron filas para {fuente_api}")
                continue

        if "satellite" in df_total.columns and not df_total.empty:
            sats = df_total["satellite"].unique().tolist()
            print(f"   Códigos 'satellite' reales en {fuente_api}: {sats}")


if __name__ == "__main__":
    main()
