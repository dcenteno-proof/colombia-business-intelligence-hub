"""Proceso ETL: importación de archivos Excel/CSV a la base SQLite.

Etapas (cada una queda registrada en el resumen del proceso):
  1. Lectura del archivo (CSV con detección de separador/codificación, o Excel).
  2. Normalización de encabezados y validación de columnas obligatorias.
  3. Limpieza (espacios, celdas vacías, filas vacías).
  4. Detección de valores nulos en columnas obligatorias.
  5. Validación de tipos: fechas, cantidades e importes COP.
  6. Reglas de negocio (cantidades positivas, descuentos válidos, etc.).
  7. Normalización de categorías, regiones y nombres.
  8. Detección de duplicados (dentro del archivo y contra la base de datos).
  9. Validación de referencias (cliente, producto, vendedor existentes).
 10. Carga transaccional de los registros válidos.
 11. Registro en ``registro_importaciones`` y archivo CSV de errores.
"""
from __future__ import annotations

import io
import json
import re
import shutil
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import BinaryIO

import pandas as pd
from sqlalchemy import Engine, select

from src.config import PROCESSED_DIR, RAW_DIR
from src.database import models as m
from src.database.connection import get_engine, session_scope

SUPPORTED_EXTENSIONS = {".csv", ".txt", ".xlsx", ".xlsm"}
MIN_VALID_DATE = date(2000, 1, 1)


@dataclass(frozen=True)
class EntitySpec:
    required: tuple[str, ...]
    optional: tuple[str, ...]
    key: tuple[str, ...]
    dates: tuple[str, ...] = ()
    integers: tuple[str, ...] = ()       # cantidades: enteros
    money: tuple[str, ...] = ()          # importes COP: enteros (redondeo al peso)
    description: str = ""


SPECS: dict[str, EntitySpec] = {
    "clientes": EntitySpec(
        required=("codigo", "nombre", "tipo", "region", "ciudad"), optional=("fecha_registro",),
        key=("codigo",), dates=("fecha_registro",), description="Maestro de clientes"),
    "productos": EntitySpec(
        required=("sku", "nombre", "categoria", "precio_lista", "costo_unitario"),
        optional=("unidad", "stock_minimo", "proveedor_codigo"), key=("sku",),
        integers=("stock_minimo",), money=("precio_lista", "costo_unitario"), description="Maestro de productos"),
    "ventas": EntitySpec(
        required=("numero_factura", "fecha", "codigo_cliente", "sku", "cantidad", "precio_unitario"),
        optional=("descuento", "cantidad_devuelta", "codigo_vendedor", "canal"), key=("numero_factura", "sku"),
        dates=("fecha",), integers=("cantidad", "cantidad_devuelta"), money=("precio_unitario", "descuento"),
        description="Facturas de venta (una fila por línea de factura)"),
    "gastos": EntitySpec(
        required=("fecha", "categoria_gasto", "monto"), optional=("region", "descripcion"),
        key=("fecha", "categoria_gasto", "region", "descripcion", "monto"), dates=("fecha",), money=("monto",),
        description="Gastos operativos"),
}

ALIASES = {
    "factura": "numero_factura", "no_factura": "numero_factura", "num_factura": "numero_factura",
    "cliente": "codigo_cliente", "cod_cliente": "codigo_cliente", "cliente_codigo": "codigo_cliente",
    "vendedor": "codigo_vendedor", "cod_vendedor": "codigo_vendedor",
    "codigo_producto": "sku", "producto_sku": "sku", "referencia": "sku",
    "precio": "precio_unitario", "valor_unitario": "precio_unitario", "qty": "cantidad", "unidades": "cantidad",
    "devolucion": "cantidad_devuelta", "devoluciones": "cantidad_devuelta", "dcto": "descuento",
    "costo": "costo_unitario", "precio_venta": "precio_lista", "categoria_producto": "categoria",
    "valor": "monto", "importe": "monto", "categoria_de_gasto": "categoria_gasto", "concepto": "categoria_gasto",
    "tipo_cliente": "tipo", "nombre_cliente": "nombre", "nombre_producto": "nombre",
    "proveedor": "proveedor_codigo", "fecha_factura": "fecha",
}

