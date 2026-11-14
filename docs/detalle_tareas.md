# Detalle de las tareas — Ulinautas

Especificación técnica de cada tarea de [`TODO.md`](../TODO.md): archivos, código, criterio de "hecho". Mismos IDs.

---

## Contrato de datos (se fija en W0-D2, todos lo respetan)

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

---

## Wave 0 — Base del proyecto (P0)

> Fin de la ola: el repo arranca, el mapa base se ve **en el dominio**, el front tiene datos de ejemplo.

- [ ] **W0-D1** · Configuración + clave FIRMS · 👤 ___
  - Pedir la MAP_KEY en https://firms.modaps.eosdis.nasa.gov/api/map_key/ y probarla:
    `curl "https://firms.modaps.eosdis.nasa.gov/api/area/csv/$FIRMS_MAP_KEY/VIIRS_SNPP_NRT/world/1"`
  - `requirements.txt`, `.gitignore` (`.env`, `data/raw/`, `__pycache__/`), `.env.example` con `FIRMS_MAP_KEY=`
  - Elegir zona y periodo de demo (~2 semanas con incendios visibles en FIRMS) → `scripts/config.py`:
    ```python
    BBOX = (-72.0, -38.0, -70.0, -33.0)   # oeste, sur, este, norte → reemplazar
    FECHA_INICIO, FECHA_FIN = "2026-02-01", "2026-02-14"
    RAW, SAMPLE, PROCESSED = Path("data/raw"), Path("web/data/sample"), Path("web/data/processed")
    ```
  - **Hecho cuando:** la API responde, la clave solo está en `.env`, `config.py` se importa
- [ ] **W0-D2** · Datos de ejemplo del contrato · 👤 ___
  - `web/data/sample/focos_sample.geojson` (~50 focos, MODIS + VIIRS, 3 días, 3 confianzas, con `t`)
  - `web/data/sample/resumen_diario_sample.json`, `web/data/sample/alertas_sample.json`
  - **Hecho cuando:** los 3 archivos respetan el contrato y están en `main` (el front depende de ellos)
- [ ] **W0-F1** · Esqueleto web: mapa + estado · 👤 ___
  - `web/index.html` carga MapLibre `4.7.1` desde unpkg; `web/app.js` crea el mapa centrado en el `BBOX`
  - Fondo: `https://demotiles.maplibre.org/style.json` o teselas raster OSM
  - Zonas de la página: mapa (centro), panel izquierdo (filtros + calendario + capas), panel derecho (alertas), barra inferior (línea de tiempo)
  - `web/state.js`:
    ```js
    export const state = { fecha: null, rango: null, sensores: ["MODIS","VIIRS"], confianzas: ["baja","media","alta"], hora: null, capas: {} };
    const listeners = [];
    export const subscribe = f => listeners.push(f);
    export function setState(c) { Object.assign(state, c); listeners.forEach(f => f(state)); }
    ```
  - **Hecho cuando:** `cd web && python -m http.server 8000` → mapa visible con el diseño de paneles vacío

