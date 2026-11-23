import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

"""
etl_load.py — Carga del DataMart DM_ComprasPublicas (rol P3: Modelado y Carga)

Toma los CSV limpios que entrega P2 (stg_*.csv) y los carga en SQL Server:

  1. Dimensiones  -> upsert por llave de negocio (MERGE, SCD tipo 1).
                     Las llaves sustitutas (SK) nunca cambian entre cargas,
                     así los hechos ya cargados siguen apuntando bien.
  2. FACT_CONTRATOS -> carga INCREMENTAL con marca de agua (ETL_Watermark):
                     solo entran adjudicaciones con fecha > FechaCorte y que
                     no estén ya cargadas. Nunca se hace TRUNCATE del hecho.

Uso:
  python etl_load.py --revisar                 # revisa columnas de los CSV, no toca la BD
  python etl_load.py --sin-bd                  # arma todo en memoria y muestra conteos
  python etl_load.py --hasta 2023-12-31        # carga 1 de la demo (2022-2023)
  python etl_load.py --hasta 2024-12-31        # carga 2 (solo 2024)
  python etl_load.py                           # carga 3 (2025-2026, todo lo pendiente)
  python etl_load.py --reiniciar               # borra hechos y regresa la marca de agua (repetir demo)
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import re
import sys
import time
import unicodedata
from datetime import datetime

import pandas as pd

import config as cfg

log = logging.getLogger("etl_load")


# ===========================================================================
# Utilidades
# ===========================================================================
def configurar_log() -> None:
    cfg.LOG_DIR.mkdir(parents=True, exist_ok=True)
    archivo = cfg.LOG_DIR / f"etl_load_{datetime.now():%Y%m%d_%H%M%S}.log"
    formato = "%(asctime)s | %(levelname)-7s | %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=formato,
        datefmt="%H:%M:%S",
        handlers=[logging.FileHandler(archivo, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
    )
    log.info("Log de esta ejecución: %s", archivo)


def normalizar(texto) -> str | None:
    """Mayúsculas, sin tildes y sin espacios repetidos."""
    if texto is None or (isinstance(texto, float) and pd.isna(texto)):
        return None
    t = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii")
    t = re.sub(r"\s+", " ", t).strip().upper()
    return t or None


def extraer_ruc(valor) -> str | None:
    """'EC-RUC-1790012345001' o '1790012345001' -> '1790012345001'."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    texto = str(valor).strip()
    m = re.search(r"(?<!\d)(\d{13})(?!\d)", texto)   # primer bloque de 13 dígitos
    if m:
        return m.group(1)
    if re.fullmatch(r"\d+\.0", texto):                 # número leído como float
        texto = texto[:-2]
    if re.fullmatch(r"\d{12}", texto):                  # RUC que perdió el 0 inicial
        return "0" + texto
    m = re.search(r"(?<!\d)(\d{10})(?!\d)", texto)    # cédula sin el 001
    if m:
        return m.group(1) + "001"
    return None


def es_persona_natural(ruc: str | None, tipo_contribuyente) -> bool:
    tipo = normalizar(tipo_contribuyente) or ""
    if "NATURAL" in tipo:
        return True
    if "SOCIEDAD" in tipo or "PUBLIC" in tipo:
        return False
    # Regla del SRI: el tercer dígito del RUC es 0-5 para personas naturales
    return bool(ruc and len(ruc) == 13 and ruc[2].isdigit() and int(ruc[2]) < 6)


def hash_corto(texto: str) -> str:
    return hashlib.sha256(f"{cfg.SAL_ANONIMIZACION}|{texto}".encode()).hexdigest()[:10].upper()


def a_fecha(serie: pd.Series) -> pd.Series:
    """Fechas OCDS (ISO con zona horaria) -> fecha local sin hora."""
    try:
        f = pd.to_datetime(serie, errors="coerce", utc=True, format="ISO8601")
    except (TypeError, ValueError):
        f = pd.to_datetime(serie, errors="coerce", utc=True)
    return f.dt.tz_convert(cfg.ZONA_HORARIA).dt.tz_localize(None).dt.normalize()


