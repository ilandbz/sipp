# Skill: Seed Inicial desde CSV
# Archivo: .claude/skills/01_csv_seed.md
# Cuándo usarlo: SOLO para crear el script de carga inicial
# backend/app/management/seed_inicial.py
# NO es un flujo operacional — se ejecuta UNA SOLA VEZ en el arranque del proyecto.

---

## Propósito
Leer `PROGRAMACIÓN_ABRIL.csv` para poblar las tablas maestras y cargar
las primeras órdenes de fabricación como datos de referencia inicial.
Después de esta carga, las OFs se registran **manualmente por formulario en Streamlit**.

## ⚠ Este script NO es un endpoint de la API
No crear router ni vista para esto. Se ejecuta directamente:
```bash
cd backend
python -m app.management.seed_inicial --archivo="../data/PROGRAMACIÓN_ABRIL.csv"
```

---

## Lo que hace el seed (en orden)

1. Poblar `sipp.maquinas` con los códigos únicos de la columna `MAQ`
2. Poblar `sipp.materiales` con los tipos únicos de `MATERIAL` + `GRAMAJE`
3. Poblar `sipp.clientes` con las razones sociales únicas de `RAZON SOCIAL`
4. Poblar `sipp.cilindros` con los códigos únicos de `CILINDRO`
5. Insertar las OFs del CSV como registros iniciales en `sipp.ordenes_fabricacion`
6. Todo con `INSERT ... ON CONFLICT DO NOTHING` — idempotente, seguro de re-ejecutar

---

## Lectura correcta del CSV

```python
import pandas as pd

def leer_csv(ruta: str) -> pd.DataFrame:
    df = pd.read_csv(ruta, encoding="utf-8-sig", sep=";")
    # La fila 0 es el header real
    df.columns = df.iloc[0]
    df = df[1:].reset_index(drop=True)
    # Limpiar espacios en headers (CRÍTICO — hay columnas con espacios)
    df.columns = df.columns.str.strip()
    # Reemplazar errores de Excel
    df.replace(["#N/D", "#¡VALOR!", "#VALUE!", ""], None, inplace=True)
    return df
```

---

## Mapa CSV → tablas maestras (lo que importa del seed)

| Columna CSV | Tabla maestra | Campo |
|---|---|---|
| `MAQ` | `sipp.maquinas` | `codigo` |
| `MATERIAL` | `sipp.materiales` | `tipo` |
| `GRAMAJE` | `sipp.materiales` | `gramaje_min` (referencia) |
| `RAZON SOCIAL` | `sipp.clientes` | `razon_social` |
| `MARCA` | `sipp.clientes` | `marca` |
| `VENDEDOR` | `sipp.clientes` | `vendedor` |
| `CILINDRO` | `sipp.cilindros` | `codigo` |

---

## Columna `Medida` — regex de descomposición

```python
import re

def parsear_medida(texto: str | None) -> dict:
    """
    "18X32X10.5"   → ancho=18,  alto=32,  fuelle=10.5
    "35X36"        → ancho=35,  alto=36,  fuelle=None
    "27.3 X 25.20" → ancho=27.3, alto=25.2, fuelle=None
    """
    if not texto or str(texto).strip() in ("0", ""):
        return {"ancho_mm": None, "alto_mm": None, "fuelle_mm": None}
    partes = re.split(r"[xX\s]+", str(texto).strip())
    partes = [p for p in partes if p]
    try:
        return {
            "ancho_mm":  float(partes[0]) if len(partes) > 0 else None,
            "alto_mm":   float(partes[1]) if len(partes) > 1 else None,
            "fuelle_mm": float(partes[2]) if len(partes) > 2 else None,
        }
    except (ValueError, IndexError):
        return {"ancho_mm": None, "alto_mm": None, "fuelle_mm": None}
```

---

## Checklist del seed

- [ ] Se ejecuta UNA sola vez (o de forma idempotente con `ON CONFLICT DO NOTHING`)
- [ ] Puebla maestros ANTES de insertar OFs (respetar FK)
- [ ] `df.columns.str.strip()` aplicado
- [ ] Fechas con `pd.to_datetime(..., errors="coerce")`
- [ ] `parsear_medida()` aplicado a columna `Medida`
- [ ] No crear endpoint en FastAPI para esto — es un script de management
- [ ] Documentar en el README cómo ejecutarlo
