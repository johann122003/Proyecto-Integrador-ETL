# Proyecto Integrador de Business Intelligence (2022–2026)
## Transparencia en Compras Públicas (SERCOP) y Análisis Tributario (SRI)

Bienvenido al repositorio oficial del **Proyecto Integrador de Business Intelligence**. Este proyecto implementa una solución *end-to-end* de ingeniería de datos y analítica empresarial: desde la extracción masiva en streaming de datos abiertos gubernamentales en formato OCDS, su transformación, limpieza y anonimización ética, hasta el modelado dimensional en SQL Server mediante carga incremental transaccional y la visualización analítica de alto impacto en Microsoft Power BI.

---

## 🗺️ Guía de Estructura del Repositorio (Mapa para Evaluación)

Para facilitar la navegación y revisión por parte del docente evaluador, el repositorio ha sido estructurado de forma modular y estandarizada:

```text
Proyecto-Integrador-ETL/
│
├── README.md                      # [ESTE ARCHIVO] Guía maestra del proyecto y navegación
├── requirements.txt               # Dependencias de Python (pandas, numpy, pyodbc)
├── .gitignore                     # Configuración de exclusión de datos pesados (>100MB) y binarios
│
├── etl/                           # 🐍 FASE ETL (PYTHON) — Extracción, Transformación y Carga
│   ├── config.py                  # Configuración centralizada de rutas dinámicas, conexión y reglas
│   ├── etl_extract.py             # Extracción streaming línea a línea de JSONL (SERCOP) y CSV (SRI)
│   ├── etl_transform.py           # Limpieza, anonimización ética SHA-256 y cruce por RUC
│   ├── etl_load.py                # Carga de dimensiones (upsert) y hechos incremental (watermark)
│   └── README.md                  # Documentación detallada del pipeline de ingeniería de datos
│
├── sql/                           # 🗄️ MODELADO DIMENSIONAL Y BASE DE DATOS (SQL SERVER)
│   ├── ddl_datamart.sql           # [1] DDL: BD DM_ComprasPublicas, esquema estrella y calendario
│   ├── etl_watermark.sql          # [2] Control incremental: marcas de agua, log y stored procedures
│   ├── queries_validacion.sql     # [3] 10 consultas de control de calidad, integridad y no-huérfanos
│   ├── generar_backup.sql         # [4] Script para generar y verificar el archivo .bak
│   └── README.md                  # Explicación técnica de cada script SQL y orden de ejecución
│
├── powerbi/                       # 📊 VISUALIZACIÓN Y BUSINESS INTELLIGENCE (POWER BI)
│   ├── DASHBOARD_CONTRATACION.pbix# Tablero analítico interactivo con medidas DAX avanzadas
│   └── README.md                  # Ficha técnica del dashboard, KPIs, páginas y fórmulas DAX
│
├── docs/                          # 📑 DOCUMENTACIÓN, INFORME Y PRESENTACIÓN
│   ├── S8 Proyecto Integrador - Entrega parcial.pdf    # Informe escrito y memoria técnica del proyecto
│   ├── Presentación - Proyecto Integrador BI 2022-2026.pdf # Diapositivas oficiales para la defensa
│   ├── capturas/                  # 9 capturas de evidencia de ejecución, logs y consultas en SSMS
│   └── README.md                  # Índice y descripción de los documentos y evidencias
│
├── data_staging/                  # 📂 DATOS PROCESADOS (CAPA DE STAGING)
│   ├── README.md                  # Diccionario de datos, volúmenes de las tablas y fuentes oficiales
│   └── samples/                   # Muestras representativas (~100 filas) para inspección inmediata
│       ├── stg_procesos_sample.csv
│       ├── stg_adjudicaciones_sample.csv
│       ├── stg_contratos_sample.csv
│       ├── stg_parties_sample.csv
│       ├── stg_proveedores_ruc_sample.csv
│       └── stg_recaudacion_sample.csv
│
└── backup/                        # 💾 RESPALDO FÍSICO DE BASE DE DATOS (.BAK)
    ├── README.md                  # Instrucciones para restaurar DM_ComprasPublicas.bak en SSMS
    └── DM_ComprasPublicas.bak     # Respaldo completo de la BD (~250 MB, ignorado por Git por tamaño)
```

