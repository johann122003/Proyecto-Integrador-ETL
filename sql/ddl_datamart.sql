/* ==========================================================================
   ddl_datamart.sql — DataMart DM_ComprasPublicas (esquema estrella)
   Proyecto BI: Transparencia en Compras Públicas del SERCOP — rol P3

   Grano de FACT_CONTRATOS: 1 fila = 1 contrato adjudicado
                            (llave de negocio: ID_Proceso + ID_Adjudicacion)

   Orden de ejecución:  1) ddl_datamart.sql   2) etl_watermark.sql
   ATENCIÓN: este script BORRA y recrea las tablas. Ejecútalo solo al inicio.
   ========================================================================== */

IF DB_ID('DM_ComprasPublicas') IS NULL
    CREATE DATABASE DM_ComprasPublicas;
GO
USE DM_ComprasPublicas;
GO

IF SCHEMA_ID('stg') IS NULL EXEC('CREATE SCHEMA stg');   -- tablas de paso del ETL
GO
IF SCHEMA_ID('etl') IS NULL EXEC('CREATE SCHEMA etl');   -- procedimientos del ETL
GO

/* ---------- Limpieza (primero el hecho, luego las dimensiones) ---------- */
DROP TABLE IF EXISTS dbo.FACT_CONTRATOS;
DROP TABLE IF EXISTS dbo.DIM_TIEMPO;
DROP TABLE IF EXISTS dbo.DIM_PROVEEDOR;
DROP TABLE IF EXISTS dbo.DIM_ENTIDAD;
DROP TABLE IF EXISTS dbo.DIM_METODO_CONTRATACION;
DROP TABLE IF EXISTS dbo.DIM_CATEGORIA;
DROP TABLE IF EXISTS stg.FACT_CONTRATOS;
DROP TABLE IF EXISTS stg.DIM_PROVEEDOR;
DROP TABLE IF EXISTS stg.DIM_ENTIDAD;
DROP TABLE IF EXISTS stg.DIM_METODO_CONTRATACION;
DROP TABLE IF EXISTS stg.DIM_CATEGORIA;
GO

/* ==========================================================================
   DIMENSIONES
   Cada dimensión tiene:
     - SK_xxx  : llave sustituta (PK). DIM_TIEMPO usa llave inteligente AAAAMMDD.
     - Código  : llave de negocio, única (la usa el ETL para el MERGE y el lookup).
     - Fila -1 : miembro "Desconocido" para no dejar hechos huérfanos.
   ========================================================================== */

CREATE TABLE dbo.DIM_TIEMPO (
    SK_Tiempo   INT          NOT NULL CONSTRAINT PK_DIM_TIEMPO PRIMARY KEY,  -- AAAAMMDD
    Fecha       DATE         NULL,
    Anio        SMALLINT     NULL,
    Trimestre   TINYINT      NULL,
    Mes         TINYINT      NULL,
    NombreMes   VARCHAR(15)  NULL,
    DiaSemana   TINYINT      NULL,   -- 1 = lunes ... 7 = domingo
    EsQ4        BIT          NULL,
    CONSTRAINT UQ_DIM_TIEMPO_Fecha UNIQUE (Fecha)
);

CREATE TABLE dbo.DIM_PROVEEDOR (
    SK_Proveedor             INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_DIM_PROVEEDOR PRIMARY KEY,
    RUC                      VARCHAR(20)   NOT NULL,   -- RUC de sociedades; 'PN-<hash>' en personas naturales
    RazonSocial_Anonimizada  NVARCHAR(300) NOT NULL,
    Provincia                NVARCHAR(100) NULL,
    ActividadEconomica_CIIU  NVARCHAR(400) NULL,
    TipoContribuyente        NVARCHAR(100) NULL,
    FechaInicioActividades   DATE          NULL,
    CONSTRAINT UQ_DIM_PROVEEDOR_RUC UNIQUE (RUC)
);

CREATE TABLE dbo.DIM_ENTIDAD (
    SK_Entidad     INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_DIM_ENTIDAD PRIMARY KEY,
    CodigoEntidad  VARCHAR(100)  NOT NULL,             -- buyer.id del OCDS
    NombreEntidad  NVARCHAR(300) NOT NULL,
    NivelGobierno  NVARCHAR(60)  NULL,                 -- deducido del nombre (config.py)
    Sector         NVARCHAR(60)  NULL,
    Provincia      NVARCHAR(100) NULL,
    CONSTRAINT UQ_DIM_ENTIDAD_Codigo UNIQUE (CodigoEntidad)
);