def columnas_de(tabla: str, *, solo_existentes: bool = True) -> dict[str, str]:
    mapa = cfg.COLUMNAS[tabla]
    return {k: v for k, v in mapa.items() if v} if solo_existentes else mapa


def ruta(tabla: str):
    return cfg.STAGING_DIR / cfg.ARCHIVOS[tabla]


def leer_encabezado(tabla: str) -> list[str]:
    return list(pd.read_csv(ruta(tabla), sep=cfg.CSV_SEP, encoding=cfg.CSV_ENCODING, nrows=0).columns)


def leer_csv(tabla: str, filtro=None) -> pd.DataFrame:
    """Lee solo las columnas mapeadas y las renombra a nombres lógicos.
    `filtro` (opcional) se aplica a cada bloque para no cargar en memoria
    archivos enormes completos (parties, catastro RUC)."""
    mapa = columnas_de(tabla)
    inverso = {real: logico for logico, real in mapa.items()}
    t0 = time.time()
    bloques = []
    lector = pd.read_csv(
        ruta(tabla), sep=cfg.CSV_SEP, encoding=cfg.CSV_ENCODING,
        usecols=list(inverso), dtype=str, chunksize=cfg.CHUNK_SIZE, low_memory=False,
    )
    total = 0
    for bloque in lector:
        total += len(bloque)
        bloque = bloque.rename(columns=inverso)
        if filtro is not None:
            bloque = filtro(bloque)
        bloques.append(bloque)
    df = pd.concat(bloques, ignore_index=True) if bloques else pd.DataFrame(columns=list(mapa))
    log.info("Leído %-15s %10s filas (%s conservadas) en %.1fs",
             cfg.ARCHIVOS[tabla], f"{total:,}", f"{len(df):,}", time.time() - t0)
    return df


# ===========================================================================
# Modo --revisar: valida el mapeo de columnas contra los CSV reales
# ===========================================================================
OBLIGATORIAS = {
    "procesos": ["ocid", "metodo_detalle", "entidad_id"],
    "adjudicaciones": ["ocid", "adjudicacion_id", "fecha_adjudicacion", "monto", "proveedor_id"],
    "contratos": ["ocid", "monto"],
    "parties": [],
    "ruc": ["ruc"],
}


def revisar_columnas() -> bool:
    todo_bien = True
    for tabla in cfg.ARCHIVOS:
        if tabla == "parties" and not cfg.ACTIVAR_PARTIES:
            continue
        print(f"\n=== {cfg.ARCHIVOS[tabla]} ===")
        if not ruta(tabla).exists():
            print(f"  [FALTA] No existe el archivo {ruta(tabla)}")
            todo_bien = False
            continue
        reales = leer_encabezado(tabla)
        print(f"  Columnas en el CSV: {', '.join(reales)}")
        for logico, real in columnas_de(tabla, solo_existentes=False).items():
            if real is None:
                estado = "OBLIGATORIA SIN MAPEAR" if logico in OBLIGATORIAS[tabla] else "omitida (None)"
                todo_bien &= logico not in OBLIGATORIAS[tabla]
            elif real in reales:
                estado = "ok"
            else:
                estado = "NO EXISTE -> corrige config.COLUMNAS"
                todo_bien = False
            print(f"  {logico:<20} -> {str(real):<35} {estado}")
        muestra = pd.read_csv(ruta(tabla), sep=cfg.CSV_SEP, encoding=cfg.CSV_ENCODING, nrows=2, dtype=str)
        print("  Primera fila:", muestra.iloc[0].to_dict() if len(muestra) else "(vacío)")
    print("\nResultado:", "mapeo correcto, ya puedes cargar." if todo_bien else "hay columnas por corregir en config.py.")
    return todo_bien


