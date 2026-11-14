# TODO — Ulinautas (focos de incendio MODIS + VIIRS)

Detalle técnico de cada tarea (archivos, código, criterio de "hecho", contrato de datos): [`docs/detalle_tareas.md`](docs/detalle_tareas.md).

---

## 1. Roles

| Rol | Persona | Responsable de |
|---|---|---|
| **D1 — Datos: armonización** | ___ | Descarga FIRMS, armonización MODIS / VIIRS, incendios, alertas. Dueño del contrato de datos. |
| **D2 — Datos: contexto** | ___ | Datos de ejemplo, normalización y tests, población, meteorología, automatización. |
| **F1 — Front: mapa y animación** | ___ | Mapa, capas, línea de tiempo, animación, modo en vivo. Dueño de `app.js` y `state.js`. |
| **F2 — Front: interfaz y despliegue** | ___ | Dominio y despliegue, filtros, calendario, paneles de capas y alertas. Dueño de `main`. |

---

## 2. Tareas por rol

| Wave | D1 — Datos: armonización | D2 — Datos: contexto | F1 — Front: mapa y animación | F2 — Front: interfaz y despliegue |
|---|---|---|---|---|
| **0 · Base** | **W0-D1** Configuración + clave FIRMS + zona de demo | **W0-D2** Datos de ejemplo del contrato | **W0-F1** Esqueleto web: mapa + paneles + estado | **W0-F2** Publicar el sitio en el dominio |
| **1 · MVP** | **W1-D1** Descarga FIRMS (MODIS + VIIRS)<br>**W1-D3** Export `focos.geojson` + `resumen_diario.json` | **W1-D2** Normalización MODIS + VIIRS + tests | **W1-F1** Capa de focos: estilo, leyenda, popup | **W1-F2** Filtros fecha / sensor / confianza + datos reales |
| **2 · Calendario + simulación** | **W2-D1** Deduplicación + agrupación en incendios | — | **W2-F2** Línea de tiempo + animación + contador | **W2-F1** Calendario conectado al mapa<br>**W2-F3** Capa de incendios + ficha |
| **3 · Alerta población** | **W3-D2** Población expuesta + riesgo + `alertas.json` | **W3-D1** Capa de población (WorldPop) | — | **W3-F1** Panel de capas + capa población + panel de alertas |
| **4 · Viento + tiempo** | — | **W4-D1** Meteo por hora + riesgo ajustado por el viento | **W4-F1** Capas viento + meteorología | — |
| **5 · Agua, rutas, terreno** | **W5-D1** OSM: agua, rutas, bomberos + distancias | — | **W5-F1** Capas agua, rutas, bomberos + relieve | — |
| **6 · Después** | **W6-1** Backend FastAPI<br>**W6-4** Notificaciones de alertas | **W6-3** Actualización automática (GitHub Actions)<br>**W6-5** Proyección de propagación | **W6-2** Modo en vivo<br>**W6-6** Exportar la animación | **W6-7** Interfaz en inglés<br>**W6-8** Versión móvil |

Una casilla con **—**: el rol ayuda a los demás en esa wave (pruebas, integración, bugs).

---

## 3. Waves

Cada wave deja la app **funcionando y publicada**. A partir de la Wave 1 ya hay un MVP presentable; las siguientes agregan **una feature a la vez**, sin romper lo anterior. No se empieza una wave sin haber cerrado la anterior.

| Wave | Objetivo | Resultado visible | Prio | Tareas |
|---|---|---|---|---|
| **0 · Base** | Que todos puedan trabajar en paralelo | Mapa vacío en el dominio + datos de ejemplo | P0 | W0-D1 · W0-D2 · W0-F1 · W0-F2 |
| **1 · MVP** | Leer MODIS + VIIRS armonizados | **Mapa de focos reales con filtros por fecha, sensor y confianza** | P0 | W1-D1 · W1-D2 · W1-D3 · W1-F1 · W1-F2 |
| **2 · Calendario + simulación** | Navegar en el tiempo | Calendario de focos + reproducción animada de los incendios | P0 / P1 | W2-D1 · W2-F1 · W2-F2 · W2-F3 |
| **3 · Alerta población** | Saber qué incendios amenazan a la gente | Capa de densidad poblacional + panel de alertas por riesgo | P1 | W3-D1 · W3-D2 · W3-F1 |
| **4 · Viento + tiempo** | Entender hacia dónde avanza el fuego | Flechas de viento animadas + capa meteorológica | P1 | W4-D1 · W4-F1 |
| **5 · Agua, rutas, terreno** | Ayudar a la intervención | Capas agua, rutas / caminos, bomberos, relieve + accesibilidad por incendio | P2 | W5-D1 · W5-F1 |
| **6 · Después** | Pasar de demo a producto | Tiempo real, backend, notificaciones, propagación… (tareas independientes, en cualquier orden) | P2 | W6-1 … W6-8 |

**Prio:** P0 = indispensable para el MVP · P1 = mejora fuerte · P2 = cuando lo anterior esté terminado.

### Cómo agregar una feature después del MVP
1. Agregar una fila en la tabla de la sección 2, en la wave que corresponda (o en una nueva).
2. Si necesita datos: un script en `scripts/` que escribe en `web/data/processed/` (y se documenta en el contrato).
3. Si es una capa: un archivo en `web/layers/` registrado en `web/layers/index.js`, nada más.
4. Una tarea = una rama `feature/<id>-<nombre>` = un PR corto a `main`.
