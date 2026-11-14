# TODO — Ulinautas (focos de incendio MODIS + VIIRS)

Contrato de datos (formato de cada archivo, correspondencia de campos MODIS / VIIRS): [`docs/contrato_datos.md`](docs/contrato_datos.md).

---

## 1. Roles

| Rol | Persona | Responsable de |
|---|---|---|
| **D1 — Datos: armonización** | ___ | Descarga FIRMS, armonización MODIS / VIIRS, incendios, riesgo y alertas. **Dueño del contrato de datos.** |
| **D2 — Datos: contexto** | ___ | Datos de ejemplo, normalización y tests, población, meteorología, propagación. |
| **F — Front** | ___ | Toda la interfaz: mapa, capas, filtros, calendario, línea de tiempo, alertas. **Dueño de `web/`.** |
| **O — DevOps** | ___ | Repo y entorno, despliegue y dominio, CI, pipeline de datos automático, modo en vivo, rendimiento. **Dueño de `main` y de `.github/`.** |

---

## 2. Tareas por rol

| Wave | D1 — Datos: armonización | D2 — Datos: contexto | F — Front | O — DevOps |
|---|---|---|---|---|
| **0 · Base** | **W0-D1** Clave FIRMS + zona y periodo de demo | **W0-D2** Contrato + datos de ejemplo | **W0-F1** Esqueleto web: mapa + paneles + estado | **W0-O1** Repo y entorno<br>**W0-O2** Despliegue en el dominio |
| **1 · MVP** | **W1-D1** Descarga FIRMS<br>**W1-D3** Export focos + resumen diario | **W1-D2** Normalización MODIS / VIIRS + tests | **W1-F1** Capa de focos: estilo, leyenda, popup<br>**W1-F2** Filtros fecha / sensor / confianza | **W1-O1** Pipeline en un comando + CI<br>**W1-O2** Datos reales en el sitio publicado |
| **2 · Calendario + simulación** | **W2-D1** Deduplicación + incendios | — | **W2-F1** Calendario<br>**W2-F2** Línea de tiempo + animación<br>**W2-F3** Capa de incendios | **W2-O1** Actualización automática de los datos |
| **3 · Alerta población** | **W3-D2** Población expuesta + riesgo + alertas | **W3-D1** Capa de población | **W3-F1** Panel de capas + población + alertas | **W3-O1** Validación del contrato + chequeo post-despliegue |
| **4 · Viento + tiempo** | — | **W4-D1** Meteo + riesgo por viento | **W4-F1** Capas viento + meteorología | **W4-O1** Modo en vivo |
| **5 · Agua, rutas, terreno** | **W5-D1** OSM: agua, rutas, bomberos + distancias | — | **W5-F1** Capas agua, rutas, bomberos + relieve | **W5-O1** Rendimiento y peso de los datos |
| **6 · Después** | **W6-D1** API FastAPI<br>**W6-D2** Notificaciones | **W6-D3** Proyección de propagación | **W6-F1** Exportar la animación<br>**W6-F2** Inglés + móvil | **W6-O1** Hosting de la API + respaldo estático |

Casilla **—**: el rol ayuda a los demás en esa wave. Regla: **si F se atrasa, O o D2 toman la siguiente tarea front libre.**

---

## 3. Waves

Cada wave deja la app **funcionando y publicada**. Desde la Wave 1 hay un MVP presentable; las siguientes agregan **una feature a la vez**, sin romper lo anterior. No se empieza una wave sin cerrar la anterior.

| Wave | Objetivo | Resultado visible | Prio |
|---|---|---|---|
| **0 · Base** | Que todos puedan trabajar en paralelo | Mapa vacío en el dominio, datos de ejemplo, CI listo | P0 |
| **1 · MVP** | Leer MODIS + VIIRS armonizados | **Mapa de focos reales con filtros por fecha, sensor y confianza** | P0 |
| **2 · Calendario + simulación** | Navegar en el tiempo | Calendario de focos + reproducción animada + datos que se actualizan solos | P0 / P1 |
| **3 · Alerta población** | Saber qué incendios amenazan a la gente | Capa de densidad poblacional + panel de alertas por riesgo | P1 |
| **4 · Viento + tiempo** | Entender hacia dónde avanza el fuego | Flechas de viento animadas, capa meteo, botón "En vivo" | P1 |
| **5 · Agua, rutas, terreno** | Ayudar a la intervención | Capas agua, rutas, bomberos, relieve + accesibilidad por incendio | P2 |
| **6 · Después** | Pasar de demo a producto | API, notificaciones, propagación, móvil… (independientes, en cualquier orden) | P2 |