CREATE TABLE dbo.DIM_METODO_CONTRATACION (
    SK_Metodo          INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_DIM_METODO PRIMARY KEY,
    CodigoMetodo       NVARCHAR(100) NOT NULL,         -- método normalizado (mayúsculas, sin tildes)
    DescripcionMetodo  NVARCHAR(200) NOT NULL,         -- tender.procurementMethodDetails
    CategoriaMetodo    NVARCHAR(60)  NULL,             -- Emergencia, Ínfima cuantía, Licitación...
    EsCompetitivo      BIT           NULL,
    CONSTRAINT UQ_DIM_METODO_Codigo UNIQUE (CodigoMetodo)
);

CREATE TABLE dbo.DIM_CATEGORIA (
    SK_Categoria          INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_DIM_CATEGORIA PRIMARY KEY,
    CodigoCPC             VARCHAR(30)   NOT NULL,
    DescripcionCategoria  NVARCHAR(400) NOT NULL,
    GrupoCategoria        NVARCHAR(100) NULL,          -- sección CPC (primer dígito)
    CONSTRAINT UQ_DIM_CATEGORIA_Codigo UNIQUE (CodigoCPC)
);
GO

/* ---------- Miembros "Desconocido" (SK = -1) ---------- */
INSERT INTO dbo.DIM_TIEMPO (SK_Tiempo, Fecha, Anio, Trimestre, Mes, NombreMes, DiaSemana, EsQ4)
VALUES (-1, NULL, NULL, NULL, NULL, 'Desconocido', NULL, NULL);

SET IDENTITY_INSERT dbo.DIM_PROVEEDOR ON;
INSERT INTO dbo.DIM_PROVEEDOR (SK_Proveedor, RUC, RazonSocial_Anonimizada)
VALUES (-1, 'DESCONOCIDO', N'DESCONOCIDO');
SET IDENTITY_INSERT dbo.DIM_PROVEEDOR OFF;

SET IDENTITY_INSERT dbo.DIM_ENTIDAD ON;
INSERT INTO dbo.DIM_ENTIDAD (SK_Entidad, CodigoEntidad, NombreEntidad)
VALUES (-1, 'DESCONOCIDO', N'DESCONOCIDO');
SET IDENTITY_INSERT dbo.DIM_ENTIDAD OFF;

SET IDENTITY_INSERT dbo.DIM_METODO_CONTRATACION ON;
INSERT INTO dbo.DIM_METODO_CONTRATACION (SK_Metodo, CodigoMetodo, DescripcionMetodo, CategoriaMetodo)
VALUES (-1, N'DESCONOCIDO', N'Desconocido', N'Desconocido');
SET IDENTITY_INSERT dbo.DIM_METODO_CONTRATACION OFF;

SET IDENTITY_INSERT dbo.DIM_CATEGORIA ON;
INSERT INTO dbo.DIM_CATEGORIA (SK_Categoria, CodigoCPC, DescripcionCategoria, GrupoCategoria)
VALUES (-1, 'DESCONOCIDO', N'Desconocido', N'Desconocido');
SET IDENTITY_INSERT dbo.DIM_CATEGORIA OFF;
GO

/* ---------- DIM_TIEMPO: calendario completo 2022-01-01 a 2026-12-31 ----------
   Se genera una sola vez aquí (no depende de los datos), así Power BI tiene
   todos los días para las funciones de inteligencia de tiempo (YTD, YoY). */
SET DATEFIRST 1;
WITH dias AS (
    SELECT CAST('2022-01-01' AS DATE) AS Fecha
    UNION ALL
    SELECT DATEADD(DAY, 1, Fecha) FROM dias WHERE Fecha < '2026-12-31'
)
INSERT INTO dbo.DIM_TIEMPO (SK_Tiempo, Fecha, Anio, Trimestre, Mes, NombreMes, DiaSemana, EsQ4)
SELECT
    YEAR(Fecha) * 10000 + MONTH(Fecha) * 100 + DAY(Fecha),
    Fecha,
    YEAR(Fecha),
    DATEPART(QUARTER, Fecha),
    MONTH(Fecha),
    CHOOSE(MONTH(Fecha), 'Enero','Febrero','Marzo','Abril','Mayo','Junio',
                         'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'),
    DATEPART(WEEKDAY, Fecha),
    CASE WHEN DATEPART(QUARTER, Fecha) = 4 THEN 1 ELSE 0 END
FROM dias
OPTION (MAXRECURSION 0);
GO

/* ==========================================================================
   TABLA DE HECHOS
   ========================================================================== */
