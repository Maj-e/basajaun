# Ulinautas

Visualización de focos de incendio a partir de los satélites **MODIS** y **VIIRS** (NASA FIRMS), armonizados en una sola fuente de datos y mostrados en una página web: mapa con capas, calendario, alertas por densidad poblacional y reproducción temporal.

> Proyecto de hackathon (1 día). El plan de trabajo está en [`TODO.md`](TODO.md).

---

## Stack

| Parte | Tecnología | Rol |
|---|---|---|
| Procesamiento de datos | **Python 3.11** · pandas · geopandas · rasterio · rasterstats · scikit-learn · requests | Descargar, armonizar y enriquecer los datos |
| Entorno Python | **uv** (o `venv` + `pip`) | Instalación en segundos |
| Formato de intercambio | **GeoJSON / JSON** estáticos | Contrato entre los scripts y el front |
| Front | **HTML + JavaScript** (módulos ES, sin framework, sin build) | Interfaz |
| Mapa | **MapLibre GL JS 4.7.1** (CDN) | Mapa vectorial, filtros, animación, capas |
| Hosting | **GitHub Pages** + dominio propio | Publicación automática en cada push a `main`, HTTPS gratis |
| CI/CD | **GitHub Actions** | Tests y validación en cada PR, despliegue de `web/`, actualización automática de los datos |

### Por qué esta stack

- **Sin servidor que mantener.** Los datos se calculan con Python, en local o en GitHub Actions cada 30 min (la misma frescura que FIRMS, que publica ~3 h después de cada paso de satélite), y se publican como archivos. La página no depende de ninguna API en vivo: nada puede caerse durante la demo.
- **Python para lo geoespacial.** Proyecciones, rásteres, clustering y estadísticas zonales son mucho más simples en Python que en JavaScript.
- **MapLibre para el mapa.** Gratis, sin clave, muestra decenas de miles de puntos con fluidez y permite filtrar y animar con expresiones, sin recargar los datos.
- **Sin framework ni build.** Nadie pierde tiempo configurando npm, Webpack o Docker. Se abre con `python -m http.server`.
- **Dos equipos que no se bloquean.** El contrato de datos separa la pista datos de la pista front: el front avanza con datos de ejemplo mientras los scripts preparan los reales.

### Alternativas descartadas (por ahora)

| Alternativa | Por qué no hoy | Cuándo sí |
|---|---|---|
| React + Vite | Configuración y gestión de estado de más para un día | Si el proyecto continúa y la interfaz crece |
| deck.gl | Una API más que aprender | Si la animación con MapLibre no es fluida |
| Streamlit | Interfaz y animación limitadas | Si nadie del equipo hace JavaScript |
| FastAPI + PostGIS | Infraestructura de más | Para el modo en tiempo real, después del hackathon |
| Leaflet | Menos rendimiento con muchos puntos | Si alguien lo domina y hay pocos datos |