---

## 🔍 Descripción de Componentes Clave

### 1. Scripts de SQL (`sql/`) — ¿A qué corresponde cada uno?

| Script | Orden | ¿A qué corresponde y qué hace? |
|---|:---:|---|
| **`ddl_datamart.sql`** | 1 | **Definición de Esquema Estrella:** Crea la base de datos `DM_ComprasPublicas`, los esquemas `stg` y `etl`, las 5 dimensiones (`DIM_TIEMPO`, `DIM_PROVEEDOR`, `DIM_ENTIDAD`, `DIM_METODO_CONTRATACION`, `DIM_CATEGORIA`), la tabla de hechos central `FACT_CONTRATOS` (grano: 1 contrato adjudicado) y genera el calendario completo 2022–2026 en `DIM_TIEMPO`. |
| **`etl_watermark.sql`** | 2 | **Lógica de Carga Incremental:** Crea la tabla de control `ETL_Watermark`, la bitácora `ETL_Log` y los procedimientos almacenados transaccionales `usp_CargarFactContratos` (append idempotente con resolución de claves foráneas) y `usp_ReiniciarCarga` (para reiniciar demostraciones en vivo). |
| **`queries_validacion.sql`** | 3 | **Auditoría y Control de Calidad:** Contiene 10 consultas SQL (Sección 2.4 del informe) para certificar ante el docente que la base de datos no tiene hechos huérfanos (0 filas), no tiene duplicados en el grano, y que las marcas de agua son consistentes. |
| **`generar_backup.sql`** | 4 | **Respaldo y Portabilidad:** Comando para generar el backup físico con `CHECKSUM` y verificar su integridad con `RESTORE VERIFYONLY`, facilitando su portabilidad. |

*Para más detalles, consultar [sql/README.md](sql/README.md).*

---

### 2. Pipeline ETL en Python (`etl/`)

El pipeline resuelve la ingesta de fuentes heterogéneas y masivas:
- **`config.py`:** Configuración compartida con rutas relativas inteligentes, detección automática de datos, credenciales de conexión ODBC y diccionarios de normalización.
- **`etl_extract.py`:** Extracción en **streaming línea por línea** de archivos JSONL del SERCOP (Open Contracting Data Standard - OCDS) para evitar desbordamiento de memoria RAM, junto con la lectura optimizada de catastros de RUC del SRI.
- **`etl_transform.py`:** Estandarización de métodos de contratación, cruce relacional entre compradores y proveedores, y **anonimización ética con SHA-256** para personas naturales.
- **`etl_load.py`:** Carga dimensional mediante **upsert (MERGE - SCD Tipo 1)** para preservar claves sustitutas (`SK`), y carga de hechos incremental gobernada por marca de agua con registro simultáneo en `dbo.ETL_Log` y en disco.

*Para más detalles y modos de ejecución, consultar [etl/README.md](etl/README.md).*

---

### 3. Modelo y Dashboard en Power BI (`powerbi/`)

- Archivo: **`DASHBOARD_CONTRATACION.pbix`**
- Conectado en **Modo Import** al DataMart `DM_ComprasPublicas`.
- Incluye más de 7 medidas DAX avanzadas (Índice de Concentración Herfindahl-Hirschman HHI, Pareto Top 10 Proveedores, % de Gasto en Q4 vs Total Anual, Crecimiento Interanual YoY, Acumulado YTD y Ratio de Métodos No Competitivos).
- Visuales con diseño estructurado: Resumen Gerencial, Concentración y Riesgo de Mercado, y Detalle Institucional (Drill-through).

*Para más detalles, consultar [powerbi/README.md](powerbi/README.md).*

---

### 4. Documentación y Entregables (`docs/`)

- **`S8 Proyecto Integrador - Entrega parcial.pdf`:** Documento formal consolidado que contiene la justificación teórica, marco metodológico, diccionario de datos, DER, estadísticas de limpieza y conclusiones.
- **`Presentación - Proyecto Integrador BI 2022-2026.pdf`:** Diapositivas preparadas para la defensa oral del proyecto.
- **`capturas/`:** 9 capturas fotográficas que evidencian la ejecución paso a paso de los scripts y las consultas de validación en SQL Server.