- [ ] **W0-F2** · Publicar el sitio en el dominio · 👤 ___ · **empezar primero** (el DNS puede tardar)
  - Dominio: usar uno existente o comprarlo (Cloudflare, Namecheap, Porkbun…); decidir si es la raíz (`ulinautas.xyz`) o un subdominio (`app.ulinautas.xyz`)
  - `web/CNAME` con el dominio en una sola línea
  - `.github/workflows/deploy.yml`: publica la carpeta `web/` en cada push a `main`
    ```yaml
    name: deploy
    on: { push: { branches: [main] }, workflow_dispatch: {} }
    permissions: { contents: read, pages: write, id-token: write }
    concurrency: { group: pages, cancel-in-progress: true }
    jobs:
      deploy:
        runs-on: ubuntu-latest
        environment: { name: github-pages, url: "${{ steps.d.outputs.page_url }}" }
        steps:
          - uses: actions/checkout@v4
          - uses: actions/configure-pages@v5
          - uses: actions/upload-pages-artifact@v3
            with: { path: web }
          - id: d
            uses: actions/deploy-pages@v4
    ```
  - En GitHub: *Settings → Pages → Source: GitHub Actions*, luego *Custom domain* = el dominio
  - DNS (en el registrador):
    | Caso | Registro |
    |---|---|
    | Subdominio | `CNAME app → maj-e.github.io` |
    | Raíz | 4 registros `A` → `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153` (+ `CNAME www → maj-e.github.io`) |
  - Si el DNS está en Cloudflare: proxy **desactivado** (nube gris) hasta que GitHub emita el certificado
  - Marcar *Enforce HTTPS* cuando esté disponible
  - Rutas **siempre relativas** en el front (`data/processed/focos.geojson`, nunca `/data/...`)
  - Plan B si el DNS no responde a tiempo: presentar en `https://maj-e.github.io/ulinautas/`
  - **Hecho cuando:** `https://<dominio>` muestra el mapa de W0-F1 con candado HTTPS

---

## Wave 1 — MVP: mapa de focos armonizados (P0)

> Fin de la ola: **el mapa muestra los focos MODIS + VIIRS reales, unificados, con filtros.** Ya se puede presentar.

### Pista D
- [ ] **W1-D1** · Descarga FIRMS · 👤 ___ · ← W0-D1
  - `scripts/download_firms.py`
  - `https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{FUENTE}/{oeste},{sur},{este},{norte}/{DIAS}/{FECHA}`
  - Fuentes: `MODIS_NRT`, `VIIRS_SNPP_NRT`, `VIIRS_NOAA20_NRT`, `VIIRS_NOAA21_NRT` (`_SP` para fechas antiguas)
  - `DIAS` limitado (máx. 10): cortar el periodo en bloques y concatenar; no volver a descargar si el archivo existe
  - **Hecho cuando:** los 4 CSV del periodo están en `data/raw/`
- [ ] **W1-D2** · Normalización MODIS + VIIRS + tests · 👤 ___ · ← W0-D2 (se puede empezar con un CSV de prueba)
  - `scripts/harmonize.py`: `normalizar_modis(df)`, `normalizar_viirs(df, satelite)`, `parse_fecha(acq_date, acq_time)`
  - Según la tabla de correspondencia; VIIRS acepta `l/n/h` **y** `low/nominal/high`; `acq_time` con `str.zfill(4)` (`742` → `0742`)
  - `scripts/tests/test_harmonize.py`: 3 filas MODIS + 3 VIIRS escritas a mano → columnas del contrato, confianza ∈ {baja, media, alta}, fecha UTC correcta
  - **Hecho cuando:** `pytest scripts/tests` pasa
- [ ] **W1-D3** · Export `focos.geojson` + `resumen_diario.json` · 👤 ___ · ← W1-D1, W1-D2
  - `harmonize.py main()`: leer `data/raw/*.csv` → normalizar → `pd.concat` → `id`, `fecha`, `t` → filtrar al `BBOX` → GeoJSON
  - Redondear coordenadas a 4 decimales y FRP a 1 (peso del archivo)
  - En el mismo script: `resumen_diario.json` con **todos** los días del periodo (`focos: 0`, `sin_datos: true` si no hay nada)
  - **Hecho cuando:** `python scripts/harmonize.py` genera los 2 archivos; `focos.geojson` < 10 MB

### Pista F
- [ ] **W1-F1** · Capa de focos: estilo + leyenda + popup · 👤 ___ · ← W0-F1, W0-D2
  - `web/layers/focos.js`: source `geojson` + capa `circle`
    ```js
    "circle-color": ["match", ["get","confianza"], "alta","#d7301f", "media","#fc8d59", "baja","#fdcc8a", "#999"],
    "circle-radius": ["interpolate", ["linear"], ["get","frp"], 0,3, 50,8, 500,16],
    "circle-stroke-color": ["match", ["get","sensor"], "MODIS","#ffffff", "#222222"],
    "circle-stroke-width": 1.5
    ```
  - Leyenda fija (colores, tamaños, bordes); popup al clic (sensor, satélite, fecha/hora UTC, confianza, FRP, coordenadas); cursor `pointer`
  - **Hecho cuando:** con los datos de ejemplo se distinguen confianza, FRP y sensor, y el popup funciona
