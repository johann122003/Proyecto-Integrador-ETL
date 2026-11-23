/* ==========================================================================
   queries_validacion.sql — Verificación de la población del DataMart
   DM_ComprasPublicas — rol P3 (sección 2.4 del documento)

   Ejecutar después de cada carga y capturar los resultados para el informe.
   Resultado esperado en las pruebas 2 a 5: 0 filas o conteo 0.
   ========================================================================== */
USE DM_ComprasPublicas;
GO

/* ---------- 1. Conteo y monto por año ---------- */
SELECT  YEAR(f.FechaAdjudicacion)      AS Anio,
        COUNT(*)                       AS Contratos,
        SUM(f.MontoAdjudicado)         AS MontoAdjudicado,
        SUM(f.MontoContrato)           AS MontoContratado
FROM dbo.FACT_CONTRATOS f
GROUP BY YEAR(f.FechaAdjudicacion)
ORDER BY Anio;

/* ---------- 2. Integridad referencial: hechos huérfanos por dimensión ----------
   Las FK de SQL Server ya lo impiden; esta consulta lo demuestra. */
SELECT 'DIM_TIEMPO' AS Dimension, COUNT(*) AS Huerfanos
FROM dbo.FACT_CONTRATOS f LEFT JOIN dbo.DIM_TIEMPO t ON f.FK_Tiempo = t.SK_Tiempo
WHERE t.SK_Tiempo IS NULL
UNION ALL
SELECT 'DIM_PROVEEDOR', COUNT(*)
FROM dbo.FACT_CONTRATOS f LEFT JOIN dbo.DIM_PROVEEDOR p ON f.FK_Proveedor = p.SK_Proveedor
WHERE p.SK_Proveedor IS NULL
UNION ALL
SELECT 'DIM_ENTIDAD', COUNT(*)
FROM dbo.FACT_CONTRATOS f LEFT JOIN dbo.DIM_ENTIDAD e ON f.FK_Entidad = e.SK_Entidad
WHERE e.SK_Entidad IS NULL
UNION ALL
SELECT 'DIM_METODO_CONTRATACION', COUNT(*)
FROM dbo.FACT_CONTRATOS f LEFT JOIN dbo.DIM_METODO_CONTRATACION m ON f.FK_Metodo = m.SK_Metodo
WHERE m.SK_Metodo IS NULL
UNION ALL
SELECT 'DIM_CATEGORIA', COUNT(*)
FROM dbo.FACT_CONTRATOS f LEFT JOIN dbo.DIM_CATEGORIA c ON f.FK_Categoria = c.SK_Categoria
WHERE c.SK_Categoria IS NULL;

/* ---------- 3. Duplicados en el hecho (grano: proceso + adjudicación) ---------- */
SELECT ID_Proceso, ID_Adjudicacion, COUNT(*) AS Veces
FROM dbo.FACT_CONTRATOS
GROUP BY ID_Proceso, ID_Adjudicacion
HAVING COUNT(*) > 1;

/* ---------- 4. Duplicados en las llaves de negocio de las dimensiones ---------- */
SELECT 'DIM_PROVEEDOR' AS Dimension, RUC AS Llave, COUNT(*) AS Veces
FROM dbo.DIM_PROVEEDOR GROUP BY RUC HAVING COUNT(*) > 1
UNION ALL
SELECT 'DIM_ENTIDAD', CodigoEntidad, COUNT(*)
FROM dbo.DIM_ENTIDAD GROUP BY CodigoEntidad HAVING COUNT(*) > 1;

/* ---------- 5. Coherencia de la marca de agua ----------
   La FechaCorte debe ser igual a la mayor fecha cargada. */
SELECT w.FechaCorte,
       (SELECT MAX(FechaAdjudicacion) FROM dbo.FACT_CONTRATOS) AS MaxFechaEnHechos,
       CASE WHEN CAST(w.FechaCorte AS DATE) =
                 (SELECT MAX(FechaAdjudicacion) FROM dbo.FACT_CONTRATOS)
            THEN 'OK' ELSE 'REVISAR' END AS Estado
FROM dbo.ETL_Watermark w
WHERE w.Tabla = 'FACT_CONTRATOS';

/* ---------- 6. Calidad: hechos asignados al miembro "Desconocido" (-1) ----------
   No es un error, pero hay que reportar el porcentaje en el informe. */
SELECT  SUM(CASE WHEN FK_Proveedor = -1 THEN 1 ELSE 0 END) AS SinProveedor,
        SUM(CASE WHEN FK_Entidad   = -1 THEN 1 ELSE 0 END) AS SinEntidad,
        SUM(CASE WHEN FK_Metodo    = -1 THEN 1 ELSE 0 END) AS SinMetodo,
        SUM(CASE WHEN FK_Categoria = -1 THEN 1 ELSE 0 END) AS SinCategoria,
        COUNT(*)                                           AS Total,
        CAST(100.0 * SUM(CASE WHEN FK_Proveedor = -1 THEN 1 ELSE 0 END)
             / NULLIF(COUNT(*), 0) AS DECIMAL(5,2))        AS PctSinProveedor
FROM dbo.FACT_CONTRATOS;

/* ---------- 7. Montos fuera de rango ---------- */
SELECT  SUM(CASE WHEN MontoAdjudicado < 0  THEN 1 ELSE 0 END) AS MontosNegativos,
        SUM(CASE WHEN MontoAdjudicado = 0  THEN 1 ELSE 0 END) AS MontosCero,
        SUM(CASE WHEN DiasAdjudicacion < 0 THEN 1 ELSE 0 END) AS DiasNegativos
FROM dbo.FACT_CONTRATOS;

/* ---------- 8. Resumen por tabla (tabla resumen del informe) ---------- */
SELECT 'FACT_CONTRATOS'          AS Tabla, COUNT(*) AS Filas FROM dbo.FACT_CONTRATOS
UNION ALL SELECT 'DIM_TIEMPO',              COUNT(*) FROM dbo.DIM_TIEMPO
UNION ALL SELECT 'DIM_PROVEEDOR',           COUNT(*) FROM dbo.DIM_PROVEEDOR
UNION ALL SELECT 'DIM_ENTIDAD',             COUNT(*) FROM dbo.DIM_ENTIDAD
UNION ALL SELECT 'DIM_METODO_CONTRATACION', COUNT(*) FROM dbo.DIM_METODO_CONTRATACION
UNION ALL SELECT 'DIM_CATEGORIA',           COUNT(*) FROM dbo.DIM_CATEGORIA;

/* ---------- 9. Historial de cargas incrementales (demo) ---------- */
SELECT ID_Ejecucion, Inicio, RegistrosStaging, RegistrosInsertados, RegistrosOmitidos,
       WatermarkAnterior, WatermarkNuevo
FROM dbo.ETL_Log
ORDER BY ID_Ejecucion;

/* ---------- 10. Distribución por método (sanity check de la hipótesis) ---------- */
SELECT m.CategoriaMetodo, m.EsCompetitivo, COUNT(*) AS Contratos, SUM(f.MontoAdjudicado) AS Monto
FROM dbo.FACT_CONTRATOS f
JOIN dbo.DIM_METODO_CONTRATACION m ON m.SK_Metodo = f.FK_Metodo
GROUP BY m.CategoriaMetodo, m.EsCompetitivo
ORDER BY Monto DESC;
