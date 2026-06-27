"""Validación del modelo de zonas calientes contra el ground-truth sintético.

Como el dataset es sintético, conocemos la VERDAD: los centros reales de cada zona
(en el config), `is_hot_true` (si una celda es realmente caliente) y `zone_id_true`
(a qué zona real pertenece). Aquí medimos qué tan bien la salida del modelo
(filtro de alta demanda + DBSCAN haversine) recupera esa verdad.

IMPORTANTE: las etiquetas ground-truth se usan SOLO para MEDIR, nunca como entrada
del modelo (el clustering es no supervisado).

Cuatro validaciones + generalización:
  A. Recuperación espacial  -> ¿las zonas predichas caen sobre los centros reales?
  B. Detección de calientes -> precision/recall vs is_hot_true
  C. Concordancia clustering -> ARI/NMI de los clusters vs zone_id_true
  D. Coherencia temporal    -> la demanda predicha sigue el patrón horario plantado
  E. Generalización         -> con OTRA semilla (datos nuevos) sigue recuperando los centros
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

from app.infrastructure.data.demanda import cargar_demanda
from app.infrastructure.ml.dbscan import clusterizar_demanda, R_TIERRA_M

PARAMS = {"umbral_densidad": 50.0, "umbral_ratio": 1.0, "eps_m": 450.0, "min_samples": 1}
CONFIG_PATH = "config/02-config-generacion.yaml"


def haversine_m(lat1, lng1, lat2, lng2):
    """Distancia haversine en metros (acepta escalares o arrays en lat2/lng2)."""
    lat1, lng1, lat2, lng2 = map(np.radians, (lat1, lng1, lat2, lng2))
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlng / 2) ** 2
    return 2 * R_TIERRA_M * np.arcsin(np.sqrt(a))


def centros_reales(cfg) -> dict[int, np.ndarray]:
    """{municipio: array Nx2 de [lat, lng]} con los centros plantados en el config."""
    return {int(m): np.array([z["centro"] for z in zs]) for m, zs in cfg["zonas"].items()}


def _candidatas_labels(bucket: pd.DataFrame, params=PARAMS):
    """Replica el filtro+DBSCAN de clusterizar_demanda devolviendo las celdas
    candidatas y su etiqueta de cluster (para poder comparar contra zone_id_true)."""
    cand = bucket[
        (bucket["demand_density"] >= params["umbral_densidad"])
        & (bucket["supply_demand_ratio"] <= params["umbral_ratio"])
    ]
    if len(cand) == 0:
        return cand, np.array([], dtype=int)
    coords = np.radians(cand[["centroid_lat", "centroid_lon"]].to_numpy())
    labels = DBSCAN(
        eps=params["eps_m"] / R_TIERRA_M, min_samples=params["min_samples"], metric="haversine"
    ).fit_predict(coords)
    return cand, labels


# --- A. Recuperación espacial ------------------------------------------------
def recuperacion_espacial(df_b: pd.DataFrame, centros: dict, params=PARAMS) -> pd.DataFrame:
    """Por cada zona predicha: distancia al centro real más cercano de su municipio."""
    filas = []
    for (muni, dt, hora), bucket in df_b.groupby(["municipio", "dia_tipo", "hour"]):
        zonas = clusterizar_demanda(bucket, **params)
        cs = centros.get(int(muni))
        for z in zonas:
            d = float(haversine_m(z.lat, z.lng, cs[:, 0], cs[:, 1]).min()) if cs is not None else np.nan
            filas.append({
                "municipio": muni, "dia_tipo": dt, "hora": hora,
                "lat": z.lat, "lng": z.lng, "demand_density": z.demand_density,
                "dist_centro_real_m": round(d, 1),
            })
    return pd.DataFrame(filas)


# --- B. Detección de calientes ----------------------------------------------
def metricas_deteccion(df_b: pd.DataFrame, params=PARAMS) -> dict:
    """Precision/recall de las celdas en zona (= candidatas, porque min_samples=1) vs is_hot_true."""
    cand = df_b[
        (df_b["demand_density"] >= params["umbral_densidad"])
        & (df_b["supply_demand_ratio"] <= params["umbral_ratio"])
    ]
    out = {}
    if len(cand):
        out["precision_hot"] = float(cand["is_hot_true"].mean())
    tot = float(df_b["is_hot_true"].sum())
    if tot:
        out["recall_hot"] = float(cand["is_hot_true"].sum() / tot)
    return out


# --- C. Concordancia de clustering ------------------------------------------
def concordancia_clustering(df_b: pd.DataFrame, params=PARAMS) -> pd.DataFrame:
    """ARI/NMI por bucket: clusters predichos vs zone_id_true sobre las celdas candidatas."""
    filas = []
    for (muni, dt, hora), bucket in df_b.groupby(["municipio", "dia_tipo", "hour"]):
        cand, labels = _candidatas_labels(bucket, params)
        if len(cand) < 2:
            continue
        verdad = cand["zone_id_true"].to_numpy()
        filas.append({
            "municipio": muni, "dia_tipo": dt, "hora": hora, "n_celdas": int(len(cand)),
            "n_clusters": int(len(set(labels))), "n_zonas_reales": int(cand["zone_id_true"].nunique()),
            "ARI": round(float(adjusted_rand_score(verdad, labels)), 3),
            "NMI": round(float(normalized_mutual_info_score(verdad, labels)), 3),
        })
    return pd.DataFrame(filas)


# --- D. Coherencia temporal --------------------------------------------------
def coherencia_temporal(df_b: pd.DataFrame, params=PARAMS) -> pd.DataFrame:
    """Demanda capturada por las zonas predichas, agregada por (dia_tipo, hora)."""
    filas = []
    for (dt, hora), bucket in df_b.groupby(["dia_tipo", "hour"]):
        n_zonas = dens = req = 0
        for _muni, g in bucket.groupby("municipio"):
            zonas = clusterizar_demanda(g, **params)
            n_zonas += len(zonas)
            dens += sum(z.demand_density for z in zonas)
            req += sum(z.n_requests for z in zonas)
        filas.append({"dia_tipo": dt, "hora": int(hora), "n_zonas": n_zonas,
                      "densidad_total": round(float(dens), 1), "solicitudes_en_zonas": int(req)})
    return pd.DataFrame(filas).sort_values(["dia_tipo", "hora"]).reset_index(drop=True)


# --- E. Generalización (otra semilla) ---------------------------------------
def validar_generalizacion(semilla: int = 123, params=PARAMS) -> dict:
    """Regenera un dataset NUEVO (otra semilla) y mide la recuperación espacial sobre él."""
    from generate_synthetic import cargar_config, generar_nivel_a, agregar_nivel_b
    cfg = cargar_config(CONFIG_PATH)
    cfg["random_seed"] = semilla
    b = agregar_nivel_b(generar_nivel_a(cfg), cfg)
    rec = recuperacion_espacial(b, centros_reales(cfg), params)
    return {
        "semilla": semilla, "n_zonas": int(len(rec)),
        "dist_mediana_m": float(rec["dist_centro_real_m"].median()),
        "dist_p90_m": float(rec["dist_centro_real_m"].quantile(0.9)),
        "frac_dentro_300m": float((rec["dist_centro_real_m"] <= 300).mean()),
    }


# --- Resumen + MLflow --------------------------------------------------------
def resumen(df_b: pd.DataFrame, cfg, params=PARAMS) -> dict:
    rec = recuperacion_espacial(df_b, centros_reales(cfg), params)
    con = concordancia_clustering(df_b, params)
    multi = con[con["n_zonas_reales"] >= 2]
    r = {
        "n_zonas": int(len(rec)),
        "dist_mediana_m": float(rec["dist_centro_real_m"].median()),
        "dist_p90_m": float(rec["dist_centro_real_m"].quantile(0.9)),
        "frac_zonas_dentro_300m": float((rec["dist_centro_real_m"] <= 300).mean()),
        "frac_zonas_dentro_150m": float((rec["dist_centro_real_m"] <= 150).mean()),
        "ARI_medio": float(con["ARI"].mean()) if len(con) else float("nan"),
        "ARI_medio_multizona": float(multi["ARI"].mean()) if len(multi) else float("nan"),
        "NMI_medio": float(con["NMI"].mean()) if len(con) else float("nan"),
        **metricas_deteccion(df_b, params),
    }
    return r


def main() -> None:
    import mlflow
    from generate_synthetic import cargar_config
    from app.config import settings

    cfg = cargar_config(CONFIG_PATH)
    df_b = cargar_demanda()
    r = resumen(df_b, cfg)
    g = validar_generalizacion(123)
    r["generaliza_dist_mediana_m"] = g["dist_mediana_m"]
    r["generaliza_frac_dentro_300m"] = g["frac_dentro_300m"]

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    with mlflow.start_run(run_name="validacion"):
        mlflow.set_tag("tipo", "validacion")
        mlflow.log_params({f"val_{k}": v for k, v in PARAMS.items()})
        mlflow.log_metrics({
            f"val_{k}": v for k, v in r.items()
            if isinstance(v, (int, float)) and not (isinstance(v, float) and np.isnan(v))
        })
    print("VALIDACIÓN del modelo de zonas calientes:")
    for k, v in r.items():
        print(f"  {k}: {round(v, 3) if isinstance(v, float) else v}")


if __name__ == "__main__":
    main()