- [ ] **W1-F2** · Filtros fecha / sensor / confianza + datos reales · 👤 ___ · ← W0-F1 · cambio a reales ← W1-D3
  - `web/filters.js`: `<input type="date">` + casillas → `setState` → `map.setFilter("focos", ...)`
    ```js
    ["all",
      ["==", ["get","fecha"], state.fecha],
      ["in", ["get","sensor"], ["literal", state.sensores]],
      ["in", ["get","confianza"], ["literal", state.confianzas]]]
    ```
  - Constante `DATA_URL` en `app.js`: pasar de `data/sample/focos_sample.geojson` a `data/processed/focos.geojson` cuando W1-D3 esté listo
  - **Hecho cuando:** los filtros actualizan el mapa al instante **con los datos reales**, en local y en el dominio

---

## Wave 2 — Calendario + reproducción (P0 / P1)

> Fin de la ola: se navega en el tiempo y se ve la propagación.

- [ ] **W2-D1** · Deduplicación + incendios (P1) · 👤 ___ · ← W1-D3
  - `scripts/fires.py`, sobre coordenadas proyectadas en metros (UTM de la zona)
  - Deduplicar: distancia < 1 km **y** |Δt| < 60 min → conservar el VIIRS, `detectado_por: ["MODIS","VIIRS"]`; imprimir cuántos se unieron
  - Incendios: `DBSCAN(eps=1.0, min_samples=2)` sobre `[x_km, y_km, t / 12]` → `incendio_id` en cada foco
  - `web/data/processed/incendios.geojson`: envolvente convexa + buffer 500 m; `incendio_id`, `inicio`, `fin`, `n_focos`, `frp_max`, `frp_total`, `area_km2`
  - **Hecho cuando:** los incendios conocidos de la zona salen como 1 grupo y no como 50
- [ ] **W2-F1** · Calendario conectado al mapa (P0) · 👤 ___ · ← W0-F1 (usa `resumen_diario_sample.json`)
  - `web/calendar.js`: grilla mensual de 7 columnas, color según `focos` (5 tonos), gris rayado si `sin_datos`, número al pasar el ratón, flechas de mes
  - Clic → `setState({ fecha })`; Mayús + clic → `setState({ rango: [inicio, fin] })`; el filtro de W1-F2 acepta el rango (`>=` / `<=`)
  - **Hecho cuando:** calendario y selector de fecha siempre sincronizados
- [ ] **W2-F2** · Línea de tiempo + animación + contador (P1) · 👤 ___ · ← W1-F2
  - `web/timeline.js`: `<input type="range">` en horas + ⏮ ▶/⏸ ⏭ + x1 / x4 / x16, bucle con `requestAnimationFrame` que avanza `state.hora`
  - Filtro: `t ≤ hora` y `t > hora − 6`; opacidad `["interpolate", ["linear"], ["-", hora, ["get","t"]], 0,1, 6,0.1]` (estela de 6 h)
  - Contador "Focos activos: N · FRP: X MW"
  - **Hecho cuando:** los focos aparecen a su hora y se apagan en 6 h, fluido con los datos de demo
- [ ] **W2-F3** · Capa de incendios (P1) · 👤 ___ · ← W2-D1
  - `web/layers/incendios.js`: polígonos `fill` semitransparentes + contorno; clic → ficha (inicio, duración, focos, FRP máx, área)
  - **Hecho cuando:** se ven los contornos y la ficha al hacer clic

---

## Wave 3 — Alerta por densidad poblacional (P1)

> Fin de la ola: la app dice qué incendios amenazan a la población.

