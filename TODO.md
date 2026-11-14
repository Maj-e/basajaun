# TODO — Ulinautas (focos de incendio MODIS + VIIRS)

Equipo: **4 backend** (B1–B4) y **1 front / devops** (F).
Contrato de datos (formatos, manifest de capas, correspondencia MODIS / VIIRS): [`docs/contrato_datos.md`](docs/contrato_datos.md).

---

## 1. Roles

| Rol | Persona | Responsable de |
|---|---|---|
| **B1 — Armonización** | ___ | Contrato de datos (**dueño**), normalización MODIS / VIIRS, deduplicación, riesgo y alertas |
| **B2 — Ingesta e incendios** | ___ | Clave FIRMS y zona, descarga, agrupación en incendios, viento y meteorología, propagación |
| **B3 — Agregados y población** | ___ | Medición del volumen, export de focos, resúmenes (calendario, series temporales), población |
| **B4 — Plataforma de datos** | ___ | Repo y CI, validador del contrato, manifest de capas, pruebas sobre la URL publicada, OSM, actualización automática, API |
| **F — Front / DevOps** | ___ | Página web, cargador genérico de capas, filtros, calendario, línea de tiempo, paneles; despliegue y dominio |

**Principio:** con un solo front, **el backend entrega datos listos para mostrar** (colores, tamaños, leyendas ya calculados) y **declara cada capa en un manifest**. F escribe una vez un cargador genérico; después, **agregar una capa = un archivo + una línea en el manifest**, sin tocar el front.

---

## 2. Tareas por rol

| Wave | B1 — Armonización | B2 — Ingesta e incendios | B3 — Agregados y población | B4 — Plataforma de datos | F — Front / DevOps |
|---|---|---|---|---|---|
| **0 · Base** | **W0-B1** Contrato gelado + datos de ejemplo | **W0-B2** Clave FIRMS + zona + `config.py` | **W0-B3** Medición del volumen FIRMS | **W0-B4** Repo, entorno, Makefile, CI | **W0-F1** Esqueleto web + despliegue |
| **1 · MVP** | **W1-B1** Normalización MODIS / VIIRS + tests | **W1-B2** Descarga FIRMS completa | **W1-B3** Export focos + resumen diario | **W1-B4** Validador del contrato + manifest | **W1-F1** Cargador de capas + capa de focos<br>**W1-F2** Filtros + estado "sin datos" |
| **2 · Calendario + simulación** | **W2-B1** Deduplicación MODIS / VIIRS | **W2-B2** Incendios (agrupación) | **W2-B3** Series temporales (contador, gráfico) | **W2-B4** Prueba de extremo a extremo en la URL | **W2-F1** Calendario<br>**W2-F2** Línea de tiempo + animación |
| **3 · Capas + alerta** | **W3-B1** Población expuesta + riesgo + alertas | **W3-B2** Viento + meteorología | **W3-B3** Población (WorldPop) | **W3-B4** OSM: agua, rutas, bomberos + accesibilidad | **W3-F1** Panel de capas + capas temporales + relieve<br>**W3-F2** Panel de alertas |
| **4 · En vivo** | **W4-B1** Alertas sobre los datos recientes | — | — | **W4-B4** Actualización automática con validación | **W4-F1** Botón "En vivo" |
| **5 · Después** | **W5-B1** Notificaciones | **W5-B2** Proyección de propagación | **W5-B3** Pendiente y cobertura del suelo | **W5-B4** API FastAPI + hosting | **W5-F1** Móvil, inglés, export de la animación |

Casilla **—**: el rol ayuda a los demás (pruebas, revisión de PR, datos para el front).

---

## 3. Waves

Cada wave deja la app **funcionando y publicada**. Desde la Wave 1 hay un MVP presentable; las siguientes agregan features **detrás de un interruptor** (campo `activa` del manifest): una feature que no está lista se queda apagada y no rompe la demo.