CUSTOMER_TYPES = ["Tienda de barrio", "Minimercado", "Supermercado independiente", "HORECA", "Institucional"]


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def norm_key(value) -> str:
    """Clave de comparación: minúsculas, sin tildes, espacios simples."""
    return re.sub(r"\s+", " ", strip_accents(str(value)).strip().lower())


def normalize_header(col: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", norm_key(col)).strip("_")
    return ALIASES.get(key, key)


def clean_text(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = re.sub(r"\s+", " ", str(value)).strip()
    return s or None


_COP_THOUSANDS = re.compile(r"^-?\d{1,3}(\.\d{3})+(,\d+)?$")


def parse_number(value) -> float | None:
    """Convierte importes en formato colombiano o estándar: '$ 1.234.567', '1234567', '12500,5', '12500.0'."""
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return None if pd.isna(value) else float(value)
    s = str(value).strip().replace("$", "").replace("COP", "").replace(" ", "").replace(" ", "")
    if s == "":
        return None
    if _COP_THOUSANDS.match(s):
        s = s.replace(".", "").replace(",", ".")
    elif "," in s and "." not in s:
        s = s.replace(",", ".")
    elif "," in s and "." in s:          # formato 1,234,567.50
        s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S",
                "%d/%m/%y")


def parse_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else value.date()
    s = str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


@dataclass
class ETLResult:
    entidad: str
    archivo: str
    estado: str = "PENDIENTE"
    filas_leidas: int = 0
    filas_vacias: int = 0
    filas_validas: int = 0
    filas_cargadas: int = 0
    filas_rechazadas: int = 0
    duplicados_archivo: int = 0
    duplicados_base: int = 0
    nulos: dict[str, int] = field(default_factory=dict)
    columnas_faltantes: list[str] = field(default_factory=list)
    columnas_ignoradas: list[str] = field(default_factory=list)
    normalizaciones: int = 0
    pasos: list[str] = field(default_factory=list)
    errores: list[dict] = field(default_factory=list)
    archivo_errores: str | None = None
    validos: pd.DataFrame | None = None

    def add_error(self, fila: int | None, columna: str, valor, error: str) -> None:
        self.errores.append({"fila": fila, "columna": columna, "valor": None if valor is None else str(valor),
                             "error": error})

    def errors_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.errores, columns=["fila", "columna", "valor", "error"])

    def summary(self) -> dict:
        return {
            "entidad": self.entidad, "archivo": self.archivo, "estado": self.estado,
            "filas_leidas": self.filas_leidas, "filas_vacias": self.filas_vacias,
            "filas_validas": self.filas_validas, "filas_cargadas": self.filas_cargadas,
            "filas_rechazadas": self.filas_rechazadas, "duplicados_archivo": self.duplicados_archivo,
            "duplicados_base": self.duplicados_base, "nulos": self.nulos,
            "columnas_faltantes": self.columnas_faltantes, "columnas_ignoradas": self.columnas_ignoradas,
            "normalizaciones": self.normalizaciones, "errores": len(self.errores),
        }


# ------------------------------------------------------------------ lectura
def read_file(source: str | Path | BinaryIO | bytes, filename: str | None = None) -> pd.DataFrame:
    """Lee CSV o Excel como texto (dtype=str) para validar sin conversiones implícitas."""
    name = filename or (str(source) if isinstance(source, (str, Path)) else "archivo")
    ext = Path(name).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Formato no soportado: {ext or 'sin extensión'}. Use CSV o Excel (.xlsx).")
    if isinstance(source, (str, Path)):
        raw = Path(source).read_bytes()
    elif isinstance(source, bytes):
        raw = source
    else:
        raw = source.read()
    if not raw:
        raise ValueError("El archivo está vacío.")
    if ext in {".xlsx", ".xlsm"}:
        try:
            return pd.read_excel(io.BytesIO(raw), dtype=object, engine="openpyxl")
        except Exception as exc:  # archivo corrupto o no es Excel real
            raise ValueError(f"No fue posible leer el Excel: {exc}") from exc
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(io.BytesIO(raw), dtype=str, sep=None, engine="python", encoding=encoding,
                               keep_default_na=False)
        except (UnicodeDecodeError, pd.errors.ParserError, ValueError) as exc:
            last_error = exc
    raise ValueError(f"No fue posible leer el CSV: {last_error}")