# ===========================================================================
# Construcción de dimensiones y hechos (en memoria)
# ===========================================================================
def clasificar_metodo(detalle_norm: str | None, metodo_ocds) -> tuple[str, bool | None]:
    for clave, categoria, competitivo in cfg.REGLAS_METODO:
        if detalle_norm and clave in detalle_norm:
            return categoria, competitivo
    ocds = (str(metodo_ocds).strip().lower() if isinstance(metodo_ocds, str) else None)
    if ocds in cfg.METODO_OCDS_COMPETITIVO:
        return "Otro", cfg.METODO_OCDS_COMPETITIVO[ocds]
    return "Otro", None


def nivel_gobierno(nombre_norm: str | None) -> str:
    if nombre_norm:
        texto = f"{nombre_norm} "
        for clave, nivel in cfg.REGLAS_NIVEL_GOBIERNO:
            if clave in texto:
                return nivel
    return "Otro / no determinado"


def construir_modelo(hasta: pd.Timestamp | None):
    """Devuelve (dimensiones, hechos) como DataFrames listos para cargar."""
    # ---------------- Procesos (1 fila por ocid) ----------------
    proc = leer_csv("procesos")
    antes = len(proc)
    proc = proc.drop_duplicates(subset="ocid", keep="last")
    if antes != len(proc):
        log.warning("procesos: %s ocid duplicados descartados (se conserva el último)", f"{antes - len(proc):,}")
    # Los métodos del catálogo traen el convenio ("... EN EL CONVENIO SERCOP-..., MUEBLES"): se agrupan por tipo
    proc["metodo_detalle"] = proc["metodo_detalle"].map(
        lambda v: re.split(r"\s+EN EL CONVENIO|,", v)[0].strip() if isinstance(v, str) else v)
    proc["metodo_norm"] = proc["metodo_detalle"].map(normalizar).fillna("NO ESPECIFICADO").str[:100]
    # buyer.id viene como EC-RUC-<RUC>-<n.º de proceso>: la entidad se identifica por su RUC
    proc["entidad_id"] = [extraer_ruc(v) or (str(v).strip() if isinstance(v, str) else None) for v in proc["entidad_id"]]
    if "fecha_publicacion" in proc:
        proc["fecha_publicacion"] = a_fecha(proc["fecha_publicacion"])
    if "cpc_codigo" in proc:
        proc["cpc_codigo"] = proc["cpc_codigo"].str.strip().str.replace(r"\.0$", "", regex=True)

    # ---------------- Adjudicaciones (grano del hecho) ----------------
    adj = leer_csv("adjudicaciones")
    adj["fecha_adjudicacion"] = a_fecha(adj["fecha_adjudicacion"])
    if "fecha_respaldo" in adj:
        vacias = adj["fecha_adjudicacion"].isna()
        adj.loc[vacias, "fecha_adjudicacion"] = a_fecha(adj.loc[vacias, "fecha_respaldo"])
        log.info("adjudicaciones: %s sin award_date usan la fecha de publicación (release_date)", f"{vacias.sum():,}")
    adj["monto"] = pd.to_numeric(adj["monto"], errors="coerce")
    adj["ruc"] = adj["proveedor_id"].map(extraer_ruc)
    sin_id = adj["adjudicacion_id"].isna()
    if sin_id.any():  # sin award_id no se puede garantizar el grano -> se descartan
        log.warning("adjudicaciones: %s sin award_id descartadas", f"{sin_id.sum():,}")
        adj = adj[~sin_id]
    adj = adj[adj["ocid"].notna()]

    sin_fecha = adj["fecha_adjudicacion"].isna().sum()
    adj = adj[adj["fecha_adjudicacion"].notna()]
    adj = adj[adj["fecha_adjudicacion"].dt.year.between(cfg.ANIO_INICIO, cfg.ANIO_FIN)]
    antes = len(adj)
    adj = adj.drop_duplicates(subset=["ocid", "adjudicacion_id"], keep="last")
    log.info("adjudicaciones: %s sin fecha válida descartadas; %s duplicadas (ocid + award_id) descartadas",
             f"{sin_fecha:,}", f"{antes - len(adj):,}")

    # ---------------- Contratos: monto firmado por adjudicación ----------------
    con = leer_csv("contratos")
    con["monto"] = pd.to_numeric(con["monto"], errors="coerce")
    llave_con = ["ocid", "adjudicacion_id"] if "adjudicacion_id" in con else ["ocid"]
    con = con.groupby(llave_con, as_index=False)["monto"].sum(min_count=1).rename(columns={"monto": "monto_contrato"})

    # ---------------- Hechos ----------------
    fact = adj.merge(proc, on="ocid", how="left", suffixes=("", "_proc"))
    fact = fact.merge(con, on=llave_con, how="left")
    sin_proceso = fact["metodo_detalle"].isna().sum()
    if sin_proceso:
        log.warning("%s adjudicaciones sin proceso en stg_procesos -> irán a los miembros 'Desconocido' (-1)",
                    f"{sin_proceso:,}")

    # Regla de calidad: el monto de contrato en 0 o mayor a 10 veces lo adjudicado se trata como dato inválido
    mc = fact["monto_contrato"]
    invalido = (mc <= 0) | ((fact["monto"] > 0) & (mc > 10 * fact["monto"]))
    if invalido.any():
        log.warning("contratos: %s montos de contrato en 0 o > 10x lo adjudicado -> NULL "
                    "(%s en 0, %s atípicos)", f"{invalido.sum():,}", f"{(mc <= 0).sum():,}",
                    f"{(invalido & (mc > 0)).sum():,}")
        fact.loc[invalido, "monto_contrato"] = pd.NA

    if "fecha_publicacion" in fact:
        dias = (fact["fecha_adjudicacion"] - fact["fecha_publicacion"]).dt.days
        fact["dias_adjudicacion"] = dias.where(dias >= 0)  # fechas incoherentes -> NULL
    else:
        fact["dias_adjudicacion"] = pd.NA

    # ---------------- Proveedores + catastro RUC ----------------
    rucs = set(adj["ruc"].dropna())

    def solo_rucs_del_proyecto(b: pd.DataFrame) -> pd.DataFrame:
        b["ruc"] = b["ruc"].map(extraer_ruc)
        return b[b["ruc"].isin(rucs)]

    sri = leer_csv("ruc", filtro=solo_rucs_del_proyecto).drop_duplicates(subset="ruc", keep="first")
    prov = (adj[["ruc", "proveedor_nombre"]] if "proveedor_nombre" in adj else adj[["ruc"]].assign(proveedor_nombre=None))
    prov = prov.dropna(subset=["ruc"]).drop_duplicates(subset="ruc", keep="last")
    prov = prov.merge(sri, on="ruc", how="left")
    log.info("proveedores: %s distintos, %s encontrados en el catastro RUC (%.1f%%)",
             f"{len(prov):,}", f"{prov['razon_social'].notna().sum():,}",
             100 * prov["razon_social"].notna().mean() if len(prov) else 0)

    prov["nombre"] = prov["razon_social"].fillna(prov["proveedor_nombre"]).map(normalizar)
    prov["es_pn"] = [es_persona_natural(r, t) for r, t in zip(prov["ruc"], prov.get("tipo_contribuyente", pd.Series(index=prov.index)))]
    prov["ruc_dm"] = prov["ruc"]
    if cfg.ANONIMIZAR_PERSONAS_NATURALES:
        h = prov.loc[prov["es_pn"], "ruc"].map(hash_corto)
        prov.loc[prov["es_pn"], "ruc_dm"] = "PN-" + h
        prov.loc[prov["es_pn"], "nombre"] = "PERSONA NATURAL " + h
        log.info("proveedores: %s personas naturales anonimizadas", f"{prov['es_pn'].sum():,}")

    dim_proveedor = pd.DataFrame({
        "RUC": prov["ruc_dm"],
        "RazonSocial_Anonimizada": prov["nombre"].fillna("SIN NOMBRE"),
        "Provincia": prov.get("provincia", pd.Series(index=prov.index)).map(normalizar),
        "ActividadEconomica_CIIU": (prov.get("ciiu", pd.Series(index=prov.index)).fillna("").str.strip()
                                    + " " + prov.get("actividad", pd.Series(index=prov.index)).fillna("").str.strip()
                                    ).str.strip().replace("", None),
        "TipoContribuyente": prov.get("tipo_contribuyente", pd.Series(index=prov.index)).map(normalizar)
                             .fillna(prov["es_pn"].map({True: "PERSONA NATURAL", False: "SOCIEDAD"})),
        "FechaInicioActividades": pd.to_datetime(prov.get("fecha_inicio", pd.Series(index=prov.index)),
                                                 errors="coerce").dt.date,
    })
    mapa_ruc = dict(zip(prov["ruc"], prov["ruc_dm"]))
    fact["ruc_dm"] = fact["ruc"].map(mapa_ruc)

    # ---------------- Entidades ----------------
    ent = proc[["entidad_id"] + (["entidad_nombre"] if "entidad_nombre" in proc else [])].dropna(subset=["entidad_id"])
    ent = ent.drop_duplicates(subset="entidad_id", keep="last")
    ent["nombre_norm"] = ent["entidad_nombre"].map(normalizar) if "entidad_nombre" in ent else None
    ent["provincia"] = None
    if cfg.ACTIVAR_PARTIES and cfg.COLUMNAS["parties"].get("provincia"):
        ids = set(ent["entidad_id"])

        def solo_compradores(b: pd.DataFrame) -> pd.DataFrame:
            b = b.assign(party_id=b["party_id"].map(extraer_ruc))
            b = b[b["party_id"].isin(ids)]
            if "roles" in b:
                b = b[b["roles"].fillna("").str.contains("buyer|procuringEntity", case=False)]
            return b

        par = leer_csv("parties", filtro=solo_compradores).dropna(subset=["provincia"])
        par = par.drop_duplicates(subset="party_id", keep="last")
        ent["provincia"] = ent["entidad_id"].map(dict(zip(par["party_id"], par["provincia"].map(normalizar))))

    dim_entidad = pd.DataFrame({
        "CodigoEntidad": ent["entidad_id"],
        "NombreEntidad": ent["nombre_norm"].fillna("SIN NOMBRE") if "entidad_nombre" in proc else "SIN NOMBRE",
        "NivelGobierno": ent["nombre_norm"].map(nivel_gobierno) if "entidad_nombre" in proc else "Otro / no determinado",
        "Sector": "Público",
        "Provincia": ent["provincia"],
    })

    # ---------------- Métodos de contratación ----------------
    met = proc[["metodo_norm", "metodo_detalle"] + (["metodo_ocds"] if "metodo_ocds" in proc else [])]
    met = met.drop_duplicates(subset="metodo_norm", keep="last")
    clasif = [clasificar_metodo(n, met.get("metodo_ocds", pd.Series(index=met.index)).loc[i]) for i, n in zip(met.index, met["metodo_norm"])]
    dim_metodo = pd.DataFrame({
        "CodigoMetodo": met["metodo_norm"].str[:100],
        "DescripcionMetodo": met["metodo_detalle"].fillna("No especificado").str.strip(),
        "CategoriaMetodo": [c for c, _ in clasif],
        "EsCompetitivo": [e for _, e in clasif],
    })
    sin_regla = dim_metodo[dim_metodo["EsCompetitivo"].isna()]
    if len(sin_regla):
        log.warning("Métodos sin regla en config.REGLAS_METODO (EsCompetitivo = NULL): %s",
                    "; ".join(sin_regla["CodigoMetodo"].head(15)))

    # ---------------- Categorías CPC ----------------
    if "cpc_codigo" in proc:
        cat = proc[["cpc_codigo"] + (["cpc_descripcion"] if "cpc_descripcion" in proc else [])]
        cat = cat.dropna(subset=["cpc_codigo"]).drop_duplicates(subset="cpc_codigo", keep="last")
        dim_categoria = pd.DataFrame({
            "CodigoCPC": cat["cpc_codigo"].str[:30],
            "DescripcionCategoria": cat["cpc_descripcion"].map(normalizar).fillna("SIN DESCRIPCION")
                                    if "cpc_descripcion" in cat else "SIN DESCRIPCION",
            "GrupoCategoria": cat["cpc_codigo"].str[0].map(cfg.SECCIONES_CPC).fillna("Otra"),
        })
    else:
        dim_categoria = pd.DataFrame(columns=["CodigoCPC", "DescripcionCategoria", "GrupoCategoria"])

    # ---------------- Hechos: columnas finales ----------------
    hechos = pd.DataFrame({
        "ID_Proceso": fact["ocid"].str[:100],
        "ID_Adjudicacion": fact["adjudicacion_id"].astype(str).str[:100],
        "FechaAdjudicacion": fact["fecha_adjudicacion"],
        "RUC": fact["ruc_dm"],
        "CodigoEntidad": fact["entidad_id"],
        "CodigoMetodo": fact["metodo_norm"].str[:100],
        "CodigoCPC": fact["cpc_codigo"].str[:30] if "cpc_codigo" in fact else None,
        "MontoAdjudicado": fact["monto"].fillna(0).round(2),
        "MontoContrato": fact["monto_contrato"].round(2),
        "NumOfertas": pd.to_numeric(fact["num_ofertas"], errors="coerce").astype("Int64") if "num_ofertas" in fact else pd.NA,
        "DiasAdjudicacion": pd.to_numeric(fact["dias_adjudicacion"], errors="coerce").astype("Int64"),
    })
    nulos_monto = fact["monto"].isna().sum()
    if nulos_monto:
        log.warning("%s adjudicaciones sin monto -> MontoAdjudicado = 0 (regla de negocio)", f"{nulos_monto:,}")

    if hasta is not None:
        hechos = hechos[hechos["FechaAdjudicacion"] <= hasta]
        log.info("Corte de la demo: solo adjudicaciones hasta %s", hasta.date())

    dims = {
        "DIM_PROVEEDOR": dim_proveedor,
        "DIM_ENTIDAD": dim_entidad,
        "DIM_METODO_CONTRATACION": dim_metodo,
        "DIM_CATEGORIA": dim_categoria,
    }
    for nombre, df in dims.items():
        log.info("%-24s %10s filas", nombre, f"{len(df):,}")
    log.info("%-24s %10s filas disponibles en staging", "FACT_CONTRATOS", f"{len(hechos):,}")
    return dims, hechos