**Prio:** P0 = indispensable para el MVP · P1 = mejora fuerte · P2 = cuando lo anterior esté terminado.

### Cómo agregar una feature después del MVP
1. Agregar una fila en la tabla de la sección 2 y su detalle en la sección 4.
2. Si necesita datos: un script en `scripts/` que escribe en `web/data/processed/`, agregado al pipeline (`make data`) y documentado en el contrato.
3. Si es una capa: un archivo en `web/layers/` registrado en `web/layers/index.js`, nada más.
4. Una tarea = una rama `feature/<id>-<nombre>` = un PR corto; el CI debe pasar antes del merge.

---

## 4. Detalle de las tareas

Formato: **qué hacer** · **archivos** · **hecho cuando** (criterio verificable) · **depende de**.

### Wave 0 — Base (P0)

- [ ] **W0-D1** · Clave FIRMS + zona y periodo de demo · **D1**
  - Pedir la MAP_KEY en https://firms.modaps.eosdis.nasa.gov/api/map_key/ y probarla:
    `curl "https://firms.modaps.eosdis.nasa.gov/api/area/csv/$FIRMS_MAP_KEY/VIIRS_SNPP_NRT/world/1"`
  - Elegir una zona y ~2 semanas con incendios bien visibles en el visor FIRMS (un episodio real, bueno para la reproducción)
  - Escribirlo en `scripts/config.py`:
    ```python
    BBOX = (-72.0, -38.0, -70.0, -33.0)   # oeste, sur, este, norte → reemplazar
    FECHA_INICIO, FECHA_FIN = "2026-02-01", "2026-02-14"
    RAW = Path("data/raw"); SAMPLE = Path("web/data/sample"); PROCESSED = Path("web/data/processed")
    ```
  - Archivos: `scripts/config.py`, `.env` (local, nunca en el repo)
  - **Hecho cuando:** la API responde con la clave y `config.py` tiene zona y fechas definitivas
  - Depende de: —

- [ ] **W0-D2** · Contrato + datos de ejemplo · **D2**
  - Validar con el equipo el esquema de [`docs/contrato_datos.md`](docs/contrato_datos.md)
  - Escribir a mano (o con un script) datos falsos pero realistas en la zona de demo:
    - `focos_sample.geojson`: ~50 focos, MODIS + VIIRS, 3 días, 3 niveles de confianza, con `t`
    - `resumen_diario_sample.json`, `alertas_sample.json`
  - Archivos: `web/data/sample/*`
  - **Hecho cuando:** los 3 archivos respetan el contrato y están en `main` (F trabaja con ellos desde el inicio)
  - Depende de: —

- [ ] **W0-F1** · Esqueleto web: mapa + paneles + estado · **F**
  - `index.html` carga MapLibre GL `4.7.1` desde unpkg; fondo `https://demotiles.maplibre.org/style.json` o teselas raster OSM
  - Diseño: mapa al centro, panel izquierdo (filtros, calendario, capas), panel derecho (alertas), barra inferior (línea de tiempo)
  - Estado compartido en `state.js`:
    ```js
    export const state = { fecha: null, rango: null, sensores: ["MODIS","VIIRS"], confianzas: ["baja","media","alta"], hora: null, capas: {} };
    const listeners = [];
    export const subscribe = f => listeners.push(f);
    export function setState(c) { Object.assign(state, c); listeners.forEach(f => f(state)); }
    ```
  - Archivos: `web/index.html`, `web/style.css`, `web/app.js`, `web/state.js`
  - **Hecho cuando:** `cd web && python -m http.server 8000` muestra el mapa centrado en la zona con los paneles vacíos
  - Depende de: W0-D1 (solo para el centro del mapa)

