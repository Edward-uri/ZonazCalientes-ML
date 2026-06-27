# Diccionario de Datos — Dos Niveles
## Zonas Calientes — ViajeSeguro

**Versión:** 2.0 (diseño de dos niveles)
**Generador:** `generate_synthetic.py` + `config/02-config-generacion.yaml`
**Archivos:**
- `solicitudes_profesor.csv` (Nivel A completo con `zone_id_true`)
- `solicitudes_estudiante.csv` (Nivel A sin `zone_id_true`)
- `demanda_agregada_profesor.csv` (Nivel B completo con `is_hot_true`/`zone_id_true`)
- `demanda_agregada_estudiante.csv` (Nivel B sin columnas de ground-truth)

---

## Nivel A — Solicitudes (`solicitudes_*.csv`)

| # | Columna | Tipo Python | Dominio / Rango | Fuente real (BD/App) | Regla de Calidad | Ground-Truth |
|---|---|---|---|---|---|---|
| 1 | `request_id` | `str` | `REQ-NNNNNN` (6 dígitos) | `viajes.id` | Único; formato `^REQ-\d{6}$`; no nulo | No |
| 2 | `timestamp` | `str` ISO 8601 | `2026-01-01T00:00:00` a `2026-03-31T23:59:00` | `viajes.fechaSolicitud` | Formato datetime válido; no nulo; dentro del rango YAML | No |
| 3 | `municipio` | `int` | `{1, 2}` | `viajes.municipio` | Valor en `{1, 2}`; no nulo | No |
| 4 | `lat` | `float` | Municipio 1: `[16.70, 16.80]`; Municipio 2: `[16.86, 16.94]`. Anomalías fuera. | `viajes.origen_lat` | Dentro de `bbox[municipio]` en filas normales; 6 decimales | No |
| 5 | `lng` | `float` | Municipio 1: `[-93.16, -93.08]`; Municipio 2: `[-92.12, -92.04]`. Anomalías fuera. | `viajes.origen_lng` | Dentro de `bbox[municipio]` en filas normales; 6 decimales | No |
| 6 | `hour` | `int` | `[0, 23]` en filas normales; puede ser `> 23` en anomalías inyectadas | derivado de `viajes.fechaSolicitud` | `hour ∈ [0, 23]` en filas normales; anomalías tienen `hour ∈ [24, 29]` | No |
| 7 | `day_of_week` | `int` | `[0, 6]` — 0=lunes, 6=domingo | derivado de `viajes.fechaSolicitud` | Coincide con `pd.Timestamp(timestamp).dayofweek`; no nulo | No |
| 8 | `is_weekend` | `bool` | `{True, False}` | derivado: `day_of_week >= 5` | Consistente con `day_of_week`; no nulo | No |
| 9 | `is_holiday` | `bool` | `{True, False}` | calendario (`festivos` del YAML) | `True` en fechas `{2026-01-01, 2026-02-02, 2026-03-16}`; no nulo | No |
| 10 | `distancia_km` | `float` | `> 0` (lognormal, típicamente 1–15 km) | `viajes.distanciaKm` | `distancia_km > 0` en filas sin nulos; puede ser `NaN` (~3% de filas) | No |
| 11 | `zona_destino` | `int` | `-1` (afueras) o `0..K-1` según zonas del municipio | `viajes.destino → idZonaDestino` | Valor en `{-1, 0, 1, ...}`; ~15% de filas con `-1` (afueras); no nulo | No |
| 12 | `costo_mxn` | `float` | **Tarifa FIJA** por zona de destino (MXN); valores discretos según `tarifas` del YAML (`{12,14,15,16,18}`) o `tarifa_fuera` (20) | `TarifaPorZona` (tarifas por zona — no dinámica) | Valor en el set de tarifas del YAML; puede ser `NaN` (~3% de filas por inyección de nulos) | No |
| 13 | `accepted` | `bool` | `{True, False}` | `viajes.estado` (completado/aceptado = True) | ~70–97% `True` según hora (menor en pico); no nulo | No |
| 14 | `zone_id_true` | `int` | `[-1, n_zonas_municipio - 1]`: -1=ruido, 0,1,2=zona plantada | (oculto al modelo — solo validación) | No nulo; ~8% de filas con `-1` (ruido); valores `≥ 0` corresponden a zonas del YAML | **Sí** |

---

## Nivel B — Demanda Agregada (`demanda_agregada_*.csv`)

