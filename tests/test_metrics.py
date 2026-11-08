"""Fórmulas: ventas netas, utilidad bruta, márgenes, crecimiento, ticket y rotación."""
import pytest

from src.analytics import metrics as mt
from tests.conftest import make_lines


def test_net_sales():
    assert mt.net_sales(1_000_000, 50_000, 20_000) == 930_000
    assert mt.net_sales(1_000_000) == 1_000_000
    with pytest.raises(ValueError):
        mt.net_sales(1000, -1, 0)


def test_gross_profit_and_margin():
    gp = mt.gross_profit(930_000, 700_000)
    assert gp == 230_000
    assert mt.gross_margin_pct(gp, 930_000) == pytest.approx(24.731, abs=1e-3)
    assert mt.gross_margin_pct(100, 0) is None          # sin ventas: no hay margen


def test_operating_profit_and_margin():
    op = mt.operating_profit(230_000, 180_000)
    assert op == 50_000
    assert mt.operating_margin_pct(op, 1_000_000) == pytest.approx(5.0)
    assert mt.operating_margin_pct(-50_000, 1_000_000) == pytest.approx(-5.0)


def test_growth():
    assert mt.growth_pct(110, 100) == pytest.approx(10.0)
    assert mt.growth_pct(90, 100) == pytest.approx(-10.0)
    assert mt.growth_pct(100, 0) is None
    assert mt.growth_pct(100, None) is None
    assert mt.growth_pct(100, -50) is None              # base negativa: no interpretable


def test_ticket_and_safe_divide():
    assert mt.average_ticket(1_000_000, 4) == 250_000
    assert mt.average_ticket(1_000_000, 0) is None
    assert mt.safe_divide(None, 3) is None
    assert mt.safe_divide(float("nan"), 3) is None


def test_inventory_turnover():
    assert mt.inventory_turnover(1_200_000, 300_000) == pytest.approx(4.0)
    assert mt.inventory_turnover(1_200_000, 0) is None
    assert mt.days_of_inventory(4.0, 360) == pytest.approx(90.0)
    assert mt.days_of_inventory(None, 360) is None


def test_change_pp():
    assert mt.change_pp(22.0, 24.5) == pytest.approx(-2.5)
    assert mt.change_pp(None, 24.5) is None


def test_enrich_lines_integer_arithmetic():
    lines = make_lines([
        # 10 und x 100 = 1000 brutas, descuento 100, devuelve 3 => devolución = 3 * (900/10) = 270
        {"venta_id": 1, "fecha": "2025-01-05", "cantidad": 10, "precio_unitario": 100, "descuento": 100,
         "cantidad_devuelta": 3, "costo_unitario": 60},
    ])
    r = lines.iloc[0]
    assert r["ventas_brutas"] == 1000
    assert r["devoluciones"] == 270
    assert r["ventas_netas"] == 630
    assert r["costo_ventas"] == 7 * 60
    assert r["utilidad_bruta"] == 630 - 420
    assert r["mes"] == "2025-01"
    assert str(lines["ventas_netas"].dtype).startswith("int")


def test_summarize_kpis():
    lines = make_lines([
        {"venta_id": 1, "fecha": "2025-01-05", "cantidad": 10, "precio_unitario": 100, "costo_unitario": 70},
        {"venta_id": 1, "fecha": "2025-01-05", "cantidad": 5, "precio_unitario": 200, "costo_unitario": 150,
         "descuento": 100},
        {"venta_id": 2, "fecha": "2025-01-09", "cantidad": 1, "precio_unitario": 1000, "costo_unitario": 500,
         "cliente_id": 2},
    ])
    s = mt.summarize(lines, opex_total=500)
    assert s["ventas_brutas"] == 3000
    assert s["ventas_netas"] == 2900
    assert s["costo_ventas"] == 700 + 750 + 500
    assert s["utilidad_bruta"] == 950
    assert s["margen_bruto"] == pytest.approx(950 / 2900 * 100)
    assert s["utilidad_operacional"] == 450
    assert s["transacciones"] == 2
    assert s["ticket_promedio"] == pytest.approx(1450)
    assert s["clientes_activos"] == 2


def test_summarize_without_attributable_opex():
    lines = make_lines([{"venta_id": 1, "fecha": "2025-01-05", "cantidad": 1, "precio_unitario": 100}])
    s = mt.summarize(lines, opex_total=None)
    assert s["utilidad_operacional"] is None and s["margen_operacional"] is None