# ===========================================================================
# SQL Server
# ===========================================================================
def conectar():
    import pyodbc

    s = cfg.SQL_SERVER
    partes = [f"DRIVER={{{s['driver']}}}", f"SERVER={s['server']}", f"DATABASE={s['database']}"]
    if s["trusted_connection"]:
        partes.append("Trusted_Connection=yes")
    else:
        partes += [f"UID={s['user']}", f"PWD={s['password']}"]
    if s.get("trust_server_certificate"):
        partes.append("TrustServerCertificate=yes")
    conn = pyodbc.connect(";".join(partes), autocommit=False)
    log.info("Conectado a %s / %s", s["server"], s["database"])
    return conn


def a_filas(df: pd.DataFrame) -> list[tuple]:
    """DataFrame -> tuplas con tipos de Python (NaN/NaT/NA -> None)."""
    columnas = []
    for c in df.columns:
        valores = df[c].tolist()
        columnas.append([None if (v is None or v is pd.NA or (not isinstance(v, str) and pd.isna(v))) else
                         (v.to_pydatetime() if isinstance(v, pd.Timestamp) else v) for v in valores])
    return list(zip(*columnas))


def insertar_masivo(conn, tabla: str, df: pd.DataFrame, lote: int = 50_000) -> None:
    cur = conn.cursor()
    cur.fast_executemany = True
    cols = ", ".join(f"[{c}]" for c in df.columns)
    marcas = ", ".join("?" * len(df.columns))
    sql = f"INSERT INTO {tabla} ({cols}) VALUES ({marcas})"
    filas = a_filas(df)
    for i in range(0, len(filas), lote):
        cur.executemany(sql, filas[i:i + lote])
    cur.close()


