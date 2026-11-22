# Pipeline ETL — Contratación Pública SERCOP y Datos Tributarios SRI

Pipeline desarrollado en Python para la extracción, limpieza, anonimización y transformación de datos abiertos de contratación pública del Ecuador (estándar OCDS, 2022–2026) y registros tributarios del Servicio de Rentas Internas (catastro RUC de Pichincha y Guayas, y recaudación fiscal 2024), dejando las tablas listas para su carga en SQL Server.

---

## Estructura del repositorio

```text
etl_python/
├── config.py           # Rutas centralizadas de entrada (data_raw) y salida (data_staging)
├── etl_extract.py      # Extracción en streaming línea por línea de JSONL (SERCOP) y lectura de CSV (SRI)
├── etl_transform.py    # Limpieza, validación temporal, anonimización SHA-256 y cruce por RUC
├── requirements.txt    # Dependencias de Python (pandas, numpy)
├── .gitignore          # Exclusión de archivos pesados y temporales
└── README.md           # Documentación del pipeline y fuentes de datos
```

---

## Carpetas no incluidas en este repositorio (y cómo generarlas)

Por políticas de tamaño de GitHub (límite de 100 MB por archivo), las carpetas de datos crudos y procesados están excluidas en `.gitignore` y deben crearse localmente antes de ejecutar el pipeline:

1. **`data_raw/` (~5.65 GB — Datos fuente sin procesar):**
   Crea esta carpeta en la raíz del proyecto y coloca dentro los siguientes archivos descargados desde las fuentes oficiales listadas abajo:
   - `sercop_2022.jsonl`
   - `sercop_2023.jsonl`
   - `sercop_2024.jsonl`
   - `sercop_2025.jsonl`
   - `sercop_2026.jsonl`
   - `SRI_RUC_Pichincha.csv`
   - `SRI_RUC_Guayas.csv`
   - `sri_recaudacion_2024.csv`

2. **`data_staging/` (~2.72 GB — Tablas limpias listas para SQL Server):**
   Se genera automáticamente al ejecutar `python etl_transform.py` e incluye los 6 archivos CSV estandarizados:
   - `stg_procesos.csv` (623,826 filas)
   - `stg_adjudicaciones.csv` (600,069 filas)
   - `stg_contratos.csv` (581,875 filas)
   - `stg_parties.csv` (1,756,302 filas — personas naturales anonimizadas con SHA-256)
   - `stg_proveedores_ruc.csv` (3,496,177 filas — padrón único Pichincha + Guayas)
   - `stg_recaudacion.csv` (665,184 filas — recaudación fiscal 2024)

---

## Instalación y ejecución

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Asegurarse de tener los archivos fuente dentro de data_raw/
# 3. Ejecutar el flujo ETL completo
python etl_transform.py
```

---

## Fuentes de datos 

**1. Contratación Pública del Ecuador — SERCOP (Estándar OCDS, 2022–2026)**
Open Contracting Partnership. (s. f.). *Ecuador: Servicio Nacional de Contratación Pública (SERCOP) — Datos OCDS (Publicación 110)* [Conjunto de datos]. Open Contracting Data Registry. https://data.open-contracting.org/es/publication/110#access

**2. Recaudación Fiscal por Impuestos — SRI (2024)**
Servicio de Rentas Internas. (2024). *Recaudación de impuestos 2024* [Conjunto de datos]. Portal Nacional de Datos Abiertos del Ecuador. https://www.datosabiertos.gob.ec/dataset/recaudacion-de-impuestos-2024/resource/a5f27ccb-6d6a-4556-9ffb-90bf6d9964c4

**3. Catastro del Registro Único de Contribuyentes (RUC) — Provincia del Guayas**
Servicio de Rentas Internas. (s. f.). *Registro Único de Contribuyentes (RUC) — Guayas* [Conjunto de datos]. Portal Nacional de Datos Abiertos del Ecuador. https://www.datosabiertos.gob.ec/dataset/registro-unico-de-contribuyentes-ruc-guayas

**4. Catastro del Registro Único de Contribuyentes (RUC) — Provincia de Pichincha**
Servicio de Rentas Internas. (s. f.). *Registro Único de Contribuyentes (RUC) — Pichincha* [Conjunto de datos]. Portal Nacional de Datos Abiertos del Ecuador. https://www.datosabiertos.gob.ec/dataset/registro-unico-de-contribuyentes-ruc-pichincha
