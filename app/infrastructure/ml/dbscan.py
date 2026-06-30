import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from app.domain.entities import ZonaCaliente

R_TIERRA_M = 6_371_000.0

def _haversine_max(centro: np.ndarray, puntos: np.ndarray) -> float:
    lat1, lng1 = np.radians(centro)
    lat2 = np.radians(puntos[:, 0])
    lng2 = np.radians(puntos[:, 1])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlng / 2) ** 2
    return float((2 * R_TIERRA_M * np.arcsin(np.sqrt(a))).max())

def clusterizar_demanda(
    celdas: pd.DataFrame,
    *,
    umbral_densidad: float = 50.0,
    umbral_ratio: float = 1.0,
    eps_m: float = 300.0,
    min_samples: int = 1,
    radio_min_m: float = 150.0,
) -> list[ZonaCaliente]:
    # 1) Filtrar celdas candidatas (alta demanda Y oferta rebasada).
    cand = celdas[
        (celdas["demand_density"] >= umbral_densidad)
        & (celdas["supply_demand_ratio"] <= umbral_ratio)
    ]
    if len(cand) == 0:
        return []
    # 2) DBSCAN haversine sobre los centroides candidatos (coords en radianes).
    coords = cand[["centroid_lat", "centroid_lon"]].to_numpy()
    labels = DBSCAN(
        eps=eps_m / R_TIERRA_M, min_samples=min_samples, metric="haversine"
    ).fit_predict(np.radians(coords))
    # 3) Construir una ZonaCaliente por cluster.
    crudas: list[dict] = []
    for c in sorted(l for l in set(labels) if l >= 0):
        m = cand[labels == c]
        pts = m[["centroid_lat", "centroid_lon"]].to_numpy()
        pesos = m["demand_density"].to_numpy()
        centro = np.average(pts, axis=0, weights=pesos)
        radio = max(_haversine_max(centro, pts) if len(pts) > 1 else 0.0, radio_min_m)
        crudas.append({
            "lat": round(float(centro[0]), 6),
            "lng": round(float(centro[1]), 6),
            "demand_density": round(float(m["demand_density"].mean()), 2),
            "supply_demand_ratio": round(float(m["supply_demand_ratio"].mean()), 3),
            "n_requests": int(m["n_requests"].sum()),
            "n_celdas": int(len(m)),
            "radio_m": round(float(radio), 1),
        })
    # 4) intensidad = densidad normalizada dentro del bucket; rankear por densidad desc.
    max_d = max(z["demand_density"] for z in crudas)
    zonas = [
        ZonaCaliente(intensidad=round(z["demand_density"] / max_d, 4), **z)
        for z in crudas
    ]
    zonas.sort(key=lambda z: z.demand_density, reverse=True)
    return zonas