---

### 5. Datos y Zona de Staging (`data_staging/`)

- El procesamiento completo genera 6 archivos CSV con un volumen aproximado de **2.85 GB** (~6.8 millones de filas consolidadas).
- **Por qué no se suben completos a GitHub:** GitHub restringe estrictamente cualquier archivo superior a **100 MB** (archivos como `stg_proveedores_ruc.csv` pesan 1.32 GB y `stg_parties.csv` pesa 781 MB). Subirlos provocaría el bloqueo inmediato del `git push`.
- **Solución implementada:** Se proporciona la carpeta **`data_staging/samples/`** con muestras reales de 100 filas de cada tabla para evaluación inmediata. Para generar los archivos completos, basta con ejecutar `python etl/etl_transform.py` disponiendo de las fuentes en `data_raw/`.

---

## 🚀 Guía Rápida de Reproducción para el Docente

Siga estos pasos para replicar o evaluar el proyecto desde cero:

### 1. Clonar el repositorio e instalar dependencias
```bash
git clone https://github.com/johann122003/Proyecto-Integrador-ETL.git
cd Proyecto-Integrador-ETL
pip install -r requirements.txt
```

### 2. Configurar la Base de Datos en SQL Server (SSMS)
1. Abrir **SQL Server Management Studio (SSMS)** y conectarse a `localhost`.
2. Abrir y ejecutar **`sql/ddl_datamart.sql`** (crea la base `DM_ComprasPublicas`, tablas y calendario).
3. Abrir y ejecutar **`sql/etl_watermark.sql`** (crea tablas de control y procedimientos almacenados).

### 3. Ejecutar la Carga Incremental (Python)
Desde la raíz del repositorio, ejecute la demo en 3 etapas:
```bash
# Carga inicial 2022-2023
python etl/etl_load.py --hasta 2023-12-31

# Carga incremental 2024
python etl/etl_load.py --hasta 2024-12-31

# Carga incremental 2025-2026
python etl/etl_load.py
```

### 4. Validar Consistencia en SSMS
Abrir y ejecutar **`sql/queries_validacion.sql`** en SSMS para comprobar:
- Conteos anuales consistentes.
- **0 hechos huérfanos** en todas las dimensiones.
- **0 duplicados** en la tabla de hechos.

### 5. Explorar en Power BI
Abrir **`powerbi/DASHBOARD_CONTRATACION.pbix`** en Power BI Desktop para interactuar con los tableros analíticos y segmentadores.

---

## 👥 Integrantes y Asignación de Roles

| Rol | Responsabilidad Central |
|---|---|
| **P1 — Analista de Negocio / PM** | Planteamiento del problema, hipótesis, compilación del informe técnico, presentación y conclusiones. |
| **P2 — Ingeniero de Datos (ETL - Extracción y Transformación)** | Extracción streaming OCDS, limpieza, anonimización SHA-256 y generación de tablas staging. |
| **P3 — Ingeniero de Datos (Modelado y Carga Incremental)** | Diseño dimensional en estrella, scripts DDL, lógica transaccional de marcas de agua y carga en SQL Server. |
| **P4 — Analista BI / Visualización** | Modelado semántico en Power BI, diseño de medidas DAX complejas, tableros analíticos y análisis de resultados. |

---

## 📚 Fuentes de Información Oficiales

1. **SERCOP — Servicio Nacional de Contratación Pública del Ecuador (OCDS 2022–2026)**  
   Open Contracting Partnership. *Publicación 110 Ecuador*. [https://data.open-contracting.org/es/publication/110#access](https://data.open-contracting.org/es/publication/110#access)
2. **SRI — Catastro del Registro Único de Contribuyentes (Pichincha y Guayas)**  
   Servicio de Rentas Internas. *Portal Nacional de Datos Abiertos del Ecuador*. [https://www.datosabiertos.gob.ec/](https://www.datosabiertos.gob.ec/)
3. **SRI — Recaudación Tributaria 2024**  
   Servicio de Rentas Internas. *Recaudación de impuestos 2024*. [https://www.datosabiertos.gob.ec/dataset/recaudacion-de-impuestos-2024](https://www.datosabiertos.gob.ec/dataset/recaudacion-de-impuestos-2024)
