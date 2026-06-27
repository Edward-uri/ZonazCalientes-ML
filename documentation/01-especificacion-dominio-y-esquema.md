# Especificación de Dominio y Esquema — Zonas Calientes (Dos Niveles)

## Microservicio de Zonas Calientes — ViajeSeguro

**Versión:** 2.0 (diseño de dos niveles)
**Referencia config:** `config/02-config-generacion.yaml`

---

## 1. Descripción del Problema

ViajeSeguro opera en varios municipios y conecta pasajeros con conductores. Un conductor que termina un viaje necesita saber **dónde posicionarse** para conseguir la siguiente solicitud rápidamente. El microservicio de zonas calientes responde esta pregunta: dado un **municipio**, un **tipo de día** (entre semana / fin de semana) y la **hora actual**, ¿qué celdas geográficas concentran más solicitudes de viaje con menor oferta de conductores?

El objetivo analítico es identificar esas celdas automáticamente a partir del **historial de orígenes de viaje** (coordenadas `lat/lng` donde el pasajero inicia la solicitud) y de la disponibilidad de conductores. No se predice el destino ni la ruta; solo el punto de alta densidad de origen donde la demanda supera la oferta.

---

## 2. Diseño de Dos Niveles

El análisis opera en dos niveles complementarios:

### Nivel A — Solicitudes crudas (`solicitudes.csv`)

Cada fila es **una solicitud de viaje individual** capturada de la base de datos real (`viajes`). Es el registro atómico del evento.

- Permite detectar patrones temporales (por hora, día, festivo).
- Permite estudiar calidad de datos: nulos, duplicados, anomalías geográficas.
- Es la fuente para agregar el Nivel B.

### Nivel B — Demanda agregada (`demanda_agregada.csv`)

Cada fila representa **una celda espacial × franja temporal × municipio**: cuántas solicitudes llegaron ahí, cuántos conductores había disponibles, qué tan densa es la demanda, y si la celda es "caliente" en ground-truth.

- Es la **entrada del modelo de clustering** (DBSCAN multivariado).
- Permite comparar demanda vs oferta mediante `supply_demand_ratio`.
- Permite calcular `demand_density` (solicitudes / km²), la métrica principal de calor.

---

## 3. Por Qué "Caliente"

Una celda×franja se considera **caliente** cuando:
- La `demand_density` es alta (muchas solicitudes en poco espacio).
- Y/o el `supply_demand_ratio` es bajo (hay menos conductores que solicitudes).

Estas dos condiciones juntas definen una zona donde la oferta no cubre la demanda: exactamente donde el conductor debería estar.

El ground-truth `is_hot_true` se define como: zona dominante de la celda es real (≥ 0) **y** `n_requests >= min_requests_hot` (config YAML).

---

## 4. Bucketing `(municipio, dia_tipo, hora)`

Las celdas se agrupan por la tupla `(municipio, dia_tipo, hora)`:

| Dimensión | Valores | Razón |
|---|---|---|
| `municipio` | 1, 2 | Geografías distintas, sin mezclar coords |
| `dia_tipo` | `entre_semana` (lun–vie), `fin_de_semana` (sab–dom) | Comportamiento diferente (trabajo vs ocio) |
| `hora` | 0–23 | Horas pico (7–9, 17–20) vs valle (madrugada) |

`time_bucket` = `"{dia_tipo}_{hora:02d}"` (ej. `entre_semana_18`).

Esto permite que el modelo aprenda **patrones recurrentes** independientes del día calendario exacto.

---

## 5. El Modelo Generador Sintético

El generador planta **zonas gaussianas** en las coordenadas de cada municipio (definidas en `config/02-config-generacion.yaml`). Cada zona tiene un centro, una desviación estándar en metros y un peso relativo de demanda.

### Flujo

1. Para cada fecha y cada hora, calcula la demanda esperada con `n_base_por_bucket × peso_horario`.
2. Con probabilidad `frac_ruido`, genera solicitudes en posiciones aleatorias dentro del bbox (`zone_id_true = -1`).
3. Con el resto, elige una zona con probabilidad proporcional a su peso y muestrea `(lat, lng)` de una distribución normal alrededor del centro.
4. Asigna la `zona_destino` del viaje (con probabilidad `prob_destino_fuera` el destino es afueras, `zona_destino = -1`) y el `costo_mxn` como **tarifa FIJA** de esa zona de destino (según `tarifas[municipio][zona_destino]` o `tarifa_fuera`). El precio NO es dinámico ni depende de la distancia.
5. Inyecta anomalías (coords fuera de bbox u hora > 23), nulos y duplicados.
5. Agrega Nivel B: divide el municipio en celdas de `cell_size_m × cell_size_m` metros y cuenta solicitudes por celda×franja.