- [ ] **W3-D1** · Capa de población · 👤 ___ · ← W0-D1
  - `scripts/population.py`: WorldPop "Population counts, 1 km, UN adjusted" del país, recorte al `BBOX` con `rasterio.mask`
  - Exportar `web/data/processed/poblacion.tif` + `poblacion.png` (coloreado) con sus 4 esquinas para el front
  - **Hecho cuando:** los 2 archivos existen y la imagen se superpone bien en el mapa
- [ ] **W3-D2** · Exposición + riesgo + `alertas.json` · 👤 ___ · ← W3-D1, W2-D1
  - `scripts/exposure.py`: buffers 1 / 5 / 10 km por incendio, `rasterstats.zonal_stats(stats="sum")` → `pob_1km`, `pob_5km`, `pob_10km`
  - Riesgo (umbrales en `config.py`):
    | Riesgo | Regla |
    |---|---|
    | `critico` | `pob_1km ≥ 1000` o (`pob_5km ≥ 10000` y `frp_max ≥ 100`) |
    | `alto` | `pob_5km ≥ 1000` |
    | `medio` | `pob_10km ≥ 100` |
    | `bajo` | resto |
  - `desde` = hora del primer foco del incendio; ordenar de más a menos grave
  - **Hecho cuando:** `alertas.json` respeta el contrato y no todo sale `critico`
- [ ] **W3-F1** · Panel de capas + capa población + panel de alertas · 👤 ___ · ← W0-F1 (usa `alertas_sample.json`)
  - `web/layers/index.js`: cada capa exporta `{ id, nombre, agregar(map), mostrar(bool) }`; el panel de casillas se genera solo a partir de la lista
  - `web/layers/poblacion.js`: source `type: "image"` con `poblacion.png`, opacidad 0.6
  - `web/alerts.js`: lista lateral con color por riesgo, población a 5 km, hora; clic → `map.flyTo({ center, zoom: 11 })`
  - Durante la reproducción: mostrar solo las alertas con `desde ≤ state.hora`
  - **Hecho cuando:** capa de población activable, alertas clicables y sincronizadas con la línea de tiempo

---

## Wave 4 — Viento y meteorología (P1)

> Fin de la ola: se ve hacia dónde empuja el viento cada incendio.

- [ ] **W4-D1** · Meteo por hora + riesgo ajustado por el viento · 👤 ___ · ← W0-D1 · ajuste ← W3-D2
  - `scripts/weather.py`: grilla 5×5 sobre el `BBOX`, una sola llamada con coordenadas separadas por comas:
    `https://archive-api.open-meteo.com/v1/archive?latitude=..&longitude=..&start_date=..&end_date=..&hourly=wind_speed_10m,wind_direction_10m,temperature_2m,relative_humidity_2m,precipitation`
  - Salida `web/data/processed/meteo.json`: `{ "puntos": [[lon,lat],...], "horas": [...], "viento_vel": [[...]], "viento_dir": [[...]], "temp": [[...]], "humedad": [[...]], "lluvia": [[...]] }`
  - En `exposure.py`: si el viento sopla hacia el píxel más poblado a < 10 km (diferencia < 45° con `dir + 180°`) y `vel ≥ 20 km/h` → riesgo +1 nivel, `viento_hacia_poblacion: true`
  - **Hecho cuando:** `meteo.json` completo y el campo aparece en `alertas.json`
- [ ] **W4-F1** · Capas viento + meteorología · 👤 ___ · ← W4-D1, W3-F1 (panel de capas), W2-F2 (hora)
  - `web/layers/viento.js`: capa `symbol` con ícono de flecha, `icon-rotate` = dirección, tamaño según velocidad, actualizada con `state.hora`
  - `web/layers/meteo.js`: puntos coloreados por la variable elegida (temperatura / humedad / lluvia) + leyenda
  - **Hecho cuando:** las flechas giran durante la reproducción y se cambia de variable meteo

---

