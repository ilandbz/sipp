from datetime import datetime, timedelta

def calcular_horas_produccion(
    cantidad_mt: float,
    velocidad_bpm_max: float, 
    factor_velocidad: float
) -> float:
    if not cantidad_mt or not velocidad_bpm_max or not factor_velocidad:
        return 0.0
    bolsas_por_min = velocidad_bpm_max * factor_velocidad
    minutos = (cantidad_mt * 1000) / bolsas_por_min
    return round(minutos / 60, 2)

def calcular_capacidad_semanal(
    turno_horas: float,
    dias_semana: int,
    horas_mantenimiento: float = 0.0
) -> float:
    return (turno_horas * dias_semana) - horas_mantenimiento

def calcular_fecha_fin_of(
    inicio: datetime,
    horas_produccion: float,
    horas_setup: float
) -> datetime:
    total_horas = horas_produccion + horas_setup
    return inicio + timedelta(hours=total_horas)

def calcular_utilizacion(
    horas_produccion_total: float,
    horas_setup_total: float,
    horas_disponibles: float
) -> dict:
    horas_usadas = horas_produccion_total + horas_setup_total
    if not horas_disponibles:
        pct = 0.0
    else:
        pct = round(horas_usadas / horas_disponibles * 100, 1)
    return {
        "horas_usadas": round(horas_usadas, 2),
        "horas_disponibles": horas_disponibles,
        "utilizacion_pct": pct,
        "horas_libres": round(horas_disponibles - horas_usadas, 2)
    }
