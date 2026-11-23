import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
from pathlib import Path
import pandas as pd
import config


def _leer_csv_seguro(ruta_csv: Path) -> pd.DataFrame:
    if not ruta_csv.exists():
        print(f"[AVISO] No existe: {ruta_csv.name}")
        return pd.DataFrame()
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        for sep in (";", ",", "|", "\t"):
            try:
                df = pd.read_csv(ruta_csv, sep=sep, encoding=enc, dtype=str, low_memory=False)
                if df.shape[1] > 1:
                    return df
            except Exception:
                continue
    return pd.read_csv(ruta_csv, encoding="latin-1", dtype=str, low_memory=False)


def extraer_sercop_streaming(archivos: list[Path]) -> dict:
    procesos, adjudicaciones, contratos, parties = [], [], [], []
    conteos_anio = {}

    for ruta in archivos:
        if not ruta.exists():
            print(f"[AVISO] No existe: {ruta.name}")
            continue

        print(f"Extrayendo {ruta.name}...")
        leidos = 0
        with open(ruta, "r", encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if not linea:
                    continue
                obj = json.loads(linea)
                rels = obj.get("releases", [obj]) if isinstance(obj, dict) else []

                for r in rels:
                    if not isinstance(r, dict):
                        continue
                    leidos += 1
                    ocid = r.get("ocid")
                    rel_date = r.get("date")
                    tender = r.get("tender") if isinstance(r.get("tender"), dict) else {}
                    buyer = r.get("buyer") if isinstance(r.get("buyer"), dict) else {}
                    period = tender.get("tenderPeriod") if isinstance(tender.get("tenderPeriod"), dict) else {}
                    items = tender.get("items") if isinstance(tender.get("items"), list) else []
                    first_item = items[0] if items and isinstance(items[0], dict) else {}
                    clasif = first_item.get("classification") if isinstance(first_item.get("classification"), dict) else {}
                    bids = r.get("bids") if isinstance(r.get("bids"), dict) else {}
                    bid_details = bids.get("details") if isinstance(bids.get("details"), list) else []

                    procesos.append({
                        "ocid": ocid,
                        "release_date": rel_date,
                        "anio_archivo": ruta.stem.split("_")[-1],
                        "buyer_id": buyer.get("id"),
                        "buyer_name": buyer.get("name"),
                        "procurementMethod": tender.get("procurementMethod"),
                        "procurementMethodDetails": tender.get("procurementMethodDetails"),
                        "tender_startDate": period.get("startDate"),
                        "cpc_id": clasif.get("id"),
                        "cpc_description": clasif.get("description"),
                        "num_ofertas": len(bid_details),
                    })

                    for aw in (r.get("awards") if isinstance(r.get("awards"), list) else []):
                        if not isinstance(aw, dict):
                            continue
                        val = aw.get("value") if isinstance(aw.get("value"), dict) else {}
                        suppliers = aw.get("suppliers") if isinstance(aw.get("suppliers"), list) else []
                        sup = suppliers[0] if suppliers and isinstance(suppliers[0], dict) else {}
                        adjudicaciones.append({
                            "ocid": ocid,
                            "release_date": rel_date,
                            "anio_archivo": ruta.stem.split("_")[-1],
                            "award_id": aw.get("id"),
                            "award_date": aw.get("date"),
                            "award_status": aw.get("status"),
                            "monto_adjudicado": val.get("amount"),
                            "moneda": val.get("currency"),
                            "supplier_id": sup.get("id"),
                            "supplier_name": sup.get("name"),
                        })

                    for ct in (r.get("contracts") if isinstance(r.get("contracts"), list) else []):
                        if isinstance(ct, dict):
                            cval = ct.get("value") if isinstance(ct.get("value"), dict) else {}
                            contratos.append({
                                "ocid": ocid,
                                "awardID": ct.get("awardID"),
                                "contract_id": ct.get("id"),
                                "contract_dateSigned": ct.get("dateSigned"),
                                "monto_contrato": cval.get("amount"),
                            })
                        elif isinstance(ct, str):
                            contratos.append({
                                "ocid": ocid,
                                "awardID": None,
                                "contract_id": ct,
                                "contract_dateSigned": None,
                                "monto_contrato": None,
                            })

                    for pt in (r.get("parties") if isinstance(r.get("parties"), list) else []):
                        if not isinstance(pt, dict):
                            continue
                        ident = pt.get("identifier") if isinstance(pt.get("identifier"), dict) else {}
                        addr = pt.get("address") if isinstance(pt.get("address"), dict) else {}
                        roles = pt.get("roles") if isinstance(pt.get("roles"), list) else []
                        parties.append({
                            "ocid": ocid,
                            "party_id": pt.get("id"),
                            "identifier_id": ident.get("id"),
                            "name": pt.get("name"),
                            "roles": ",".join(str(x) for x in roles),
                            "region": addr.get("region"),
                            "locality": addr.get("locality"),
                        })

        conteos_anio[ruta.name] = leidos
        print(f"  -> {ruta.name}: {leidos:,} releases extraídos")

    return {
        "procesos": pd.DataFrame(procesos),
        "adjudicaciones": pd.DataFrame(adjudicaciones),
        "contratos": pd.DataFrame(contratos),
        "parties": pd.DataFrame(parties),
        "conteos_anio": conteos_anio,
    }


def run_extract() -> dict:
    config.STAGING_DIR.mkdir(parents=True, exist_ok=True)
    datos = extraer_sercop_streaming(config.SERCOP_FILES)

    dfs_ruc = []
    for f_ruc in config.SRI_RUC_FILES:
        df_tmp = _leer_csv_seguro(f_ruc)
        if not df_tmp.empty:
            df_tmp["_origen_ruc"] = f_ruc.name
            dfs_ruc.append(df_tmp)
            print(f"SRI RUC ({f_ruc.name}): {len(df_tmp):,} filas | Columnas: {list(df_tmp.columns[:8])}")

    datos["sri_ruc"] = pd.concat(dfs_ruc, ignore_index=True) if dfs_ruc else pd.DataFrame()
    datos["sri_recaudacion"] = _leer_csv_seguro(config.SRI_RECAUDACION_FILE)
    print(f"SRI Recaudación: {len(datos['sri_recaudacion']):,} filas")
    return datos


if __name__ == "__main__":
    run_extract()