# --------------------------------------------------------------- validación
def _reference_maps(engine: Engine) -> dict[str, dict[str, object]]:
    with session_scope(engine) as s:
        return {
            "regiones": {norm_key(r.nombre): r for r in s.scalars(select(m.Region))},
            "categorias": {norm_key(c.nombre): c for c in s.scalars(select(m.Categoria))},
            "clientes": {norm_key(c.codigo): c for c in s.scalars(select(m.Cliente))},
            "productos": {norm_key(p.sku): p for p in s.scalars(select(m.Producto))},
            "vendedores": {norm_key(v.codigo): v for v in s.scalars(select(m.Vendedor))},
            "proveedores": {norm_key(p.codigo): p for p in s.scalars(select(m.Proveedor))},
            "facturas": {norm_key(f) for f in s.scalars(select(m.Venta.numero_factura))},
            "categorias_gasto": {norm_key(c): c for c in
                                 s.scalars(select(m.GastoOperativo.categoria_gasto).distinct())},
            "gastos": {
                (g.fecha.isoformat(), norm_key(g.categoria_gasto), g.region_id, norm_key(g.descripcion or ""), g.monto)
                for g in s.scalars(select(m.GastoOperativo))
            },
        }


def validate(df: pd.DataFrame, entity: str, filename: str, engine: Engine | None = None) -> ETLResult:
    """Ejecuta las etapas 2 a 9 y devuelve el resultado con las filas válidas en ``result.validos``."""
    if entity not in SPECS:
        raise ValueError(f"Entidad no soportada: {entity}. Opciones: {', '.join(SPECS)}")
    engine = engine or get_engine()
    spec = SPECS[entity]
    res = ETLResult(entidad=entity, archivo=filename)
    res.filas_leidas = len(df)
    res.pasos.append(f"1. Lectura: {len(df)} filas y {len(df.columns)} columnas.")

    # 2. encabezados
    df = df.copy()
    df.columns = [normalize_header(c) for c in df.columns]
    df = df.loc[:, ~pd.Index(df.columns).duplicated()]
    res.columnas_faltantes = [c for c in spec.required if c not in df.columns]
    known = set(spec.required) | set(spec.optional)
    res.columnas_ignoradas = [c for c in df.columns if c not in known]
    if res.columnas_faltantes:
        res.estado = "FALLIDO"
        res.pasos.append(f"2. Columnas obligatorias faltantes: {', '.join(res.columnas_faltantes)}. Proceso detenido.")
        for c in res.columnas_faltantes:
            res.add_error(None, c, None, "Columna obligatoria no encontrada")
        return res
    for c in spec.optional:
        if c not in df.columns:
            df[c] = None
    df = df[list(spec.required) + list(spec.optional)]
    res.pasos.append("2. Estructura válida." + (f" Columnas ignoradas: {', '.join(res.columnas_ignoradas)}."
                                                if res.columnas_ignoradas else ""))

    # 3. limpieza
    for c in df.columns:
        df[c] = df[c].map(clean_text)
    df["_fila"] = df.index + 2  # fila del archivo (la 1 es el encabezado)
    empty = df[list(spec.required) + list(spec.optional)].isna().all(axis=1)
    res.filas_vacias = int(empty.sum())
    df = df[~empty]
    res.pasos.append(f"3. Limpieza de espacios y celdas vacías; filas vacías descartadas: {res.filas_vacias}.")

    # 4. nulos
    res.nulos = {c: int(df[c].isna().sum()) for c in df.columns if c != "_fila" and df[c].isna().any()}
    bad = pd.Series(False, index=df.index)
    for c in spec.required:
        for idx in df.index[df[c].isna()]:
            res.add_error(int(df.at[idx, "_fila"]), c, None, "Valor obligatorio vacío")
        bad |= df[c].isna()
    res.pasos.append(f"4. Nulos en columnas obligatorias: {int(bad.sum())} filas afectadas.")

    # 5. tipos
    today = date.today()
    for c in spec.dates:
        parsed = df[c].map(parse_date)
        for idx in df.index[df[c].notna() & parsed.isna()]:
            res.add_error(int(df.at[idx, "_fila"]), c, df.at[idx, c], "Fecha inválida (use AAAA-MM-DD o DD/MM/AAAA)")
            bad[idx] = True
        out_of_range = parsed.map(lambda d: d is not None and (d > today or d < MIN_VALID_DATE))
        for idx in df.index[out_of_range]:
            res.add_error(int(df.at[idx, "_fila"]), c, df.at[idx, c], "Fecha fuera de rango (futura o anterior a 2000)")
            bad[idx] = True
        df[c] = parsed
    for c in spec.integers + spec.money:
        parsed = df[c].map(parse_number)
        invalid = df[c].notna() & parsed.isna()
        if c in spec.integers:
            invalid |= parsed.notna() & parsed.map(lambda v: v is not None and not float(v).is_integer())
        for idx in df.index[invalid]:
            msg = "Cantidad inválida (debe ser un número entero)" if c in spec.integers else "Importe inválido"
            res.add_error(int(df.at[idx, "_fila"]), c, df.at[idx, c], msg)
            bad[idx] = True
        df[c] = pd.Series([None if v is None or pd.isna(v) else int(round(v)) for v in parsed],
                          index=df.index, dtype=object)
    res.pasos.append("5. Validación de tipos de fecha, cantidades e importes COP.")

    # 6. reglas de negocio
    def rule(mask: pd.Series, col: str, msg: str) -> None:
        mask = mask.fillna(False).astype(bool) & ~bad
        for idx in df.index[mask]:
            res.add_error(int(df.at[idx, "_fila"]), col, df.at[idx, col], msg)
            bad[idx] = True

    num = lambda c: pd.to_numeric(df[c], errors="coerce")  # noqa: E731
    if entity == "ventas":
        rule(num("cantidad") <= 0, "cantidad", "La cantidad debe ser mayor que cero")
        rule(num("precio_unitario") < 0, "precio_unitario", "El precio no puede ser negativo")
        rule(num("descuento") < 0, "descuento", "El descuento no puede ser negativo")
        rule(num("descuento") > num("cantidad") * num("precio_unitario"), "descuento",
             "El descuento supera el valor bruto de la línea")
        rule(num("cantidad_devuelta") < 0, "cantidad_devuelta", "La devolución no puede ser negativa")
        rule(num("cantidad_devuelta") > num("cantidad"), "cantidad_devuelta", "Se devuelven más unidades que las vendidas")
    elif entity == "productos":
        rule(num("precio_lista") < 0, "precio_lista", "El precio no puede ser negativo")
        rule(num("costo_unitario") < 0, "costo_unitario", "El costo no puede ser negativo")
        rule(num("stock_minimo") < 0, "stock_minimo", "El stock mínimo no puede ser negativo")
    elif entity == "gastos":
        rule(num("monto") <= 0, "monto", "El monto del gasto debe ser mayor que cero")
    res.pasos.append("6. Reglas de negocio aplicadas.")

    # 7. normalización y 9. referencias
    refs = _reference_maps(engine)
    changes = 0

    def normalize_col(col: str, mapping: dict, label: str, create_unknown: bool = False) -> None:
        nonlocal changes
        for idx in df.index[df[col].notna() & ~bad]:
            original = df.at[idx, col]
            hit = mapping.get(norm_key(original))
            if hit is None:
                if create_unknown:
                    canonical = original[:1].upper() + original[1:].lower()
                else:
                    res.add_error(int(df.at[idx, "_fila"]), col, original, f"{label} no existe en la base de datos")
                    bad[idx] = True
                    continue
            else:
                canonical = hit.nombre
            if canonical != original:
                changes += 1
            df.at[idx, col] = canonical

    if entity == "clientes":
        normalize_col("region", refs["regiones"], "Región")
        types = {norm_key(t): t for t in CUSTOMER_TYPES}
        for idx in df.index[df["tipo"].notna()]:
            canonical = types.get(norm_key(df.at[idx, "tipo"]), df.at[idx, "tipo"])
            changes += canonical != df.at[idx, "tipo"]
            df.at[idx, "tipo"] = canonical
        df["codigo"] = df["codigo"].str.upper()
    elif entity == "productos":
        normalize_col("categoria", refs["categorias"], "Categoría", create_unknown=True)
        df["sku"] = df["sku"].str.upper()
        for idx in df.index[df["proveedor_codigo"].notna() & ~bad]:
            if norm_key(df.at[idx, "proveedor_codigo"]) not in refs["proveedores"]:
                res.add_error(int(df.at[idx, "_fila"]), "proveedor_codigo", df.at[idx, "proveedor_codigo"],
                              "Proveedor no existe en la base de datos")
                bad[idx] = True
    elif entity == "ventas":
        for col, key, label in (("codigo_cliente", "clientes", "Cliente"), ("sku", "productos", "Producto")):
            for idx in df.index[df[col].notna() & ~bad]:
                if norm_key(df.at[idx, col]) not in refs[key]:
                    res.add_error(int(df.at[idx, "_fila"]), col, df.at[idx, col], f"{label} no existe en la base de datos")
                    bad[idx] = True
        for idx in df.index[df["codigo_vendedor"].notna() & ~bad]:
            if norm_key(df.at[idx, "codigo_vendedor"]) not in refs["vendedores"]:
                res.add_error(int(df.at[idx, "_fila"]), "codigo_vendedor", df.at[idx, "codigo_vendedor"],
                              "Vendedor no existe en la base de datos")
                bad[idx] = True
        # coherencia del encabezado: misma fecha y cliente en todas las líneas de una factura
        ok = df[~bad]
        inconsistent = ok.groupby(ok["numero_factura"].map(norm_key)).agg(
            f=("fecha", "nunique"), c=("codigo_cliente", lambda s: s.map(norm_key).nunique()))
        inconsistent = set(inconsistent.index[(inconsistent.f > 1) | (inconsistent.c > 1)])
        for idx in df.index[~bad & df["numero_factura"].map(norm_key).isin(inconsistent)]:
            res.add_error(int(df.at[idx, "_fila"]), "numero_factura", df.at[idx, "numero_factura"],
                          "La factura tiene fechas o clientes diferentes entre sus líneas")
            bad[idx] = True
        df["descuento"] = df["descuento"].map(lambda v: 0 if v is None else v)
        df["cantidad_devuelta"] = df["cantidad_devuelta"].map(lambda v: 0 if v is None else v)
    elif entity == "gastos":
        for idx in df.index[df["region"].notna() & ~bad]:
            if norm_key(df.at[idx, "region"]) in {"corporativo", "nacional", "general"}:
                df.at[idx, "region"] = None
        normalize_col("region", refs["regiones"], "Región")
        for idx in df.index[df["categoria_gasto"].notna()]:
            v = df.at[idx, "categoria_gasto"]
            canonical = refs["categorias_gasto"].get(norm_key(v)) or v[:1].upper() + v[1:].lower()
            changes += canonical != v
            df.at[idx, "categoria_gasto"] = canonical
    res.normalizaciones = int(changes)
    res.pasos.append(f"7. Normalización de nombres/categorías/regiones: {res.normalizaciones} valores ajustados.")

    # 8. duplicados
    valid = df[~bad].copy()
    key_series = valid[list(spec.key)].apply(lambda r: tuple(norm_key(v) if v is not None else "" for v in r), axis=1)
    dup_file = key_series.duplicated(keep="first")
    res.duplicados_archivo = int(dup_file.sum())
    for idx in valid.index[dup_file]:
        res.add_error(int(valid.at[idx, "_fila"]), ",".join(spec.key), " | ".join(str(v) for v in key_series[idx]),
                      "Registro duplicado dentro del archivo")
    valid = valid[~dup_file]

    if entity == "clientes":
        in_db = valid["codigo"].map(norm_key).isin(refs["clientes"].keys())
    elif entity == "productos":
        in_db = valid["sku"].map(norm_key).isin(refs["productos"].keys())
    elif entity == "ventas":
        in_db = valid["numero_factura"].map(norm_key).isin(refs["facturas"])
    else:
        region_ids = {r.nombre: r.id for r in refs["regiones"].values()}
        in_db = valid.apply(lambda r: (r["fecha"].isoformat(), norm_key(r["categoria_gasto"]),
                                       region_ids.get(r["region"]), norm_key(r["descripcion"] or ""),
                                       r["monto"]) in refs["gastos"], axis=1) if not valid.empty else \
            pd.Series(dtype=bool)
    res.duplicados_base = int(in_db.sum())
    valid = valid[~in_db] if len(in_db) else valid
    res.pasos.append(f"8. Duplicados: {res.duplicados_archivo} en el archivo y {res.duplicados_base} ya existentes "
                     "en la base (se omiten sin error).")

    rejected_rows = {e["fila"] for e in res.errores if e["fila"] is not None
                     and e["error"] != "Registro duplicado dentro del archivo"}
    res.filas_rechazadas = len(rejected_rows)
    res.filas_validas = len(valid)
    res.validos = valid
    res.pasos.append(f"9. Referencias validadas. Filas válidas para cargar: {res.filas_validas}; "
                     f"rechazadas: {res.filas_rechazadas}.")
    res.estado = "VALIDADO"
    return res


