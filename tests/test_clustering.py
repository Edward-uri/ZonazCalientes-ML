import numpy as np
import pandas as pd
from app.infrastructure.ml.dbscan import clusterizar_demanda
from app.application.buckets import dia_tipo

def test_dia_tipo():
    assert dia_tipo(0) == "entre_semana"
    assert dia_tipo(5) == "fin_de_semana"
    assert dia_tipo(6) == "fin_de_semana"

def test_filtra_fondo_y_agrupa_celdas_calientes():
    # 3 celdas calientes adyacentes (< 450 m entre sí) = 1 zona
    calientes = pd.DataFrame({
        "centroid_lat": [16.7515, 16.7518, 16.7521],
        "centroid_lon": [-93.1160, -93.1158, -93.1162],
        "demand_density": [420.0, 380.0, 460.0],
        "supply_demand_ratio": [0.12, 0.18, 0.10],
        "n_requests": [150, 130, 170],
    })
    # 30 celdas de fondo de baja demanda (deben filtrarse)
    fondo = pd.DataFrame({
        "centroid_lat": np.linspace(16.70, 16.79, 30),
        "centroid_lon": np.linspace(-93.16, -93.09, 30),
        "demand_density": [11.0] * 30,
        "supply_demand_ratio": [3.6] * 30,
        "n_requests": [1] * 30,
    })
    celdas = pd.concat([calientes, fondo], ignore_index=True)
    zonas = clusterizar_demanda(celdas)
    assert len(zonas) == 1
    z = zonas[0]
    assert z.n_celdas == 3 and z.n_requests == 450
    assert abs(z.lat - 16.7518) < 0.01
    assert z.intensidad == 1.0
    assert z.demand_density >= 380.0
    assert z.radio_m >= 150.0

def test_bucket_sin_candidatas_devuelve_vacio():
    fondo = pd.DataFrame({
        "centroid_lat": [16.70, 16.79],
        "centroid_lon": [-93.16, -93.09],
        "demand_density": [11.0, 12.0],
        "supply_demand_ratio": [3.6, 3.5],
        "n_requests": [1, 1],
    })
    assert clusterizar_demanda(fondo) == []