- [ ] **W0-O1** · Repo y entorno · **O**
  - Crear la estructura de carpetas del [README](README.md#estructura-del-proyecto)
  - `requirements.txt` (pandas, geopandas, requests, rasterio, rasterstats, scikit-learn, pytest, python-dotenv)
  - `.gitignore` (`.env`, `data/raw/`, `__pycache__/`, `.venv/`), `.env.example` con `FIRMS_MAP_KEY=`
  - Protección de `main` en GitHub: PR obligatorio + CI verde; plantilla de PR (`.github/pull_request_template.md`)
  - **Hecho cuando:** `uv venv && uv pip install -r requirements.txt` funciona en una máquina limpia y nadie puede hacer push directo a `main`
  - Depende de: —

- [ ] **W0-O2** · Despliegue en el dominio · **O** · *empezar primero: el DNS puede tardar*
  - `.github/workflows/deploy.yml`: publica la carpeta `web/` en GitHub Pages en cada push a `main`
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
  - `web/CNAME` con el dominio; en GitHub: *Settings → Pages → Source: GitHub Actions* + *Custom domain*
  - DNS: subdominio → `CNAME app → maj-e.github.io`; raíz → 4 registros `A` (`185.199.108.153`, `.109.153`, `.110.153`, `.111.153`)
  - Cloudflare: proxy **desactivado** hasta que GitHub emita el certificado; luego *Enforce HTTPS*
  - Plan B si el DNS no está listo: `https://maj-e.github.io/ulinautas/` (por eso las rutas del front son **siempre relativas**)
  - **Hecho cuando:** `https://<dominio>` muestra el esqueleto de W0-F1 con HTTPS
  - Depende de: W0-O1

### Wave 1 — MVP (P0)

- [ ] **W1-D1** · Descarga FIRMS · **D1**
  - Endpoint: `https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{FUENTE}/{oeste},{sur},{este},{norte}/{DIAS}/{FECHA}`
  - Fuentes: `MODIS_NRT`, `VIIRS_SNPP_NRT`, `VIIRS_NOAA20_NRT`, `VIIRS_NOAA21_NRT` (`_SP` para fechas antiguas)
  - `DIAS` limitado (máx. 10): cortar el periodo en bloques y concatenar; no volver a descargar si el archivo existe
  - Verificar los códigos reales de la columna `satellite` y corregir el contrato si hace falta
  - Archivos: `scripts/download_firms.py` → `data/raw/{FUENTE}_{inicio}_{fin}.csv`
  - **Hecho cuando:** los 4 CSV del periodo están en `data/raw/`
  - Depende de: W0-D1

- [ ] **W1-D2** · Normalización MODIS / VIIRS + tests · **D2**
  - `normalizar_modis(df)`: confianza 0–100 → `baja` (< 30) / `media` (30–79) / `alta` (≥ 80); `brightness` → `brillo_k`; `resolucion_m = 1000`
  - `normalizar_viirs(df, satelite)`: `l`/`low` → baja, `n`/`nominal` → media, `h`/`high` → alta; `bright_ti4` → `brillo_k`; `resolucion_m = 375`
  - `parse_fecha(acq_date, acq_time)`: `acq_time` con `str.zfill(4)` (`742` → `0742`) → datetime UTC
  - Tests con 3 filas MODIS + 3 VIIRS escritas a mano: columnas del contrato, confianza válida, fecha UTC correcta
  - Archivos: `scripts/harmonize.py`, `scripts/tests/test_harmonize.py`
  - **Hecho cuando:** `pytest scripts/tests` pasa (se puede empezar con un CSV de prueba, sin esperar W1-D1)
  - Depende de: W0-D2

- [ ] **W1-D3** · Export focos + resumen diario · **D1**
  - `harmonize.py main()`: leer `data/raw/*.csv` → normalizar → `pd.concat` → calcular `id`, `fecha`, `t` (horas desde 1970) → filtrar al `BBOX` → GeoJSON
  - Redondear coordenadas a 4 decimales y FRP a 1 para reducir el peso
  - `resumen_diario.json`: **todos** los días del periodo, con `focos: 0` y `sin_datos: true` si no hay nada
  - Archivos: `web/data/processed/focos.geojson`, `web/data/processed/resumen_diario.json`
  - **Hecho cuando:** `python scripts/harmonize.py` genera los 2 archivos y `focos.geojson` pesa < 10 MB
  - Depende de: W1-D1, W1-D2

- [ ] **W1-F1** · Capa de focos: estilo, leyenda, popup · **F**
  - Source `geojson` + capa `circle`, primero con `data/sample/focos_sample.geojson`:
    ```js
    "circle-color": ["match", ["get","confianza"], "alta","#d7301f", "media","#fc8d59", "baja","#fdcc8a", "#999"],
    "circle-radius": ["interpolate", ["linear"], ["get","frp"], 0,3, 50,8, 500,16],
    "circle-stroke-color": ["match", ["get","sensor"], "MODIS","#ffffff", "#222222"],
    "circle-stroke-width": 1.5
    ```
  - Leyenda fija (colores, tamaños, bordes); popup al clic (sensor, satélite, fecha/hora UTC, confianza, FRP, coordenadas); cursor `pointer`
  - Archivos: `web/layers/focos.js`, `web/style.css`
  - **Hecho cuando:** con los datos de ejemplo se distinguen confianza, FRP y sensor, y el popup funciona
  - Depende de: W0-F1, W0-D2

- [ ] **W1-F2** · Filtros fecha / sensor / confianza · **F**
  - `<input type="date">` + casillas MODIS / VIIRS + casillas de confianza → `setState` → `map.setFilter("focos", ...)`
    ```js
    ["all",
      ["==", ["get","fecha"], state.fecha],
      ["in", ["get","sensor"], ["literal", state.sensores]],
      ["in", ["get","confianza"], ["literal", state.confianzas]]]
    ```
  - Archivos: `web/filters.js`
  - **Hecho cuando:** cada filtro actualiza el mapa al instante, sin recargar
  - Depende de: W1-F1

- [ ] **W1-O1** · Pipeline en un comando + CI · **O**
  - `Makefile`: `make data` (ejecuta los scripts en orden), `make test` (pytest), `make serve` (servidor local en `web/`)
  - `.github/workflows/ci.yml` en cada PR: instalar dependencias + `pytest` + verificar que los JSON de `web/data/` se pueden leer
  - **Hecho cuando:** `make data` regenera todo desde cero y un PR con un test roto queda bloqueado
  - Depende de: W0-O1, W1-D2

- [ ] **W1-O2** · Datos reales en el sitio publicado · **O**
  - Cambiar `DATA_URL` en `web/app.js` de `data/sample/focos_sample.geojson` a `data/processed/focos.geojson`
  - Comprobar en el dominio: tiempo de carga, peso transferido (GitHub Pages comprime en gzip), ningún error en la consola
  - **Hecho cuando:** el MVP funciona en `https://<dominio>` con los datos reales → ✅ **MVP**
  - Depende de: W1-D3, W1-F2, W0-O2

### Wave 2 — Calendario + simulación (P0 / P1)

- [ ] **W2-D1** · Deduplicación + incendios · **D1** · P1
  - Proyectar a metros (UTM de la zona)
  - Deduplicar: distancia < 1 km **y** |Δt| < 60 min → conservar el VIIRS (más preciso), `detectado_por: ["MODIS","VIIRS"]`; imprimir cuántos se unieron
  - Incendios: `DBSCAN(eps=1.0, min_samples=2)` sobre `[x_km, y_km, t / 12]` → `incendio_id` en cada foco
  - Polígono por incendio: envolvente convexa + buffer 500 m; propiedades `incendio_id`, `inicio`, `fin`, `n_focos`, `frp_max`, `frp_total`, `area_km2`
  - Archivos: `scripts/fires.py` → `web/data/processed/incendios.geojson` (+ actualiza `focos.geojson`)
  - **Hecho cuando:** los incendios conocidos de la zona salen como 1 grupo y no como 50
  - Depende de: W1-D3

- [ ] **W2-F1** · Calendario · **F** · P0
  - Grilla mensual de 7 columnas generada en JS, color según `focos` (5 tonos), gris rayado si `sin_datos`, número al pasar el ratón, flechas de mes
  - Clic → `setState({ fecha })`; Mayús + clic → `setState({ rango: [inicio, fin] })`; el filtro de W1-F2 acepta el rango (`>=` / `<=`)
  - Archivos: `web/calendar.js` (empezar con `resumen_diario_sample.json`)
  - **Hecho cuando:** calendario y selector de fecha quedan siempre sincronizados
  - Depende de: W1-F2

- [ ] **W2-F2** · Línea de tiempo + animación · **F** · P1
  - `<input type="range">` en horas + ⏮ ▶/⏸ ⏭ + velocidad x1 / x4 / x16; bucle con `requestAnimationFrame` que avanza `state.hora`
  - Filtro: `t ≤ hora` y `t > hora − 6`; opacidad `["interpolate", ["linear"], ["-", hora, ["get","t"]], 0,1, 6,0.1]` (estela de 6 h)
  - Contador "Focos activos: N · FRP: X MW"
  - Archivos: `web/timeline.js`
  - **Hecho cuando:** los focos aparecen a su hora y se apagan en 6 h, de forma fluida con los datos de demo
  - Depende de: W1-F2

- [ ] **W2-F3** · Capa de incendios · **F** · P1
  - Polígonos `fill` semitransparentes + contorno; clic → ficha (inicio, duración, focos, FRP máx, área)
  - Archivos: `web/layers/incendios.js`
  - **Hecho cuando:** contornos visibles y ficha al hacer clic
  - Depende de: W2-D1

- [ ] **W2-O1** · Actualización automática de los datos · **O** · P1
  - `.github/workflows/update-data.yml` con `schedule` (cada 30 min) + `workflow_dispatch`: `make data` + commit de `web/data/processed/` si cambió → dispara el despliegue
  - `FIRMS_MAP_KEY` en los *secrets* del repo
  - Mantener el episodio de demo fijo en `web/data/processed/demo/` y los datos recientes en `web/data/processed/live/` (para W4-O1)
  - **Hecho cuando:** un lanzamiento manual del workflow actualiza los datos del sitio sin intervención
  - Depende de: W1-O1

### Wave 3 — Alerta población (P1)

- [ ] **W3-D1** · Capa de población · **D2**
  - WorldPop "Population counts, 1 km, UN adjusted" del país → recorte al `BBOX` con `rasterio.mask`
  - Exportar el ráster para los cálculos y una imagen coloreada para el front (con sus 4 esquinas en un JSON)
  - Archivos: `scripts/population.py` → `poblacion.tif`, `poblacion.png`, `poblacion_bounds.json`
  - **Hecho cuando:** la imagen se superpone exactamente en el mapa
  - Depende de: W0-D1

- [ ] **W3-D2** · Población expuesta + riesgo + alertas · **D1**
  - Buffers de 1 / 5 / 10 km por incendio, `rasterstats.zonal_stats(stats="sum")` → `pob_1km`, `pob_5km`, `pob_10km`
  - Riesgo (umbrales en `config.py`):
    | Riesgo | Regla |
    |---|---|
    | `critico` | `pob_1km ≥ 1000` o (`pob_5km ≥ 10000` y `frp_max ≥ 100`) |
    | `alto` | `pob_5km ≥ 1000` |
    | `medio` | `pob_10km ≥ 100` |
    | `bajo` | resto |
  - `desde` = hora del primer foco del incendio; ordenar de más a menos grave
  - Archivos: `scripts/exposure.py` → `web/data/processed/alertas.json`
  - **Hecho cuando:** `alertas.json` respeta el contrato y no todo sale `critico`
  - Depende de: W3-D1, W2-D1

- [ ] **W3-F1** · Panel de capas + población + alertas · **F**
  - Registro de capas: cada archivo de `web/layers/` exporta `{ id, nombre, agregar(map), mostrar(visible) }`; el panel de casillas se genera solo
  - Capa población: source `type: "image"` con `poblacion.png`, opacidad 0.6, leyenda hab/km²
  - Panel de alertas: color por riesgo, población a 5 km, hora; clic → `map.flyTo({ center, zoom: 11 })`; durante la reproducción solo las alertas con `desde ≤ state.hora`
  - Archivos: `web/layers/index.js`, `web/layers/poblacion.js`, `web/alerts.js` (empezar con `alertas_sample.json`)
  - **Hecho cuando:** capa activable, alertas clicables y sincronizadas con la línea de tiempo
  - Depende de: W2-F2

- [ ] **W3-O1** · Validación del contrato + chequeo post-despliegue · **O**
  - Esquemas JSON (`docs/schemas/*.json`) de cada archivo del contrato; el CI valida `web/data/` contra ellos (`jsonschema`)
  - Después de cada despliegue: un job que descarga `https://<dominio>/data/processed/*.json` y falla si alguno no responde o no es válido
  - **Hecho cuando:** romper un campo en un PR hace fallar el CI
  - Depende de: W1-O1, W0-D2

### Wave 4 — Viento + tiempo (P1)

- [ ] **W4-D1** · Meteo + riesgo por viento · **D2**
  - Grilla 5×5 sobre el `BBOX`, una sola llamada con coordenadas separadas por comas:
    `https://archive-api.open-meteo.com/v1/archive?latitude=..&longitude=..&start_date=..&end_date=..&hourly=wind_speed_10m,wind_direction_10m,temperature_2m,relative_humidity_2m,precipitation`
  - Salida `meteo.json`: `{ "puntos": [[lon,lat],...], "horas": [...], "viento_vel": [[...]], "viento_dir": [[...]], "temp": [[...]], "humedad": [[...]], "lluvia": [[...]] }`
  - En `exposure.py`: si el viento sopla hacia el píxel más poblado a < 10 km (diferencia < 45° con `dir + 180°`) y `vel ≥ 20 km/h` → riesgo +1 nivel, `viento_hacia_poblacion: true`
  - Archivos: `scripts/weather.py`, `scripts/exposure.py`
  - **Hecho cuando:** `meteo.json` completo y el campo aparece en `alertas.json`
  - Depende de: W0-D1, W3-D2

- [ ] **W4-F1** · Capas viento + meteorología · **F**
  - Viento: capa `symbol` con ícono de flecha, `icon-rotate` = dirección, tamaño según velocidad, actualizada con `state.hora` (hora más cercana de `meteo.json`)
  - Meteo: puntos coloreados por la variable elegida (temperatura / humedad / lluvia) + leyenda
  - Archivos: `web/layers/viento.js`, `web/layers/meteo.js`
  - **Hecho cuando:** las flechas giran durante la reproducción y se puede cambiar de variable
  - Depende de: W4-D1, W3-F1

- [ ] **W4-O1** · Modo en vivo · **O**
  - El pipeline (W2-O1) genera además `live/focos_48h.geojson` con las últimas 48 h
  - Botón "En vivo" en la barra inferior: cambia `DATA_URL` a `live/`, relee cada 5 min, animación de "pulso" en los focos nuevos, indicador "Actualizado hace X min"
  - El modo demo (episodio fijo) sigue siendo el predeterminado
  - Archivos: `scripts/live.py`, `web/live.js`
  - **Hecho cuando:** un clic pasa al modo en vivo y aparecen los focos recientes sin recargar la página
  - Depende de: W2-O1, W2-F2

### Wave 5 — Agua, rutas, terreno (P2)

- [ ] **W5-D1** · OSM: agua, rutas, bomberos + distancias · **D1**
  - Una sola consulta Overpass en el `BBOX`: agua (`natural=water`, `waterway=river`, `landuse=reservoir`), rutas (`highway=primary|secondary|tertiary|track|path`), bomberos (`amenity=fire_station`)
  - A cada incendio: `dist_ruta_km`, `dist_agua_km`, `dist_bomberos_km` (accesibilidad)
  - Archivos: `scripts/osm.py` → `agua.geojson`, `rutas.geojson`, `bomberos.geojson`
  - **Hecho cuando:** los 3 archivos existen y `incendios.geojson` tiene las 3 distancias
  - Depende de: W2-D1

- [ ] **W5-F1** · Capas agua, rutas, bomberos + relieve · **F**
  - 3 capas registradas en el panel; rutas con estilo por tipo
  - Relieve sin script: source `raster-dem` (teselas Terrarium de AWS) + capa `hillshade`
  - La ficha del incendio (W2-F3) muestra las 3 distancias
  - Archivos: `web/layers/agua.js`, `rutas.js`, `bomberos.js`, `relieve.js`
  - **Hecho cuando:** las 4 capas se activan desde el panel
  - Depende de: W5-D1, W3-F1

- [ ] **W5-O1** · Rendimiento y peso de los datos · **O**
  - Medir peso y tiempo de carga de cada capa; presupuesto: página inicial < 5 MB
  - Si se supera: cargar las capas solo al activarlas, simplificar geometrías OSM (`mapshaper`), cortar los focos por día
  - **Hecho cuando:** carga inicial < 3 s en una conexión normal, verificado en el dominio
  - Depende de: W5-D1

### Wave 6 — Después (P2, tareas independientes)

- [ ] **W6-D1** · API FastAPI · **D1** — `api/main.py`: `GET /focos?desde=&hasta=&bbox=`, `/incendios`, `/alertas`, reutilizando las funciones de `scripts/`
- [ ] **W6-D2** · Notificaciones · **D1** — una alerta nueva `critico` → mensaje por webhook (Telegram / Discord / email)
- [ ] **W6-D3** · Proyección de propagación · **D2** — elipse a 6 h según viento y pendiente (Copernicus DEM), marcada como "estimación"
- [ ] **W6-F1** · Exportar la animación (MP4 / GIF) · **F**
- [ ] **W6-F2** · Interfaz en inglés (`web/i18n.js`) + versión móvil (paneles plegables) · **F**
- [ ] **W6-O1** · Hosting de la API · **O** — Render / Railway / Fly.io en `api.<dominio>`, CORS, y respaldo: si la API no responde, el front lee los archivos estáticos