# --------------------------------------------------------------------- carga
def _load(res: ETLResult, engine: Engine) -> int:
    df = res.validos
    if df is None or df.empty:
        return 0
    origin = f"IMPORTACION:{Path(res.archivo).name}"[:80]
    with session_scope(engine) as s:
        regions = {r.nombre: r for r in s.scalars(select(m.Region))}
        if res.entidad == "clientes":
            for _, r in df.iterrows():
                s.add(m.Cliente(codigo=r["codigo"], nombre=r["nombre"], tipo=r["tipo"],
                                region_id=regions[r["region"]].id, ciudad=r["ciudad"],
                                fecha_registro=r["fecha_registro"] or date.today(), origen=origin))
        elif res.entidad == "productos":
            cats = {c.nombre: c for c in s.scalars(select(m.Categoria))}
            sups = {norm_key(p.codigo): p for p in s.scalars(select(m.Proveedor))}
            for _, r in df.iterrows():
                cat = cats.get(r["categoria"])
                if cat is None:
                    cat = m.Categoria(nombre=r["categoria"], descripcion="Creada por importación")
                    s.add(cat)
                    s.flush()
                    cats[cat.nombre] = cat
                sup = sups.get(norm_key(r["proveedor_codigo"])) if r["proveedor_codigo"] else None
                prod = m.Producto(sku=r["sku"], nombre=r["nombre"], categoria_id=cat.id,
                                  proveedor_id=sup.id if sup else None, unidad=r["unidad"] or "UND",
                                  precio_lista=r["precio_lista"], costo_unitario=r["costo_unitario"],
                                  stock_minimo=r["stock_minimo"] or 0, origen=origin)
                s.add(prod)
                s.flush()
                s.add(m.Costo(producto_id=prod.id, fecha_vigencia=date.today(), costo_unitario=r["costo_unitario"],
                              motivo="Costo inicial (importación)"))
        elif res.entidad == "ventas":
            clients = {norm_key(c.codigo): c for c in s.scalars(select(m.Cliente))}
            prods = {norm_key(p.sku): p for p in s.scalars(select(m.Producto))}
            sellers = {norm_key(v.codigo): v for v in s.scalars(select(m.Vendedor))}
            for invoice, lines in df.groupby(df["numero_factura"].map(str.upper), sort=False):
                first = lines.iloc[0]
                cli = clients[norm_key(first["codigo_cliente"])]
                seller = sellers.get(norm_key(first["codigo_vendedor"])) if first["codigo_vendedor"] else None
                sale = m.Venta(numero_factura=invoice, fecha=first["fecha"], cliente_id=cli.id,
                               vendedor_id=seller.id if seller else None, region_id=cli.region_id,
                               canal=first["canal"] or "Sin canal", origen=origin)
                for _, ln in lines.iterrows():
                    prod = prods[norm_key(ln["sku"])]
                    sale.detalles.append(m.DetalleVenta(
                        producto_id=prod.id, cantidad=ln["cantidad"], precio_unitario=ln["precio_unitario"],
                        descuento=ln["descuento"], cantidad_devuelta=ln["cantidad_devuelta"],
                        costo_unitario=prod.costo_unitario))
                s.add(sale)
        elif res.entidad == "gastos":
            for _, r in df.iterrows():
                s.add(m.GastoOperativo(fecha=r["fecha"], categoria_gasto=r["categoria_gasto"],
                                       region_id=regions[r["region"]].id if r["region"] else None,
                                       descripcion=r["descripcion"], monto=r["monto"], origen=origin))
    return len(df)


