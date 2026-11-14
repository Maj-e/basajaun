# Contrato de datos — Ulinautas

Se gela en la tarea **W0-B1** (B1 + F). Todos los scripts y el front lo respetan; cualquier cambio pasa por B1 (dueño del contrato) y se anuncia a todo el equipo. El validador (`scripts/validate.py`, W1-B4) lo comprueba en el CI.

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
    "incendio_id": null,
    "color": "#d7301f",
    "radio": 6.2,
    "borde": "#222222"
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

### Reglas comunes a todos los archivos
- **Estilo calculado por el backend:** cada Feature lleva sus propiedades de visualización (`color`, `radio`, `borde`, `opacidad`, `rotacion`, `tamano` según el tipo de capa). El front no decide colores.
- **Horodatage:** cada archivo JSON tiene `actualizado` (ISO 8601 UTC) a nivel raíz (en GeoJSON: propiedad del `FeatureCollection`). El front muestra "Datos del JJ/MM HH:MM".
- **Capas temporales:** las Features llevan `t` (horas desde 1970, número) para la línea de tiempo.

### `web/data/manifest.json` — lista de capas
Generado por `scripts/make_manifest.py`. **Solo aparecen las capas cuyo archivo existe.** Agregar una capa = agregar un archivo + su entrada aquí.
```json
{
  "actualizado": "2026-02-14T08:00:00Z",
  "capas": [
    {
      "id": "focos",
      "nombre": "Focos de calor",
      "archivo": "processed/focos.geojson",
      "tipo": "circle",
      "temporal": true,
      "activa": true,
      "popup": ["sensor", "satelite", "fecha_hora_utc", "confianza", "frp"],
      "leyenda": [{"color": "#d7301f", "texto": "Confianza alta"}, {"color": "#fc8d59", "texto": "Confianza media"}, {"color": "#fdcc8a", "texto": "Confianza baja"}]
    },
    {
      "id": "poblacion",
      "nombre": "Densidad poblacional",
      "archivo": "processed/poblacion.png",
      "tipo": "image",
      "esquinas": [[-72.0, -33.0], [-70.0, -33.0], [-70.0, -38.0], [-72.0, -38.0]],
      "temporal": false,
      "activa": false,
      "leyenda": [{"color": "#fee5d9", "texto": "< 10 hab/km²"}, {"color": "#a50f15", "texto": "> 1000 hab/km²"}]
    }
  ]
}
```
Tipos que conoce el cargador del front: `circle`, `fill`, `line`, `image`, `flechas`. Un tipo nuevo = una tarea front.

`activa` es el **interruptor**: una capa queda en `false` hasta estar verificada en la URL publicada.

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

> Verificar los códigos de `satellite` con la primera descarga real (W1-B2) y ajustar la tabla si difieren.
