import json
import os
from dataclasses import asdict
import mlflow
import pandas as pd
from app.config import settings
from app.infrastructure.data.demanda import cargar_demanda
from app.infrastructure.ml.dbscan import clusterizar_demanda
from training.pyfunc_model import ZonasPyfunc

def construir_artefacto(df_b: pd.DataFrame, **params) -> dict:
    artefacto: dict[str, list[dict]] = {}
    for (muni, dt, hora), grupo in df_b.groupby(["municipio", "dia_tipo", "hour"]):
        zonas = clusterizar_demanda(grupo, **params)
        if zonas:
            artefacto[f"{muni}|{dt}|{hora}"] = [asdict(z) for z in zonas]
    return artefacto

def _metricas_filtro(df_b: pd.DataFrame, umbral_densidad: float, umbral_ratio: float) -> dict:
    # Evidencia (no entrena): precisión/recall del filtro vs is_hot_true.
    if "is_hot_true" not in df_b.columns:
        return {}
    cand = df_b[(df_b["demand_density"] >= umbral_densidad) & (df_b["supply_demand_ratio"] <= umbral_ratio)]
    mets: dict[str, float] = {}
    if len(cand):
        mets["precision_hot_filtro"] = float(cand["is_hot_true"].mean())
    total_hot = float(df_b["is_hot_true"].sum())
    if total_hot:
        mets["recall_hot_filtro"] = float(cand["is_hot_true"].sum() / total_hot)
    return mets

def main(eps_m: float = 450.0, min_samples: int = 1, umbral_densidad: float = 50.0, umbral_ratio: float = 1.0) -> None:
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    df_b = cargar_demanda()
    params = {"umbral_densidad": umbral_densidad, "umbral_ratio": umbral_ratio, "eps_m": eps_m, "min_samples": min_samples}
    artefacto = construir_artefacto(df_b, **params)
    os.makedirs("artefactos", exist_ok=True)
    ruta = "artefactos/zonas.json"
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(artefacto, f)
    n_zonas = sum(len(v) for v in artefacto.values())
    with mlflow.start_run():
        mlflow.log_params(params)
        metricas = {"buckets_con_zonas": len(artefacto), "total_zonas": n_zonas}
        metricas.update(_metricas_filtro(df_b, umbral_densidad, umbral_ratio))
        mlflow.log_metrics(metricas)
        mlflow.pyfunc.log_model(
            artifact_path="model",
            python_model=ZonasPyfunc(),
            artifacts={"zonas": ruta},
            registered_model_name=settings.modelo_nombre,
        )
    print(f"Entrenado: {len(artefacto)} buckets con zonas, {n_zonas} zonas. Métricas: {metricas}. "
          f"Registrado como {settings.modelo_nombre}.")

if __name__ == "__main__":
    main()
