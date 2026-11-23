# Módulo de Ingeniería de Datos y Pipeline ETL (Python)

Este módulo implementa el pipeline integral de extracción, transformación, anonimización ética y carga incremental de datos abiertos de contratación pública (SERCOP - Estándar OCDS 2022–2026) e información tributaria (SRI) hacia SQL Server (Roles **P2: Extracción y Transformación** y **P3: Modelado y Carga**).

---

## 🏗️ Arquitectura de Scripts en `etl/`

```text
etl/
├── config.py           # Configuración unificada de rutas, conexión SQL Server, mapeos y reglas de negocio
├── etl_extract.py      # Extracción streaming línea a línea de JSONL (SERCOP) y lectura optimizada de CSV (SRI)
├── etl_transform.py    # Limpieza, anonimización ética SHA-256, validación temporal y cruce de datos
├── etl_load.py         # Carga dimensional (upsert/MERGE) y carga incremental transaccional con marca de agua
└── logs/               # Registro detallado de cada corrida del ETL (creado automáticamente)
```

---

## ⚙️ Configuración (`config.py`)

El archivo `config.py` centraliza de forma transparente:
1. **Detección inteligente de directorios:** Localiza automáticamente la carpeta `data_staging/` (ya sea en la raíz del repositorio o en la carpeta superior de trabajo) y `data_raw/`.
2. **Conexión a SQL Server:** Configuración del driver ODBC (`ODBC Driver 17 for SQL Server` o `18`), servidor (`localhost`), base de datos (`DM_ComprasPublicas`) y autenticación de Windows (`trusted_connection = True`).
3. **Mapeo de atributos:** Diccionario semántico que vincula los nombres de columnas de los CSV limpios con las columnas del modelo relacional.
4. **Reglas de clasificación:**
   - Normalización de métodos de contratación pública y detección del flag `EsCompetitivo`.
   - Inferencia del nivel de gobierno de la entidad compradora (GAD, Central, EP, Universidad, Hospital).
   - Clasificación por secciones del Clasificador Central de Productos (CPC).
5. **Políticas de anonimización:** Parámetros para la protección de identidad de proveedores personas naturales mediante hash SHA-256 truncado con sal.

---

## 🚀 Flujo de Ejecución del Pipeline

### Paso 1: Instalación de Dependencias
```bash
pip install -r requirements.txt
```
*(Requiere `pandas`, `numpy`, `pyodbc` y el ODBC Driver de Microsoft SQL Server instalado en el sistema).*

---

### Paso 2: Extracción y Transformación (Fase P2)
Genera los 6 archivos intermedios en `data_staging/`:
```bash
# Ejecutar el flujo completo de extracción y transformación
python etl/etl_transform.py
```
*Nota: Si se cuenta con los archivos crudos en `data_raw/`, este comando lee los JSONL en streaming para no saturar memoria RAM, aplica las transformaciones y genera las tablas de staging.*

---

### Paso 3: Carga hacia SQL Server (Fase P3)

El script `etl_load.py` incluye múltiples modos de ejecución:

#### 1. Verificación previa de columnas (sin tocar la base):
```bash
python etl/etl_load.py --revisar
```
Valida que todas las columnas requeridas por el DataMart existan en los CSV de `data_staging/`.

#### 2. Simulación en memoria (prueba sin conexión a SQL Server):
```bash
python etl/etl_load.py --sin-bd
```
Ejecuta la preparación lógica en memoria, mostrando conteos y validaciones de calidad sin escribir en base de datos.

#### 3. Demostración de Carga Incremental (Demo en 3 pasos para defensa):
```bash
# Carga 1: Procesa el histórico inicial (2022 a 2023)
python etl/etl_load.py --hasta 2023-12-31

# Carga 2: Carga incremental de 2024 (solo se insertan registros nuevos; la marca avanza)
python etl/etl_load.py --hasta 2024-12-31

# Carga 3: Carga incremental del resto disponible (2025-2026)
python etl/etl_load.py

# Prueba de Idempotencia: Ejecutar de nuevo (debe reportar 0 filas nuevas y 0 duplicados)
python etl/etl_load.py
```

#### 4. Reinicio de la Demostración:
Para vaciar la tabla de hechos y regresar la marca de agua al inicio para una nueva prueba:
```bash
python etl/etl_load.py --reiniciar
```

---

## 🛡️ Principios Técnicos Implementados

1. **Streaming y Chunking:** Extracción de fuentes masivas SERCOP línea a línea y lectura por bloques (`chunksize = 500,000`) para manejar archivos de más de 1 GB con consumo controlado de memoria RAM.
2. **Dimensiones con MERGE (SCD Tipo 1):** Las dimensiones se actualizan sin destruir las claves sustitutas (`SK`), garantizando que las referencias históricas en la tabla de hechos permanezcan intactas.
3. **Doble Barrera contra Duplicados:** Filtro por fecha de adjudicación en Python y comprobación `NOT EXISTS` en el procedimiento almacenado de SQL Server dentro de una transacción `XACT_ABORT`.
4. **Trazabilidad y Auditoría:** Toda corrida escribe simultáneamente en la consola, genera un log en `etl/logs/` y registra una fila en la tabla relacional `dbo.ETL_Log`.
