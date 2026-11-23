/* ==========================================================================
   etl_watermark.sql — Marca de agua y lógica de carga incremental
   DataMart DM_ComprasPublicas — rol P3

   Contiene:
     1. ETL_Watermark            tabla de control (última fecha cargada por tabla)
     2. ETL_Log                  bitácora de cada ejecución (evidencia para el informe)
     3. etl.usp_CargarFactContratos  APPEND incremental de FACT_CONTRATOS
     4. etl.usp_ReiniciarCarga       vacía hechos y reinicia la marca (repetir la demo)

   Ejecutar DESPUÉS de ddl_datamart.sql.
   ========================================================================== */
USE DM_ComprasPublicas;
GO

/* ---------- 1. Tabla de marca de agua ---------- */
DROP TABLE IF EXISTS dbo.ETL_Watermark;
CREATE TABLE dbo.ETL_Watermark (
    Tabla            VARCHAR(100) NOT NULL CONSTRAINT PK_ETL_Watermark PRIMARY KEY,
    FechaCorte       DATETIME     NOT NULL,   -- mayor FechaAdjudicacion ya cargada
    UltimaEjecucion  DATETIME     NOT NULL
);

-- Valor inicial: 1900-01-01 -> la primera ejecución carga todo lo disponible
INSERT INTO dbo.ETL_Watermark (Tabla, FechaCorte, UltimaEjecucion)
VALUES ('FACT_CONTRATOS', '1900-01-01', GETDATE());
GO

/* ---------- 2. Bitácora de ejecuciones ---------- */
DROP TABLE IF EXISTS dbo.ETL_Log;
CREATE TABLE dbo.ETL_Log (
    ID_Ejecucion       INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_ETL_Log PRIMARY KEY,
    Tabla              VARCHAR(100) NOT NULL,
    Inicio             DATETIME2(0) NOT NULL,
    Fin                DATETIME2(0) NOT NULL,
    RegistrosStaging   INT          NOT NULL,   -- filas recibidas del ETL
    RegistrosInsertados INT         NOT NULL,   -- filas nuevas en el hecho
    RegistrosOmitidos  INT          NOT NULL,   -- ya cargadas o anteriores a la marca
    WatermarkAnterior  DATETIME     NOT NULL,
    WatermarkNuevo     DATETIME     NOT NULL
);
GO

/* ---------- 3. Carga incremental de FACT_CONTRATOS ----------
   Lee stg.FACT_CONTRATOS (la llena etl_load.py) y:
     a) descarta lo que no supera la marca de agua o ya existe (idempotente)
     b) busca las llaves sustitutas en las dimensiones (-1 si no hay coincidencia)
     c) hace APPEND al hecho (nunca TRUNCATE)
     d) avanza la marca de agua y registra la ejecución
   Todo dentro de una transacción: si algo falla, no queda nada a medias. */
CREATE OR ALTER PROCEDURE etl.usp_CargarFactContratos
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @Inicio      DATETIME2(0) = SYSDATETIME();
    DECLARE @WmAnterior  DATETIME = (SELECT FechaCorte FROM dbo.ETL_Watermark WHERE Tabla = 'FACT_CONTRATOS');
    DECLARE @EnStaging   INT = (SELECT COUNT(*) FROM stg.FACT_CONTRATOS);
    DECLARE @Insertados  INT;
    DECLARE @WmNuevo     DATETIME;

    BEGIN TRANSACTION;

        INSERT INTO dbo.FACT_CONTRATOS
            (FK_Tiempo, FK_Proveedor, FK_Entidad, FK_Metodo, FK_Categoria,
             ID_Proceso, ID_Adjudicacion, FechaAdjudicacion,
             MontoAdjudicado, MontoContrato, NumOfertas, DiasAdjudicacion, FechaCargaETL)
        SELECT
            ISNULL(t.SK_Tiempo,    -1),
            ISNULL(p.SK_Proveedor, -1),
            ISNULL(e.SK_Entidad,   -1),
            ISNULL(m.SK_Metodo,    -1),
            ISNULL(c.SK_Categoria, -1),
            s.ID_Proceso,
            s.ID_Adjudicacion,
            s.FechaAdjudicacion,
            ISNULL(s.MontoAdjudicado, 0),
            s.MontoContrato,
            s.NumOfertas,
            s.DiasAdjudicacion,
            GETDATE()
        FROM stg.FACT_CONTRATOS s
        LEFT JOIN dbo.DIM_TIEMPO              t ON t.Fecha         = s.FechaAdjudicacion
        LEFT JOIN dbo.DIM_PROVEEDOR           p ON p.RUC           = s.RUC
        LEFT JOIN dbo.DIM_ENTIDAD             e ON e.CodigoEntidad = s.CodigoEntidad
        LEFT JOIN dbo.DIM_METODO_CONTRATACION m ON m.CodigoMetodo  = s.CodigoMetodo
        LEFT JOIN dbo.DIM_CATEGORIA           c ON c.CodigoCPC     = s.CodigoCPC
        WHERE s.FechaAdjudicacion > @WmAnterior                       -- regla de la marca de agua
          AND s.ID_Proceso IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM dbo.FACT_CONTRATOS f            -- nunca duplicar
                          WHERE f.ID_Proceso = s.ID_Proceso
                            AND f.ID_Adjudicacion = s.ID_Adjudicacion);

        SET @Insertados = @@ROWCOUNT;

        SET @WmNuevo = ISNULL((SELECT MAX(FechaAdjudicacion) FROM dbo.FACT_CONTRATOS), @WmAnterior);

        UPDATE dbo.ETL_Watermark
        SET FechaCorte = @WmNuevo, UltimaEjecucion = GETDATE()
        WHERE Tabla = 'FACT_CONTRATOS';

        INSERT INTO dbo.ETL_Log (Tabla, Inicio, Fin, RegistrosStaging, RegistrosInsertados,
                                 RegistrosOmitidos, WatermarkAnterior, WatermarkNuevo)
        VALUES ('FACT_CONTRATOS', @Inicio, SYSDATETIME(), @EnStaging, @Insertados,
                @EnStaging - @Insertados, @WmAnterior, @WmNuevo);

    COMMIT TRANSACTION;

    TRUNCATE TABLE stg.FACT_CONTRATOS;

    SELECT @EnStaging              AS EnStaging,
           @Insertados             AS Insertados,
           @EnStaging - @Insertados AS Omitidos,
           @WmAnterior             AS WatermarkAnterior,
           @WmNuevo                AS WatermarkNuevo;
END;
GO

/* ---------- 4. Reinicio para repetir la demo ---------- */
CREATE OR ALTER PROCEDURE etl.usp_ReiniciarCarga
AS
BEGIN
    SET NOCOUNT ON;
    DELETE FROM dbo.FACT_CONTRATOS;
    DBCC CHECKIDENT ('dbo.FACT_CONTRATOS', RESEED, 0);
    UPDATE dbo.ETL_Watermark
    SET FechaCorte = '1900-01-01', UltimaEjecucion = GETDATE()
    WHERE Tabla = 'FACT_CONTRATOS';
END;
GO

/* ---------- Consultas útiles para la demo ---------- */
-- Estado actual de la marca de agua
SELECT * FROM dbo.ETL_Watermark;
-- Historial de cargas (captura para el informe)
SELECT * FROM dbo.ETL_Log ORDER BY ID_Ejecucion;