# Llave de negocio y columnas a actualizar de cada dimensión
DEF_DIMENSIONES = {
    "DIM_PROVEEDOR": ("RUC", ["RazonSocial_Anonimizada", "Provincia", "ActividadEconomica_CIIU",
                              "TipoContribuyente", "FechaInicioActividades"]),
    "DIM_ENTIDAD": ("CodigoEntidad", ["NombreEntidad", "NivelGobierno", "Sector", "Provincia"]),
    "DIM_METODO_CONTRATACION": ("CodigoMetodo", ["DescripcionMetodo", "CategoriaMetodo", "EsCompetitivo"]),
    "DIM_CATEGORIA": ("CodigoCPC", ["DescripcionCategoria", "GrupoCategoria"]),
}


LIMITES = {  # tamaño de cada columna de texto en SQL Server
    "RUC": 20, "RazonSocial_Anonimizada": 300, "Provincia": 100, "ActividadEconomica_CIIU": 400,
    "TipoContribuyente": 100, "CodigoEntidad": 100, "NombreEntidad": 300, "NivelGobierno": 60,
    "Sector": 60, "CodigoMetodo": 100, "DescripcionMetodo": 200, "CategoriaMetodo": 60,
    "CodigoCPC": 30, "DescripcionCategoria": 400, "GrupoCategoria": 100,
    "ID_Proceso": 100, "ID_Adjudicacion": 100,
}


