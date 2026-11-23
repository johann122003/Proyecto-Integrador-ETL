# Módulo de Business Intelligence y Visualización (Power BI)

Este directorio contiene el modelo semántico, capa analítica y tableros interactivos desarrollados en **Microsoft Power BI** (Rol **P4: Analista BI / Visualización**) para la toma de decisiones y auditoría del gasto público en el Ecuador.

---

## 📊 Archivo del Modelo

- **`DASHBOARD_CONTRATACION.pbix`** (~11.4 MB)
  - **Modo de Conexión:** *Import Mode* (Carga en memoria VertiPaq para máximo rendimiento analítico y habilitación de funciones de Inteligencia de Tiempo avanzadas).
  - **Origen de Datos:** DataMart `DM_ComprasPublicas` en SQL Server (`localhost`).
  - **Estructura del Modelo:** Esquema en Estrella con 1 tabla de hechos (`FACT_CONTRATOS`) y 5 dimensiones relacionadas con cardinalidad 1 a Muchos (`DIM_TIEMPO`, `DIM_PROVEEDOR`, `DIM_ENTIDAD`, `DIM_METODO_CONTRATACION`, `DIM_CATEGORIA`).

---

## 📈 Páginas del Dashboard

### 1. Página 1 — Resumen Gerencial y Evolución Temporal
- **Objetivo:** Proporcionar una visión macroscópica del volumen de contratación pública nacional (2022–2026).
- **Componentes Visuales:**
  - **Tarjetas de KPIs Gerenciales:** Monto total adjudicado, número de procesos, ahorro potencial y porcentaje de contratación competitiva.
  - **Evolución Temporal:** Gráfico combinado de líneas y columnas que muestra montos adjudicados mensuales y acumulados.
  - **Evaluación de Estacionalidad Q4:** Visualización específica del incremento de gasto en el último trimestre de cada año (validación empírica de la hipótesis de agotamiento presupuestario).
  - **Segmentadores Interactivos:** Filtros cruzados por Año, Trimestre y Nivel de Gobierno.

### 2. Página 2 — Análisis de Concentración y Riesgo de Mercado
- **Objetivo:** Auditar la competencia en compras públicas, concentración de proveedores y recurrencia de métodos no competitivos.
- **Componentes Visuales:**
  - **Curva de Pareto (Top 10 Proveedores):** Visualiza la proporción del monto adjudicado absorbida por los contratistas predominantes.
  - **Índice Herfindahl-Hirschman (HHI):** Medición de la concentración económica por sector y entidad.
  - **Distribución por Método:** Desglose entre métodos competitivos (licitaciones, subastas inversas) frente a no competitivos (emergencias, regímenes especiales, compras directas).
  - **Mapa y Matriz Geográfica:** Distribución provincial del gasto público.

### 3. Página 3 — Detalle Institucional y Drill-Through
- **Objetivo:** Navegación en detalle a nivel de cada entidad contratante y contratista para auditoría puntual de contratos.

---

## 🧮 Medidas DAX Principales Implementadas

1. **Monto Acumulado Anual (YTD):**
   ```dax
   Monto_YTD = TOTALYTD(SUM(FACT_CONTRATOS[MontoAdjudicado]), DIM_TIEMPO[Fecha])
   ```
2. **Crecimiento Interanual (YoY %):**
   ```dax
   Crecimiento_YoY = 
   VAR MontoActual = SUM(FACT_CONTRATOS[MontoAdjudicado])
   VAR MontoAnterior = CALCULATE(SUM(FACT_CONTRATOS[MontoAdjudicado]), SAMEPERIODLASTYEAR(DIM_TIEMPO[Fecha]))
   RETURN DIVIDE(MontoActual - MontoAnterior, MontoAnterior, 0)
   ```
3. **Porcentaje de Gasto en Q4:**
   ```dax
   Porcentaje_Q4 = 
   VAR MontoQ4 = CALCULATE(SUM(FACT_CONTRATOS[MontoAdjudicado]), DIM_TIEMPO[EsQ4] = 1)
   VAR MontoTotal = CALCULATE(SUM(FACT_CONTRATOS[MontoAdjudicado]), ALL(DIM_TIEMPO[Mes]))
   RETURN DIVIDE(MontoQ4, MontoTotal, 0)
   ```
4. **Ratio de Contratación No Competitiva:**
   ```dax
   Ratio_No_Competitivo = 
   VAR MontoNoComp = CALCULATE(SUM(FACT_CONTRATOS[MontoAdjudicado]), DIM_METODO_CONTRATACION[EsCompetitivo] = FALSE)
   RETURN DIVIDE(MontoNoComp, SUM(FACT_CONTRATOS[MontoAdjudicado]), 0)
   ```
5. **Índice HHI de Concentración:**
   Cálculo cuadrático de participaciones de mercado por proveedor para evaluar el nivel de concentración de mercado (mercado diversificado < 1500; moderado 1500–2500; concentrado > 2500).

---

## 🖥️ Cómo Abrir y Actualizar el Archivo

1. Asegurarse de tener instalado **Power BI Desktop** (versión actualizada).
2. Verificar que SQL Server esté ejecutándose localmente con la base `DM_ComprasPublicas` poblada.
3. Abrir `DASHBOARD_CONTRATACION.pbix`.
4. En caso de cambiar el nombre del servidor SQL, ir a **Transformar datos > Configuración de origen de datos** y ajustar el nombre del servidor (ej. `localhost` o `localhost\SQLEXPRESS`).
5. Hacer clic en **Actualizar** (*Refresh*) para recargar todos los visuales.
