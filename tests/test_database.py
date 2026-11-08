"""Conexión SQLite, creación de tablas, restricciones y carga de datos DEMO."""
from datetime import date

import pandas as pd
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.database import models as m
from src.database import repository as repo
from src.database.connection import check_connection, is_populated, session_scope, table_names

EXPECTED_TABLES = {"regiones", "vendedores", "categorias", "proveedores", "productos", "clientes", "ventas",
                   "detalle_ventas", "compras", "detalle_compras", "inventario", "movimientos_inventario",
                   "gastos_operativos", "costos", "registro_importaciones"}


def test_connection(engine):
    assert check_connection(engine) is True


def test_tables_created(engine):
    assert EXPECTED_TABLES <= set(table_names(engine))
    assert is_populated(engine) is False


def test_foreign_keys_enforced(engine):
    with pytest.raises(IntegrityError):
        with session_scope(engine) as s:
            s.add(m.Producto(sku="X-1", nombre="Huérfano", categoria_id=999, precio_lista=100, costo_unitario=80))


def test_check_constraints(engine):
    with session_scope(engine) as s:
        s.add(m.Categoria(id=1, nombre="Cat"))
    with pytest.raises(IntegrityError):
        with session_scope(engine) as s:
            s.add(m.Producto(sku="X-2", nombre="Precio negativo", categoria_id=1, precio_lista=-1, costo_unitario=80))


def test_unique_constraint(engine):
    with session_scope(engine) as s:
        s.add(m.Categoria(nombre="Única"))
    with pytest.raises(IntegrityError):
        with session_scope(engine) as s:
            s.add(m.Categoria(nombre="Única"))


def test_return_cannot_exceed_quantity(engine):
    with session_scope(engine) as s:
        s.add_all([m.Region(id=1, codigo="R", nombre="R", ciudad_principal="C"), m.Categoria(id=1, nombre="C"),
                   m.Producto(id=1, sku="P", nombre="P", categoria_id=1, precio_lista=100, costo_unitario=70),
                   m.Cliente(id=1, codigo="C1", nombre="C1", tipo="T", region_id=1, ciudad="X",
                             fecha_registro=date(2025, 1, 1))])
    with pytest.raises(IntegrityError):
        with session_scope(engine) as s:
            v = m.Venta(numero_factura="F1", fecha=date(2025, 1, 2), cliente_id=1, region_id=1)
            v.detalles.append(m.DetalleVenta(producto_id=1, cantidad=2, precio_unitario=100, descuento=0,
                                             cantidad_devuelta=3, costo_unitario=70))
            s.add(v)


def test_demo_load_counts(demo_engine):
    counts = repo.table_counts(demo_engine).set_index("tabla")["registros"]
    for table in ["regiones", "productos", "clientes", "ventas", "detalle_ventas", "compras", "inventario",
                  "movimientos_inventario", "gastos_operativos", "costos"]:
        assert counts[table] > 0, table
    assert is_populated(demo_engine)


def test_demo_data_is_labeled(demo_engine):
    with demo_engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM clientes WHERE codigo NOT LIKE 'DEMO-%'")).scalar() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM ventas WHERE origen <> 'DEMO'")).scalar() == 0


def test_kardex_matches_inventory_snapshot(demo_engine):
    snaps = repo.inventory_snapshots(demo_engine)
    last = snaps[snaps["fecha_corte"] == snaps["fecha_corte"].max()].set_index("producto_id")["cantidad"]
    kardex = repo.movements_summary(demo_engine).set_index("producto_id")["saldo_kardex"]
    assert (kardex.reindex(last.index) == last).all()
    assert (snaps["cantidad"] >= 0).all()


def test_parameterized_query_filters_dates(demo_engine):
    df = repo.sales_lines(demo_engine, date(2025, 3, 1), date(2025, 3, 31))
    assert not df.empty
    assert df["fecha"].min() >= pd.Timestamp("2025-03-01")
    assert df["fecha"].max() <= pd.Timestamp("2025-03-31")


def test_read_table_rejects_unknown_table(demo_engine):
    with pytest.raises(ValueError):
        repo.read_table("ventas; DROP TABLE ventas", demo_engine)