| # | Columna | Tipo Python | Dominio / Rango | Fuente real (BD/App) | Regla de Calidad | Ground-Truth |
|---|---|---|---|---|---|---|
| 1 | `cell_id` | `str` | `"{municipio}-{row}-{col}"` | derivado del grid de `viajes.origen_lat/lng` | Formato `\d+-\d+-\d+`; único por `(municipio, time_bucket)` | No |
| 2 | `municipio` | `int` | `{1, 2}` | `viajes.municipio` | Valor en `{1, 2}`; no nulo | No |
| 3 | `time_bucket` | `str` | `entre_semana_HH` o `fin_de_semana_HH` (HH = 00–23) | derivado de `viajes.fechaSolicitud` | Formato `^(entre_semana|fin_de_semana)_\d{2}$`; no nulo | No |
| 4 | `dia_tipo` | `str` | `{'entre_semana', 'fin_de_semana'}` | derivado de `day_of_week` | Valor en el conjunto; consistente con `time_bucket`; no nulo | No |
| 5 | `hour` | `int` | `[0, 23]` | derivado de `timestamp` | `hour ∈ [0, 23]`; consistente con `time_bucket`; no nulo | No |
| 6 | `centroid_lat` | `float` | dentro del `bbox[municipio].lat` | calculado: `bbox_lat_min + (row + 0.5) * cell_deg` | Dentro del bbox del municipio; 6 decimales | No |
| 7 | `centroid_lon` | `float` | dentro del `bbox[municipio].lng` | calculado: `bbox_lng_min + (col + 0.5) * cell_deg` | Dentro del bbox del municipio; 6 decimales | No |
| 8 | `n_requests` | `int` | `>= 1` (solo celdas con solicitudes) | conteo de `viajes` en la celda×franja | `n_requests >= 1`; entero; no nulo | No |
| 9 | `n_drivers_available` | `int` | `>= 0` (Poisson con media `base_drivers = 4`) | `conductor_sesiones` (conductores activos en la zona) | Entero no negativo; no nulo | No |
| 10 | `supply_demand_ratio` | `float` | `>= 0`; < 1 = demanda supera oferta; > 1 = oferta supera demanda | calculado: `n_drivers_available / max(n_requests, 1)` | No negativo; 3 decimales; no nulo | No |
| 11 | `demand_density` | `float` | `> 0` solicitudes/km² | calculado: `n_requests / (cell_size_m/1000)²` | `demand_density > 0` siempre (solo celdas con solicitudes); 2 decimales | No |
| 12 | `cancel_rate` | `float` | `[0.0, 1.0]` | calculado: `1 - mean(viajes.estado == accepted)` en la celda×franja | `[0, 1]`; 3 decimales; no nulo | No |
| 13 | `is_hot_true` | `bool` | `{True, False}` | (oculto al modelo — solo validación) | `True` cuando `zone_id_true >= 0` y `n_requests >= min_requests_hot (5)` | **Sí** |
| 14 | `zone_id_true` | `int` | `[-1, n_zonas_municipio - 1]` | (oculto al modelo — solo validación) | Moda de `zone_id_true` de las solicitudes de esa celda×franja; -1 si todas son ruido | **Sí** |

---

## Columnas Disponibles por Archivo

### Nivel A

| Columna | `solicitudes_estudiante.csv` | `solicitudes_profesor.csv` |
|---|---|---|
| `request_id` | ✓ | ✓ |
| `timestamp` | ✓ | ✓ |
| `municipio` | ✓ | ✓ |
| `lat` | ✓ | ✓ |
| `lng` | ✓ | ✓ |
| `hour` | ✓ | ✓ |
| `day_of_week` | ✓ | ✓ |
| `is_weekend` | ✓ | ✓ |
| `is_holiday` | ✓ | ✓ |
| `distancia_km` | ✓ | ✓ |
| `zona_destino` | ✓ | ✓ |
| `costo_mxn` | ✓ | ✓ |
| `accepted` | ✓ | ✓ |
| `zone_id_true` | — | ✓ |

### Nivel B

| Columna | `demanda_agregada_estudiante.csv` | `demanda_agregada_profesor.csv` |
|---|---|---|
| `cell_id` | ✓ | ✓ |
| `municipio` | ✓ | ✓ |
| `time_bucket` | ✓ | ✓ |
| `dia_tipo` | ✓ | ✓ |
| `hour` | ✓ | ✓ |
| `centroid_lat` | ✓ | ✓ |
| `centroid_lon` | ✓ | ✓ |
| `n_requests` | ✓ | ✓ |
| `n_drivers_available` | ✓ | ✓ |
| `supply_demand_ratio` | ✓ | ✓ |
| `demand_density` | ✓ | ✓ |
| `cancel_rate` | ✓ | ✓ |
| `is_hot_true` | — | ✓ |
| `zone_id_true` | — | ✓ |

---

## Notas sobre Calidad de Datos

### Nulos inyectados (~3% de filas — Nivel A)

Los nulos se inyectan aleatoriamente en:
- `distancia_km`
- `costo_mxn`

El resto de columnas del Nivel A no tiene nulos salvo en filas de anomalías extremas.

### Anomalías inyectadas (~2% de filas — Nivel A)

Dos tipos:
1. **Coordenada fuera de bbox**: `lat` o `lng` desplazados ±0.5 grados fuera del bbox.
2. **Hora inválida**: `hour ∈ [24, 29]`.

Estas filas son **filtradas antes de agregar el Nivel B** (función `_filas_validas`), por lo que el Nivel B solo contiene datos limpios.

### Duplicados (~1% de filas — Nivel A)

Filas con valores idénticos en todas las columnas (el `request_id` puede repetirse en duplicados). Detectables con `df.duplicated()`.

### Ruido espacial (~8% de filas — Nivel A)

Solicitudes con `zone_id_true = -1`: orígenes uniformes dentro del bbox, sin patrón de zona.
