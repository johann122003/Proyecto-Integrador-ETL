from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "data_raw"
STAGING_DIR = BASE_DIR / "data_staging"

SERCOP_FILES = [
    RAW_DIR / "sercop_2022.jsonl",
    RAW_DIR / "sercop_2023.jsonl",
    RAW_DIR / "sercop_2024.jsonl",
    RAW_DIR / "sercop_2025.jsonl",
    RAW_DIR / "sercop_2026.jsonl",
]

SRI_RUC_FILES = [
    RAW_DIR / "SRI_RUC_Pichincha.csv",
    RAW_DIR / "SRI_RUC_Guayas.csv",
]

SRI_RECAUDACION_FILE = RAW_DIR / "sri_recaudacion_2024.csv"

OUT_PROCESOS = STAGING_DIR / "stg_procesos.csv"
OUT_ADJUDICACIONES = STAGING_DIR / "stg_adjudicaciones.csv"
OUT_CONTRATOS = STAGING_DIR / "stg_contratos.csv"
OUT_PARTIES = STAGING_DIR / "stg_parties.csv"
OUT_RUC = STAGING_DIR / "stg_proveedores_ruc.csv"
OUT_RECAUDACION = STAGING_DIR / "stg_recaudacion.csv"