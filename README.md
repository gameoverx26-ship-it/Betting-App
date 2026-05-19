
# Predictor de Partidos de Fútbol

> Herramienta de análisis y predicción de partidos combinando datos en tiempo real con inteligencia artificial local.

---

## Descripción General

**Betting App** obtiene estadísticas reales de la API [football-data.org](https://www.football-data.org/) y las procesa con el modelo de lenguaje **llama3.2** corriendo localmente a través de **Ollama**, generando predicciones de resultado, marcador esperado, probabilidades y análisis detallado por partido.

El proyecto tiene dos fases de desarrollo:

| Fase | Archivo | Estado |
|------|---------|--------|
| **Beta** | `betbot.py` | ✅ Estable — Herramienta CLI |
| **Alpha** | `betbot_Alpha.py` | ⚠️ En desarrollo — Interfaz Web con errores conocidos |

---

## Requisitos previos

Antes de ejecutar cualquier versión, asegúrate de tener instalado lo siguiente:

- Python 3.8 o superior
- [Ollama](https://ollama.com/) instalado y corriendo (`ollama serve`)
- El modelo `llama3.2` descargado (`ollama pull llama3.2`)
- Una API Key gratuita de [football-data.org](https://www.football-data.org/client/register)

### Instalación de dependencias Python

```bash
pip install requests ollama flask
```

---

---

# 📟 FASE BETA — Herramienta CLI (`betbot.py`)

## ¿Qué hace?

La fase Beta es la versión **estable y completamente funcional** del proyecto. Corre en la terminal e implementa el flujo completo de análisis:

1. Busca los equipos ingresados en todas las ligas disponibles
2. Obtiene los últimos 5 partidos de cada equipo
3. Calcula promedios de goles, forma reciente y balance V/E/D
4. Consulta el historial directo entre ambos equipos (H2H)
5. Verifica si hay un partido en vivo entre ellos
6. Muestra los próximos enfrentamientos programados
7. Envía todos los datos a **Ollama (llama3.2)** para generar la predicción
8. Muestra el resultado con probabilidades, marcador esperado y análisis

## Ligas soportadas

| Código | Liga |
|--------|------|
| `CL` | Champions League |
| `PL` | Premier League |
| `PD` | La Liga |
| `BL1` | Bundesliga |
| `SA` | Serie A |
| `FL1` | Ligue 1 |
| `CLI` | Copa Libertadores |
| `EC` | Eurocopa |

## Cómo ejecutar (Beta)

### 1. Configura tu API Key

Abre `betbot.py` y reemplaza la línea 7:

```python
API_KEY = "tu_api_key_aqui"
```

### 2. Asegúrate de que Ollama esté corriendo

```bash
ollama serve
```

En otra terminal (si aún no tienes el modelo):

```bash
ollama pull llama3.2
```

### 3. Ejecuta el script

```bash
python betbot.py
```

### 4. Ingresa los equipos cuando se solicite

```
Equipo LOCAL:     Arsenal
Equipo VISITANTE: Chelsea
```

> Los nombres pueden estar en español o inglés. Si hay varios resultados, el programa te pedirá que elijas.

## Ejemplo de salida

```
Últimos 5 partidos - ARSENAL
────────────────────────────────────────────────────────────────────
  FECHA        RIVAL                  COND    RES   GF  GC  COMPETICION
────────────────────────────────────────────────────────────────────
  2024-05-01   Chelsea                LOCAL   V      2   0  Premier League
  ...

PREDICCIÓN - ARSENAL vs CHELSEA
================================================================
Resultado probable:  ARSENAL
Marcador esperado:   Arsenal 2 - 1 Chelsea
Confianza:           ALTA

Victoria Arsenal     65.0%  ####################........
Empate               20.0%  ######......................
Victoria Chelsea     15.0%  ####........................
```

## Notas importantes (Beta)

- La API gratuita tiene un límite de requests. El script aplica delays automáticos (`time.sleep`) para evitar errores 429.
- Si ves `Error HTTP 403`, tu API Key no tiene permisos para esa liga en el plan gratuito.
- Si Ollama no responde, verifica que esté activo con `ollama serve`.

---

---

# 🌐 FASE ALPHA — Interfaz Web (`betbot_Alpha.py`)

## ¿Qué agrega respecto a la Beta?

La fase Alpha expande el análisis con datos adicionales y lo presenta en una interfaz web:

- **Posición en tabla** de cada equipo en su liga
- **Goleadores** del equipo en la liga actual
- Estadísticas separadas como **local** y como **visitante**
- Porcentaje de partidos con **ambos equipos anotando**
- Porcentaje de partidos con **más de 2.5 goles**
- **Racha actual** del equipo (ej: 3 victorias seguidas)
- **Recomendaciones de apuesta** generadas por IA: 1X2, ambos anotan, total de goles, apuesta más segura
- **Interfaz web** en tiempo real con actualizaciones por streaming (SSE)

## Arquitectura

```
betbot_Alpha.py  →  Flask (servidor Python)
     ↕
index.html       →  Frontend en el navegador
     ↕
football-data.org API  +  Ollama (llama3.2)
```

## Cómo ejecutar (Alpha)

### 1. Configura tu API Key en `betbot_Alpha.py`

```python
API_KEY = "tu_api_key_aqui"
```

### 2. Coloca `index.html` en la carpeta `templates/`

Flask requiere que los archivos HTML estén dentro de una carpeta llamada `templates` en el mismo directorio del script:

```
tu_proyecto/
├── betbot_Alpha.py
└── templates/
    └── index.html
```

### 3. Inicia el servidor

```bash
python betbot_Alpha.py
```

### 4. Abre el navegador en

```
http://localhost:5000
```

---

## ⚠️ Estado actual — Errores conocidos en la fase Alpha

> **La interfaz web de la fase Alpha presenta errores en la integración con Flask que impiden su correcto funcionamiento. Esta sección se encuentra actualmente en proceso de solución.**

Los problemas identificados afectan principalmente la capa de comunicación entre el frontend (`index.html`) y el backend Flask (`betbot_Alpha.py`), específicamente en el manejo del streaming de eventos (Server-Sent Events / SSE) y el renderizado dinámico de los resultados en la interfaz.

**Se está trabajando en una corrección** que garantice:

- El flujo correcto de datos entre el servidor y el navegador
- El renderizado apropiado de estadísticas, tablas y predicciones en la UI
- La estabilidad del endpoint `/analizar` bajo distintos navegadores

Mientras tanto, se recomienda usar la **Fase Beta (CLI)** para obtener resultados completos y confiables.

---

---

## Estructura del proyecto

```
match-oracle/
├── betbot.py            # Fase Beta — CLI estable
├── betbot_Alpha.py      # Fase Alpha — Web Flask (en desarrollo)
├── betbot2.py           # Versión alternativa / experimental
└── templates/
    └── index.html       # Frontend para la fase Alpha
```

---

## Créditos y recursos

- API de datos: [football-data.org](https://www.football-data.org/)
- Modelo de IA: [Ollama](https://ollama.com/) + [llama3.2](https://ollama.com/library/llama3.2)
- Desarrollado en Python 3

---

*Documentación generada para Match Oracle — Proyecto en desarrollo activo.*
