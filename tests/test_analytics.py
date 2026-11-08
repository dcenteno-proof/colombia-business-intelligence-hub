"""Indicadores comerciales, financieros, de inventario y segmentación RFM."""
from datetime import date

import pandas as pd
import pytest

from src.analytics import commercial, customers as cu, financial, operational as op
from src.analytics.filters import Filters, apply_expenses, apply_sales
from tests.conftest import make_lines


# ------------------------------------------------------------------ filtros
def test_filters_previous_period_and_dimensions():
    f = Filters("2025-04", "2025-06", regions=("Caribe",))
    prev = f.previous_period()
    assert (prev.start_month, prev.end_month) == ("2025-01", "2025-03")
    assert f.dimension_filtered
    assert apply_expenses(pd.DataFrame({"mes": ["2025-04"], "monto": [10]}), f) is None
    assert f.bounds() == (date(2025, 4, 1), date(2025, 6, 30))


def test_apply_sales_filters(demo_dataset):
    f = Filters("2025-03", "2025-04", regions=("Andina",))
    out = apply_sales(demo_dataset.lines, f)
    assert not out.empty
    assert set(out["region"]) == {"Andina"}
    assert out["mes"].min() >= "2025-03" and out["mes"].max() <= "2025-04"


# --------------------------------------------------------------- comercial
def test_by_dimension_and_concentration():
    lines = make_lines([
        {"venta_id": 1, "fecha": "2025-01-05", "cantidad": 6, "precio_unitario": 100, "cliente": "A", "cliente_id": 1},
        {"venta_id": 2, "fecha": "2025-01-06", "cantidad": 3, "precio_unitario": 100, "cliente": "B", "cliente_id": 2},
        {"venta_id": 3, "fecha": "2025-01-07", "cantidad": 1, "precio_unitario": 100, "cliente": "C", "cliente_id": 3},
    ])
    t = commercial.by_dimension(lines, "cliente")
    assert t["cliente"].tolist() == ["A", "B", "C"]
    assert t["participacion"].tolist() == pytest.approx([60, 30, 10])
    c = commercial.concentration(lines, "cliente")
    assert c["top1"] == pytest.approx(60)
    assert c["hhi"] == pytest.approx(60 ** 2 + 30 ** 2 + 10 ** 2)
    assert c["n_80pct"] == 2
    assert commercial.hhi_label(c["hhi"]) == "Alta"


def test_monthly_growth():
    lines = make_lines([
        {"venta_id": 1, "fecha": "2025-01-05", "cantidad": 10, "precio_unitario": 100},
        {"venta_id": 2, "fecha": "2025-02-05", "cantidad": 12, "precio_unitario": 100},
    ])
    m = commercial.monthly(lines)
    assert m["crecimiento"].iloc[0] is None or pd.isna(m["crecimiento"].iloc[0])
    assert m["crecimiento"].iloc[1] == pytest.approx(20.0)


def test_low_performers_flag():
    cur = make_lines([{"venta_id": i, "fecha": "2025-02-05", "cantidad": q, "precio_unitario": 100,
                       "producto": f"P{i}", "producto_id": i} for i, q in enumerate([50, 40, 30, 20, 2], start=1)])
    prev = make_lines([{"venta_id": 10 + i, "fecha": "2025-01-05", "cantidad": q, "precio_unitario": 100,
                        "producto": f"P{i}", "producto_id": i} for i, q in enumerate([50, 100, 30, 20, 2], start=1)])
    perf = commercial.product_performance(cur, prev).set_index("producto")
    assert perf.loc["P5", "bajo_rendimiento"]                # quintil inferior
    assert perf.loc["P2", "bajo_rendimiento"]                # cayó 60 %
    assert not perf.loc["P1", "bajo_rendimiento"]