| Wave | Objetivo | Resultado visible | Prio |
|---|---|---|---|
| **0 · Base** | Que los 5 trabajen en paralelo desde el inicio | Página en línea con datos de ejemplo, contrato gelado, volumen medido | P0 |
| **1 · MVP** | Leer MODIS + VIIRS armonizados | **Mapa de focos reales con filtros por fecha, sensor y confianza, publicado** | P0 |
| **2 · Calendario + simulación** | Navegar en el tiempo | Calendario de focos, reproducción animada, contorno de los incendios | P0 / P1 |
| **3 · Capas + alerta** | Contexto y riesgo para la población | Capas población, viento, meteo, agua, rutas, bomberos, relieve + panel de alertas | P1 |
| **4 · En vivo** | Foco activo casi en tiempo real | Botón "En vivo": últimas 48 h, actualizadas solas | P1 / P2 |
| **5 · Después** | Pasar de demo a producto | API, notificaciones, propagación, móvil… (independientes) | P2 |

**Prio:** P0 = indispensable para el MVP · P1 = mejora fuerte · P2 = cuando lo anterior esté terminado.

### Reglas del día
1. **El contrato se gela antes del primer filtro** (W0-B1 + F, 20 minutos juntos). Después, todo cambio pasa por B1 y se anuncia a todo el equipo.
2. **El sitio está en línea desde la Wave 0.** El MVP no es "publicar", es reemplazar los datos de ejemplo por los reales.
3. **Una tarea está hecha cuando funciona en la URL publicada**, no "en mi máquina".
4. **Punto de control a mitad de jornada:** si la armonización no está lista, se publica VIIRS solo como repliegue (sin cambiar el objetivo).
5. **Hora de congelación fijada al empezar:** lo que no está empezado a esa hora se abandona; lo que no funciona se apaga en el manifest.
6. Una tarea = una rama `feature/<id>-<nombre>` = un PR corto con el CI en verde.

### Cómo agregar una feature después del MVP
1. Backend: un script en `scripts/` que escribe un archivo en `web/data/processed/` **ya estilizado** (propiedades `color`, `radio`, etc.), agregado a `make data`.
2. Backend: una entrada en `web/data/manifest.json` (tipo de capa, leyenda, `activa: false` hasta que esté verificada).
3. El validador (W1-B4) pasa en el CI → merge → se verifica en la URL → `activa: true`.
4. F solo interviene si la capa necesita un tipo de visualización que el cargador todavía no conoce.

---

## 4. Detalle de las tareas

Formato: **qué hacer** · **archivos** · **hecho cuando** · **depende de**.

### Wave 0 — Base (P0)

- [ ] **W0-B1** · Contrato gelado + datos de ejemplo · **B1** (con F)
  - Sesión de 20 min B1 + F: revisar [`docs/contrato_datos.md`](docs/contrato_datos.md) campo por campo (focos, resumen diario, incendios, alertas, **manifest**, propiedades de estilo, campo `actualizado`) y gelarlo
  - Script que **genera** los datos de ejemplo desde el contrato (no a mano): ~50 focos MODIS + VIIRS en la zona, 3 días, 3 confianzas, con `t`, `color`, `radio`; `resumen_diario`, `alertas`, `manifest.json`
  - Archivos: `scripts/make_sample.py` → `web/data/sample/*`
  - **Hecho cuando:** F carga los archivos de ejemplo sin pedir ningún cambio de formato
  - Depende de: —

- [ ] **W0-B2** · Clave FIRMS + zona + `config.py` · **B2**
  - Pedir la MAP_KEY en https://firms.modaps.eosdis.nasa.gov/api/map_key/ y probarla:
    `curl "https://firms.modaps.eosdis.nasa.gov/api/area/csv/$FIRMS_MAP_KEY/VIIRS_SNPP_NRT/world/1"`
  - Elegir zona y ~2 semanas con un episodio de incendios real (bueno para la reproducción)
    ```python
    BBOX = (-72.0, -38.0, -70.0, -33.0)   # oeste, sur, este, norte → reemplazar
    FECHA_INICIO, FECHA_FIN = "2026-02-01", "2026-02-14"
    RAW = Path("data/raw"); SAMPLE = Path("web/data/sample"); PROCESSED = Path("web/data/processed")
    ```
  - Archivos: `scripts/config.py`, `.env` (local, nunca en el repo)
  - **Hecho cuando:** la API responde y la zona y las fechas están definidas
  - Depende de: —

