"""Inteligencia comercial: ventas por dimensión, tendencias, rankings y concentración."""
from __future__ import annotations

import pandas as pd

from src.analytics.metrics import growth_pct, pct, safe_divide

DIMENSIONS = {"producto": "Producto", "categoria": "Categoría", "region": "Región", "vendedor": "Vendedor",
              "cliente": "Cliente", "canal": "Canal", "tipo_cliente": "Tipo de cliente"}


def by_dimension(lines: pd.DataFrame, dim: str) -> pd.DataFrame:
    """Ventas netas, utilidad bruta, margen, unidades, transacciones y participación por dimensión."""
    cols = [dim, "ventas_netas", "utilidad_bruta", "margen_bruto", "unidades", "transacciones",
            "ticket_promedio", "participacion"]
    if lines.empty:
        return pd.DataFrame(columns=cols)
    g = lines.groupby(dim, dropna=False).agg(
        ventas_netas=("ventas_netas", "sum"), utilidad_bruta=("utilidad_bruta", "sum"),
        unidades=("unidades_netas", "sum"), transacciones=("venta_id", "nunique")).reset_index()
    total = g["ventas_netas"].sum()
    g["margen_bruto"] = [pct(u, v) for u, v in zip(g["utilidad_bruta"], g["ventas_netas"])]
    g["ticket_promedio"] = [safe_divide(v, t) for v, t in zip(g["ventas_netas"], g["transacciones"])]
    g["participacion"] = [pct(v, total) for v in g["ventas_netas"]]
    return g.sort_values("ventas_netas", ascending=False)[cols].reset_index(drop=True)


def monthly(lines: pd.DataFrame) -> pd.DataFrame:
    cols = ["mes", "ventas_netas", "utilidad_bruta", "transacciones", "clientes", "ticket_promedio",
            "margen_bruto", "crecimiento"]
    if lines.empty:
        return pd.DataFrame(columns=cols)
    g = lines.groupby("mes").agg(ventas_netas=("ventas_netas", "sum"), utilidad_bruta=("utilidad_bruta", "sum"),
                                 transacciones=("venta_id", "nunique"), clientes=("cliente_id", "nunique")
                                 ).reset_index().sort_values("mes")
    g["ticket_promedio"] = [safe_divide(v, t) for v, t in zip(g["ventas_netas"], g["transacciones"])]
    g["margen_bruto"] = [pct(u, v) for u, v in zip(g["utilidad_bruta"], g["ventas_netas"])]
    prev = g["ventas_netas"].shift(1)
    g["crecimiento"] = [growth_pct(c, p) if pd.notna(p) else None for c, p in zip(g["ventas_netas"], prev)]
    return g[cols].reset_index(drop=True)


def monthly_by(lines: pd.DataFrame, dim: str) -> pd.DataFrame:
    if lines.empty:
        return pd.DataFrame(columns=["mes", dim, "ventas_netas"])
    return lines.groupby(["mes", dim]).ventas_netas.sum().reset_index().sort_values("mes")


def product_performance(current: pd.DataFrame, previous: pd.DataFrame | None,
                        bottom_share: float = 0.2, decline_pct: float = -30.0) -> pd.DataFrame:
    """Tabla por producto con crecimiento frente al periodo anterior y bandera de bajo rendimiento.

    Bajo rendimiento = producto en el quintil inferior de ventas netas del periodo,
    o con caída mayor al 30 % frente al periodo anterior (si existe base comparable).
    """
    cur = by_dimension(current, "producto")
    if cur.empty:
        return cur
    cat = current.groupby("producto")["categoria"].first()
    cur.insert(1, "categoria", cur["producto"].map(cat))
    if previous is not None and not previous.empty:
        prev = previous.groupby("producto").ventas_netas.sum()
        cur["ventas_periodo_anterior"] = cur["producto"].map(prev)
        cur["crecimiento"] = [growth_pct(c, p) if pd.notna(p) else None
                              for c, p in zip(cur["ventas_netas"], cur["ventas_periodo_anterior"])]
    else:
        cur["ventas_periodo_anterior"] = None
        cur["crecimiento"] = None
    threshold = cur["ventas_netas"].quantile(bottom_share)
    reasons = []
    for _, r in cur.iterrows():
        rs = []
        if r["ventas_netas"] <= threshold:
            rs.append("Quintil inferior de ventas")
        if r["crecimiento"] is not None and pd.notna(r["crecimiento"]) and r["crecimiento"] < decline_pct:
            rs.append(f"Caída {r['crecimiento']:.0f} % vs periodo anterior")
        reasons.append("; ".join(rs))
    cur["motivo_bajo_rendimiento"] = reasons
    cur["bajo_rendimiento"] = cur["motivo_bajo_rendimiento"] != ""
    return cur


def concentration(lines: pd.DataFrame, dim: str = "cliente") -> dict:
    """Concentración de ingresos: participación top-1/5/10, índice HHI y curva de Pareto.

    HHI = Σ (participación %)²; < 1.500 baja, 1.500-2.500 moderada, > 2.500 alta
    (escala usual de 0 a 10.000).
    """
    empty = {"n": 0, "top1": None, "top5": None, "top10": None, "top20pct": None, "hhi": None,
             "n_80pct": None, "pareto": pd.DataFrame(columns=[dim, "ventas_netas", "participacion", "acumulado"])}
    if lines.empty:
        return empty
    s = lines.groupby(dim).ventas_netas.sum().sort_values(ascending=False)
    s = s[s > 0]
    total = s.sum()
    if total <= 0:
        return empty
    share = s / total * 100
    cum = share.cumsum()
    n = len(s)
    k20 = max(1, int(round(n * 0.2)))
    pareto = pd.DataFrame({dim: s.index, "ventas_netas": s.values, "participacion": share.values,
                           "acumulado": cum.values})
    return {"n": n, "top1": float(share.iloc[:1].sum()), "top5": float(share.iloc[:5].sum()),
            "top10": float(share.iloc[:10].sum()), "top20pct": float(share.iloc[:k20].sum()),
            "hhi": float((share ** 2).sum()), "n_80pct": int((cum < 80).sum() + 1), "pareto": pareto}


def hhi_label(hhi: float | None) -> str:
    if hhi is None:
        return "N/D"
    return "Baja" if hhi < 1500 else ("Moderada" if hhi <= 2500 else "Alta")
