def _get(obj, campo, default=None):
    if isinstance(obj, dict):
        return obj.get(campo, default)
    return getattr(obj, campo, default)

def extraer_color_primario(colores_detalle: str | None) -> str:
    if not colores_detalle:
        return ""
    return colores_detalle.split(",")[0].split("(")[0].strip().upper()

def calcular_ancho_bobina(of) -> float:
    """ Ancho de Bobina (mm) = (ancho_mm * 2) + (fuelle_mm * 2) + pega_cm * 10 """
    ancho_mm = _get(of, "ancho_mm")
    fuelle_mm = _get(of, "fuelle_mm")
    if not all([ancho_mm, fuelle_mm]):
        return 0.0
    pega = _get(of, "pega_cm", 2.5) or 2.5
    return (float(ancho_mm) * 2) + (float(fuelle_mm) * 2) + (float(pega) * 10.0)

def es_cambio_contiguo(of_a, of_b) -> bool:
    """
    Verifica si la transición entre dos OFs es una 'jugada corta'.
    Regla: Si mantienen el mismo ancho, pero varía el fuelle o el alto, es cambio parcial (105 min).
    """
    if _get(of_a, "ancho_mm") == _get(of_b, "ancho_mm"):
        if _get(of_a, "alto_mm") != _get(of_b, "alto_mm") or _get(of_a, "fuelle_mm") != _get(of_b, "fuelle_mm"):
            return True
    return False

async def calcular_costo_cambio_async(db, of_a: dict, of_b: dict, penalizaciones: dict) -> tuple:
    """
    Versión async que consulta la tabla de excepciones M8.
    Retorna (total_min, {"detalle": [...], "total_min": float})
    """
    from sqlalchemy import text
    total = 0.0
    detalle = []
    hay_setup = False

    ancho_a = float(_get(of_a, "ancho_mm") or 0)
    ancho_b = float(_get(of_b, "ancho_mm") or 0)
    alto_a  = float(_get(of_a, "alto_mm") or 0)
    alto_b  = float(_get(of_b, "alto_mm") or 0)
    fuelle_a = float(_get(of_a, "fuelle_mm") or 0)
    fuelle_b = float(_get(of_b, "fuelle_mm") or 0)
    num_a = _get(of_a, "tipo_bolsa_num") or _get(of_a, "tipo_bolsa_id")
    num_b = _get(of_b, "tipo_bolsa_num") or _get(of_b, "tipo_bolsa_id")
    maq_a = _get(of_a, "maquina_asignada_id")

    # T_formato
    if ancho_a != ancho_b or fuelle_a != fuelle_b:
        # Cambio de ancho o fuelle = cambio completo
        costo_medida = 480.0
        # Verificar excepción M8
        if num_a and num_b and num_a != num_b:
            result = await db.execute(text("""
                SELECT m.codigo, sc.minutos
                FROM sipp.maquinas m
                LEFT JOIN sipp.setup_cambio_medida_m8 sc
                    ON sc.bolsa_origen = :num_a
                    AND sc.bolsa_destino = :num_b
                WHERE m.id = :maq_id
            """), {"num_a": num_a, "num_b": num_b, "maq_id": maq_a})
            row = result.mappings().one_or_none()
            if row and row["codigo"] == "M8" and row["minutos"] is not None:
                costo_medida = float(row["minutos"])
        total += costo_medida
        detalle.append(f"Cambio medida +{costo_medida:.0f}min")
        hay_setup = True
    elif alto_a != alto_b:
        # Solo cambia alto = cambio parcial
        costo = float(penalizaciones.get("CAMBIO_SOLO_ALTURA", 60))
        total += costo
        detalle.append(f"Cambio altura +{costo:.0f}min")
        hay_setup = True

    # T_color
    col_a = (str(_get(of_a, "colores_detalle") or "")).split(",")[0].strip().upper()
    col_b = (str(_get(of_b, "colores_detalle") or "")).split(",")[0].strip().upper()
    if col_a and col_b and col_a != col_b:
        costo = float(penalizaciones.get("CAMBIO_COLOR_LAVADO_ESTACION", 30))
        total += costo
        detalle.append(f"Cambio color +{costo:.0f}min")
        hay_setup = True

    # T_clise (2h × N° colores destino)
    cil_a = _get(of_a, "cilindro_id")
    cil_b = _get(of_b, "cilindro_id")
    if cil_a and cil_b and cil_a != cil_b:
        num_colores_b = int(_get(of_b, "num_colores") or 1)
        costo_por_color = float(penalizaciones.get("CAMBIO_CLISE_POR_COLOR", 120))
        costo_clise = costo_por_color * num_colores_b
        total += costo_clise
        detalle.append(f"Cambio clisé +{costo_clise:.0f}min ({num_colores_b} colores × {costo_por_color:.0f}min)")
        hay_setup = True

    # T_material
    mat_a = _get(of_a, "material_id")
    mat_b = _get(of_b, "material_id")
    if mat_a and mat_b and mat_a != mat_b:
        costo = float(penalizaciones.get("CAMBIO_MATERIAL", 18))
        total += costo
        detalle.append(f"Cambio material +{costo:.0f}min")
        hay_setup = True

    # T_pruebas (fijo si hay cualquier setup)
    if hay_setup:
        costo_pruebas = float(penalizaciones.get("PRUEBAS_REAJUSTES", 120))
        total += costo_pruebas
        detalle.append(f"Pruebas y reajustes +{costo_pruebas:.0f}min")

    return total, {"detalle": detalle, "total_min": total}