### Features del Nivel B

- `n_drivers_available`: simulado con distribución Poisson(`base_drivers`), que corresponde en producción a `conductor_sesiones`.
- `supply_demand_ratio`: `n_drivers / max(n_requests, 1)`. Bajo = demanda supera oferta.
- `demand_density`: `n_requests / area_celda_km2`. Métrica principal de calor.
- `cancel_rate`: `1 - mean(accepted)`. En pico la tasa de cancelación sube porque la oferta no alcanza.

---

## 6. Lógica Ground-Truth

- `zone_id_true` (Nivel A): índice de la zona plantada que generó la solicitud (0, 1, 2…), o -1 para ruido.
- `zone_id_true` (Nivel B): zona dominante dentro de la celda×franja (moda de las solicitudes).
- `is_hot_true` (Nivel B): `True` si la zona dominante es real (≥ 0) **y** `n_requests >= min_requests_hot`.

El ground-truth **solo se usa para validar** los resultados del clustering (ARI, NMI, precisión/recall). **Nunca es feature del modelo.**

---

## 7. Esquema — Nivel A (`solicitudes.csv`)

| Columna | Tipo | Significado | Fuente real (BD/App) |
|---|---|---|---|
| `request_id` | str | PK `REQ-000001` | viajes.id |
| `timestamp` | str ISO | Momento de la solicitud | viajes.fechaSolicitud |
| `municipio` | int | Municipio | viajes.municipio |
| `lat` / `lng` | float | Origen | viajes.origen_lat/lng |
| `hour` | int 0-23 | Hora (derivada) | de timestamp |
| `day_of_week` | int 0-6 | 0=lunes (derivada) | de timestamp |
| `is_weekend` | bool | Fin de semana | derivada |
| `is_holiday` | bool | Festivo MX | calendario |
| `distancia_km` | float | Distancia del viaje | viajes.distanciaKm |
| `zona_destino` | int | Zona de destino (0..K-1, -1=afueras) | viajes.destino → idZonaDestino |
| `costo_mxn` | float | **Tarifa FIJA** de la zona de destino (no dinámica) | tarifas por zona (TarifaPorZona) |
| `accepted` | bool | La solicitud fue atendida | viajes.estado (completado/aceptado) |
| `zone_id_true` | int | **Ground-truth**: zona plantada (0..K-1) o -1 ruido | (oculto al modelo) |

## 8. Esquema — Nivel B (`demanda_agregada.csv`)

| Columna | Tipo | Significado | Fuente real (BD/App) |
|---|---|---|---|
| `cell_id` | str | `muni-row-col` | derivado del grid |
| `municipio` | int | Municipio | viajes.municipio |
| `time_bucket` | str | `dia_tipo_hora` (ej. `entre_semana_18`) | derivado |
| `dia_tipo` | str | entre_semana / fin_de_semana | de day_of_week |
| `hour` | int 0-23 | Hora de la franja | de timestamp |
| `centroid_lat` / `centroid_lon` | float | Centro de la celda | calculado del grid |
| `n_requests` | int | Demanda: solicitudes en celda×franja | conteo de viajes |
| `n_drivers_available` | int | Oferta: conductores disponibles | conductor_sesiones |
| `supply_demand_ratio` | float | `n_drivers / max(n_requests,1)` | calculado |
| `demand_density` | float | `n_requests / area_celda_km2` | calculado |
| `cancel_rate` | float | `1 - mean(accepted)` | de viajes.estado |
| `is_hot_true` | bool | **Ground-truth**: celda×franja caliente | (solo validación) |
| `zone_id_true` | int | **Ground-truth**: zona real dominante | (solo validación) |

Las versiones `_estudiante` omiten las columnas de ground-truth (`zone_id_true` en A; `is_hot_true`/`zone_id_true` en B).

---

## 9. Features Excluidas (No Disponibles en la BD Actual)

- `surge_multiplier`: no implementado.
- `weather`: no hay integración meteorológica.
- `event_flag`: no hay calendario de eventos.
- `wait_time_min`: no se registra en la BD.

---

## 10. Referencia de Configuración

Todos los parámetros del generador se encuentran en `config/02-config-generacion.yaml`. El análisis es completamente reproducible con `random_seed: 42`. Para cambiar la proporción de ruido, anomalías, tamaño del grid o densidad de zonas, modificar ese YAML sin tocar el código.
