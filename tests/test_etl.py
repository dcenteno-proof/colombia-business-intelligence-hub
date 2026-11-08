"""ETL: lectura de CSV/Excel, validaciones, normalización, duplicados y bitácora."""
import pandas as pd
import pytest
from sqlalchemy import text

from src.data import etl
from src.data.sample_files import write_samples


@pytest.fixture()
def samples(tmp_path):
    return dict(zip(["ventas", "clientes", "productos", "gastos"], write_samples(tmp_path / "sample")))


def run(source, entity, engine, tmp_path, **kw):
    return etl.run_etl(source, entity, engine=engine, keep_copy=False, errors_dir=tmp_path / "err", **kw)


def test_parsers():
    assert etl.parse_number("$ 1.234.567") == 1234567
    assert etl.parse_number("12.500") == 12500
    assert etl.parse_number("12500,5") == 12500.5
    assert etl.parse_number("1,5") == 1.5
    assert etl.parse_number("abc") is None
    assert str(etl.parse_date("31/12/2025")) == "2025-12-31"
    assert str(etl.parse_date("2025-12-31")) == "2025-12-31"
    assert etl.parse_date("31/02/2025") is None
    assert etl.normalize_header("  Código Cliente ") == "codigo_cliente"
    assert etl.normalize_header("Factura") == "numero_factura"


def test_csv_sales_import(seeded_engine, samples, tmp_path):
    before = pd.read_sql("SELECT COUNT(*) n FROM ventas", seeded_engine)["n"][0]
    res = run(samples["ventas"], "ventas", seeded_engine, tmp_path)
    assert res.estado == "PARCIAL"
    assert res.filas_leidas == 16 and res.filas_vacias == 1
    assert res.duplicados_archivo == 1
    assert res.filas_cargadas == 7
    errors = set(res.errors_frame()["error"])
    assert "Valor obligatorio vacío" in errors
    assert any("Fecha inválida" in e for e in errors)
    assert "La cantidad debe ser mayor que cero" in errors
    assert "Cliente no existe en la base de datos" in errors
    assert "El descuento supera el valor bruto de la línea" in errors
    assert "Se devuelven más unidades que las vendidas" in errors
    assert any("número entero" in e for e in errors)
    after = pd.read_sql("SELECT COUNT(*) n FROM ventas", seeded_engine)["n"][0]
    assert after - before == 4   # 4 facturas válidas (IMP-FV-0001, 0002, 0003, 0010)
    amounts = pd.read_sql("SELECT precio_unitario, descuento FROM detalle_ventas d JOIN ventas v ON v.id=d.venta_id "
                          "WHERE v.numero_factura='IMP-FV-0001' ORDER BY d.id", seeded_engine)
    assert amounts["precio_unitario"].tolist() == [2400, 4550]   # '2.400' -> 2400 COP
    assert amounts["descuento"].tolist() == [0, 1000]
    assert res.archivo_errores and (tmp_path / "err").exists()


def test_reimport_is_idempotent(seeded_engine, samples, tmp_path):
    run(samples["ventas"], "ventas", seeded_engine, tmp_path)
    res = run(samples["ventas"], "ventas", seeded_engine, tmp_path)
    assert res.estado == "SIN_CAMBIOS"
    assert res.filas_cargadas == 0
    assert res.duplicados_base == 7


def test_excel_customers_import_normalizes(seeded_engine, samples, tmp_path):
    res = run(samples["clientes"], "clientes", seeded_engine, tmp_path)
    assert res.filas_cargadas == 4
    assert res.duplicados_archivo == 1 and res.duplicados_base == 1
    df = pd.read_sql("SELECT c.codigo, c.tipo, r.nombre region, c.nombre FROM clientes c JOIN regiones r "
                     "ON r.id=c.region_id WHERE c.codigo LIKE 'IMP-%' ORDER BY c.codigo", seeded_engine)
    assert df["region"].tolist() == ["Andina", "Caribe", "Pacífico", "Antioquia"]
    assert df["tipo"].tolist()[:3] == ["Tienda de barrio", "Minimercado", "HORECA"]
    assert df["nombre"].iloc[3] == "Supermercado La Loma DEMO-IMP4"   # espacios normalizados
    assert "Región no existe en la base de datos" in set(res.errors_frame()["error"])


def test_products_import_creates_normalized_category(seeded_engine, samples, tmp_path):
    res = run(samples["productos"], "productos", seeded_engine, tmp_path)
    assert res.filas_cargadas == 3
    cats = pd.read_sql("SELECT nombre FROM categorias", seeded_engine)["nombre"].tolist()
    assert "Mascotas" in cats
    assert "bebidas" not in cats and "BEBIDAS" not in cats
    prod = pd.read_sql("SELECT p.sku, c.nombre cat FROM productos p JOIN categorias c ON c.id=p.categoria_id "
                       "WHERE p.sku='IMP-SKU-001'", seeded_engine)
    assert prod["cat"][0] == "Bebidas"


def test_expenses_excel_import(seeded_engine, samples, tmp_path):
    res = run(samples["gastos"], "gastos", seeded_engine, tmp_path)
    assert res.filas_cargadas == 3 and res.filas_rechazadas == 2
    df = pd.read_sql("SELECT categoria_gasto, region_id FROM gastos_operativos WHERE origen LIKE 'IMPORTACION%'",
                     seeded_engine)
    assert "Transporte y logística" in df["categoria_gasto"].tolist()   # normalizado a la categoría existente
    assert df["region_id"].isna().sum() == 1                           # 'Corporativo' => sin región


def test_missing_required_columns(seeded_engine, tmp_path):
    path = tmp_path / "malo.csv"
    pd.DataFrame({"fecha": ["2025-01-01"], "monto": ["100"]}).to_csv(path, index=False)
    res = run(path, "ventas", seeded_engine, tmp_path)
    assert res.estado == "FALLIDO"
    assert "numero_factura" in res.columnas_faltantes
    assert res.filas_cargadas == 0


def test_dry_run_does_not_write(seeded_engine, samples, tmp_path):
    res = run(samples["ventas"], "ventas", seeded_engine, tmp_path, dry_run=True)
    assert res.estado == "VALIDADO" and res.filas_validas == 7
    with seeded_engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM ventas WHERE numero_factura LIKE 'IMP-%'")).scalar() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM registro_importaciones")).scalar() == 0


def test_import_log_written(seeded_engine, samples, tmp_path):
    run(samples["clientes"], "clientes", seeded_engine, tmp_path)
    log = pd.read_sql("SELECT * FROM registro_importaciones", seeded_engine)
    assert len(log) == 1 and log["estado"][0] == "PARCIAL" and log["filas_cargadas"][0] == 4


def test_unsupported_and_empty_files(seeded_engine, tmp_path):
    res = run(b"hola", "ventas", seeded_engine, tmp_path, filename="datos.pdf")
    assert res.estado == "FALLIDO"
    res = run(b"", "ventas", seeded_engine, tmp_path, filename="vacio.csv")
    assert res.estado == "FALLIDO"


def test_bytes_source_csv(seeded_engine, tmp_path):
    csv = ("codigo;nombre;tipo;region;ciudad\n"
           "IMP-B-1;Tienda Bytes DEMO;Tienda de barrio;CARIBE;Soledad\n").encode("utf-8")
    res = run(csv, "clientes", seeded_engine, tmp_path, filename="clientes.csv")
    assert res.estado == "EXITOSO" and res.filas_cargadas == 1