CREATE TABLE dbo.FACT_CONTRATOS (
    SK_Contrato        BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_FACT_CONTRATOS PRIMARY KEY,
    FK_Tiempo          INT            NOT NULL CONSTRAINT FK_FACT_Tiempo    REFERENCES dbo.DIM_TIEMPO (SK_Tiempo),
    FK_Proveedor       INT            NOT NULL CONSTRAINT FK_FACT_Proveedor REFERENCES dbo.DIM_PROVEEDOR (SK_Proveedor),
    FK_Entidad         INT            NOT NULL CONSTRAINT FK_FACT_Entidad   REFERENCES dbo.DIM_ENTIDAD (SK_Entidad),
    FK_Metodo          INT            NOT NULL CONSTRAINT FK_FACT_Metodo    REFERENCES dbo.DIM_METODO_CONTRATACION (SK_Metodo),
    FK_Categoria       INT            NOT NULL CONSTRAINT FK_FACT_Categoria REFERENCES dbo.DIM_CATEGORIA (SK_Categoria),
    ID_Proceso         VARCHAR(100)   NOT NULL,   -- ocid
    ID_Adjudicacion    VARCHAR(100)   NOT NULL,   -- awards.id
    FechaAdjudicacion  DATE           NOT NULL,   -- columna de la marca de agua
    MontoAdjudicado    DECIMAL(18,2)  NOT NULL,
    MontoContrato      DECIMAL(18,2)  NULL,
    NumOfertas         INT            NULL,
    DiasAdjudicacion   INT            NULL,
    FechaCargaETL      DATETIME       NOT NULL CONSTRAINT DF_FACT_FechaCarga DEFAULT (GETDATE()),
    CONSTRAINT UQ_FACT_Proceso_Adjudicacion UNIQUE (ID_Proceso, ID_Adjudicacion)
);

CREATE INDEX IX_FACT_Tiempo     ON dbo.FACT_CONTRATOS (FK_Tiempo)    INCLUDE (MontoAdjudicado);
CREATE INDEX IX_FACT_Proveedor  ON dbo.FACT_CONTRATOS (FK_Proveedor) INCLUDE (MontoAdjudicado);
CREATE INDEX IX_FACT_Metodo     ON dbo.FACT_CONTRATOS (FK_Metodo)    INCLUDE (MontoAdjudicado);
CREATE INDEX IX_FACT_FechaAdj   ON dbo.FACT_CONTRATOS (FechaAdjudicacion);
GO

/* ==========================================================================
   TABLAS DE PASO (schema stg) — las llena etl_load.py en cada ejecución
   ========================================================================== */
CREATE TABLE stg.DIM_PROVEEDOR (
    RUC VARCHAR(20) NOT NULL, RazonSocial_Anonimizada NVARCHAR(300) NOT NULL,
    Provincia NVARCHAR(100) NULL, ActividadEconomica_CIIU NVARCHAR(400) NULL,
    TipoContribuyente NVARCHAR(100) NULL, FechaInicioActividades DATE NULL
);
CREATE TABLE stg.DIM_ENTIDAD (
    CodigoEntidad VARCHAR(100) NOT NULL, NombreEntidad NVARCHAR(300) NOT NULL,
    NivelGobierno NVARCHAR(60) NULL, Sector NVARCHAR(60) NULL, Provincia NVARCHAR(100) NULL
);
CREATE TABLE stg.DIM_METODO_CONTRATACION (
    CodigoMetodo NVARCHAR(100) NOT NULL, DescripcionMetodo NVARCHAR(200) NOT NULL,
    CategoriaMetodo NVARCHAR(60) NULL, EsCompetitivo BIT NULL
);
CREATE TABLE stg.DIM_CATEGORIA (
    CodigoCPC VARCHAR(30) NOT NULL, DescripcionCategoria NVARCHAR(400) NOT NULL,
    GrupoCategoria NVARCHAR(100) NULL
);
CREATE TABLE stg.FACT_CONTRATOS (
    ID_Proceso VARCHAR(100) NULL, ID_Adjudicacion VARCHAR(100) NULL, FechaAdjudicacion DATE NULL,
    RUC VARCHAR(20) NULL, CodigoEntidad VARCHAR(100) NULL, CodigoMetodo NVARCHAR(100) NULL,
    CodigoCPC VARCHAR(30) NULL, MontoAdjudicado DECIMAL(18,2) NULL, MontoContrato DECIMAL(18,2) NULL,
    NumOfertas INT NULL, DiasAdjudicacion INT NULL
);
GO

PRINT 'DM_ComprasPublicas creado. Siguiente paso: ejecutar etl_watermark.sql';