def calcular_costo_cambio_sync(of_a, of_b, penalizaciones: dict) -> tuple[float, dict]:
    total = 0.0
    detalle = []
    hay_setup = False

    ancho_a = float(_get(of_a, "ancho_mm") or 0)
    ancho_b = float(_get(of_b, "ancho_mm") or 0)
    alto_a  = float(_get(of_a, "alto_mm") or 0)
    alto_b  = float(_get(of_b, "alto_mm") or 0)
    fuelle_a = float(_get(of_a, "fuelle_mm") or 0)
    fuelle_b = float(_get(of_b, "fuelle_mm") or 0)

    # T_formato
    if ancho_a != ancho_b or fuelle_a != fuelle_b:
        costo_medida = 480.0
        total += costo_medida
        detalle.append(f"Cambio medida +{costo_medida:.0f}min")
        hay_setup = True
    elif alto_a != alto_b:
        costo = float(penalizaciones.get("CAMBIO_SOLO_ALTURA", 60))
        total += costo
        detalle.append(f"Cambio altura +{costo:.0f}min")
        hay_setup = True

    # T_color
    col_a = (str(_get(of_a, "colores_detalle") or "")).split(",")[0].strip().upper()
    col_b = (str(_get(of_b, "colores_detalle") or "")).split(",")[0].strip().upper()
    if col_a and col_b and col_a != col_b:
        costo = float(penalizaciones.get("CAMBIO_COLOR_LAVADO_ESTACION", 30))
        total += costo
        detalle.append(f"Cambio color +{costo:.0f}min")
        hay_setup = True

    # T_clise
    cil_a = _get(of_a, "cilindro_id")
    cil_b = _get(of_b, "cilindro_id")
    if cil_a and cil_b and cil_a != cil_b:
        num_colores_b = int(_get(of_b, "num_colores") or 1)
        costo_por_color = float(penalizaciones.get("CAMBIO_CLISE_POR_COLOR", 120))
        costo_clise = costo_por_color * num_colores_b
        total += costo_clise
        detalle.append(f"Cambio clisé +{costo_clise:.0f}min ({num_colores_b} colores × {costo_por_color:.0f}min)")
        hay_setup = True

    # T_material
    mat_a = _get(of_a, "material_id")
    mat_b = _get(of_b, "material_id")
    if mat_a and mat_b and mat_a != mat_b:
        costo = float(penalizaciones.get("CAMBIO_MATERIAL", 18))
        total += costo
        detalle.append(f"Cambio material +{costo:.0f}min")
        hay_setup = True

    # T_pruebas
    if hay_setup:
        costo_pruebas = float(penalizaciones.get("PRUEBAS_REAJUSTES", 120))
        total += costo_pruebas
        detalle.append(f"Pruebas y reajustes +{costo_pruebas:.0f}min")

    return total, {"detalle": detalle, "total_min": total}

# Aliases para compatibilidad
calcular_costo_cambio = calcular_costo_cambio_sync

def calcular_icc(setup_total_min: float) -> float:
    """
    ICC basado en clasificación de complejidad VYGPACK:
    0-90 min   → ICC 100-81 (Bajo)
    91-300 min → ICC 80-38  (Medio)
    301-480 min → ICC 37-1  (Alto)
    >480 min   → ICC 0      (Crítico)
    """
    if setup_total_min <= 0:
        return 100.0
    if setup_total_min <= 90:
        # Escala de 100 a 81
        return round(100.0 - (setup_total_min / 90.0 * 19.0), 1)
    if setup_total_min <= 300:
        # Escala de 80 a 38
        return round(80.0 - ((setup_total_min - 90) / 210.0 * 42.0), 1)
    if setup_total_min <= 480:
        # Escala de 37 a 1
        return round(37.0 - ((setup_total_min - 300) / 180.0 * 36.0), 1)
    return 0.0
