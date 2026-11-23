"""
config.py — Configuración centralizada y unificada del Pipeline ETL.
Abarca P2 (Extracción y Transformación) y P3 (Modelado y Carga Incremental).

Proyecto: BI — Transparencia en Compras Públicas del SERCOP y Datos SRI (2022-2026)
DataMart: DM_ComprasPublicas (SQL Server, Esquema Estrella)
"""

from pathlib import Path
import os

# ---------------------------------------------------------------------------
# 1. Rutas del Proyecto y Datos
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# Carpeta de datos crudos (JSONL SERCOP y CSVs SRI)
RAW_DIR = BASE_DIR / "data_raw"

# Archivos fuente SERCOP (Open Contracting Partnership - OCDS)
SERCOP_FILES = [
    RAW_DIR / "sercop_2022.jsonl",
    RAW_DIR / "sercop_2023.jsonl",
    RAW_DIR / "sercop_2024.jsonl",
    RAW_DIR / "sercop_2025.jsonl",
    RAW_DIR / "sercop_2026.jsonl",
]

# Archivos fuente SRI (Catastro RUC de Pichincha y Guayas)
SRI_RUC_FILES = [
    RAW_DIR / "SRI_RUC_Pichincha.csv",
    RAW_DIR / "SRI_RUC_Guayas.csv",
]

# Recaudación de Impuestos SRI 2024
SRI_RECAUDACION_FILE = RAW_DIR / "sri_recaudacion_2024.csv"

# Carpeta de Staging (CSVs procesados y limpios)
# Prioridad: data_staging en la raíz del repo, o data_staging en el directorio padre
# Detección inteligente de carpeta de Staging:
# 1. En la raíz del repositorio local
# 2. En el directorio padre (un nivel arriba)
# 3. En el directorio abuelo (INTEGRADOR ANALISIS/data_staging)
# 4. Por defecto, en la raíz del repositorio
if (BASE_DIR / "data_staging").exists() and any((BASE_DIR / "data_staging").glob("stg_*.csv")):
    STAGING_DIR = BASE_DIR / "data_staging"
elif (BASE_DIR.parent / "data_staging").exists() and any((BASE_DIR.parent / "data_staging").glob("stg_*.csv")):
    STAGING_DIR = BASE_DIR.parent / "data_staging"
elif (BASE_DIR.parent.parent / "data_staging").exists() and any((BASE_DIR.parent.parent / "data_staging").glob("stg_*.csv")):
    STAGING_DIR = BASE_DIR.parent.parent / "data_staging"
else:
    STAGING_DIR = BASE_DIR / "data_staging"

# Archivos de salida de la fase de Transformación (P2)
OUT_PROCESOS = STAGING_DIR / "stg_procesos.csv"
OUT_ADJUDICACIONES = STAGING_DIR / "stg_adjudicaciones.csv"
OUT_CONTRATOS = STAGING_DIR / "stg_contratos.csv"
OUT_PARTIES = STAGING_DIR / "stg_parties.csv"
OUT_RUC = STAGING_DIR / "stg_proveedores_ruc.csv"
OUT_RECAUDACION = STAGING_DIR / "stg_recaudacion.csv"

# Diccionario de archivos staging para la fase de Carga (P3)
ARCHIVOS = {
    "procesos": "stg_procesos.csv",
    "adjudicaciones": "stg_adjudicaciones.csv",
    "contratos": "stg_contratos.csv",
    "parties": "stg_parties.csv",
    "ruc": "stg_proveedores_ruc.csv",
}

CSV_SEP = ","            # separador de los CSV de P2
CSV_ENCODING = "utf-8"   # si da error de lectura, probar "latin-1"
CHUNK_SIZE = 500_000     # filas por bloque al leer CSVs grandes

# Directorio de logs de ejecución
LOG_DIR = BASE_DIR / "etl" / "logs"

# ---------------------------------------------------------------------------
# 2. Conexión a SQL Server (DataMart DM_ComprasPublicas)
# ---------------------------------------------------------------------------
SQL_SERVER = {
    "driver": "ODBC Driver 17 for SQL Server",  # o "ODBC Driver 18 for SQL Server"
    "server": r"localhost",                     # Ajustar según instancia local, ej. r"localhost\SQLEXPRESS"
    "database": "DM_ComprasPublicas",
    "trusted_connection": True,                 # Autenticación de Windows
    "user": "",                                 # Solo si trusted_connection = False
    "password": "",
    "trust_server_certificate": True,           # Requerido para driver 18
}

# ---------------------------------------------------------------------------
# 3. Alcance del Proyecto
# ---------------------------------------------------------------------------
ANIO_INICIO = 2022
ANIO_FIN = 2026
ZONA_HORARIA = "America/Guayaquil"

