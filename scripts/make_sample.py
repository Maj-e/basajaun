import json
import random
from datetime import datetime, timezone
from pathlib import Path

try:
    from config import BBOX, SAMPLE
except ImportError:
    BBOX = (-72.0, -38.0, -70.0, -33.0)  # oeste, sur, este, norte
    SAMPLE = Path("../web/data/sample")

COLOR_CONFIANZA = {
    "alta": "#d7301f",
    "media": "#fc8d59",
    "baja": "#fdcc8a",
}

COLOR_RIESGO = {
    "critico": "#d7301f",
    "alto": "#fc8d59",
    "medio": "#fdcc8a",
    "bajo": "#fef0d9",
}


def calcular_radio(frp: float) -> float:
    """Interpola radio entre 3 y 16 px según FRP (0 a 500 MW)."""
    frp_c = max(0.0, min(500.0, frp))
    if frp_c <= 50:
        return round(3.0 + (frp_c / 50.0) * 5.0, 1)
    return round(8.0 + ((frp_c - 50.0) / 450.0) * 8.0, 1)


def main():
    random.seed(42)
    SAMPLE.mkdir(parents=True, exist_ok=True)
    ahora_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    oeste, sur, este, norte = BBOX
    fechas_demo = ["2026-02-12", "2026-02-13", "2026-02-14"]
    confianzas = ["baja", "media", "alta"]
    sensores = [
        ("MODIS", "Terra", 1000, "#ffffff"),
        ("MODIS", "Aqua", 1000, "#ffffff"),
        ("VIIRS", "S-NPP", 375, "#222222"),
        ("VIIRS", "NOAA-20", 375, "#222222"),
        ("VIIRS", "NOAA-21", 375, "#222222"),
    ]

    features = []
    resumen = {"actualizado": ahora_iso}

    for f in fechas_demo:
        resumen[f] = {
            "focos": 0,
            "frp_total": 0.0,
            "modis": 0,
            "viirs": 0,
            "sin_datos": False,
        }

    # Generar 50 focos repartidos en 3 días
    for i in range(50):
        fecha_str = fechas_demo[i % len(fechas_demo)]
        hora = random.randint(0, 23)
        minuto = random.randint(0, 59)
        dt = datetime.strptime(f"{fecha_str} {hora:02d}:{minuto:02d}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        t_horas = round(dt.timestamp() / 3600.0, 1)

        sensor, satelite, res_m, borde = random.choice(sensores)
        confianza = confianzas[i % 3]
        frp = round(random.uniform(5.0, 320.0), 1)
        brillo_k = round(random.uniform(310.0, 395.0), 1)
        dia_noche = "D" if 8 <= hora <= 20 else "N"

        lon = round(random.uniform(oeste + 0.3, este - 0.3), 4)
        lat = round(random.uniform(sur + 0.3, norte - 0.3), 4)

        cod_sat = {"S-NPP": "N", "NOAA-20": "N20", "NOAA-21": "N21", "Terra": "T", "Aqua": "A"}[satelite]
        foco_id = f"{sensor}_{cod_sat}_{fecha_str.replace('-', '')}_{hora:02d}{minuto:02d}_{lat}_{lon}"

        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "id": foco_id,
                "sensor": sensor,
                "satelite": satelite,
                "fecha_hora_utc": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "fecha": fecha_str,
                "t": t_horas,
                "confianza": confianza,
                "frp": frp,
                "brillo_k": brillo_k,
                "dia_noche": dia_noche,
                "resolucion_m": res_m,
                "detectado_por": [sensor],
                "incendio_id": None,
                "color": COLOR_CONFIANZA[confianza],
                "radio": calcular_radio(frp),
                "borde": borde,
            },
        })

        d = resumen[fecha_str]
        d["focos"] += 1
        d["frp_total"] = round(d["frp_total"] + frp, 1)
        if sensor == "MODIS":
            d["modis"] += 1
        else:
            d["viirs"] += 1

    # Día sin datos para probar el calendario rayado
    resumen["2026-02-11"] = {
        "focos": 0,
        "frp_total": 0.0,
        "modis": 0,
        "viirs": 0,
        "sin_datos": True,
    }

    # 1. focos.geojson
    focos_geojson = {
        "type": "FeatureCollection",
        "actualizado": ahora_iso,
        "features": features,
    }
    (SAMPLE / "focos.geojson").write_text(json.dumps(focos_geojson, indent=2), encoding="utf-8")

    # 2. resumen_diario.json
    (SAMPLE / "resumen_diario.json").write_text(json.dumps(resumen, indent=2), encoding="utf-8")

    # 3. alertas.json (array raíz según contrato)
    centro_lon = round((oeste + este) / 2, 2)
    centro_lat = round((sur + norte) / 2, 2)
    alertas = [
        {
            "incendio_id": 12,
            "riesgo": "critico",
            "color": COLOR_RIESGO["critico"],
            "desde": "2026-02-12T07:42:00Z",
            "pob_1km": 1200,
            "pob_5km": 23400,
            "pob_10km": 51000,
            "viento_hacia_poblacion": True,
            "centro": [centro_lon, centro_lat],
        },
        {
            "incendio_id": 15,
            "riesgo": "alto",
            "color": COLOR_RIESGO["alto"],
            "desde": "2026-02-13T14:15:00Z",
            "pob_1km": 80,
            "pob_5km": 2400,
            "pob_10km": 9500,
            "viento_hacia_poblacion": False,
            "centro": [round(centro_lon + 0.25, 2), round(centro_lat - 0.25, 2)],
        },
    ]
    (SAMPLE / "alertas.json").write_text(json.dumps(alertas, indent=2), encoding="utf-8")

    # 4. manifest.json (con "archivo": "sample/...", "popup" y "texto")
    manifest = {
        "actualizado": ahora_iso,
        "capas": [
            {
                "id": "focos",
                "nombre": "Focos de calor",
                "archivo": "sample/focos.geojson",
                "tipo": "circle",
                "temporal": True,
                "activa": True,
                "popup": ["sensor", "satelite", "fecha_hora_utc", "confianza", "frp"],
                "leyenda": [
                    {"color": "#d7301f", "texto": "Confianza alta"},
                    {"color": "#fc8d59", "texto": "Confianza media"},
                    {"color": "#fdcc8a", "texto": "Confianza baja"},
                ],
            }
        ],
    }
    (SAMPLE / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"✅ Sample generado según contrato en {SAMPLE}/")


if __name__ == "__main__":
    main()