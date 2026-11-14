Para simular el avance de incendios forestales en Python, existen varias herramientas según el nivel de complejidad que busques (desde modelos físicos avanzados hasta autómatas celulares sencillos o librerías académicas de velocidad de propagación).

---

### 1. Principales paquetes de Python para simulación de fuego

* **`forefire` (PyForeFire):**
Es una de las opciones más potentes a nivel científico. **ForeFire** es un motor escrito en C++ con *bindings* oficiales para Python (`pip install forefire`). Modela el avance del frente de fuego en función del terreno y el viento mediante métodos asíncronos avanzados. Es ideal si buscas precisión física real.
* **`wildfire_ROS_models` (o librerías basadas en la *Rothermel Equation*):**
Son librerías específicas dedicadas a calcular la **ROS (Rate of Spread** o velocidad de propagación del frente de fuego) utilizando modelos teóricos consagrados como los de Rothermel.
* **Implementaciones personalizadas con NumPy / SciPy (Autómatas Celulares):**
Para aplicaciones de visualización rápida o webapps ligeras (tipo hackathons), muchos desarrolladores programan su propio modelo de celdas acopladas usando **NumPy**. Las celdas cambian de estado (sano $\to$ ardiendo $\to$ quemado) evaluando a sus vecinos.

---

### 2. ¿Qué parámetros necesitan estos modelos para funcionar?

Dependiendo de si utilizas un modelo físico complejo (como ForeFire/Rothermel) o un autómata celular, los parámetros varían, pero los estándar de la industria se dividen en tres grandes bloques:

#### A. Parámetros Meteorológicos (Atmósfera)

* **Velocidad del viento ($Wind\ Speed$):** Velocidad media del viento (suele medirse en km/h o m/s).
* **Dirección del viento ($Wind\ Direction$):** Hacia dónde apunta o de dónde viene el viento (en grados, 0° - 360°). *Es el factor más crítico para determinar la elipse de propagación del fuego.*
* **Humedad relativa del aire ($Relative\ Humidity$) y Temperatura:** Afectan directamente a la sequedad del combustible.

#### B. Parámetros del Terreno y Topografía (Geografía)

* **Pendiente del terreno ($Slope$):** Se mide en grados o porcentaje de inclinación. El fuego se propaga cuesta arriba mucho más rápido porque las llamas precalientan el combustible superior.
* **Modelo de Elevación Digital (DEM):** Altitudes del terreno para calcular las pendientes de cada celda.

#### C. Parámetros del Combustible (Vegetación)

* **Tipo de combustible / Cobertura vegetal:** Categorías estándar (pastos, matorral denso, bosque de coníferas, frondosas). Cada uno tiene una velocidad de combustión intrínseca.
* **Carga de combustible ($Fuel\ Load$):** Cantidad de biomasa seca disponible por unidad de superficie ($kg/m^2$).
* **Humedad del combustible vivo y muerto ($Fuel\ Moisture$):** El porcentaje de agua que contiene la vegetación; por debajo de ciertos umbrales (ej. <30%), el fuego avanza de forma explosiva.

---

### 💡 Consejo para vuestro proyecto de Hotspots:

Si estáis integrando esto en una web app junto con el histórico de MODIS y VIIRS, **no intentéis calcular una física de fluidos hiperpesada en tiempo real**. Lo ideal es usar los datos de viento y humedad en tiempo real (de APIs meteorológicas abiertas como ERA5 o NOAA) combinados con una fórmula rápida de propagación elíptica (tipo modelo de Huygens simplificado en Python) para mostrar una simulación visual directa del avance del frente de fuego en el mapa.