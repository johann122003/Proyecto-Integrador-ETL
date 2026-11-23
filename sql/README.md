# Módulo de Base de Datos y Modelado Dimensional (SQL Server)

Este directorio contiene los scripts DDL, lógica transaccional de carga incremental, procedimientos de auditoría y validación de calidad de datos correspondientes a la base de datos relacional y DataMart dimensional **`DM_ComprasPublicas`** en **Microsoft SQL Server** (Rol **P3: Ingeniero de Datos — Modelado y Carga**).

---

## 📋 Guía Rápida de Scripts SQL

| Archivo | Fase / Rol | Propósito Central |
|---|---|---|
| **`ddl_datamart.sql`** | 1. DDL y Estructura | Crea la BD `DM_ComprasPublicas`, esquemas `stg` y `etl`, dimensiones del esquema estrella, tabla de hechos `FACT_CONTRATOS` y calendario inteligente en `DIM_TIEMPO`. |
| **`etl_watermark.sql`** | 2. Carga Incremental | Crea la tabla de control `ETL_Watermark`, bitácora de auditoría `ETL_Log` y los stored procedures de append idempotente (`usp_CargarFactContratos`) y reinicio (`usp_ReiniciarCarga`). |
| **`queries_validacion.sql`** | 3. Auditoría y Calidad | 10 consultas de control (Sección 2.4 del informe) para verificar integridad referencial (huérfanos), conteos por año, no duplicados en el grano y coherencia de marcas de agua. |
| **`generar_backup.sql`** | 4. Respaldo y Restauración | Genera el respaldo físico `.bak` con checksum y verificación de integridad (`RESTORE VERIFYONLY`), e incluye instrucciones de restauración. |

---

## 🚀 Orden Estricto de Ejecución en SQL Server Management Studio (SSMS)

```
[1] ddl_datamart.sql
       ↓ (crea base, esquemas, dimensiones, hechos y calendario)
[2] etl_watermark.sql
       ↓ (crea tablas de control, marcas de agua y procedimientos almacenados)
[3] Ejecución del pipeline de carga en Python: python etl/etl_load.py
       ↓ (popula dimensiones y hace append incremental a los hechos)
[4] queries_validacion.sql
       ↓ (auditoría de integridad, conteos y consistencia)
[5] generar_backup.sql
         (genera backup/DM_ComprasPublicas.bak para distribución)
```

---

## 🔍 Explicación Detallada de Cada Script

### 1. `ddl_datamart.sql` — Creación de Esquema Estrella y Staging
- **A qué corresponde:** Corresponde al diseño del DataMart dimensional (Sección 2.1 y 2.2 del informe del proyecto).
- **Esquema implementado:** Esquema Estrella (*Star Schema*) optimizado para análisis analítico OLAP y consumo en Power BI.
- **Grano de la tabla de hechos:** Un contrato adjudicado (llave de negocio compuesta `ID_Proceso + ID_Adjudicacion`).
- **Componentes creados:**
  - **Esquemas:** `dbo` (modelo dimensional estrella), `stg` (tablas de paso staging para recepción de lotes de Python), `etl` (procedimientos de control).
  - **`dbo.DIM_TIEMPO`:** Dimensión conformada con llave inteligente `SK_Tiempo` formato `AAAAMMDD`. Incluye atributos temporales: Año, Trimestre, Mes, Nombre de Mes, Día de la Semana y el flag booleano `EsQ4` (esencial para probar la hipótesis de concentración de compras a fin de año). Se puebla automáticamente mediante un CTE recursivo para el periodo completo 2022–2026.
  - **`dbo.DIM_PROVEEDOR`:** Almacena proveedores con RUC, razón social, provincia, actividad económica CIIU y tipo de contribuyente. En cumplimiento de normativas éticas de protección de datos personales, los proveedores personas naturales se registran anonimizados (`PERSONA NATURAL <hash>` y RUC `PN-<hash>`).
  - **`dbo.DIM_ENTIDAD`:** Registra las entidades compradoras públicas del Ecuador, su código de entidad, nombre institucional, provincia y categorización por nivel de gobierno (Gobierno Central, GAD Local, Empresa Pública, Universidad, Hospital, Seguridad Social).
  - **`dbo.DIM_METODO_CONTRATACION`:** Clasifica los procedimientos de contratación en categorías homologadas (Emergencia, Ínfima Cuantía, Régimen Especial, Subasta Inversa, Licitación, Cotización, etc.) e incluye el indicador booleano `EsCompetitivo`.
  - **`dbo.DIM_CATEGORIA`:** Agrupa productos y servicios según el Clasificador Central de Productos (CPC v2 de la ONU) y su sección sectorial.
  - **Miembro Desconocido (`SK = -1`):** Cada dimensión posee una fila especial con clave sustituta `-1` (*Desconocido / No asignado*) para garantizar que ningún contrato quede huérfano ante inconsistencias en fuentes abiertas.
  - **`dbo.FACT_CONTRATOS`:** Tabla de hechos central con claves foráneas a las 5 dimensiones y métricas operativas: `MontoAdjudicado`, `MontoContrato`, `NumeroOfertas`, `DiasDesdePublicacion` y `TieneContratoFirmado`.

