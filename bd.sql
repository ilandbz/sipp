-- ============================================================
-- SIPP - Sistema Inteligente de Programación de Producción
-- Modelo de Base de Datos PostgreSQL
-- Autor: Cristian Figueroa | Stack: FastAPI + SQLModel + Async
-- ============================================================

-- ============================================================
-- EXTENSIONES
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- para gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- para búsqueda fuzzy en descripciones

-- ============================================================
-- SCHEMA PRINCIPAL
-- ============================================================
CREATE SCHEMA IF NOT EXISTS sipp;

-- ============================================================
-- 1. MAESTRO DE MÁQUINAS
--    Máquinas M8, M10, M14 (y Flexo 1, Flexo 2 del CSV)
-- ============================================================
CREATE TABLE sipp.maquinas (
    id              SERIAL PRIMARY KEY,
    codigo          VARCHAR(20)  NOT NULL UNIQUE,       -- "M8", "M10", "M14", "Flexo1", etc.
    nombre          VARCHAR(100) NOT NULL,
    activa          BOOLEAN      NOT NULL DEFAULT TRUE,
    velocidad_bpm_max   NUMERIC(8,2),                   -- bolsas por minuto máxima
    turno_horas     NUMERIC(4,1) NOT NULL DEFAULT 8.0,  -- horas por turno (8 h estándar)
    dias_semana     SMALLINT     NOT NULL DEFAULT 5,     -- días laborables por semana
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  sipp.maquinas IS 'Máquinas de producción (M8, M10, M14, Flexo 1, Flexo 2)';
COMMENT ON COLUMN sipp.maquinas.velocidad_bpm_max IS 'BPM máximo; el motor lo reduce automáticamente para papeles delgados';

-- ============================================================
-- 2. MAESTRO DE CLIENTES
-- ============================================================
CREATE TABLE sipp.clientes (
    id              SERIAL PRIMARY KEY,
    razon_social    VARCHAR(200) NOT NULL,
    marca           VARCHAR(100),
    vendedor        VARCHAR(100),
    prioridad       SMALLINT     NOT NULL DEFAULT 3      -- 1=alta, 2=media, 3=baja
        CHECK (prioridad BETWEEN 1 AND 5),
    franquicia_id   INT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 2b. MAESTRO DE FRANQUICIAS
-- ============================================================
CREATE TABLE sipp.franquicias (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    nivel INT NOT NULL CHECK (nivel BETWEEN 1 AND 4),
    descripcion TEXT,
    UNIQUE (nivel)
);

ALTER TABLE sipp.clientes ADD CONSTRAINT fk_franquicia FOREIGN KEY (franquicia_id) REFERENCES sipp.franquicias(id);

CREATE INDEX idx_clientes_razon ON sipp.clientes USING GIN (razon_social gin_trgm_ops);

-- ============================================================
-- 3. MAESTRO DE MATERIALES / PAPEL
-- ============================================================
CREATE TABLE sipp.materiales (
    id              SERIAL PRIMARY KEY,
    tipo            VARCHAR(80)  NOT NULL,               -- "KRAFT", "ANTIGRASA", "ANTIGRASA MARRON", etc.
    gramaje_min     NUMERIC(5,1),
    gramaje_max     NUMERIC(5,1),
    factor_velocidad NUMERIC(4,3) NOT NULL DEFAULT 1.000, -- multiplicador sobre BPM max (< 1 para papeles delgados)
    descripcion     TEXT,
    UNIQUE (tipo)
);

COMMENT ON COLUMN sipp.materiales.factor_velocidad IS
    'Papel Kraft ≈ 1.0 (máxima velocidad). Papeles delgados < 1.0 para evitar roturas.';

-- ============================================================
-- 4. MAESTRO DE CILINDROS DE IMPRESIÓN
-- ============================================================
CREATE TABLE sipp.cilindros (
    id              SERIAL PRIMARY KEY,
    codigo          VARCHAR(30)  NOT NULL UNIQUE,        -- número/código grabado en el cilindro
    descripcion     VARCHAR(200),
    activo          BOOLEAN      NOT NULL DEFAULT TRUE
);

-- ============================================================
-- 5. MAESTRO DE CLISÉS
-- ============================================================
CREATE TABLE sipp.clises (
    id              SERIAL PRIMARY KEY,
    codigo          VARCHAR(50)  NOT NULL UNIQUE,
    descripcion     VARCHAR(200),
    activo          BOOLEAN      NOT NULL DEFAULT TRUE
);

-- ============================================================
-- 5b. MAESTRO DE TIPOS DE BOLSA (N° de bolsa)
-- ============================================================
CREATE TABLE sipp.tipos_bolsa (
    id              SERIAL PRIMARY KEY,
    numero          INTEGER NOT NULL UNIQUE,  -- 2, 4, 5, 6, 8, 10, 12
    descripcion     VARCHAR(100),
    ancho_std_mm    NUMERIC(7,2),
    alto_std_mm     NUMERIC(7,2),
    fuelle_std_mm   NUMERIC(7,2),
    activo          BOOLEAN DEFAULT TRUE
);

INSERT INTO sipp.tipos_bolsa (numero, descripcion) VALUES
(2,  'Bolsa N°2'),
(4,  'Bolsa N°4'),
(5,  'Bolsa N°5'),
(6,  'Bolsa N°6'),
(8,  'Bolsa N°8'),
(10, 'Bolsa N°10'),
(12, 'Bolsa N°12');

-- ============================================================
-- 6. ÓRDENES DE FABRICACIÓN (tabla central)
--    Alimentada desde el CSV PROGRAMACIÓN_ABRIL.csv vía importer.py
-- ============================================================
CREATE TABLE sipp.ordenes_fabricacion (
    id                      SERIAL PRIMARY KEY,
    codigo_of               VARCHAR(30)  NOT NULL UNIQUE,   -- "2603-0671", "2604-8014", etc.
    codigo_pt               VARCHAR(30),                    -- Código PT del producto terminado
    descripcion             TEXT,
    referencia              VARCHAR(200),

    -- Relaciones
    cliente_id              INT REFERENCES sipp.clientes(id) ON DELETE SET NULL,
    maquina_asignada_id     INT REFERENCES sipp.maquinas(id) ON DELETE SET NULL,
    material_id             INT REFERENCES sipp.materiales(id) ON DELETE SET NULL,
    cilindro_id             INT REFERENCES sipp.cilindros(id) ON DELETE SET NULL,
    clise_id                INT REFERENCES sipp.clises(id)   ON DELETE SET NULL,
    tipo_bolsa_id           INT REFERENCES sipp.tipos_bolsa(id) ON DELETE SET NULL,

    -- Dimensiones del producto (medida)
    medida_texto            VARCHAR(50),                    -- "18X32X10.5", "35X36", etc.
    ancho_mm                NUMERIC(7,2),
    alto_mm                 NUMERIC(7,2),
    fuelle_mm               NUMERIC(7,2),
    distancia_base_mm       NUMERIC(7,2),
    leva_requerida          VARCHAR(50),                    -- tipo/código de leva

    -- Impresión
    gramaje                 NUMERIC(5,1),
    num_colores             SMALLINT,
    colores_detalle         TEXT,                           -- "AZUL(P286U), ROJO(P2347U)..."
    tipo_bolsa              VARCHAR(80),
    tipo_etiqueta           VARCHAR(50),
    ancho_bobina_mm         NUMERIC(7,2),
    pega_cm                 NUMERIC(4,2) DEFAULT 2.5,
    franquicia_nivel        INT DEFAULT 4 CHECK (franquicia_nivel BETWEEN 1 AND 4),

    -- Cantidades
    cantidad_pedido         NUMERIC(12,3),
    saldo_por_atender       NUMERIC(12,3),
    stock_disponible        NUMERIC(12,3),
    unidad_medida           VARCHAR(20),                    -- "MIL", "KG", "UND"
    cantidad_programada     NUMERIC(12,3),                  -- MT (miles a producir)
    tp_unidades             NUMERIC(14,4),                  -- TP del CSV
    peso_por_millar         NUMERIC(10,3),
    peso_requerido          NUMERIC(12,3),
    cantidad_empaquetado    VARCHAR(50),

    -- Fechas
    fecha_emision           DATE,
    fecha_entrega           DATE,
    fecha_atencion          DATE,
    inicio_prod             TIMESTAMPTZ,
    prioridad               INT CHECK (prioridad BETWEEN 1 AND 5),

    -- Tiempos calculados (en horas decimales)
    horas_preparacion       NUMERIC(6,2),
    horas_correccion        NUMERIC(6,2),
    horas_produccion        NUMERIC(6,2),
    horas_trabajo_maquina   NUMERIC(6,2),
    dias_semana_programados SMALLINT,
    horas_estimadas         NUMERIC(6,2),
    horas_subtotal          NUMERIC(6,2),
    dia_festivo             BOOLEAN DEFAULT FALSE,
    horas_total_produccion  NUMERIC(6,2),

    -- Fin calculado / proyectado
    fin_ocupacion_calculado  TIMESTAMPTZ,
    fin_produccion_proyectado TIMESTAMPTZ,
    fin_produccion           TIMESTAMPTZ,

    -- Control
    tipo_produccion         VARCHAR(50),                    -- "Stock", "Pedido", etc.
    estado                  VARCHAR(30) NOT NULL DEFAULT 'PENDIENTE'
        CHECK (estado IN ('PENDIENTE','PROGRAMADA','EN_PROCESO','COMPLETADA','CANCELADA')),
    observacion             TEXT,

    -- Trazabilidad importación
    importado_en            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    fuente_archivo          VARCHAR(200),                   -- nombre del CSV de origen

    created_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_of_estado          ON sipp.ordenes_fabricacion(estado);
CREATE INDEX idx_of_fecha_entrega   ON sipp.ordenes_fabricacion(fecha_entrega);
CREATE INDEX idx_of_maquina         ON sipp.ordenes_fabricacion(maquina_asignada_id);
CREATE INDEX idx_of_cliente         ON sipp.ordenes_fabricacion(cliente_id);
CREATE INDEX idx_of_material        ON sipp.ordenes_fabricacion(material_id);
CREATE INDEX idx_of_cilindro        ON sipp.ordenes_fabricacion(cilindro_id);

COMMENT ON TABLE sipp.ordenes_fabricacion IS
    'Tabla central. Importada desde PROGRAMACIÓN_ABRIL.csv mediante importer.py (Pandas).';

-- ============================================================
-- 7. SEMANAS DE PROGRAMACIÓN
--    Agrupa las secuencias por semana/máquina
-- ============================================================
CREATE TABLE sipp.semanas_programacion (
    id              SERIAL PRIMARY KEY,
    maquina_id      INT NOT NULL REFERENCES sipp.maquinas(id),
    fecha_inicio    DATE NOT NULL,
    fecha_fin       DATE NOT NULL,
    horas_disponibles NUMERIC(6,2),                        -- horas netas de la semana
    estado          VARCHAR(20) NOT NULL DEFAULT 'BORRADOR'
        CHECK (estado IN ('BORRADOR','CONFIRMADA','EN_EJECUCION','CERRADA')),
    created_by      VARCHAR(100),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (maquina_id, fecha_inicio)
);

-- ============================================================
-- 8. SECUENCIAS DE PRODUCCIÓN
--    Resultado del optimizador: orden en que cada OF corre en
--    una semana/máquina. Generado por optimizer.py.
-- ============================================================
CREATE TABLE sipp.secuencias_produccion (
    id                      SERIAL PRIMARY KEY,
    semana_id               INT NOT NULL REFERENCES sipp.semanas_programacion(id) ON DELETE CASCADE,
    orden_fabricacion_id    INT NOT NULL REFERENCES sipp.ordenes_fabricacion(id),
    posicion                SMALLINT NOT NULL,              -- 1, 2, 3... orden en la cola

    -- Costo de cambio respecto al slot anterior (calculado por el optimizador)
    costo_setup_min         NUMERIC(7,1) NOT NULL DEFAULT 0,    -- minutos de setup acumulados
    motivo_setup            TEXT,                               -- "Cambio de formato (480 min), Cambio de color (45 min)"

    -- Ventana de ejecución
    inicio_estimado         TIMESTAMPTZ,
    fin_estimado            TIMESTAMPTZ,

    -- Estado ejecución
    estado                  VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE'
        CHECK (estado IN ('PENDIENTE','EN_PROCESO','COMPLETADA','OMITIDA')),
    bloqueada_por           TEXT,                           -- motivo si está bloqueada

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (semana_id, posicion)
);

CREATE INDEX idx_seq_semana   ON sipp.secuencias_produccion(semana_id);
CREATE INDEX idx_seq_of       ON sipp.secuencias_produccion(orden_fabricacion_id);

-- ============================================================
-- 9. MATRIZ DE COSTOS DE CAMBIO (SMED)
--    Penalizaciones entre pares de categorías de atributos.
--    El optimizer.py consulta esta tabla en lugar de tener
--    las penalizaciones hardcodeadas.
-- ============================================================
CREATE TABLE sipp.setup_penalizaciones (
    id              SERIAL PRIMARY KEY,
    tipo_cambio     VARCHAR(80)  NOT NULL UNIQUE,          -- nombre canónico del cambio
    minutos         NUMERIC(7,1) NOT NULL,
    descripcion     TEXT,
    activo          BOOLEAN NOT NULL DEFAULT TRUE
);

-- Datos maestros iniciales conforme a Hoja de Operación Estándar VYGPACK
INSERT INTO sipp.setup_penalizaciones (tipo_cambio, minutos, descripcion) VALUES
    ('MISMO_FORMATO_MISMO_COLOR',           0,     'Secuencia ideal — sin cambios. 0 min de setup.'),
    ('CAMBIO_COLOR_LAVADO_ESTACION',        45,    'Lavado de estación de impresión (esmeriles).'),
    ('CAMBIO_CLISE',                        17.5,  'Sacar + montar clisé (~15–20 min promedio).'),
    ('CAMBIO_CILINDRO_IMPRESION',           30,    'Cambio de cilindro de impresión.'),
    ('CAMBIO_MATERIAL',                     25,    'Cambio de tipo/gramaje de papel (~20–30 min promedio).'),
    ('CAMBIO_FORMATO_MEDIDA_COMPLETA',      480,   'Cambio de formato completo (8 horas). Mayor penalización.');

-- ============================================================
-- 10. ICC - ÍNDICE DE COMPATIBILIDAD DE CAMBIO
--     Score numérico 0-100 entre pares de OFs.
--     Calculado por optimizer.py y cacheado aquí para el frontend.
-- ============================================================
CREATE TABLE sipp.icc_cache (
    id                  BIGSERIAL PRIMARY KEY,
    of_origen_id        INT NOT NULL REFERENCES sipp.ordenes_fabricacion(id) ON DELETE CASCADE,
    of_destino_id       INT NOT NULL REFERENCES sipp.ordenes_fabricacion(id) ON DELETE CASCADE,
    icc_score           NUMERIC(5,2) NOT NULL CHECK (icc_score BETWEEN 0 AND 100),
    setup_total_min     NUMERIC(7,1) NOT NULL,              -- suma de penalizaciones aplicables
    detalle_json        JSONB,                              -- {"cambio_formato": 480, "cambio_color": 45, ...}
    calculado_en        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (of_origen_id, of_destino_id)
);

CREATE INDEX idx_icc_origen  ON sipp.icc_cache(of_origen_id);
CREATE INDEX idx_icc_destino ON sipp.icc_cache(of_destino_id);
CREATE INDEX idx_icc_score   ON sipp.icc_cache(icc_score DESC);

COMMENT ON TABLE sipp.icc_cache IS
    'Cache del ICC calculado por el optimizador. Evita recálculo en cada renderizado del frontend.';

-- ============================================================
-- 10b. USUARIOS Y ROLES DEL SISTEMA
-- ============================================================
CREATE TABLE sipp.usuarios (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(50) NOT NULL UNIQUE,
    nombre_completo VARCHAR(150),
    rol             VARCHAR(30) NOT NULL 
        CHECK (rol IN ('PROGRAMADOR','JEFE_PRODUCCION','OPERADOR')),
    activo          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO sipp.usuarios (username, nombre_completo, rol) VALUES
('admin', 'Administrador SIPP', 'PROGRAMADOR'),
('jefe', 'Jefe de Producción', 'JEFE_PRODUCCION'),
('operador1', 'Operador Planta', 'OPERADOR');

-- ============================================================
-- 11. LOG DE OPTIMIZACIONES
--     Trazabilidad de cada corrida del algoritmo heurístico
-- ============================================================
CREATE TABLE sipp.log_optimizaciones (
    id              BIGSERIAL PRIMARY KEY,
    semana_id       INT REFERENCES sipp.semanas_programacion(id),
    maquina_id      INT REFERENCES sipp.maquinas(id),
    algoritmo       VARCHAR(50)  NOT NULL DEFAULT 'HEURISTICO_PRIORIDAD_SMED',
    ordenes_evaluadas SMALLINT,
    setup_total_antes_min   NUMERIC(8,1),   -- minutos totales de setup antes de optimizar
    setup_total_despues_min NUMERIC(8,1),   -- minutos totales tras optimizar
    reduccion_pct   NUMERIC(5,2),           -- porcentaje de mejora
    duracion_ms     INT,                    -- tiempo de cómputo
    resultado_json  JSONB,                  -- snapshot de la secuencia final
    ejecutado_por   VARCHAR(100),
    ejecutado_en    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 12. DISPONIBILIDAD DE MÁQUINAS (mantenimientos, paros)
-- ============================================================
CREATE TABLE sipp.disponibilidad_maquinas (
    id              SERIAL PRIMARY KEY,
    maquina_id      INT NOT NULL REFERENCES sipp.maquinas(id),
    fecha_inicio    TIMESTAMPTZ NOT NULL,
    fecha_fin       TIMESTAMPTZ NOT NULL,
    tipo            VARCHAR(40) NOT NULL
        CHECK (tipo IN ('MANTENIMIENTO','PARO_NO_PLANIFICADO','FERIADO','CAPACITACION','OTRO')),
    descripcion     TEXT,
    horas_bloqueadas NUMERIC(6,2) GENERATED ALWAYS AS
        (EXTRACT(EPOCH FROM (fecha_fin - fecha_inicio)) / 3600.0) STORED,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_disp_maquina_fecha ON sipp.disponibilidad_maquinas(maquina_id, fecha_inicio, fecha_fin);

-- ============================================================
-- 12b. HISTORIAL DE SETUPS
-- ============================================================
CREATE TABLE sipp.setups_historial (
  id SERIAL PRIMARY KEY,
  secuencia_id INT REFERENCES sipp.secuencias_produccion(id),
  of_anterior_id INT REFERENCES sipp.ordenes_fabricacion(id),
  of_siguiente_id INT REFERENCES sipp.ordenes_fabricacion(id),
  maquina_id INT REFERENCES sipp.maquinas(id),
  setup_estimado_min NUMERIC(7,1),
  setup_real_min NUMERIC(7,1),
  inicio_setup TIMESTAMPTZ,
  fin_setup TIMESTAMPTZ,
  hubo_cambio_formato BOOLEAN DEFAULT FALSE,
  hubo_cambio_color BOOLEAN DEFAULT FALSE,
  hubo_cambio_cilindro BOOLEAN DEFAULT FALSE,
  hubo_cambio_clise BOOLEAN DEFAULT FALSE,
  hubo_cambio_material BOOLEAN DEFAULT FALSE,
  observacion TEXT,
  registrado_por VARCHAR(100),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 12c. ESTADO ACTUAL MÁQUINA Y PARADAS
-- ============================================================
CREATE TABLE sipp.ultimo_estado_maquina (
    id SERIAL PRIMARY KEY,
    maquina_id INT NOT NULL UNIQUE REFERENCES sipp.maquinas(id),
    ultima_of_id INT REFERENCES sipp.ordenes_fabricacion(id),
    ancho_mm NUMERIC(7,2),
    alto_mm NUMERIC(7,2),
    fuelle_mm NUMERIC(7,2),
    cilindro_id INT REFERENCES sipp.cilindros(id),
    material_id INT REFERENCES sipp.materiales(id),
    color_principal VARCHAR(80),
    tipo_bolsa_num INT,
    actualizado_en TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE sipp.paradas (
    id SERIAL PRIMARY KEY,
    maquina_id INT NOT NULL REFERENCES sipp.maquinas(id),
    inicio TIMESTAMPTZ NOT NULL,
    fin TIMESTAMPTZ NOT NULL,
    tipo VARCHAR(40) NOT NULL
        CHECK (tipo IN ('AVERIA','MANTENIMIENTO','PERSONAL','MATERIAL','OTRO')),
    descripcion TEXT,
    horas_perdidas NUMERIC(6,2) GENERATED ALWAYS AS
        (EXTRACT(EPOCH FROM (fin - inicio)) / 3600.0) STORED,
    registrado_por VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 13. TRIGGER: actualizar updated_at automáticamente
-- ============================================================
CREATE OR REPLACE FUNCTION sipp.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

-- Aplicar a las tablas que tienen updated_at
DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'maquinas','clientes','ordenes_fabricacion',
        'semanas_programacion','secuencias_produccion'
    ]
    LOOP
        EXECUTE format(
            'CREATE TRIGGER trg_set_updated_at
             BEFORE UPDATE ON sipp.%I
             FOR EACH ROW EXECUTE FUNCTION sipp.set_updated_at();', tbl
        );
    END LOOP;
END;
$$;

-- ============================================================
-- 14. VISTAS ÚTILES PARA EL BACKEND/FRONTEND
-- ============================================================

-- Vista: cola de producción por máquina (para el dashboard)
CREATE OR REPLACE VIEW sipp.v_cola_produccion AS
SELECT
    sp.id                   AS secuencia_id,
    m.codigo                AS maquina,
    s.fecha_inicio          AS semana_inicio,
    sp.posicion,
    of.codigo_of,
    of.descripcion,
    of.medida_texto,
    of.material_id,
    mat.tipo                AS material,
    of.gramaje,
    of.cilindro_id,
    of.num_colores,
    of.colores_detalle,
    of.cantidad_programada,
    of.fecha_entrega,
    sp.costo_setup_min,
    sp.motivo_setup,
    sp.inicio_estimado,
    sp.fin_estimado,
    sp.estado               AS estado_secuencia,
    of.estado               AS estado_of
FROM sipp.secuencias_produccion sp
JOIN sipp.semanas_programacion   s   ON s.id  = sp.semana_id
JOIN sipp.maquinas               m   ON m.id  = s.maquina_id
JOIN sipp.ordenes_fabricacion    of  ON of.id = sp.orden_fabricacion_id
LEFT JOIN sipp.materiales        mat ON mat.id = of.material_id
ORDER BY m.codigo, s.fecha_inicio, sp.posicion;

-- Vista: KPI semanal por máquina
CREATE OR REPLACE VIEW sipp.v_kpi_semanal AS
SELECT
    m.codigo                                    AS maquina,
    s.fecha_inicio,
    s.fecha_fin,
    COUNT(sp.id)                                AS total_ordenes,
    SUM(sp.costo_setup_min)                     AS setup_total_min,
    ROUND(SUM(sp.costo_setup_min) / 60.0, 2)   AS setup_total_horas,
    SUM(of.horas_produccion)                    AS horas_produccion_total,
    ROUND(
        100.0 * SUM(of.horas_produccion)
        / NULLIF(s.horas_disponibles, 0)
    , 1)                                        AS utilizacion_pct,
    s.estado                                    AS estado_semana
FROM sipp.semanas_programacion   s
JOIN sipp.maquinas               m   ON m.id  = s.maquina_id
LEFT JOIN sipp.secuencias_produccion sp ON sp.semana_id = s.id
LEFT JOIN sipp.ordenes_fabricacion   of ON of.id = sp.orden_fabricacion_id
GROUP BY m.codigo, s.fecha_inicio, s.fecha_fin, s.horas_disponibles, s.estado
ORDER BY m.codigo, s.fecha_inicio;

-- Vista: Plan semanal por máquina
CREATE OR REPLACE VIEW sipp.v_plan_semanal AS
SELECT
    m.codigo                            AS maquina,
    s.fecha_inicio                      AS semana_inicio,
    s.fecha_fin                         AS semana_fin,
    sp.posicion,
    of.codigo_of,
    of.descripcion,
    of.medida_texto,
    of.cantidad_programada              AS mt_a_producir,
    sp.costo_setup_min                  AS setup_min,
    ROUND(sp.costo_setup_min / 60.0, 2) AS setup_horas,
    of.horas_produccion,
    ROUND(sp.costo_setup_min/60.0 + COALESCE(of.horas_produccion,0), 2) 
                                        AS horas_total_of,
    sp.motivo_setup,
    of.fecha_entrega,
    sp.estado                           AS estado_secuencia
FROM sipp.secuencias_produccion sp
JOIN sipp.semanas_programacion s  ON s.id  = sp.semana_id
JOIN sipp.maquinas m              ON m.id  = s.maquina_id
JOIN sipp.ordenes_fabricacion of  ON of.id = sp.orden_fabricacion_id
ORDER BY m.codigo, s.fecha_inicio, sp.posicion;

-- ============================================================
-- DATOS SEMILLA — Máquinas (basados en CSV + documento)
-- ============================================================
INSERT INTO sipp.maquinas (codigo, nombre, velocidad_bpm_max, turno_horas) VALUES
    ('M8',      'Máquina M8',    80,  8),
    ('M10',     'Máquina M10',   100, 8),
    ('M14',     'Máquina M14',   120, 8);

-- Materiales semilla (según CSV)
INSERT INTO sipp.materiales (tipo, factor_velocidad) VALUES
    ('KRAFT',               1.000),   -- papel Kraft: velocidad máxima estable
    ('KRAFT 50 GR',         0.950),
    ('KRAFT 60 GR',         1.000),
    ('ANTIGRASA',           0.850),   -- papeles más delgados → reducen BPM
    ('ANTIGRASA MARRON',    0.840);