- [ ] **W0-B3** · Medición del volumen FIRMS · **B3**
  - Primera descarga rápida (VIIRS + MODIS, zona y periodo de demo), contar los focos y medir el peso de un GeoJSON bruto
  - Escribir el resultado en `docs/volumen.md` y decidir con B1: **si el GeoJSON supera ~10 MB**, exportar un archivo por día; si no, un solo archivo
  - Ajustar el número de focos de ejemplo de W0-B1 si el volumen real es muy distinto
  - **Hecho cuando:** el número de focos y el peso están escritos y la decisión "un archivo / uno por día" está tomada
  - Depende de: W0-B2

- [ ] **W0-B4** · Repo, entorno, Makefile, CI · **B4**
  - Estructura de carpetas del [README](README.md#estructura-del-proyecto), `requirements.txt`, `.gitignore` (`.env`, `data/raw/`, `.venv/`), `.env.example`
  - `Makefile`: `make data` (todos los scripts en orden), `make test`, `make serve`
  - `.github/workflows/ci.yml`: `pytest` en cada PR; protección de `main` (PR obligatorio + CI verde)
  - **Hecho cuando:** `make test` pasa en una máquina limpia y un PR con un test roto queda bloqueado
  - Depende de: —

- [ ] **W0-F1** · Esqueleto web + despliegue · **F**
  - `index.html` + MapLibre GL `4.7.1` (unpkg); mapa centrado en la zona; paneles vacíos: izquierda (filtros, calendario, capas), derecha (alertas), abajo (línea de tiempo)
  - `state.js`: estado compartido (`fecha`, `rango`, `sensores`, `confianzas`, `hora`, `capas`) con `setState` / `subscribe`
  - `.github/workflows/deploy.yml`: publica `web/` en GitHub Pages en cada push a `main`
  - **URL de demo: `https://maj-e.github.io/ulinautas/`** hasta que el dominio esté verificado desde fuera (`web/CNAME` + DNS + HTTPS en paralelo, sin bloquear nada)
  - Rutas **siempre relativas** (`data/processed/...`)
  - **Hecho cuando:** el esqueleto con los datos de ejemplo se ve en la URL github.io
  - Depende de: W0-B4 (estructura)

### Wave 1 — MVP (P0)

- [ ] **W1-B1** · Normalización MODIS / VIIRS + tests · **B1**
  - `normalizar_modis(df)`: confianza 0–100 → `baja` (< 30) / `media` (30–79) / `alta` (≥ 80); `brightness` → `brillo_k`; `resolucion_m = 1000`
  - `normalizar_viirs(df, satelite)`: `l`/`low` → baja, `n`/`nominal` → media, `h`/`high` → alta; `bright_ti4` → `brillo_k`; `resolucion_m = 375`
  - `parse_fecha(acq_date, acq_time)`: `str.zfill(4)` (`742` → `0742`) → datetime UTC
  - Tests con 3 filas MODIS + 3 VIIRS escritas a mano
  - Archivos: `scripts/harmonize.py`, `scripts/tests/test_harmonize.py`
  - **Hecho cuando:** `make test` pasa (se empieza con un CSV de prueba, sin esperar W1-B2)
  - Depende de: W0-B1

- [ ] **W1-B2** · Descarga FIRMS completa · **B2**
  - `https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{FUENTE}/{oeste},{sur},{este},{norte}/{DIAS}/{FECHA}`
  - Fuentes `MODIS_NRT`, `VIIRS_SNPP_NRT`, `VIIRS_NOAA20_NRT`, `VIIRS_NOAA21_NRT` (`_SP` para fechas antiguas); bloques de máx. 10 días; no volver a descargar si el archivo existe
  - Verificar los códigos reales de la columna `satellite` y avisar a B1 si difieren del contrato
  - Archivos: `scripts/download_firms.py` → `data/raw/*.csv`
  - **Hecho cuando:** los 4 CSV del periodo están en `data/raw/`
  - Depende de: W0-B2

- [ ] **W1-B3** · Export focos + resumen diario · **B3**
  - Leer `data/raw/*.csv` → funciones de W1-B1 → `pd.concat` → `id`, `fecha`, `t` (horas desde 1970) → filtrar al `BBOX`
  - **Estilo calculado aquí**: `color` según la confianza (`alta` `#d7301f`, `media` `#fc8d59`, `baja` `#fdcc8a`), `radio` según el FRP (3 a 16 px), `borde` según el sensor
  - Coordenadas a 4 decimales, FRP a 1; uno o varios archivos según la decisión de W0-B3
  - `resumen_diario.json`: **todos** los días del periodo (`focos: 0`, `sin_datos: true` si no hay nada)
  - Campo `actualizado` (fecha de generación) en cada archivo
  - Archivos: `scripts/export_focos.py` → `web/data/processed/focos*.geojson`, `resumen_diario.json`
  - **Hecho cuando:** `make data` genera los archivos y el validador (W1-B4) los acepta
  - Depende de: W1-B1, W1-B2, W0-B3

- [ ] **W1-B4** · Validador del contrato + manifest · **B4**
  - Esquemas JSON de cada archivo del contrato (`docs/schemas/*.json`) + `scripts/validate.py` que valida todo `web/data/` (`jsonschema`)
  - Agregar `python scripts/validate.py` al CI
  - `scripts/make_manifest.py`: genera `web/data/manifest.json` con **solo las capas cuyo archivo existe** (nombre, archivo, tipo, temporal, leyenda, `activa`, `actualizado`)
  - **Hecho cuando:** romper un campo en un PR hace fallar el CI, y el manifest refleja los archivos presentes
  - Depende de: W0-B1, W0-B4

- [ ] **W1-F1** · Cargador de capas + capa de focos · **F**
  - `web/layers/loader.js`: lee `manifest.json` y, para cada capa `activa`, crea source + layer según `tipo` (`circle`, `fill`, `line`, `image`) usando **las propiedades de estilo del archivo**:
    ```js
    "circle-color": ["get", "color"], "circle-radius": ["get", "radio"], "circle-stroke-color": ["get", "borde"]
    ```
  - Leyenda generada desde el manifest; popup genérico (muestra las propiedades listadas en el manifest)
  - **Hecho cuando:** los focos de ejemplo se ven con su estilo y popup, sin estilo escrito a mano en el front
  - Depende de: W0-F1, W0-B1

- [ ] **W1-F2** · Filtros + estado "sin datos" · **F**
  - Fecha (`<input type="date">`), sensor (MODIS / VIIRS), confianza → `setState` → `map.setFilter`
  - Banda de estado: "Datos del JJ/MM HH:MM" (campo `actualizado`) o "Capa no disponible" si el archivo falta
  - Pasar `DATA_URL` de `data/sample/` a `data/processed/` cuando W1-B3 esté en `main`
  - **Hecho cuando:** los filtros funcionan **con los datos reales en la URL publicada** → ✅ **MVP**
  - Depende de: W1-F1, W1-B3

### Wave 2 — Calendario + simulación (P0 / P1)

- [ ] **W2-B1** · Deduplicación MODIS / VIIRS · **B1** · P1
  - Proyectar a metros (UTM); distancia < 1 km **y** |Δt| < 60 min → un solo foco (se conserva el VIIRS), `detectado_por: ["MODIS","VIIRS"]`
  - Imprimir cuántos focos se unieron
  - Archivos: `scripts/dedup.py`
  - **Hecho cuando:** el validador acepta el resultado y el número de duplicados está documentado
  - Depende de: W1-B3

- [ ] **W2-B2** · Incendios (agrupación) · **B2** · P1
  - `DBSCAN(eps=1.0, min_samples=2)` sobre `[x_km, y_km, t / 12]` → `incendio_id` en cada foco
  - Polígono por incendio (envolvente convexa + buffer 500 m), **ya estilizado** (`color`, `opacidad`), con `inicio`, `fin`, `n_focos`, `frp_max`, `area_km2`
  - Entrada en el manifest con `activa: false` hasta verificarla
  - Archivos: `scripts/fires.py` → `web/data/processed/incendios.geojson`
  - **Hecho cuando:** los incendios conocidos de la zona salen como 1 grupo y la capa aparece en el mapa sin código front nuevo
  - Depende de: W2-B1

- [ ] **W2-B3** · Series temporales · **B3** · P1
  - Por hora: focos activos y FRP total (para el contador y un mini-gráfico de la línea de tiempo)
  - Archivos: `scripts/series.py` → `web/data/processed/serie_horaria.json`
  - **Hecho cuando:** el archivo cubre todo el periodo, hora por hora, y pasa el validador
  - Depende de: W1-B3

- [ ] **W2-B4** · Prueba de extremo a extremo en la URL · **B4**
  - Job después de cada despliegue: descarga `manifest.json` y cada archivo listado desde la URL publicada, valida contra el contrato, falla si alguno no responde
  - Prueba de carga simple: tiempo de descarga de los archivos de la página inicial
  - Archivos: `.github/workflows/e2e.yml`, `scripts/check_site.py`
  - **Hecho cuando:** un archivo roto o ausente en el sitio publicado hace fallar el job
  - Depende de: W1-B4, W0-F1

- [ ] **W2-F1** · Calendario · **F** · P0
  - Grilla mensual desde `resumen_diario.json`: color por número de focos, días sin datos rayados, número al pasar el ratón
  - Clic → `setState({ fecha })`; Mayús + clic → rango
  - Archivos: `web/calendar.js`
  - **Hecho cuando:** calendario y filtro de fecha siempre sincronizados, en la URL publicada
  - Depende de: W1-F2

- [ ] **W2-F2** · Línea de tiempo + animación · **F** · P1
  - Slider en horas + ▶/⏸ + x1 / x4 / x16; `requestAnimationFrame` avanza `state.hora`
  - El cargador aplica a toda capa `temporal: true`: filtro `t ≤ hora` y `t > hora − 6`, opacidad decreciente (estela de 6 h)
  - Contador y mini-gráfico desde `serie_horaria.json`
  - Archivos: `web/timeline.js`
  - **Hecho cuando:** los focos aparecen a su hora y se apagan en 6 h, de forma fluida con los datos reales
  - Depende de: W1-F2, W2-B3

### Wave 3 — Capas + alerta (P1)

- [ ] **W3-B1** · Población expuesta + riesgo + alertas · **B1**
  - Buffers 1 / 5 / 10 km por incendio, `rasterstats.zonal_stats(stats="sum")` → `pob_1km`, `pob_5km`, `pob_10km`
  - Riesgo (umbrales en `config.py`): `critico` si `pob_1km ≥ 1000` o (`pob_5km ≥ 10000` y `frp_max ≥ 100`) · `alto` si `pob_5km ≥ 1000` · `medio` si `pob_10km ≥ 100` · `bajo` resto
  - +1 nivel si el viento (W3-B2) sopla hacia la zona poblada (< 45°) a ≥ 20 km/h → `viento_hacia_poblacion: true`
  - `desde` = hora del primer foco; `color` por riesgo; ordenadas de más a menos grave
  - Archivos: `scripts/exposure.py` → `web/data/processed/alertas.json`
  - **Hecho cuando:** el validador acepta `alertas.json` y no todo sale `critico`
  - Depende de: W3-B3, W2-B2 (viento opcional: W3-B2)

- [ ] **W3-B2** · Viento + meteorología · **B2**
  - Grilla 5×5 sobre el `BBOX`, una llamada Open-Meteo:
    `https://archive-api.open-meteo.com/v1/archive?latitude=..&longitude=..&start_date=..&end_date=..&hourly=wind_speed_10m,wind_direction_10m,temperature_2m,relative_humidity_2m,precipitation`
  - Salida GeoJSON **temporal**: un punto por celda y por hora con `t`, `dir`, `vel`, `temp`, `humedad`, `lluvia` + estilo (`rotacion`, `tamano`, `color`)
  - Entradas en el manifest: capa "viento" (tipo `flechas`, temporal) y capa "meteo" (tipo `circle`, temporal)
  - Archivos: `scripts/weather.py` → `web/data/processed/meteo.geojson`
  - **Hecho cuando:** el archivo pasa el validador y cubre todas las horas
  - Depende de: W0-B2

- [ ] **W3-B3** · Población (WorldPop) · **B3**
  - WorldPop "Population counts, 1 km, UN adjusted" del país → recorte al `BBOX` (`rasterio.mask`)
  - Exportar `poblacion.tif` (para W3-B1) y `poblacion.png` coloreado + sus 4 esquinas en el manifest (tipo `image`)
  - Archivos: `scripts/population.py`
  - **Hecho cuando:** la imagen se superpone exactamente en el mapa
  - Depende de: W0-B2

- [ ] **W3-B4** · OSM: agua, rutas, bomberos + accesibilidad · **B4**
  - Una sola consulta Overpass en el `BBOX`: agua (`natural=water`, `waterway=river`, `landuse=reservoir`), rutas (`highway=primary|secondary|tertiary|track|path`), bomberos (`amenity=fire_station`)
  - Estilo calculado (color y grosor por tipo de ruta), geometrías simplificadas
  - A cada incendio: `dist_ruta_km`, `dist_agua_km`, `dist_bomberos_km`
  - Archivos: `scripts/osm.py` → `agua.geojson`, `rutas.geojson`, `bomberos.geojson` + entradas en el manifest
  - **Hecho cuando:** las 3 capas aparecen en el panel sin código front nuevo y los incendios tienen las 3 distancias
  - Depende de: W2-B2

- [ ] **W3-F1** · Panel de capas + capas temporales + relieve · **F**
  - Panel de casillas generado desde el manifest (una casilla por capa `activa`)
  - Nuevo tipo `flechas` en el cargador: capa `symbol` con `icon-rotate: ["get","rotacion"]`, `icon-size: ["get","tamano"]`
  - Relieve: source `raster-dem` (teselas Terrarium de AWS) + capa `hillshade`
  - Ficha del incendio: muestra las distancias de W3-B4
  - **Hecho cuando:** todas las capas del manifest se activan desde el panel y el viento gira durante la reproducción
  - Depende de: W2-F2

- [ ] **W3-F2** · Panel de alertas · **F**
  - Lista desde `alertas.json`: color por riesgo, población a 5 km, hora; clic → `map.flyTo({ center, zoom: 11 })`
  - Durante la reproducción: solo las alertas con `desde ≤ state.hora`
  - Archivos: `web/alerts.js`
  - **Hecho cuando:** alertas clicables y sincronizadas con la línea de tiempo, en la URL publicada
  - Depende de: W1-F2 (con `alertas` de ejemplo), W3-B1

### Wave 4 — En vivo (P1 / P2)

- [ ] **W4-B4** · Actualización automática con validación · **B4**
  - `.github/workflows/update-data.yml` cada 30 min + lanzamiento manual: descarga las últimas 48 h → pipeline → **`validate.py`** → commit **solo si es válido**; si no, se conserva el último archivo bueno
  - Datos en `web/data/processed/live/` (el episodio de demo no se toca)
  - `FIRMS_MAP_KEY` en los secrets del repo, nunca en el navegador
  - **Hecho cuando:** un lanzamiento manual actualiza `live/`, y un archivo inválido no llega al sitio
  - Depende de: W1-B4, W2-B4

- [ ] **W4-B1** · Alertas sobre los datos recientes · **B1**
  - Ejecutar dedup + incendios + exposición sobre `live/` → `live/alertas.json`
  - **Hecho cuando:** el modo en vivo tiene sus propias alertas válidas
  - Depende de: W4-B4, W3-B1

- [ ] **W4-F1** · Botón "En vivo" · **F**
  - Botón en la barra inferior: cambia la base de datos de `processed/` a `processed/live/`, relee el manifest cada 5 min, "pulso" en los focos nuevos, indicador "Actualizado hace X min"
  - El modo demo (episodio fijo) sigue siendo el predeterminado; `activa: false` si el modo en vivo no está listo
  - **Hecho cuando:** un clic pasa al modo en vivo y aparecen los focos recientes sin recargar
  - Depende de: W4-B4

### Wave 5 — Después (P2, independientes)

- [ ] **W5-B1** · Notificaciones · **B1** — alerta nueva `critico` en `live/` → mensaje por webhook (Telegram / Discord / email)
- [ ] **W5-B2** · Proyección de propagación · **B2** — elipse a 6 h según viento y pendiente, capa "estimación" en el manifest
- [ ] **W5-B3** · Pendiente y cobertura del suelo · **B3** — pendiente media por incendio (Copernicus DEM), vegetación (ESA WorldCover)
- [ ] **W5-B4** · API FastAPI + hosting · **B4** — `GET /focos?desde=&hasta=&bbox=`, `/incendios`, `/alertas` en `api.<dominio>` (Render / Railway / Fly.io), con respaldo: si la API no responde, el front lee los archivos estáticos
- [ ] **W5-F1** · Móvil, inglés, export de la animación · **F** — paneles plegables, `web/i18n.js`, captura MP4 / GIF