def recortar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c, n in LIMITES.items():
        if c in df.columns:
            df[c] = df[c].map(lambda v: v[:n] if isinstance(v, str) else v)
    return df


def cargar_dimension(conn, nombre: str, df: pd.DataFrame) -> None:
    """Upsert (SCD tipo 1): actualiza atributos de las filas existentes e
    inserta las nuevas. No borra filas para no romper la integridad con los
    hechos ya cargados."""
    llave, atributos = DEF_DIMENSIONES[nombre]
    stg = f"stg.{nombre}"
    cur = conn.cursor()
    cur.execute(f"TRUNCATE TABLE {stg}")
    df = recortar(df).drop_duplicates(subset=llave, keep="last")
    insertar_masivo(conn, stg, df[[llave] + atributos])
    sets = ", ".join(f"d.[{a}] = s.[{a}]" for a in atributos)
    cols = ", ".join(f"[{c}]" for c in [llave] + atributos)
    vals = ", ".join(f"s.[{c}]" for c in [llave] + atributos)
    cur.execute(f"""
        MERGE dbo.{nombre} AS d
        USING {stg} AS s ON d.[{llave}] = s.[{llave}]
        WHEN MATCHED THEN UPDATE SET {sets}
        WHEN NOT MATCHED BY TARGET THEN INSERT ({cols}) VALUES ({vals})
        OUTPUT $action;""")
    acciones = [fila[0] for fila in cur.fetchall()]
    conn.commit()
    log.info("%-24s insertadas %8s | actualizadas %8s", nombre,
             f"{acciones.count('INSERT'):,}", f"{acciones.count('UPDATE'):,}")