### 2. `etl_watermark.sql` — Lógica de Carga Incremental y Auditoría
- **A qué corresponde:** Corresponde a la sección 2.3 del informe (mecanismo de carga incremental, idempotencia y auditoría de datos).
- **Componentes creados:**
  - **`dbo.ETL_Watermark`:** Tabla de control que guarda el corte temporal (`FechaCorte`) y fecha de última ejecución. Se inicializa en `'1900-01-01'` para la carga histórica inicial.
  - **`dbo.ETL_Log`:** Tabla de bitácora que registra métricas de cada corrida: fecha/hora de inicio y fin, registros procesados en staging, registros nuevos insertados en hechos, registros omitidos por duplicidad o corte temporal, y el avance de la marca de agua.
  - **`etl.usp_CargarFactContratos`:** Procedimiento almacenado que realiza el `APPEND` incremental de la tabla de hechos desde `stg.FACT_CONTRATOS`. Resuelve llaves foráneas mediante *lookup* a dimensiones (asignando `-1` si no existe), filtra transaccionalmente con `NOT EXISTS` y `FechaAdjudicacion > FechaCorte` para evitar duplicados, e incrementa la marca de agua.
  - **`etl.usp_ReiniciarCarga`:** Procedimiento utilitario para vaciar `dbo.FACT_CONTRATOS` y reiniciar la marca de agua a `'1900-01-01'`, permitiendo repetir la demostración de incrementalidad paso a paso.

### 3. `queries_validacion.sql` — Verificación de Integridad y Calidad
- **A qué corresponde:** Corresponde a la sección 2.4 del informe (*Población del DataMart y Pruebas de Calidad*).
- **Pruebas contenidas:**
  1. Conteo de contratos y suma acumulada de montos adjudicados y contratados por año (2022–2026).
  2. Integridad referencial: Comprobación de que no existan hechos huérfanos sin correspondencia en las 5 dimensiones (resultado esperado: 0 filas).
  3. Detección de duplicados a nivel de grano (`ID_Proceso + ID_Adjudicacion`) (resultado esperado: 0 filas).
  4. Detección de duplicados en llaves de negocio en dimensiones (`RUC`, `CodigoEntidad`) (resultado esperado: 0 filas).
  5. Coherencia de marca de agua: Valida que `FechaCorte` coincida exactamente con el `MAX(FechaAdjudicacion)` de `FACT_CONTRATOS`.
  6. Proporción de hechos vinculados al miembro `SK = -1`.
  7. Auditoría de ejecuciones en `dbo.ETL_Log`.
  8. Detección de valores anómalos (montos nulos, negativos o incongruentes).
  9. Consistencia lógica de contratos (`TieneContratoFirmado` vs `MontoContrato > 0`).
  10. Conteo global de registros en todas las tablas del modelo.

### 4. `generar_backup.sql` — Respaldo Físico del DataMart
- **A qué corresponde:** Generación del respaldo integral `DM_ComprasPublicas.bak` para portabilidad y entrega.
- **Acciones:**
  - Ejecuta `BACKUP DATABASE DM_ComprasPublicas` con validación `CHECKSUM` y encabezado `INIT, FORMAT`.
  - Ejecuta `RESTORE VERIFYONLY` para certificar la consistencia del archivo antes de su distribución.
  - Proporciona las directivas documentadas de `RESTORE DATABASE` para desplegar la base en cualquier entorno SQL Server.
