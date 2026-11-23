# Datos Procesados y Zona de Staging (`data_staging`)

Este directorio representa la **capa de Staging** del pipeline de Business Intelligence. Contiene las tablas intermedias estandarizadas, limpias y anonimizadas generadas por el script `etl/etl_transform.py` y consumidas por el proceso de carga `etl/etl_load.py` hacia SQL Server.

---

## ⚠️ Política de Almacenamiento y Límites de GitHub

Los archivos procesados completos suman **~2.85 GB** de información transaccional y catastral. Debido a las **políticas de tamaño de GitHub** (límite estricto de **100 MB por archivo** y recomendaciones de repositorio < 1 GB), los archivos `.csv` completos están excluidos del control de versiones mediante `.gitignore`:

| Archivo Staging | Filas Reales | Tamaño Aprox. | Estado en GitHub |
|---|---|---|---|
| **`stg_proveedores_ruc.csv`** | 3,496,177 | **1.32 GB** | Excluido por `.gitignore` (> 100 MB) |
| **`stg_parties.csv`** | 1,756,302 | **781 MB** | Excluido por `.gitignore` (> 100 MB) |
| **`stg_procesos.csv`** | 623,826 | **286 MB** | Excluido por `.gitignore` (> 100 MB) |
| **`stg_adjudicaciones.csv`** | 600,069 | **268 MB** | Excluido por `.gitignore` (> 100 MB) |
| **`stg_recaudacion.csv`** | 665,184 | **94 MB** | Excluido por `.gitignore` (umbral límite) |
| **`stg_contratos.csv`** | 581,875 | **52 MB** | Excluido por `.gitignore` (volumen total) |

---

## 📂 Muestras Incluidas para Evaluación Inmediata (`samples/`)

Para que el docente y evaluadores puedan **inspeccionar de inmediato la estructura, columnas, tipos de datos y transformaciones** sin necesidad de descargar gigabytes de datos, se incluye la subcarpeta **`data_staging/samples/`** con las primeras 100 filas de cada archivo:

- `samples/stg_procesos_sample.csv`
- `samples/stg_adjudicaciones_sample.csv`
- `samples/stg_contratos_sample.csv`
- `samples/stg_parties_sample.csv` (con anonimización SHA-256 aplicada)
- `samples/stg_proveedores_ruc_sample.csv`
- `samples/stg_recaudacion_sample.csv`

---

## 🔄 ¿Cómo generar los datasets completos localmente?

Para reproducir los archivos `.csv` completos de staging desde cero:

1. **Descargar los datos fuente oficiales** y colocarlos en la carpeta `data_raw/` en la raíz del repositorio:
   - **SERCOP (OCDS 2022–2026):** `sercop_2022.jsonl`, `sercop_2023.jsonl`, `sercop_2024.jsonl`, `sercop_2025.jsonl`, `sercop_2026.jsonl`  
     *Fuente:* Open Contracting Partnership — [Publicación 110 Ecuador](https://data.open-contracting.org/es/publication/110#access).
   - **SRI Catastro RUC:** `SRI_RUC_Pichincha.csv`, `SRI_RUC_Guayas.csv`  
     *Fuente:* Portal Nacional de Datos Abiertos del Ecuador — [RUC Guayas](https://www.datosabiertos.gob.ec/dataset/registro-unico-de-contribuyentes-ruc-guayas) y [RUC Pichincha](https://www.datosabiertos.gob.ec/dataset/registro-unico-de-contribuyentes-ruc-pichincha).
   - **SRI Recaudación Fiscal 2024:** `sri_recaudacion_2024.csv`  
     *Fuente:* Portal Nacional de Datos Abiertos del Ecuador — [Recaudación de Impuestos 2024](https://www.datosabiertos.gob.ec/dataset/recaudacion-de-impuestos-2024/resource/a5f27ccb-6d6a-4556-9ffb-90bf6d9964c4).

2. **Ejecutar el script de transformación:**
   ```bash
   python etl/etl_transform.py
   ```
   El script procesará los archivos en streaming, aplicará las reglas de limpieza, anonimizará los datos sensibles y generará automáticamente los 6 archivos CSV en esta carpeta.
