import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.config import settings

async def ejecutar_deploy():
    engine = create_async_engine(settings.DATABASE_URL)
    
    async with engine.begin() as conn:
        print("1. Verificando schema sipp...")
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS sipp"))
        await conn.execute(text("SET timezone = 'America/Lima'"))
        
        print("2. Creando/actualizando tablas...")
        # Leer y ejecutar bd.sql
        import os
        bd_sql_path = "bd.sql"
        if not os.path.exists(bd_sql_path) and os.path.exists("../bd.sql"):
            bd_sql_path = "../bd.sql"
        with open(bd_sql_path, "r", encoding="utf-8") as f:
            sql = f.read()
        # Ejecutar statement por statement
        for stmt in sql.split(";"):
            stmt = stmt.strip()
            if stmt and not stmt.startswith("--"):
                try:
                    await conn.execute(text(stmt))
                except Exception as e:
                    print(f"  Skip (ya existe): {str(e)[:60]}")
        
        print("2b. Verificando columnas y tablas de autenticación...")
        # Verificar columna password_hash en sipp.usuarios
        try:
            usuarios_exists = (await conn.execute(text("""
                SELECT EXISTS (
                   SELECT FROM information_schema.tables 
                   WHERE  table_schema = 'sipp'
                   AND    table_name   = 'usuarios'
                )
            """))).scalar()

            if usuarios_exists:
                col_exists = (await conn.execute(text("""
                    SELECT EXISTS (
                       SELECT FROM information_schema.columns 
                       WHERE  table_schema = 'sipp'
                       AND    table_name   = 'usuarios'
                       AND    column_name  = 'password_hash'
                    )
                """))).scalar()

                if not col_exists:
                    print("   Agregando columna password_hash a sipp.usuarios...")
                    await conn.execute(text("ALTER TABLE sipp.usuarios ADD COLUMN password_hash VARCHAR(200)"))
        except Exception as e:
            print(f"  Error al verificar/agregar password_hash: {e}")

        # Verificar tabla sipp.sesiones
        try:
            sesiones_exists = (await conn.execute(text("""
                SELECT EXISTS (
                   SELECT FROM information_schema.tables 
                   WHERE  table_schema = 'sipp'
                   AND    table_name   = 'sesiones'
                )
            """))).scalar()

            if not sesiones_exists:
                print("   Creando tabla sipp.sesiones...")
                await conn.execute(text("""
                    CREATE TABLE sipp.sesiones (
                        id              SERIAL PRIMARY KEY,
                        usuario_id      INT REFERENCES sipp.usuarios(id) ON DELETE CASCADE,
                        token           VARCHAR(100) NOT NULL UNIQUE,
                        expira_en       TIMESTAMPTZ NOT NULL,
                        created_at      TIMESTAMPTZ DEFAULT NOW()
                    )
                """))
        except Exception as e:
            print(f"  Error al verificar/crear tabla sesiones: {e}")
        
        print("3. Insertando datos semilla...")
        await seed_penalizaciones(conn)
        await seed_maquinas(conn)
        await seed_materiales(conn)
        await seed_franquicias(conn)
        await seed_tipos_bolsa(conn)
        await seed_usuarios(conn)
        
        print("Deploy completado con exito")

async def seed_usuarios(conn):
    import bcrypt
    
    usuarios_seed = [
        ("admin",     "admin123",    "PROGRAMADOR",     "Administrador"),
        ("jefe",      "jefe123",     "JEFE_PRODUCCION", "Jefe de Producción"),
        ("operador1", "operador123", "OPERADOR",        "Operador Planta"),
    ]
    
    for username, raw_password, rol, nombre in usuarios_seed:
        pwd_hash = bcrypt.hashpw(raw_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        await conn.execute(text("""
            INSERT INTO sipp.usuarios (username, password_hash, rol, nombre_completo, activo)
            VALUES (:username, :pwd_hash, :rol, :nombre, true)
            ON CONFLICT (username) DO UPDATE SET
                password_hash = EXCLUDED.password_hash,
                rol = EXCLUDED.rol,
                nombre_completo = EXCLUDED.nombre_completo,
                activo = EXCLUDED.activo
        """), {"username": username, "pwd_hash": pwd_hash, "rol": rol, "nombre": nombre})

async def seed_penalizaciones(conn):
    await conn.execute(text("""
        INSERT INTO sipp.setup_penalizaciones 
            (tipo_cambio, minutos, descripcion) VALUES
        ('MISMO_FORMATO_MISMO_COLOR', 0, 'Sin cambio'),
        ('CAMBIO_COLOR_LAVADO_ESTACION', 45, 'Lavado de esmeriles'),
        ('CAMBIO_CLISE', 17.5, 'Cambio de clisé'),
        ('CAMBIO_CILINDRO_IMPRESION', 30, 'Cambio de cilindro'),
        ('CAMBIO_MATERIAL', 25, 'Cambio de material'),
        ('CAMBIO_FORMATO_MEDIDA_COMPLETA', 480, 'Cambio de formato completo')
        ON CONFLICT (tipo_cambio) DO NOTHING
    """))

async def seed_maquinas(conn):
    await conn.execute(text("""
        INSERT INTO sipp.maquinas 
            (codigo, nombre, velocidad_bpm_max, turno_horas, dias_semana, activa) VALUES
        ('M8',  'Máquina M8',  80,  8, 5, true),
        ('M10', 'Máquina M10', 100, 8, 5, true),
        ('M14', 'Máquina M14', 120, 8, 5, true)
        ON CONFLICT (codigo) DO UPDATE SET
            velocidad_bpm_max = EXCLUDED.velocidad_bpm_max,
            activa = EXCLUDED.activa
    """))

async def seed_materiales(conn):
    await conn.execute(text("""
        INSERT INTO sipp.materiales (tipo, factor_velocidad) VALUES
        ('KRAFT',            1.000),
        ('KRAFT 50 GR',      0.950),
        ('KRAFT 60 GR',      1.000),
        ('LINER',            0.900),
        ('ANTIGRASA',        0.850),
        ('ANTIGRASA MARRON', 0.840)
        ON CONFLICT (tipo) DO NOTHING
    """))

async def seed_franquicias(conn):
    await conn.execute(text("""
        INSERT INTO sipp.franquicias (nombre, nivel) VALUES
        ('Franquicia Nivel 1 - Prioritario', 1),
        ('Franquicia Nivel 2 - Alto',        2),
        ('Franquicia Nivel 3 - Normal',      3),
        ('Franquicia Nivel 4 - Estándar',    4)
        ON CONFLICT DO NOTHING
    """))

async def seed_tipos_bolsa(conn):
    await conn.execute(text("""
        INSERT INTO sipp.tipos_bolsa (numero, descripcion) VALUES
        (2,  'Bolsa N°2'),
        (4,  'Bolsa N°4'),
        (5,  'Bolsa N°5'),
        (6,  'Bolsa N°6'),
        (8,  'Bolsa N°8'),
        (10, 'Bolsa N°10'),
        (12, 'Bolsa N°12')
        ON CONFLICT (numero) DO NOTHING
    """))

if __name__ == "__main__":
    asyncio.run(ejecutar_deploy())