## Wave 5 — Agua, rutas, accesibilidad, terreno (P2)

> Solo si las olas anteriores están en `main`.

- [ ] **W5-D1** · Datos OSM + distancias · 👤 ___ · ← W2-D1
  - `scripts/osm.py`: **una sola consulta Overpass** en el `BBOX` para agua (`natural=water`, `waterway=river`, `landuse=reservoir`), rutas (`highway=primary|secondary|tertiary|track|path`) y bomberos (`amenity=fire_station`)
  - Exportar `agua.geojson`, `rutas.geojson`, `bomberos.geojson`
  - Agregar a cada incendio: `dist_ruta_km`, `dist_agua_km`, `dist_bomberos_km` (accesibilidad)
  - **Hecho cuando:** los 3 archivos existen y `incendios.geojson` tiene las 3 distancias
- [ ] **W5-F1** · Capas agua, rutas, bomberos + relieve · 👤 ___ · ← W5-D1, W3-F1
  - 3 archivos en `web/layers/` registrados en el panel; rutas con estilo por tipo
  - Relieve sin script: source `raster-dem` (teselas Terrarium de AWS) + capa `hillshade`
  - La ficha del incendio (W2-F3) muestra las 3 distancias
  - **Hecho cuando:** las 4 capas se activan desde el panel

---

## Wave 6 — Después del MVP completo (P2)

> Tareas independientes, en cualquier orden, una vez cerradas las waves 0–5.

- [ ] **W6-1** · Backend FastAPI · D1
  - `api/main.py`: `GET /focos?desde=&hasta=&bbox=`, `GET /incendios`, `GET /alertas`, reutilizando las funciones de `scripts/`
  - **Hecho cuando:** el front puede leer la API y, si no responde, vuelve a los archivos de `web/data/processed/`
- [ ] **W6-2** · Modo en vivo · F1 · ← W6-3
  - Botón "En vivo": muestra las últimas 24 / 48 h, relee los datos cada 5–10 min, animación de "pulso" en los focos nuevos, indicador "Actualizado hace X min"
  - **Hecho cuando:** el modo demo (episodio fijo) sigue siendo el predeterminado y el modo en vivo se activa con un clic
- [ ] **W6-3** · Actualización automática · D2
  - `.github/workflows/update-data.yml` con `schedule` cada 30 min: descarga FIRMS (`DIAS=2`) + toda la cadena de scripts + commit de `web/data/processed/`; MAP_KEY en los secrets del repo
  - **Hecho cuando:** los datos del sitio se actualizan solos
- [ ] **W6-4** · Notificaciones de alertas · D1 · ← W6-3
  - Una alerta nueva `critico` → mensaje por webhook (Telegram / Discord / email)
  - **Hecho cuando:** llega un mensaje de prueba
- [ ] **W6-5** · Proyección de propagación · D2
  - Elipse orientada según el viento, alargada según la velocidad y la pendiente (Copernicus DEM), a 6 h; marcada como "estimación"
  - **Hecho cuando:** `propagacion.geojson` existe y se ve como capa
- [ ] **W6-6** · Exportar la animación (MP4 / GIF) · F1
- [ ] **W6-7** · Interfaz en inglés (`web/i18n.js`) · F2
- [ ] **W6-8** · Versión móvil (paneles plegables) · F2

Otras ideas sin asignar: pendiente media y cobertura del suelo por incendio, ráster de accesibilidad (Malaria Atlas Project), historial de riesgo por incendio, filtros combinados avanzados.

---

## Fuentes de datos

| Uso | Fuente | Acceso |
|---|---|---|
| Focos MODIS / VIIRS | NASA FIRMS | API con MAP_KEY |
| Viento / meteorología | Open-Meteo (archivo histórico, ERA5) | API sin clave |
| Población | WorldPop 1 km | Descarga GeoTIFF por país |
| Agua, rutas, bomberos | OpenStreetMap | Overpass API |
| Relieve | Teselas Terrarium (AWS) | Teselas sin clave |
