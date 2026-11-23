# Documentación y Entregables del Proyecto Integrador

Este directorio contiene los documentos formales de entrega, diapositivas ejecutivas para defensa y evidencias fotográficas de ejecución del proyecto **Business Intelligence: Transparencia en Compras Públicas del SERCOP y Análisis Tributario SRI (2022–2026)**.

---

## 📄 Documentos Principales

| Archivo | Tipo | Descripción |
|---|---|---|
| **`S8 Proyecto Integrador - Entrega parcial.pdf`** | Documento Técnico / Académico | Informe formal completo que detalla el planteamiento del problema, hipótesis de negocio, preguntas analíticas, arquitectura técnica, diseño dimensional, desarrollo del pipeline ETL, pruebas de calidad y análisis de resultados. |
| **`Presentación - Proyecto Integrador BI 2022-2026.pdf`** | Diapositivas de Defensa | Presentación visual estructurada para la sustentación ante el tribunal docente: contexto, arquitectura de datos, demostración del ETL, dashboards en Power BI y conclusiones. |

---

## 📸 Carpeta de Evidencias (`docs/capturas/`)

Contiene 9 capturas de pantalla que respaldan la ejecución verídica del sistema en SQL Server Management Studio (SSMS) y la consola de Python (Sección 2.4 del informe):

- **`captura_1.png` a `captura_3.png`:** Evidencia de ejecución del pipeline de carga incremental en Python (`etl_load.py`), mostrando conteos de registros procesados, tiempos de carga y avance de marcas de agua.
- **`captura_4.png` a `captura_6.png`:** Resultados de las consultas de validación de integridad referencial (`queries_validacion.sql`), certificando la ausencia de hechos huérfanos y duplicados.
- **`captura_7.png` y `captura_8.png`:** Inspección de las tablas de auditoría `dbo.ETL_Watermark` y `dbo.ETL_Log` en SQL Server.
- **`captura_9.png`:** Resumen global de registros cargados y métricas anuales en `dbo.FACT_CONTRATOS`.
