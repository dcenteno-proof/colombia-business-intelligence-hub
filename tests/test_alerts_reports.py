"""Reglas del centro de alertas y generación de reportes."""
import io

import pandas as pd
import pytest

from src.analytics.alerts import AlertEngine, evaluate_alerts, last_complete_month
from src.analytics.filters import Filters
from src.config import AlertThresholds
from src.reports import exporter
from tests.conftest import make_lines

T = AlertThresholds(sales_drop_pct=15, region_sales_drop_pct=20, margin_drop_pp=2, category_margin_drop_pp=3,
                    top_customer_share_pct=10, top10_customer_share_pct=50, cost_increase_pct=8, opex_ratio_pct=25,
                    opex_increase_pct=15, min_months_history=3, min_customers_concentration=20)


def _series(month_values: dict[str, int], cost: int = 70, region: str = "Andina", customers: int = 25):
    rows, vid = [], 0
    for mth, units in month_values.items():
        for c in range(customers):                        # misma venta repartida entre clientes
            vid += 1
            rows.append({"venta_id": vid, "fecha": f"{mth}-28", "cantidad": max(1, units // customers),
                         "precio_unitario": 100, "costo_unitario": cost, "cliente": f"C{c}", "cliente_id": c,
                         "region": region})
    return make_lines(rows)


EMPTY_SNAP = pd.DataFrame(columns=["fecha_corte", "producto_id", "producto", "stock_minimo", "activo", "cantidad",
                                   "valor"])
EMPTY_COST = pd.DataFrame(columns=["producto_id", "fecha_vigencia", "costo_unitario", "sku", "producto",
                                   "categoria"])


def _expenses(values: dict[str, int]) -> pd.DataFrame:
    return pd.DataFrame({"mes": list(values), "monto": list(values.values()),
                         "categoria_gasto": ["Nómina"] * len(values)})


def _run(lines, exp=None):
    exp = exp if exp is not None else _expenses({m: 1 for m in lines["mes"].unique()})
    return AlertEngine(lines, exp, EMPTY_SNAP, EMPTY_COST, T).run()


def test_sales_drop_triggers():
    lines = _series({"2025-01": 1000, "2025-02": 1000, "2025-03": 1000, "2025-04": 750})
    alerts, ev = _run(lines)
    assert "Caída de ventas" in set(alerts["regla"])
    row = alerts[alerts["regla"] == "Caída de ventas"].iloc[0]
    assert row["valor_observado"] == "-25,0 %"
    assert row["severidad"] == "Media"            # Alta sólo si la caída duplica el umbral (≤ -30 %)
    severe, _ = _run(_series({"2025-01": 1000, "2025-02": 1000, "2025-03": 1000, "2025-04": 600}))
    assert severe[severe["regla"] == "Caída de ventas"].iloc[0]["severidad"] == "Alta"
    assert row["recomendacion"] and row["motivo"] and row["indicador"]


def test_no_sales_alert_when_stable():
    lines = _series({"2025-01": 1000, "2025-02": 1000, "2025-03": 1000, "2025-04": 950})
    alerts, ev = _run(lines)
    assert "Caída de ventas" not in set(alerts["regla"])
    assert ev.set_index("regla").loc["Caída de ventas", "estado"] == "Sin alerta"


def test_insufficient_history_produces_no_alert():
    lines = _series({"2025-01": 1000, "2025-02": 100})
    alerts, ev = _run(lines)
    assert "Caída de ventas" not in set(alerts["regla"])
    assert ev.set_index("regla").loc["Caída de ventas", "estado"] == "Sin datos suficientes"


def test_margin_drop_triggers():
    base = _series({"2025-01": 1000, "2025-02": 1000, "2025-03": 1000}, cost=70)
    last = _series({"2025-04": 1000}, cost=78)
    last["venta_id"] += 10_000
    alerts, _ = _run(pd.concat([base, last], ignore_index=True))
    assert "Disminución de margen bruto" in set(alerts["regla"])


def test_concentration_rule():
    lines = _series({"2025-01": 1000, "2025-02": 1000, "2025-03": 1000, "2025-04": 1000}, customers=25)
    big = _series({"2025-04": 5000}, customers=1)
    big["venta_id"] += 50_000
    big["cliente"], big["cliente_id"] = "Grande", 999
    alerts, _ = _run(pd.concat([lines, big], ignore_index=True))
    assert any(alerts["titulo"].str.contains("Grande"))
    few = _series({"2025-01": 1000, "2025-02": 1000, "2025-03": 1000, "2025-04": 1000}, customers=5)
    _, ev = _run(few)
    assert ev.set_index("regla").loc["Concentración de ventas", "estado"] == "Sin datos suficientes"


def test_opex_rules():
    lines = _series({"2025-01": 1000, "2025-02": 1000, "2025-03": 1000, "2025-04": 1000})
    # ventas mensuales = 1.000 und x $100 = $100.000; gasto final $30.000 = 30 % y +50 % vs promedio
    exp = _expenses({"2025-01": 20_000, "2025-02": 20_000, "2025-03": 20_000, "2025-04": 30_000})
    alerts, _ = _run(lines, exp)
    titles = " ".join(alerts["titulo"])
    assert "crecieron" in titles            # +50 % vs promedio
    assert "equivalen" in titles            # 30 % de las ventas > 25 %


def test_last_complete_month():
    lines = make_lines([{"venta_id": 1, "fecha": "2025-03-29", "cantidad": 1, "precio_unitario": 1},
                        {"venta_id": 2, "fecha": "2025-04-10", "cantidad": 1, "precio_unitario": 1}])
    assert last_complete_month(lines) == "2025-03"      # abril incompleto


def test_demo_alerts_end_to_end(demo_dataset):
    alerts, ev, month = evaluate_alerts(demo_dataset.lines, demo_dataset.expenses, demo_dataset.snapshots,
                                        demo_dataset.costs)
    assert month == "2025-08"
    assert len(ev) == 7 and not (ev["estado"] == "Error").any()
    assert not alerts.empty
    assert {"Inventario bajo", "Aumento de costos"} <= set(alerts["regla"])     # escenarios DEMO


@pytest.mark.parametrize("builder", [exporter.commercial_report, exporter.financial_report,
                                     exporter.inventory_report, exporter.customers_report, exporter.alerts_report])
def test_reports_are_valid_excel(demo_dataset, builder):
    f = Filters("2025-05", "2025-08")
    xlsx, main = builder(demo_dataset, f)
    book = pd.read_excel(io.BytesIO(xlsx), sheet_name=None)
    assert "Notas" in book
    assert book["Notas"]["Valor"].astype(str).str.contains("DEMO").any()
    assert len(book) >= 3
    csv = exporter.to_csv(main).decode("utf-8-sig")
    assert ";" in csv.splitlines()[0]