def leer_watermark(conn) -> pd.Timestamp:
    cur = conn.cursor()
    cur.execute("SELECT FechaCorte FROM dbo.ETL_Watermark WHERE Tabla = 'FACT_CONTRATOS'")
    fila = cur.fetchone()
    if fila is None:
        raise RuntimeError("No existe la fila de FACT_CONTRATOS en ETL_Watermark. Ejecuta sql/etl_watermark.sql.")
    return pd.Timestamp(fila[0])


def cargar_hechos(conn, hechos: pd.DataFrame) -> None:
    # 1. Marca de agua actual
    marca = leer_watermark(conn)
    log.info("Marca de agua actual (FechaCorte): %s", marca)

    # 2. Solo registros nuevos
    nuevos = hechos[hechos["FechaAdjudicacion"] > marca]
    log.info("Registros en staging: %s | posteriores a la marca de agua: %s",
             f"{len(hechos):,}", f"{len(nuevos):,}")
    if nuevos.empty:
        log.info("-> Sin registros nuevos para cargar. La marca de agua no cambia.")
        cur = conn.cursor()
        cur.execute("UPDATE dbo.ETL_Watermark SET UltimaEjecucion = SYSDATETIME() WHERE Tabla = 'FACT_CONTRATOS'")
        conn.commit()
        return

    # 3. Subir a staging y dejar que SQL Server haga el lookup de llaves,
    #    el APPEND y el avance de la marca de agua en una sola transacción.
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE stg.FACT_CONTRATOS")
    insertar_masivo(conn, "stg.FACT_CONTRATOS", nuevos)
    conn.commit()
    cur.execute("EXEC etl.usp_CargarFactContratos")
    r = cur.fetchone()
    conn.commit()
    log.info("OK  Cargados %s registros nuevos (%s ya existían y se omitieron)",
             f"{r.Insertados:,}", f"{r.Omitidos:,}")
    log.info("Marca de agua: %s -> %s", r.WatermarkAnterior, r.WatermarkNuevo)