# ---------------------------------------------------------------------------
# 4. Mapeo de Columnas (Staging CSV -> Modelo Dimensional)
# ---------------------------------------------------------------------------
COLUMNAS = {
    "procesos": {
        "ocid": "ocid",
        "fecha_publicacion": "tender_startDate",
        "metodo_detalle": "metodo_estandarizado",
        "metodo_ocds": "procurementMethod",
        "entidad_id": "buyer_id",
        "entidad_nombre": "buyer_name",
        "cpc_codigo": "cpc_id",
        "cpc_descripcion": "cpc_description",
        "num_ofertas": "num_ofertas",
    },
    "adjudicaciones": {
        "ocid": "ocid",
        "adjudicacion_id": "award_id",
        "fecha_adjudicacion": "award_date",
        "fecha_respaldo": "release_date",
        "monto": "monto_adjudicado",
        "proveedor_id": "ruc_proveedor",
        "proveedor_nombre": "supplier_name",
    },
    "contratos": {
        "ocid": "ocid",
        "adjudicacion_id": "awardID",
        "monto": "monto_contrato",
    },
    "parties": {
        "party_id": "ruc_limpio",
        "roles": "roles",
        "provincia": "region",
    },
    "ruc": {
        "ruc": "NUMERO_RUC",
        "razon_social": "RAZON_SOCIAL",
        "provincia": "CODIGO_JURISDICCION",
        "ciiu": "CODIGO_CIIU",
        "actividad": "ACTIVIDAD_ECONOMICA",
        "tipo_contribuyente": "TIPO_CONTRIBUYENTE",
        "fecha_inicio": "FECHA_INICIO_ACTIVIDADES",
    },
}

ACTIVAR_PARTIES = True

# ---------------------------------------------------------------------------
# 5. Reglas de Negocio para Clasificación y Normalización
# ---------------------------------------------------------------------------
REGLAS_METODO = [
    ("EMERGENCIA", "Emergencia", False),
    ("INFIMA", "Ínfima cuantía", False),
    ("CATALOGO ELECTRONICO - COMPRA DIRECTA", "Catálogo electrónico - compra directa", False),
    ("CATALOGO", "Catálogo electrónico - puja / mejor oferta", True),
    ("DIRECTA", "Contratación directa", False),
    ("REGIMEN ESPECIAL", "Régimen especial", False),
    ("ENTIDADES PUBLICAS", "Régimen especial", False),
    ("EMPRESAS PUBLICAS", "Régimen especial", False),
    ("BIENES Y SERVICIOS UNICOS", "Régimen especial", False),
    ("REPUESTOS", "Régimen especial", False),
    ("OBRA ARTISTICA", "Régimen especial", False),
    ("ASESORIA Y PATROCINIO", "Régimen especial", False),
    ("TRANSPORTE DE CORREO", "Régimen especial", False),
    ("SUBASTA", "Subasta inversa", True),
    ("LICITACION", "Licitación", True),
    ("COTIZACION", "Cotización", True),
    ("MENOR CUANTIA", "Menor cuantía", True),
    ("LISTA CORTA", "Lista corta", True),
    ("CONCURSO", "Concurso público", True),
    ("PROCESO DE SELECCION", "Concurso público", True),
    ("FERIA", "Feria inclusiva", True),
]

METODO_OCDS_COMPETITIVO = {"open": True, "selective": True, "limited": False, "direct": False}

REGLAS_NIVEL_GOBIERNO = [
    ("GOBIERNO AUTONOMO DESCENTRALIZADO", "Local (GAD)"),
    ("MUNICIPIO", "Local (GAD)"),
    ("MUNICIPAL", "Local (GAD)"),
    ("PREFECTURA", "Local (GAD)"),
    ("GAD ", "Local (GAD)"),
    ("JUNTA PARROQUIAL", "Local (GAD)"),
    ("EMPRESA PUBLICA", "Empresa pública"),
    ("EP ", "Empresa pública"),
    ("UNIVERSIDAD", "Educación superior"),
    ("ESCUELA POLITECNICA", "Educación superior"),
    ("MINISTERIO", "Central"),
    ("SECRETARIA", "Central"),
    ("SERVICIO NACIONAL", "Central"),
    ("AGENCIA", "Central"),
    ("HOSPITAL", "Salud"),
    ("INSTITUTO ECUATORIANO DE SEGURIDAD SOCIAL", "Seguridad social"),
]

SECCIONES_CPC = {
    "0": "Productos agropecuarios, forestales y de pesca",
    "1": "Minerales; electricidad, gas y agua",
    "2": "Alimentos, bebidas, tabaco y textiles",
    "3": "Otros bienes transportables",
    "4": "Productos metálicos, maquinaria y equipo",
    "5": "Construcción y servicios de construcción",
    "6": "Comercio, alojamiento, comidas y transporte",
    "7": "Servicios financieros e inmobiliarios",
    "8": "Servicios prestados a las empresas y de producción",
    "9": "Servicios comunitarios, sociales y personales",
}

ANONIMIZAR_PERSONAS_NATURALES = True
SAL_ANONIMIZACION = "dm-compras-2026"