# --------------------------------------------------------------- financiero
def test_income_statement_and_monthly_pnl():
    lines = make_lines([
        {"venta_id": 1, "fecha": "2025-01-05", "cantidad": 10, "precio_unitario": 100, "descuento": 50,
         "costo_unitario": 60},
        {"venta_id": 2, "fecha": "2025-02-05", "cantidad": 10, "precio_unitario": 100, "costo_unitario": 60},
    ])
    pnl = financial.income_statement(lines, 300).set_index("clave")["valor"]
    assert pnl["ventas_netas"] == 1950
    assert pnl["utilidad_bruta"] == 1950 - 1200
    assert pnl["utilidad_operacional"] == 750 - 300
    exp = pd.DataFrame({"mes": ["2025-01", "2025-02"], "monto": [100, 200]})
    m = financial.monthly_pnl(lines, exp)
    assert m["utilidad_operacional"].tolist() == [950 - 600 - 100, 1000 - 600 - 200]
    assert m["var_ventas_netas_pct"].iloc[1] == pytest.approx((1000 - 950) / 950 * 100)
    no_opex = financial.monthly_pnl(lines, None)
    assert no_opex["margen_operacional"].isna().all()


# --------------------------------------------------------------- inventario
def _snapshots():
    rows = []
    for fecha, q1, q2 in [("2024-12-31", 100, 10), ("2025-01-31", 50, 3), ("2025-02-28", 150, 0)]:
        rows += [{"fecha_corte": fecha, "producto_id": 1, "producto": "P1", "categoria": "C", "sku": "S1",
                  "stock_minimo": 20, "activo": True, "cantidad": q1, "costo_unitario": 10, "valor": q1 * 10},
                 {"fecha_corte": fecha, "producto_id": 2, "producto": "P2", "categoria": "C", "sku": "S2",
                  "stock_minimo": 5, "activo": True, "cantidad": q2, "costo_unitario": 10, "valor": q2 * 10}]
    df = pd.DataFrame(rows)
    df["fecha_corte"] = pd.to_datetime(df["fecha_corte"])
    return df


def test_inventory_turnover_and_average():
    snaps = _snapshots()
    lines = make_lines([{"venta_id": 1, "fecha": "2025-01-10", "cantidad": 120, "precio_unitario": 15,
                         "costo_unitario": 10, "producto": "P1", "producto_id": 1}])
    avg = op.average_inventory(snaps, date(2025, 1, 1), date(2025, 2, 28))
    assert avg == pytest.approx((1100 + 530 + 1500) / 3)
    t = op.turnover_summary(lines, snaps, date(2025, 1, 1), date(2025, 2, 28))
    assert t["rotacion"] == pytest.approx(1200 / avg)
    assert t["dias_inventario"] == pytest.approx(59 / t["rotacion"])
    by = op.turnover_by(lines, snaps, date(2025, 1, 1), date(2025, 2, 28), "producto").set_index("producto")
    assert by.loc["P2", "rotacion"] == pytest.approx(0.0)
    empty = op.turnover_summary(lines, snaps.iloc[0:0], date(2025, 1, 1), date(2025, 2, 28))
    assert empty["rotacion"] is None


def test_low_stock_and_no_movement():
    snaps = _snapshots()
    low = op.low_stock(snaps)
    assert low["producto"].tolist() == ["P2"]       # 0 <= 5; P1 150 > 20
    movements = pd.DataFrame({"producto_id": [1, 2], "producto": ["P1", "P2"], "sku": ["S1", "S2"],
                              "categoria": ["C", "C"],
                              "ultima_salida": pd.to_datetime(["2025-02-20", "2024-10-01"])})
    snaps.loc[snaps["producto_id"] == 2, "cantidad"] = 7
    idle = op.no_movement(movements, snaps, date(2025, 2, 28), days=90)
    assert idle["producto"].tolist() == ["P2"]