def resumen(conn) -> None:
    cur = conn.cursor()
    cur.execute("""
        SELECT t.Anio, COUNT(*) AS Contratos, SUM(f.MontoAdjudicado) AS Monto
        FROM dbo.FACT_CONTRATOS f JOIN dbo.DIM_TIEMPO t ON t.SK_Tiempo = f.FK_Tiempo
        GROUP BY t.Anio ORDER BY t.Anio""")
    log.info("Contenido de FACT_CONTRATOS por año:")
    for anio, n, monto in cur.fetchall():
        log.info("   %s  %10s contratos  USD %18s", anio, f"{n:,}", f"{monto:,.2f}")


def reiniciar(conn) -> None:
    cur = conn.cursor()
    cur.execute("EXEC etl.usp_ReiniciarCarga")
    conn.commit()
    log.info("FACT_CONTRATOS vaciada y marca de agua regresada a 1900-01-01.")


# ===========================================================================
def main() -> None:
    p = argparse.ArgumentParser(description="Carga del DataMart DM_ComprasPublicas (P3)")
    p.add_argument("--revisar", action="store_true", help="solo revisa las columnas de los CSV")
    p.add_argument("--sin-bd", action="store_true", help="arma el modelo en memoria sin conectarse")
    p.add_argument("--hasta", help="carga solo adjudicaciones hasta esta fecha (AAAA-MM-DD), para la demo")
    p.add_argument("--reiniciar", action="store_true", help="vacía los hechos y reinicia la marca de agua")
    args = p.parse_args()

    if args.revisar:
        sys.exit(0 if revisar_columnas() else 1)

    configurar_log()
    t0 = time.time()

    if args.reiniciar:
        conn = conectar()
        reiniciar(conn)
        conn.close()
        return

    hasta = pd.Timestamp(args.hasta) if args.hasta else None
    log.info("===== INICIO CARGA DM_ComprasPublicas =====")
    dims, hechos = construir_modelo(hasta)

    if args.sin_bd:
        log.info("Modo --sin-bd: no se escribió nada en SQL Server. (%.1fs)", time.time() - t0)
        return

    conn = conectar()
    try:
        log.info("--- Paso 1: dimensiones (upsert) ---")
        for nombre, df in dims.items():
            cargar_dimension(conn, nombre, df)
        log.info("--- Paso 2: hechos (incremental) ---")
        cargar_hechos(conn, hechos)
        resumen(conn)
    except Exception:
        conn.rollback()
        log.exception("La carga falló; se revirtió la transacción en curso.")
        raise
    finally:
        conn.close()
    log.info("===== FIN (%.1fs) =====", time.time() - t0)


if __name__ == "__main__":
    main()
