def extraer_color_primario(colores_detalle: str | None) -> str:
    if not colores_detalle:
        return ""
    return colores_detalle.split(",")[0].split("(")[0].strip().upper()

def calcular_ancho_bobina(of) -> float:
    """ Ancho de Bobina (mm) = (ancho_mm * 2) + (fuelle_mm * 2) + pega_cm * 10 """
    if not all([of.ancho_mm, of.fuelle_mm]):
        return 0.0
    pega = getattr(of, "pega_cm", 2.5) or 2.5
    return (float(of.ancho_mm) * 2) + (float(of.fuelle_mm) * 2) + (float(pega) * 10.0)

def es_cambio_contiguo(of_a, of_b) -> bool:
    """
    Verifica si la transición entre dos OFs es una 'jugada corta'.
    Regla: Si mantienen el mismo ancho, pero varía el fuelle o el alto, es cambio parcial (105 min).
    """
    if of_a.ancho_mm == of_b.ancho_mm:
        if of_a.alto_mm != of_b.alto_mm or of_a.fuelle_mm != of_b.fuelle_mm:
            return True
    return False

def calcular_costo_cambio(of_a, of_b, penalizaciones: dict) -> tuple[float, dict]:
    total_min = 0.0
    cambio_formato = False
    cambio_parcial = False
    cambio_cilindro = False
    cambio_clise = False
    cambio_color = False
    cambio_material = False
    detalle = []

    # 1. CAMBIO DE FORMATO (COMPLETO O PARCIAL)
    if of_a.ancho_mm != of_b.ancho_mm or of_a.alto_mm != of_b.alto_mm or getattr(of_a, "fuelle_mm", None) != getattr(of_b, "fuelle_mm", None):
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
    if of_a.cilindro_id != of_b.cilindro_id and of_b.cilindro_id is not None:
        costo = float(penalizaciones.get("CAMBIO_CILINDRO_IMPRESION", 30.0))
        total_min += costo
        cambio_cilindro = True
        detalle.append(f"Cambio cilindro +{costo:.1f}min")

    # 3. CAMBIO_CLISE
    if of_a.clise_id != of_b.clise_id and of_b.clise_id is not None:
        costo = float(penalizaciones.get("CAMBIO_CLISE", 17.5))
        total_min += costo
        cambio_clise = True
        detalle.append(f"Cambio clisé +{costo:.1f}min")

    # 4. CAMBIO_COLOR_LAVADO_ESTACION
    color_a = extraer_color_primario(of_a.colores_detalle)
    color_b = extraer_color_primario(of_b.colores_detalle)
    if color_a != color_b and color_a != "" and color_b != "":
        costo = float(penalizaciones.get("CAMBIO_COLOR_LAVADO_ESTACION", 45.0))
        total_min += costo
        cambio_color = True
        detalle.append(f"Cambio color +{costo:.1f}min")

    # 5. CAMBIO_MATERIAL
    if of_a.material_id != of_b.material_id:
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

def calcular_icc(setup_total_min: float) -> float:
    return max(0.0, min(100.0, 100.0 - (setup_total_min / 480.0 * 100.0)))