def test_supplier_performance_handles_pending():
    p = pd.DataFrame({
        "compra_id": [1, 1, 2, 3], "proveedor": ["A", "A", "A", "B"], "estado": ["PARCIAL", "PARCIAL", "RECIBIDA",
                                                                                 "PENDIENTE"],
        "cantidad_pedida": [10, 10, 5, 8], "cantidad_recibida": [10, 5, 5, 0], "costo_unitario": [100] * 4,
        "fecha_orden": pd.to_datetime(["2025-01-01"] * 3 + ["2025-01-20"]),
        "fecha_esperada": pd.to_datetime(["2025-01-05", "2025-01-05", "2025-01-05", "2025-01-25"]),
        "fecha_recepcion": pd.to_datetime(["2025-01-07", "2025-01-07", "2025-01-04", None]),
    })
    s = op.supplier_performance(p).set_index("proveedor")
    assert s.loc["A", "nivel_servicio"] == pytest.approx(20 / 25 * 100)
    assert s.loc["A", "entregas_a_tiempo"] == pytest.approx(50.0)
    assert s.loc["B", "nivel_servicio"] is None or pd.isna(s.loc["B", "nivel_servicio"])
    assert s.loc["B", "ordenes_pendientes"] == 1


def test_cost_changes():
    h = pd.DataFrame({"producto_id": [1, 1, 2], "sku": ["S1", "S1", "S2"], "producto": ["P1", "P1", "P2"],
                      "categoria": ["C"] * 3, "costo_unitario": [100, 112, 50],
                      "fecha_vigencia": pd.to_datetime(["2024-12-31", "2025-03-01", "2024-12-31"])})
    ch = op.cost_changes(h, date(2025, 3, 31), 90).set_index("producto")
    assert ch.loc["P1", "variacion_pct"] == pytest.approx(12.0)
    assert ch.loc["P2", "variacion_pct"] == pytest.approx(0.0)


# --------------------------------------------------------------------- RFM
def _rfm_lines(n=20):
    rows, vid = [], 0
    for c in range(1, n + 1):
        for k in range(c % 5 + 1):                       # frecuencia variable
            vid += 1
            rows.append({"venta_id": vid, "fecha": f"2025-0{1 + (c + k) % 6}-1{k}", "cantidad": c,
                         "precio_unitario": 1000, "cliente": f"C{c:02d}", "cliente_id": c})
    return make_lines(rows)


def test_rfm_scores_and_segments():
    r = cu.rfm(_rfm_lines(), date(2025, 7, 1))
    assert len(r) == 20
    assert r[["R", "F", "M"]].isin([1, 2, 3, 4, 5]).all().all()
    assert set(r["segmento"]) <= set(cu.SEGMENT_ACTIONS)
    best = r.sort_values("valor").iloc[-1]
    assert best["M"] == 5
    summary = cu.segment_summary(r)
    assert summary["clientes"].sum() == 20
    assert summary["participacion_valor"].sum() == pytest.approx(100)


def test_segment_rules():
    assert cu.segment_for(5, 5, 5) == "Campeones"
    assert cu.segment_for(3, 4, 4) == "Leales"
    assert cu.segment_for(5, 1, 2) == "Nuevos"
    assert cu.segment_for(1, 5, 5) == "En riesgo"
    assert cu.segment_for(2, 1, 1) == "Hibernando"
    assert cu.segment_for(1, 1, 1) == "Perdidos"


def test_rfm_insufficient_data():
    with pytest.raises(cu.InsufficientDataError):
        cu.rfm(_rfm_lines(5), date(2025, 7, 1))


def test_customer_metrics_frequency():
    lines = make_lines([
        {"venta_id": 1, "fecha": "2025-01-01", "cantidad": 1, "precio_unitario": 100},
        {"venta_id": 2, "fecha": "2025-01-11", "cantidad": 1, "precio_unitario": 100},
        {"venta_id": 3, "fecha": "2025-01-21", "cantidad": 1, "precio_unitario": 100},
    ])
    m = cu.customer_metrics(lines, date(2025, 2, 1)).iloc[0]
    assert m["frecuencia"] == 3 and m["valor"] == 300
    assert m["dias_entre_compras"] == pytest.approx(10.0)
    assert m["recencia_dias"] == 11


def test_activity_status(demo_dataset):
    ref = date(2025, 9, 1)
    st = cu.activity_status(demo_dataset.lines, demo_dataset.customers, ref, 90)
    assert set(st["estado"]) <= {"Activo", "Inactivo", "Sin compras"}
    assert (st["estado"] == "Activo").sum() > 0