**Plan B de demo:** si el front falla, `web/data/processed/focos.geojson` se puede arrastrar en [kepler.gl/demo](https://kepler.gl/demo) para tener un mapa animado en 2 minutos.

---

## Arquitectura

```
                 ┌────────────────────── scripts/ (Python, se ejecutan una vez) ──────────────────────┐
                 │                                                                                    │
 NASA FIRMS ───► │ download_firms.py ──► data/raw/*.csv ──► harmonize.py ──► fires.py ──► exposure.py │
 (MODIS, VIIRS)  │                                              │               │             ▲      │
                 │                                              │               │             │      │
 WorldPop ─────► │ population.py ───────────────────────────────┼───────────────┼─────────────┤      │
 Open-Meteo ───► │ weather.py ──────────────────────────────────┼───────────────┼─────────────┘      │
 OpenStreetMap ► │ osm.py ──────────────────────────────────────┼───────────────┤                    │
                 └──────────────────────────────────────────────┼───────────────┼────────────────────┘
                                                                ▼               ▼
                                                  web/data/processed/*.geojson / *.json
                                                                │
                                                                ▼
                                        web/ (HTML + JS + MapLibre) ──► GitHub Pages ──► https://<dominio>
```

1. **Descarga**: los CSV de FIRMS (MODIS + VIIRS S-NPP, NOAA-20, NOAA-21) se guardan en `data/raw/`.
2. **Armonización**: los dos sensores se llevan a un esquema común (confianza, fecha UTC, FRP, brillo, resolución).
3. **Enriquecimiento**: deduplicación MODIS/VIIRS, agrupación en incendios, población expuesta, viento, distancias a agua, rutas y bomberos.
4. **Publicación**: los resultados se escriben en `web/data/processed/`, se versionan y se publican con el sitio.
5. **Visualización**: el front carga esos archivos y todo el filtrado y la animación ocurren en el navegador.

---

## Estructura del proyecto

```
ulinautas/
├── README.md
├── TODO.md                         # roles, tareas por rol, waves, detalle de cada tarea
├── Makefile                        # make data / make test / make serve
├── docs/
│   ├── contrato_datos.md           # formato de cada archivo de datos
│   └── schemas/                    # esquemas JSON validados por el CI
├── requirements.txt
├── .env.example                    # FIRMS_MAP_KEY=
├── .gitignore                      # .env, data/raw/, __pycache__/
├── .github/
│   └── workflows/
│       ├── ci.yml                  # tests + validación del contrato en cada PR
│       ├── deploy.yml              # publica web/ en GitHub Pages en cada push a main
│       ├── e2e.yml                 # valida los datos servidos por la URL publicada
│       └── update-data.yml         # regenera los datos recientes cada 30 min (solo si son válidos)
│
├── data/
│   └── raw/                        # CSV FIRMS descargados (no versionados)
│
├── scripts/                        # BACKEND (B1–B4)
│   ├── config.py                   # zona (bbox), fechas, rutas, umbrales de riesgo
│   ├── make_sample.py              # datos de ejemplo generados desde el contrato
│   ├── download_firms.py           # descarga MODIS + VIIRS desde la API FIRMS
│   ├── harmonize.py                # normalización MODIS / VIIRS
│   ├── export_focos.py             # focos.geojson (ya estilizado) + resumen_diario.json
│   ├── dedup.py                    # deduplicación MODIS / VIIRS
│   ├── fires.py                    # agrupación en incendios → incendios.geojson
│   ├── series.py                   # series temporales por hora
│   ├── population.py               # recorte WorldPop → poblacion.tif / poblacion.png
│   ├── weather.py                  # viento y meteorología por hora → meteo.geojson
│   ├── exposure.py                 # población expuesta + riesgo + viento → alertas.json
│   ├── osm.py                      # agua, rutas, bomberos + distancias por incendio
│   ├── make_manifest.py            # manifest.json: lista de capas disponibles
│   ├── validate.py                 # valida web/data/ contra docs/schemas/
│   ├── check_site.py               # prueba de extremo a extremo sobre la URL publicada
│   └── tests/
│       └── test_harmonize.py
│
└── web/                            # FRONT (F) — todo lo que está aquí se publica
    ├── CNAME                       # nombre de dominio
    ├── index.html                  # estructura de la página (mapa + paneles + línea de tiempo)
    ├── style.css
    ├── app.js                      # crea el mapa, conecta los módulos
    ├── state.js                    # estado global compartido (fecha, filtros, hora, capas)
    ├── filters.js                  # filtros por fecha, sensor, confianza + banda de estado
    ├── calendar.js                 # calendario mensual de focos
    ├── timeline.js                 # reproducción temporal (play / pausa / velocidad)
    ├── alerts.js                   # panel de alertas por población
    ├── live.js                     # modo en vivo (recarga periódica)
    ├── layers/
    │   └── loader.js               # cargador genérico: lee manifest.json y crea cada capa
    └── data/
        ├── manifest.json           # capas disponibles (generado por el backend)
        ├── sample/                 # datos de ejemplo del contrato (para desarrollar el front sin esperar)
        └── processed/              # salidas de los scripts (versionadas y publicadas)
            ├── demo/               # episodio fijo para la reproducción
            └── live/               # últimas 48 h, actualizadas por update-data.yml
```

### Reglas de la estructura

- **Los scripts escriben en `web/data/processed/`**, nunca en otro lugar: así el sitio local y el publicado leen las mismas rutas.
- **En el front, rutas siempre relativas** (`data/processed/focos.geojson`, nunca `/data/...`), para que funcione en el dominio y en `github.io/ulinautas/`.
- **Una capa = un archivo de datos ya estilizado + una entrada en `web/data/manifest.json`.** El cargador genérico del front (`web/layers/loader.js`) la muestra sin código nuevo; el campo `activa` sirve de interruptor.
- **Un solo estado** en `state.js`: los módulos leen `state` y lo cambian con `setState()`; se suscriben con `subscribe()` para reaccionar.
- **`data/raw/` no se versiona** (peso); `web/data/processed/` sí (la demo funciona sin volver a ejecutar nada).

---

## Contrato de datos

| Archivo | Contenido | Producido por |
|---|---|---|
| `focos.geojson` | Un punto por foco, MODIS y VIIRS armonizados | `harmonize.py`, completado por `fires.py` |
| `resumen_diario.json` | Focos y FRP por día (alimenta el calendario) | `harmonize.py` |
| `incendios.geojson` | Polígono por incendio (focos agrupados) | `fires.py`, completado por `osm.py` |
| `alertas.json` | Un registro por incendio con población expuesta y riesgo | `exposure.py` |
| `poblacion.png` | Densidad poblacional recortada a la zona | `population.py` |
| `meteo.json` | Viento, temperatura, humedad, lluvia por hora | `weather.py` |
| `agua.geojson`, `rutas.geojson`, `bomberos.geojson` | Capas OpenStreetMap | `osm.py` |

Esquema detallado de cada archivo y correspondencia de campos MODIS / VIIRS: ver [`docs/contrato_datos.md`](docs/contrato_datos.md).

### Armonización MODIS / VIIRS (resumen)

| | MODIS | VIIRS | Armonizado |
|---|---|---|---|
| Resolución | ~1 km | ~375 m | `resolucion_m` |
| Confianza | 0–100 | `low` / `nominal` / `high` | `baja` / `media` / `alta` |
| Brillo | `brightness` | `bright_ti4` | `brillo_k` |
| Fecha | `acq_date` + `acq_time` | igual | `fecha_hora_utc` (ISO 8601) |
| Doble detección | — | — | un solo foco, `detectado_por: ["MODIS","VIIRS"]` |

---

## Instalación y uso

### Requisitos
- Python 3.11+
- Una clave de API FIRMS: https://firms.modaps.eosdis.nasa.gov/api/map_key/

### Datos
```bash
cp .env.example .env              # poner la FIRMS_MAP_KEY
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

make data                         # ejecuta todos los scripts en orden → web/data/processed/
make test                         # pytest
```

### Front en local
```bash
make serve                        # → http://localhost:8000
```

### Publicación
Cada push a `main` despliega `web/` en GitHub Pages (`.github/workflows/deploy.yml`). El dominio se define en `web/CNAME` y en *Settings → Pages → Custom domain*. Los datos se regeneran solos cada 30 min (`.github/workflows/update-data.yml`, con `FIRMS_MAP_KEY` en los secrets del repo).

---

## Flujo de trabajo del equipo

| Rol | Carpeta |
|---|---|
| **B1–B4** — Backend | `scripts/`, `docs/`, `.github/workflows/ci.yml`, `e2e.yml`, `update-data.yml`, `Makefile` |
| **F** — Front / DevOps | `web/`, `.github/workflows/deploy.yml`, dominio |

- Una tarea de `TODO.md` = una rama `feature/<id>-<nombre>` = un PR corto, con el CI en verde antes del merge.
- `main` siempre funciona y siempre está publicado.

## Fuentes de datos

| Uso | Fuente | Acceso |
|---|---|---|
| Focos MODIS / VIIRS | [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/) | API con MAP_KEY |
| Viento / meteorología | [Open-Meteo](https://open-meteo.com/) (archivo histórico, ERA5) | API sin clave |
| Población | [WorldPop](https://www.worldpop.org/) 1 km | GeoTIFF por país |
| Agua, rutas, bomberos | [OpenStreetMap](https://www.openstreetmap.org/) | Overpass API |
| Relieve | Teselas Terrarium (AWS Open Data) | Teselas sin clave |

## Equipo

- _Nombre_ — rol
