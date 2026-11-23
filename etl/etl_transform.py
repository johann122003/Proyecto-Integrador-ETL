import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import hashlib
import pandas as pd
import config
from etl_extract import run_extract


def _anonimizar(texto: str) -> str:
    h = hashlib.sha256(texto.strip().encode("utf-8")).hexdigest()[:12]
    return f"PERSONA_NATURAL_{h}"


def _buscar_col(df: pd.DataFrame, opciones: list[str]) -> str | None:
    mapa = {c.lower().strip(): c for c in df.columns}
    for op in opciones:
        if op.lower() in mapa:
            return mapa[op.lower()]
    return None


def run_transform(raw: dict):
    stats = {"descargados_por_archivo": raw.get("conteos_anio", {})}

    df_proc = raw["procesos"].copy()
    df_adj = raw["adjudicaciones"].copy()
    df_cont = raw["contratos"].copy()
    df_parties = raw["parties"].copy()
    df_ruc = raw["sri_ruc"].copy()
    df_rec = raw["sri_recaudacion"].copy()

    if not df_proc.empty:
        df_proc["metodo_estandarizado"] = (
            df_proc["procurementMethodDetails"]
            .fillna(df_proc["procurementMethod"])
            .fillna("NO_ESPECIFICADO")
            .astype(str).str.strip().str.upper()
        )
        top_metodos = df_proc["metodo_estandarizado"].value_counts().head(15).to_dict()
        print("\n[VERIFICACIÓN HIPÓTESIS P1] Top valores en procurementMethodDetails:")
        for m, c in top_metodos.items():
            print(f"  - {m}: {c:,}")

        antes = len(df_proc)
        df_proc = df_proc.drop_duplicates(subset=["ocid"], keep="last")
        stats["procesos_duplicados_eliminados"] = antes - len(df_proc)

    if not df_adj.empty:
        stats["adjudicaciones_iniciales"] = len(df_adj)
        stats["nulos_monto_adjudicado"] = int(df_adj["monto_adjudicado"].isna().sum())
        stats["nulos_fecha_adjudicacion"] = int(df_adj["award_date"].isna().sum())

        antes = len(df_adj)
        df_adj = df_adj.drop_duplicates(subset=["ocid", "award_id"], keep="last")
        stats["adjudicaciones_duplicados_eliminados"] = antes - len(df_adj)

        df_adj["award_date_dt"] = pd.to_datetime(df_adj["award_date"], errors="coerce", utc=True).dt.tz_localize(None)
        df_adj["release_date_dt"] = pd.to_datetime(df_adj["release_date"], errors="coerce", utc=True).dt.tz_localize(None)

        if not df_proc.empty:
            df_proc["tender_start_dt"] = pd.to_datetime(df_proc["tender_startDate"], errors="coerce", utc=True).dt.tz_localize(None)
            df_adj = df_adj.merge(
                df_proc[["ocid", "tender_start_dt", "metodo_estandarizado", "buyer_id", "buyer_name", "cpc_id", "cpc_description", "num_ofertas"]],
                on="ocid",
                how="left",
            )
            antes_f = len(df_adj)
            valido = (
                df_adj["award_date_dt"].isna()
                | df_adj["tender_start_dt"].isna()
                | (df_adj["award_date_dt"] >= df_adj["tender_start_dt"])
            )
            df_adj = df_adj[valido].copy()
            stats["adjudicaciones_fecha_invalida_descartadas"] = antes_f - len(df_adj)

        df_adj["monto_adjudicado"] = pd.to_numeric(df_adj["monto_adjudicado"], errors="coerce").fillna(0.0)
        df_adj["ruc_proveedor"] = df_adj["supplier_id"].astype(str).str.extract(r"(\d{13})", expand=False)

    if not df_cont.empty:
        df_cont = df_cont.drop_duplicates(subset=["ocid", "contract_id"], keep="last")
        df_cont["monto_contrato"] = pd.to_numeric(df_cont["monto_contrato"], errors="coerce").fillna(0.0)

    if not df_parties.empty:
        df_parties = df_parties.drop_duplicates(subset=["ocid", "party_id"], keep="last")
        df_parties["ruc_limpio"] = (
            df_parties["identifier_id"].fillna(df_parties["party_id"]).astype(str).str.extract(r"(\d{13})", expand=False)
        )
        df_parties["name_clean"] = df_parties["name"].fillna("SIN_NOMBRE").astype(str).str.strip()
        es_juridica = df_parties["name_clean"].str.upper().str.contains(
            r"\b(S\.?A\.?|CIA\.?|LTDA\.?|S\.?A\.?S\.?|EP|EMPRESA|MINISTERIO|GAD|MUNICIPIO|UNIVERSIDAD|INSTITUTO|CORPORACION|CONSORCIO)\b",
            regex=True,
        )
        df_parties["nombre_anonimizado"] = [
            n if jur else _anonimizar(n) for n, jur in zip(df_parties["name_clean"], es_juridica)
        ]

        if not df_ruc.empty:
            col_ruc = _buscar_col(df_ruc, ["NUMERO_RUC", "RUC", "IDENTIFICACION"])
            if col_ruc:
                df_ruc["ruc_limpio"] = df_ruc[col_ruc].astype(str).str.extract(r"(\d{13})", expand=False)
                df_ruc = df_ruc.dropna(subset=["ruc_limpio"]).drop_duplicates(subset=["ruc_limpio"], keep="first")
                df_parties = df_parties.merge(df_ruc, on="ruc_limpio", how="left", suffixes=("", "_sri"))
                stats["parties_con_match_sri"] = int(df_parties[col_ruc].notna().sum())

    df_proc.to_csv(config.OUT_PROCESOS, index=False, encoding="utf-8")
    df_adj.to_csv(config.OUT_ADJUDICACIONES, index=False, encoding="utf-8")
    df_cont.to_csv(config.OUT_CONTRATOS, index=False, encoding="utf-8")
    df_parties.to_csv(config.OUT_PARTIES, index=False, encoding="utf-8")
    if not df_ruc.empty:
        df_ruc.to_csv(config.OUT_RUC, index=False, encoding="utf-8")
    if not df_rec.empty:
        df_rec.to_csv(config.OUT_RECAUDACION, index=False, encoding="utf-8")

    print("\n================ ESTADÍSTICAS PARA DOCUMENTO (SECCIÓN 2.3) ================")
    for k, v in stats.items():
        print(f"{k}: {v}")
    print("===========================================================================")


if __name__ == "__main__":
    datos_raw = run_extract()
    run_transform(datos_raw)