import asyncio
from sqlmodel import select, text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import engine
from app.models.maquina import Maquina
from app.models.orden_fabricacion import OrdenFabricacion

VALID_CODES = ['M8', 'M10', 'M14']

CAPACIDADES = {
    "M8": {"velocidad_bpm_max": 80.0, "nombre": "Máquina M8", "turno_horas": 8.0, "dias_semana": 5},
    "M10": {"velocidad_bpm_max": 100.0, "nombre": "Máquina M10", "turno_horas": 8.0, "dias_semana": 5},
    "M14": {"velocidad_bpm_max": 120.0, "nombre": "Máquina M14", "turno_horas": 8.0, "dias_semana": 5}
}

async def main():
    async with AsyncSession(engine) as db:
        print("Iniciando reseteo de máquinas a M8, M10 y M14...")

        # 1. Asegurar que las 3 máquinas válidas existan con sus velocidades y nombres correctos
        for code, data in CAPACIDADES.items():
            res = await db.execute(select(Maquina).where(Maquina.codigo == code))
            maq = res.scalars().first()
            if not maq:
                maq = Maquina(codigo=code, **data)
                db.add(maq)
                print(f"Máquina creada: {code} ({data['nombre']})")
            else:
                for k, v in data.items():
                    setattr(maq, k, v)
                db.add(maq)
                print(f"Máquina actualizada: {code} ({data['nombre']}, velocidad={data['velocidad_bpm_max']})")
        await db.flush()

        # Recargar IDs de las máquinas válidas
        res = await db.execute(select(Maquina).where(Maquina.codigo.in_(VALID_CODES)))
        valid_maquinas = {m.codigo: m.id for m in res.scalars().all()}

        # 2. Cargar todas las máquinas registradas para buscar inválidas
        res = await db.execute(select(Maquina))
        all_maqs = res.scalars().all()
        invalid_maqs = [m for m in all_maqs if m.codigo not in VALID_CODES]

        for inv_maq in invalid_maqs:
            code_clean = inv_maq.codigo.strip().upper()
            
            # Determinar a qué máquina redirigir
            if "8" in code_clean:
                target_code = "M8"
            elif "10" in code_clean:
                target_code = "M10"
            elif "14" in code_clean:
                target_code = "M14"
            else:
                target_code = None

            if target_code and target_code in valid_maquinas:
                target_id = valid_maquinas[target_code]
                # Re-asignar OFs asociadas a la máquina inválida
                res_ofs = await db.execute(
                    select(OrdenFabricacion).where(OrdenFabricacion.maquina_asignada_id == inv_maq.id)
                )
                ofs_to_update = res_ofs.scalars().all()
                for of in ofs_to_update:
                    of.maquina_asignada_id = target_id
                    db.add(of)
                print(f"Re-asignadas {len(ofs_to_update)} OFs de máquina '{inv_maq.codigo}' a '{target_code}'")
            else:
                # Si no hay mapeo (ej: FLEXO1, FLEXO2), poner a NULL
                res_ofs = await db.execute(
                    select(OrdenFabricacion).where(OrdenFabricacion.maquina_asignada_id == inv_maq.id)
                )
                ofs_to_update = res_ofs.scalars().all()
                for of in ofs_to_update:
                    of.maquina_asignada_id = None
                    db.add(of)
                print(f"Removida asignación (NULL) para {len(ofs_to_update)} OFs de la máquina '{inv_maq.codigo}'")

            # Eliminar referencias en cascada de la máquina inválida
            await db.execute(
                text("DELETE FROM sipp.disponibilidad_maquinas WHERE maquina_id = :mid"),
                {"mid": inv_maq.id}
            )
            await db.execute(
                text("DELETE FROM sipp.log_optimizaciones WHERE maquina_id = :mid"),
                {"mid": inv_maq.id}
            )
            await db.execute(
                text("DELETE FROM sipp.semanas_programacion WHERE maquina_id = :mid"),
                {"mid": inv_maq.id}
            )

            # Eliminar la máquina inválida
            await db.delete(inv_maq)
            print(f"Máquina inválida eliminada: {inv_maq.codigo}")

        await db.flush()
        
        # 3. Eliminar configuraciones de medidas de máquinas inexistentes si la tabla existe
        ids_str = ",".join(str(i) for i in valid_maquinas.values())
        try:
            await db.execute(
                text(f"DELETE FROM sipp.maquina_medidas_permitidas WHERE maquina_id NOT IN ({ids_str})")
            )
        except Exception:
            # Si la tabla no existe en este ambiente, continuar silenciosamente
            pass

        await db.commit()
        print("Reseteo de máquinas finalizado con éxito [OK]")

if __name__ == "__main__":
    asyncio.run(main())
