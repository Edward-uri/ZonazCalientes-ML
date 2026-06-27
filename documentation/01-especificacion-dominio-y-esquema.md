# Especificación de Dominio y Esquema de Datos
## Microservicio de Zonas Calientes — ViajeSeguro

**Versión:** 1.0  
**Referencia config:** `config/02-config-generacion.yaml`

---

## 1. Descripción del Problema

ViajeSeguro opera en varios municipios y conecta pasajeros con conductores. Un conductor que termina un viaje necesita saber **dónde posicionarse** para conseguir la siguiente solicitud rápidamente. El microservicio de zonas calientes responde esta pregunta: dado un **municipio**, un **tipo de día** (entre semana / fin de semana) y la **hora actual**, ¿qué zonas geográficas concentran más solicitudes de viaje?

El objetivo analítico es identificar esas zonas automáticamente a partir del **historial de orígenes de viaje** (coordenadas `lat/lng` donde el pasajero inicia la solicitud). No se predice el destino, ni la ruta; solo el punto de alta densidad de origen.

---

## 2. Por qué Clustering por Densidad de Orígenes

Los orígenes de viaje no se distribuyen uniformemente en el mapa: se concentran en nodos de actividad (centros comerciales, hospitales, zonas universitarias, plazas) durante ciertos horarios. Estos nodos forman **clústeres geográficos densos** que cambian con la hora y el tipo de día.

KMeans divide el espacio en regiones de Voronoi y coloca centroides arbitrariamente, incluso en zonas sin actividad. **DBSCAN** (Density-Based Spatial Clustering of Applications with Noise), usando distancia haversine, detecta exactamente esos focos de densidad sin asumir forma esférica ni número de clústeres a priori, y clasifica como ruido los orígenes dispersos. Por eso DBSCAN es la herramienta correcta para este dominio.

---

## 3. Bucketing `(municipio, dia_tipo, hora)`

El patrón de demanda varía según:

| Dimensión | Valores | Razón |
|---|---|---|
| `municipio` | 1, 2 | Geografías distintas, sin mezclar coords |
| `dia_tipo` | `entre_semana` (lun–vie), `fin_de_semana` (sab–dom) | Comportamiento diferente (horarios de trabajo vs ocio) |
| `hora` | 0–23 | Horas pico (7–9, 17–20) vs valle (madrugada) |

El análisis de clustering se ejecuta **por bucket**: para cada combinación `(municipio, dia_tipo, hora)` se obtiene el subconjunto de orígenes y se identifican sus zonas calientes. Así, el microservicio sirve recomendaciones específicas al contexto actual del conductor.

---

## 4. Modelo Generador Sintético

El dataset se genera de forma reproducible con `random_seed: 42`. El modelo simula cómo se generarían los orígenes de viaje reales:

### 4.1 Zonas Plantadas (Ground-Truth)

Para cada municipio se definen **zonas calientes** con:
- **`centro [lat, lng]`**: coordenadas del núcleo de la zona.
- **`sigma_m`**: radio de dispersión en metros (convertido a grados: `sigma_deg = sigma_m / 6_371_000 * (180/π)`).
- **`peso`**: probabilidad relativa de que un origen provenga de esta zona.

Los orígenes dentro de una zona se generan con distribución gaussiana bivariada centrada en `centro`, con `sigma_deg` en ambas dimensiones.

### 4.2 Ruido Uniforme

Una fracción `frac_ruido = 0.08` de los orígenes se genera aleatoriamente dentro del `bbox` del municipio. Estos representan viajes ocasionales sin patrón espacial. Su `zona_real = -1`.

### 4.3 Demanda Horaria

El número de viajes por bucket escala con el `multiplicador de demanda` de esa hora:

```
n_viajes = n_base_por_bucket × peso_horario(hora, dia_tipo)
```

Las horas pico (7, 8, 17, 18, 19) tienen multiplicador 1.0. Las horas no listadas usan 0.2. Los fines de semana tienen refuerzo nocturno (21–23).

### 4.4 Anomalías, Nulos y Duplicados Inyectados

Para simular calidad de datos real:
- **`frac_anomalias = 0.02`**: coordenadas fuera del bbox o horas inválidas (`hora > 23`). Marcadas con `flag_anomalia = True`.
- **`frac_nulos = 0.03`**: valores nulos en columnas de contexto (`distancia_km`, `costo_mxn`, `tipo_servicio`).
- **`frac_duplicados = 0.01`**: filas duplicadas (simula doble registro de sistema).

---

## 5. Esquema del Dataset

### 5.1 Columnas

| Columna | Tipo | Significado |
|---|---|---|
| `id_viaje` | str | PK con formato `VJE-000001` |
| `municipio` | int | Municipio (1, 2) |
| `fecha` | date | Día del viaje (rango del YAML) |
| `dia_semana` | int 0-6 | 0=lunes (derivado de fecha) |
| `hora` | int 0-23 | Hora de solicitud |
| `lat` | float | Latitud del origen |
| `lng` | float | Longitud del origen |
| `tipo_servicio` | str | `normal` / `programado` |
| `distancia_km` | float | Distancia estimada del viaje (lognormal) |
| `pasajeros` | int | Número de pasajeros (Poisson+1, clip [1,4]) |
| `costo_mxn` | float | Costo estimado derivado de distancia + ruido |
| `lluvia` | bool | Indicador de lluvia en el momento de solicitud |
| `zona_real` | int | **Ground-truth**: id de zona caliente plantada, o -1 si es ruido |
| `flag_anomalia` | bool | **Ground-truth**: fila anómala inyectada |

### 5.2 Archivos Producidos

| Archivo | Contenido |
|---|---|
| `viajes_profesor.csv` | Dataset completo con `zona_real` y `flag_anomalia` |
| `viajes_estudiante.csv` | Sin `zona_real` ni `flag_anomalia` (como lo vería un analista real) |
| `generation_manifest.json` | Metadatos de generación: seed, conteos, validación |

---

## 6. Lógica de Ground-Truth

### `zona_real`

Asignado durante la generación:
- Si el origen proviene de una zona plantada gaussiana → `zona_real = índice de zona (0, 1, 2, ...)`
- Si el origen es ruido uniforme → `zona_real = -1`

Permite evaluar el clustering: un buen DBSCAN debe asignar la mayoría de puntos con `zona_real >= 0` al mismo clúster, y los puntos con `zona_real = -1` al label de ruido (-1).

### `flag_anomalia`

Se marca `True` en filas donde se inyectó una anomalía deliberada:
- Coordenadas desplazadas fuera del bbox del municipio (anomalía geoespacial).
- Hora fuera del rango válido [0, 23] (anomalía temporal).

Las reglas de calidad de datos deben detectar estas filas. El porcentaje esperado es ~2% del total.

---

## 7. Referencia de Configuración

Todos los parámetros del generador se encuentran en `config/02-config-generacion.yaml`. El análisis es completamente reproducible con `random_seed: 42`. Para cambiar la proporción de ruido, anomalías o la densidad de zonas, modificar ese YAML sin tocar el código.
