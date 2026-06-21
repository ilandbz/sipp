from datetime import date

def generar_analisis_semanal(kpi: dict, cola: list, setup_detalle: dict) -> str:
    """
    Genera un análisis ejecutivo automático basado en reglas
    y datos reales de la semana. Sin API externa.
    """
    if not kpi:
        return "⚠ No hay datos disponibles para esta semana."

    lineas = []

    # ── Datos base ──────────────────────────────────────────
    fecha_ini   = str(kpi.get("fecha_inicio", ""))[:10]
    fecha_fin   = str(kpi.get("fecha_fin", ""))[:10]
    total_ofs   = int(kpi.get("total_ofs", 0))
    setup_h     = float(kpi.get("setup_total_horas", 0))
    util_pct    = float(kpi.get("utilizacion_pct", 0))
    estado      = kpi.get("estado", "")
    horas_dis   = float(kpi.get("horas_disponibles", 120))
    horas_pro   = float(kpi.get("horas_produccion", 0))

    # ── Encabezado ──────────────────────────────────────────
    estado_emoji = {
        "BORRADOR": "📝",
        "CONFIRMADA": "✅",
        "EN_EJECUCION": "🔄",
        "CERRADA": "🏁"
    }.get(estado, "📋")

    lineas.append(
        f"{estado_emoji} **Semana {fecha_ini} al {fecha_fin}** — {estado}"
    )
    lineas.append("")

    # ── Resumen general ─────────────────────────────────────
    pct_setup = round(setup_h / horas_dis * 100, 1) if horas_dis > 0 else 0
    lineas.append("### 📊 Resumen")
    lineas.append(
        f"Se tienen **{total_ofs} OFs** programadas. "
        f"De las **{horas_dis:.0f}h disponibles**, "
        f"{horas_pro:.1f}h son de producción real y "
        f"{setup_h:.1f}h ({pct_setup}%) se destinan a cambios de setup."
    )
    lineas.append("")

    # ── Análisis de utilización ─────────────────────────────
    lineas.append("### 📈 Utilización")
    if util_pct >= 95:
        lineas.append(
            f"🔴 **Utilización crítica: {util_pct}%** — "
            "La semana está sobrecargada. Alto riesgo de no cumplir "
            "con todas las entregas. Considerar redistribuir OFs."
        )
    elif util_pct >= 85:
        lineas.append(
            f"🟠 **Utilización alta: {util_pct}%** — "
            "Cerca del límite recomendado (85%). "
            "Poco margen para imprevistos o paradas no planificadas."
        )
    elif util_pct >= 60:
        lineas.append(
            f"🟢 **Utilización normal: {util_pct}%** — "
            "Carga de trabajo manejable con margen para ajustes."
        )
    else:
        lineas.append(
            f"🔵 **Utilización baja: {util_pct}%** — "
            "Capacidad subutilizada. Evaluar agregar más OFs a la semana."
        )
    lineas.append("")

    # ── Análisis de setup ───────────────────────────────────
    lineas.append("### ⚙ Setup")
    if setup_h > 48:
        lineas.append(
            f"🔴 **Setup muy alto: {setup_h}h** — "
            "Más de 2 días perdidos en cambios. "
            "La mayoría son cambios de formato completo (8h c/u). "
            "Agrupar OFs de misma medida reduciría significativamente este tiempo."
        )
    elif setup_h > 24:
        lineas.append(
            f"🟠 **Setup elevado: {setup_h}h** — "
            "Hay oportunidad de mejorar la secuencia de producción "
            "agrupando OFs con medidas o materiales similares."
        )
    else:
        lineas.append(
            f"🟢 **Setup eficiente: {setup_h}h** — "
            "Buena secuenciación de OFs. Los cambios están minimizados."
        )
    lineas.append("")

    # ── Alertas por OF ──────────────────────────────────────
    alertas = []
    oportunidades = []
    hoy = date.today()

    ofs_por_maquina = {}
    for of in (cola or []):
        maq = of.get("maquina", "SIN_MAQUINA")
        if maq not in ofs_por_maquina:
            ofs_por_maquina[maq] = []
        ofs_por_maquina[maq].append(of)

        codigo   = of.get("codigo_of", "")
        colores  = str(of.get("colores_detalle") or "").upper()
        setup_of = float(of.get("costo_setup_min") or 0)
        fecha_ent = of.get("fecha_entrega")
        cantidad  = of.get("cantidad_programada") or of.get("cantidad_pedido")

        # Entrega vencida
        if fecha_ent:
            try:
                fe = date.fromisoformat(str(fecha_ent)[:10])
                dias_atraso = (hoy - fe).days
                if dias_atraso > 0:
                    alertas.append(
                        f"📅 **{codigo}** — entrega vencida hace "
                        f"**{dias_atraso} día(s)** ({fe})"
                    )
            except Exception:
                pass

        # Riesgo matizado
        palabras_riesgo = ["MATIZ", "PANTONE", "GCMI", "POR CONFIRMAR"]
        if any(p in colores for p in palabras_riesgo):
            alertas.append(
                f"🎨 **{codigo}** — colores de riesgo matizado: "
                f"{of.get('colores_detalle', '')[:50]}"
            )

        # Setup crítico individual
        if setup_of >= 480:
            alertas.append(
                f"⏱ **{codigo}** — cambio de formato completo "
                f"({setup_of:.0f} min = {setup_of/60:.1f}h)"
            )

        # Cantidad no definida
        if not cantidad:
            alertas.append(
                f"❓ **{codigo}** — sin cantidad programada definida"
            )

    # ── Balance por máquina ─────────────────────────────────
    for maq, ofs_maq in ofs_por_maquina.items():
        n = len(ofs_maq)
        if n == 1:
            oportunidades.append(
                f"💡 **{maq}** tiene solo 1 OF — "
                "considerar agregar más OFs para aprovechar la capacidad"
            )
        elif n >= 5:
            oportunidades.append(
                f"📦 **{maq}** tiene {n} OFs — "
                "verificar que el tiempo alcanza para completarlas"
            )

    # ── Mostrar alertas ─────────────────────────────────────
    if alertas:
        lineas.append("### ⚠ Alertas")
        for a in alertas[:6]:  # máximo 6 alertas
            lineas.append(f"- {a}")
        if len(alertas) > 6:
            lineas.append(f"- ... y {len(alertas)-6} alertas más")
        lineas.append("")

    # ── Oportunidades ───────────────────────────────────────
    if oportunidades:
        lineas.append("### 💡 Oportunidades")
        for o in oportunidades[:3]:
            lineas.append(f"- {o}")
        lineas.append("")

    # ── Recomendación final ─────────────────────────────────
    lineas.append("### ✅ Recomendación")
    if util_pct >= 85 and setup_h > 48:
        lineas.append(
            "Semana con alta presión. Priorizar OFs con entrega vencida "
            "y evaluar si alguna OF puede moverse a la siguiente semana "
            "para reducir la carga."
        )
    elif setup_h > 48:
        lineas.append(
            "El setup elevado indica OFs muy variadas. En la próxima "
            "semana, intentar agrupar por tipo de bolsa o material "
            "para reducir los cambios de formato."
        )
    elif util_pct < 60:
        lineas.append(
            "Hay capacidad disponible. Revisar el backlog de OFs "
            "pendientes y considerar adelantar producción de la "
            "siguiente semana."
        )
    else:
        lineas.append(
            "Semana balanceada. Mantener el seguimiento del avance "
            "diario y registrar los tiempos reales de setup para "
            "mejorar las estimaciones futuras."
        )

    lineas.append("")
    lineas.append(
        "---\n"
        f"*Análisis generado automáticamente · {hoy.strftime('%d/%m/%Y')} · "
        "Basado en datos en tiempo real de SIPP*"
    )

    return "\n".join(lineas)
