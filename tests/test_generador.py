from generate_synthetic import cargar_config, generar_nivel_a, agregar_nivel_b, validar_dataset

CFG = "config/02-config-generacion.yaml"

def _a():
    cfg = cargar_config(CFG)
    return generar_nivel_a(cfg), cfg

def test_reproducible():
    cfg = cargar_config(CFG)
    a1 = generar_nivel_a(cfg); a2 = generar_nivel_a(cfg)
    assert a1.equals(a2)
    assert agregar_nivel_b(a1, cfg).equals(agregar_nivel_b(a2, cfg))

def test_esquema_nivel_a():
    a, cfg = _a()
    cols = {"request_id","timestamp","municipio","lat","lng","hour","day_of_week",
            "is_weekend","is_holiday","distancia_km","zona_destino","costo_mxn","accepted","zone_id_true"}
    assert cols.issubset(a.columns)
    assert (a["zone_id_true"] >= 0).any() and (a["zone_id_true"] == -1).any()
    # costo es una tarifa FIJA por zona de destino (no dinámica): cada costo está en el set de tarifas
    permitidos = {float(t) for ts in cfg["tarifas"].values() for t in ts} | {float(cfg["tarifa_fuera"])}
    assert set(a["costo_mxn"].dropna().unique()).issubset(permitidos)

def test_esquema_nivel_b():
    a, cfg = _a()
    b = agregar_nivel_b(a, cfg)
    cols = {"cell_id","municipio","time_bucket","dia_tipo","hour","centroid_lat","centroid_lon",
            "n_requests","n_drivers_available","supply_demand_ratio","demand_density",
            "cancel_rate","is_hot_true","zone_id_true"}
    assert cols.issubset(b.columns)
    assert b["is_hot_true"].any()                      # hay celdas calientes
    assert (b["demand_density"] > 0).all()
    assert (b["supply_demand_ratio"] >= 0).all()

def test_anomalias_y_nulos_y_validacion():
    a, cfg = _a()
    assert a.isna().any().any()
    rep = validar_dataset(a, cfg)
    assert rep["coords_fuera_bbox"] + rep["hora_invalida"] > 0