def _write_log(res: ETLResult, engine: Engine) -> None:
    detail = res.summary() | {"pasos": res.pasos, "muestra_errores": res.errores[:50]}
    with session_scope(engine) as s:
        s.add(m.RegistroImportacion(archivo=res.archivo[:255], entidad=res.entidad, filas_leidas=res.filas_leidas,
                                    filas_cargadas=res.filas_cargadas, filas_rechazadas=res.filas_rechazadas,
                                    duplicados=res.duplicados_archivo + res.duplicados_base, estado=res.estado,
                                    detalle=json.dumps(detail, ensure_ascii=False, default=str)))


def run_etl(source, entity: str, filename: str | None = None, engine: Engine | None = None,
            dry_run: bool = False, keep_copy: bool = True, errors_dir: Path | None = None) -> ETLResult:
    """Ejecuta el ETL completo. ``dry_run=True`` sólo valida (no carga ni registra)."""
    engine = engine or get_engine()
    filename = filename or (Path(source).name if isinstance(source, (str, Path)) else "archivo")
    try:
        raw_df = read_file(source, filename)
    except ValueError as exc:
        res = ETLResult(entidad=entity, archivo=filename, estado="FALLIDO")
        res.add_error(None, "-", None, str(exc))
        res.pasos.append(f"1. Lectura fallida: {exc}")
        if not dry_run:
            _write_log(res, engine)
        return res

    res = validate(raw_df, entity, filename, engine)
    if dry_run:
        return res
    if res.estado != "FALLIDO":
        try:
            res.filas_cargadas = _load(res, engine)
            res.pasos.append(f"10. Carga transaccional: {res.filas_cargadas} filas insertadas.")
        except Exception as exc:  # la transacción se revierte completa
            res.filas_cargadas = 0
            res.estado = "FALLIDO"
            res.add_error(None, "-", None, f"Error al cargar en la base de datos: {exc}")
            res.pasos.append("10. Carga revertida por error de base de datos.")
        else:
            if res.filas_cargadas == 0:
                res.estado = "SIN_CAMBIOS"
            elif res.errores:
                res.estado = "PARCIAL"
            else:
                res.estado = "EXITOSO"

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if res.errores:
        err_dir = Path(errors_dir) if errors_dir else PROCESSED_DIR / "etl_errores"
        err_dir.mkdir(parents=True, exist_ok=True)
        err_path = err_dir / f"{stamp}_{entity}_{Path(filename).stem}_errores.csv"
        res.errors_frame().to_csv(err_path, index=False, encoding="utf-8-sig")
        res.archivo_errores = str(err_path)
    if keep_copy and isinstance(source, (str, Path)) and Path(source).exists():
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        if Path(source).resolve().parent != RAW_DIR.resolve():
            shutil.copy2(source, RAW_DIR / f"{stamp}_{Path(filename).name}")
    elif keep_copy and isinstance(source, bytes):
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        (RAW_DIR / f"{stamp}_{Path(filename).name}").write_bytes(source)
    res.pasos.append(f"11. Registro del proceso: estado {res.estado}.")
    _write_log(res, engine)
    return res
