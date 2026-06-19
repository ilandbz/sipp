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
    
    # Obtener números de bolsa
    num_a = _get(of_a, "tipo_bolsa_num") or _get(of_a, "tipo_bolsa_id")
    num_b = _get(of_b, "tipo_bolsa_num") or _get(of_b, "tipo_bolsa_id")
    maq_a = _get(of_a, "maquina_asignada_id")
    maq_b = _get(of_b, "maquina_asignada_id")
    ancho_a = float(_get(of_a, "ancho_mm") or 0)
    ancho_b = float(_get(of_b, "ancho_mm") or 0)
    
    # Verificar cambio de medida
    mismo_formato = (ancho_a == ancho_b and ancho_a > 0)
    
    if not mismo_formato:
        # Consultar excepciones de M8
        costo_medida = 480.0  # default
        
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
            else:
                costo_medida = 480.0  # M10/M14: siempre 8h
        
        total += costo_medida
        detalle.append(f"Cambio medida +{costo_medida:.0f}min")
    
    # Color
    col_a = (str(_get(of_a, "colores_detalle") or "")).split(",")[0].strip().upper()
    col_b = (str(_get(of_b, "colores_detalle") or "")).split(",")[0].strip().upper()
    if col_a and col_b and col_a != col_b:
        costo = float(penalizaciones.get("CAMBIO_COLOR_LAVADO_ESTACION", 45))
        total += costo
        detalle.append(f"Cambio color +{costo:.0f}min")
    
    # Cilindro
    cil_a = _get(of_a, "cilindro_id")
    cil_b = _get(of_b, "cilindro_id")
    if cil_a and cil_b and cil_a != cil_b:
        costo = float(penalizaciones.get("CAMBIO_CILINDRO_IMPRESION", 30))
        total += costo
        detalle.append(f"Cambio cilindro +{costo:.0f}min")
    
    # Material
    mat_a = _get(of_a, "material_id")
    mat_b = _get(of_b, "material_id")
    if mat_a and mat_b and mat_a != mat_b:
        costo = float(penalizaciones.get("CAMBIO_MATERIAL", 25))
        total += costo
        detalle.append(f"Cambio material +{costo:.0f}min")
    
    return total, {"detalle": detalle, "total_min": total}

def calcular_costo_cambio_sync(of_a, of_b, penalizaciones: dict) -> tuple[float, dict]:
    total_min = 0.0
    cambio_formato = False
    cambio_parcial = False
    cambio_cilindro = False
    cambio_clise = False
    cambio_color = False
    cambio_material = False
    detalle = []

    # 1. CAMBIO DE FORMATO (COMPLETO O PARCIAL)
    if _get(of_a, "ancho_mm") != _get(of_b, "ancho_mm") or _get(of_a, "alto_mm") != _get(of_b, "alto_mm") or _get(of_a, "fuelle_mm") != _get(of_b, "fuelle_mm"):
        if es_cambio_contiguo(of_a, of_b):
            costo = 105.0 # Jugada corta / cambio parcial
            total_min += costo
            cambio_parcial = True
            detalle.append(f"Cambio formato parcial +{costo:.1f}min")
        else:
            costo = float(penalizaciones.get("CAMBIO_FORMATO_MEDIDA_COMPLETA", 480.0))
            total_min += costo
            cambio_formato = True
            detalle.append(f"Cambio formato +{costo:.1f}min")

    # 2. CAMBIO_CILINDRO_IMPRESION
    cil_a = _get(of_a, "cilindro_id")
    cil_b = _get(of_b, "cilindro_id")
    if cil_a != cil_b and cil_b is not None:
        costo = float(penalizaciones.get("CAMBIO_CILINDRO_IMPRESION", 30.0))
        total_min += costo
        cambio_cilindro = True
        detalle.append(f"Cambio cilindro +{costo:.1f}min")

    # 3. CAMBIO_CLISE
    clise_a = _get(of_a, "clise_id")
    clise_b = _get(of_b, "clise_id")
    if clise_a != clise_b and clise_b is not None:
        costo = float(penalizaciones.get("CAMBIO_CLISE", 17.5))
        total_min += costo
        cambio_clise = True
        detalle.append(f"Cambio clisé +{costo:.1f}min")

    # 4. CAMBIO_COLOR_LAVADO_ESTACION
    color_a = extraer_color_primario(_get(of_a, "colores_detalle"))
    color_b = extraer_color_primario(_get(of_b, "colores_detalle"))
    if color_a != color_b and color_a != "" and color_b != "":
        costo = float(penalizaciones.get("CAMBIO_COLOR_LAVADO_ESTACION", 45.0))
        total_min += costo
        cambio_color = True
        detalle.append(f"Cambio color +{costo:.1f}min")

    # 5. CAMBIO_MATERIAL
    mat_a = _get(of_a, "material_id")
    mat_b = _get(of_b, "material_id")
    if mat_a != mat_b:
        costo = float(penalizaciones.get("CAMBIO_MATERIAL", 25.0))
        total_min += costo
        cambio_material = True
        detalle.append(f"Cambio material +{costo:.1f}min")

    res_dict = {
        "cambio_formato": cambio_formato,
        "cambio_parcial": cambio_parcial,
        "cambio_cilindro": cambio_cilindro,
        "cambio_clise": cambio_clise,
        "cambio_color": cambio_color,
        "cambio_material": cambio_material,
        "detalle": detalle,
        "total_min": total_min
    }
    return total_min, res_dict

# Aliases para compatibilidad
calcular_costo_cambio = calcular_costo_cambio_sync

def calcular_icc(setup_total_min: float) -> float:
    return max(0.0, min(100.0, 100.0 - (setup_total_min / 480.0 * 100.0)))
