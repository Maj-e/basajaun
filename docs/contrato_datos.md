# Contrato de datos — Ulinautas

Se fija en la tarea **W0-D2**. Todos los scripts y el front lo respetan; cualquier cambio pasa por D1 (dueño del contrato).

### `web/data/processed/focos.geojson` — un Feature por foco
```json
{
  "type": "Feature",
  "geometry": { "type": "Point", "coordinates": [-70.6483, -33.4569] },
  "properties": {
    "id": "VIIRS_N20_20260214_0742_-33.4569_-70.6483",
    "sensor": "VIIRS",
    "satelite": "NOAA-20",
    "fecha_hora_utc": "2026-02-14T07:42:00Z",
    "fecha": "2026-02-14",
    "t": 493927.7,
    "confianza": "alta",
    "frp": 18.4,
    "brillo_k": 342.1,
    "dia_noche": "N",
    "resolucion_m": 375,
    "detectado_por": ["VIIRS"],
    "incendio_id": null
  }
}
```
`t` = horas desde 1970 (número), para filtrar rápido en la animación.

### `web/data/processed/resumen_diario.json`
```json
{ "2026-02-14": { "focos": 412, "frp_total": 9832.5, "modis": 120, "viirs": 292, "sin_datos": false } }
```

### `web/data/processed/alertas.json`
```json
[{ "incendio_id": 12, "riesgo": "critico", "desde": "2026-02-14T07:42:00Z", "pob_1km": 800, "pob_5km": 23400, "pob_10km": 51000, "viento_hacia_poblacion": false, "centro": [-70.65, -33.46] }]
```

### Correspondencia de campos FIRMS → contrato
| Contrato | MODIS (CSV FIRMS) | VIIRS (CSV FIRMS) |
|---|---|---|
| `lat` / `lon` | `latitude` / `longitude` | `latitude` / `longitude` |
| `fecha_hora_utc` | `acq_date` + `acq_time` (`HHMM`) | igual |
| `satelite` | `satellite`: `Terra` / `Aqua` (o `T` / `A`) | `satellite`: `N` → S-NPP, `N20` / `1` → NOAA-20, `N21` → NOAA-21 |
| `confianza` | `confidence` 0–100: `<30` baja · `30–79` media · `≥80` alta | `confidence`: `l`/`low` → baja · `n`/`nominal` → media · `h`/`high` → alta |
| `frp` | `frp` (MW) | `frp` (MW) |
| `brillo_k` | `brightness` | `bright_ti4` |
| `dia_noche` | `daynight` | `daynight` |
| `resolucion_m` | `1000` | `375` |

> Verificar los códigos de `satellite` con la primera descarga real (W1-D1) y ajustar la tabla si difieren.
