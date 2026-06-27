from dataclasses import dataclass

@dataclass
class ZonaCaliente:
    lat: float
    lng: float
    intensidad: float          # 0..1 (demand_density normalizada dentro del bucket)
    demand_density: float      # solicitudes/km² (media de las celdas de la zona)
    supply_demand_ratio: float # oferta/demanda (media; bajo = demanda rebasa oferta)
    n_requests: int            # solicitudes totales de la zona
    n_celdas: int              # nº de celdas agrupadas
    radio_m: float
